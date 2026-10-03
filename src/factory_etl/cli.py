"""Interfaz CLI del ETL basada en typer."""

from __future__ import annotations

import dataclasses
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
import typer

from factory_etl import __version__, ids
from factory_etl.bootstrap import build_extractor
from factory_etl.config import Settings
from factory_etl.control_tables import BatchStatus, RunStatus
from factory_etl.logging_config import configure_logging

app = typer.Typer(
    name="factory-etl",
    help="ETL FactorySoft -> GCP data lake.",
    no_args_is_help=True,
    add_completion=False,
)

log = structlog.get_logger(__name__)

# Estados de batch que se consideran "no-fallo" para efectos del exit code.
_NON_FAILURE_BATCH_STATUSES = frozenset(
    {
        BatchStatus.SUCCESS.value,
        BatchStatus.SKIPPED_DUPLICATE.value,
        BatchStatus.QUARANTINED.value,
    }
)


@app.callback()
def _root() -> None:  # pyright: ignore[reportUnusedFunction]
    """Punto de entrada. Configura logging antes de cualquier comando.

    typer registra la funcion via el decorador; pyright no lo detecta.
    """


@app.command()
def version() -> None:
    """Imprime la version del paquete."""
    typer.echo(__version__)


@dataclasses.dataclass(frozen=True)
class TaskSpec:
    """Especificacion de una tarea individual dentro de un manifest de fan-out."""

    query_id: str
    source_empresa: str
    has_param: bool
    parameter_values: dict[str, object] = dataclasses.field(default_factory=dict)


def _select_task(
    manifest_json: str,
    task_index: int = 0,
    task_count: int | None = None,
    fec_des: str | None = None,
    fec_has: str | None = None,
) -> TaskSpec:
    """Valida el manifest y extrae la especificacion de la tarea para el indice dado.

    Es una funcion pura (sin efectos colaterales ni acceso a variables de entorno)
    para permitir pruebas unitarias exhaustivas.
    """
    try:
        items = json.loads(manifest_json)
    except Exception:
        raise typer.BadParameter("Manifest no es un JSON valido.") from None

    if not isinstance(items, list):
        raise typer.BadParameter("Manifest debe ser una lista de tareas.")

    total_tasks = len(items)
    if total_tasks == 0:
        raise typer.BadParameter("Manifest no puede estar vacio.")

    if task_count is not None and task_count != total_tasks:
        raise typer.BadParameter(
            f"CLOUD_RUN_TASK_COUNT ({task_count}) no coincide con el tamano del manifest ({total_tasks})."
        )

    if not (0 <= task_index < total_tasks):
        raise typer.BadParameter(
            f"task_index {task_index} fuera de rango: manifest contiene {total_tasks} tarea(s)."
        )

    task = items[task_index]
    if not isinstance(task, dict):
        raise typer.BadParameter(f"Tarea en indice {task_index} debe ser un objeto JSON.")

    query_id = task.get("query_id")
    source_empresa = task.get("source_empresa")
    has_param = task.get("has_param")

    if not isinstance(query_id, str) or not query_id.strip():
        raise typer.BadParameter(f"query_id invalido o ausente en tarea {task_index}.")
    if not isinstance(source_empresa, str) or not source_empresa.strip():
        raise typer.BadParameter(f"source_empresa invalido o ausente en tarea {task_index}.")
    if not isinstance(has_param, bool):
        raise typer.BadParameter(f"has_param debe ser booleano en tarea {task_index}.")

    parameter_values: dict[str, object] = {}
    if has_param:
        if not fec_des or not fec_has:
            raise typer.BadParameter(
                "La tarea requiere parametros (has_param=True), pero faltan fec_des y/o fec_has."
            )
        parameter_values = {"fec_des": fec_des, "fec_has": fec_has}

    return TaskSpec(
        query_id=query_id,
        source_empresa=source_empresa,
        has_param=has_param,
        parameter_values=parameter_values,
    )


def _execute_batch(
    query_id: str,
    source_empresa: str,
    dt: str,
    run_id: str | None = None,
    parameter_values: dict[str, object] | None = None,
) -> int:
    """Ejecuta un batch end-to-end y devuelve el exit code (0 o 1).

    Salida a stdout: JSON serializable del ``BatchOutcome`` (una linea).
    Errores inesperados: se registra ``type(exc).__name__`` mas un
    ``error_id`` corto. El mensaje del exception **no** se propaga a stdout
    ni a stderr para evitar filtrar datos sensibles del payload; solo se
    encuentra en los logs estructurados.
    """
    settings = Settings.load()
    configure_logging(env=settings.env)
    effective_run_id = run_id or ids.new_run_id()

    # La particion Bronze (dt=<valor>) debe usar la fecha real, nunca el token
    # "TODAY": de lo contrario se crean particiones literales dt=TODAY que
    # rompen la derivacion de snapshot_date en las capas historicas/SCD.
    dt = datetime.now(UTC).strftime("%Y-%m-%d") if dt.upper() == "TODAY" else dt

    params = parameter_values or {}

    extractor = build_extractor(settings)
    control = extractor.control

    control.start_run(
        run_id=effective_run_id,
        extras={
            "query_id": query_id,
            "source_empresa": source_empresa,
            "dt": dt,
            "cli_version": __version__,
        },
    )

    try:
        outcome = extractor.run_batch(
            query_id=query_id,
            source_empresa=source_empresa,
            dt=dt,
            run_id=effective_run_id,
            parameter_values=params,
        )
    except Exception as exc:
        # No se persiste `str(exc)` ni en logs ni en control: el mensaje
        # puede contener fragmentos del payload de FactorySoft. Se emite
        # solo `type(exc).__name__` y un correlator para operaciones.
        error_id = uuid.uuid4().hex[:8]
        error_type = type(exc).__name__
        # No se loggea `str(exc)` ni el traceback via `log.exception`:
        # el mensaje del exception puede contener fragmentos del payload de
        # FactorySoft (URLs, credenciales rotativas, etc). Se emite solo
        # el nombre del tipo y un correlator estable para operaciones,
        # que se cruza con `etl_runs.extras.error_id`.
        log.error(
            "run_batch_failed",
            run_id=effective_run_id,
            query_id=query_id,
            source_empresa=source_empresa,
            dt=dt,
            error_type=error_type,
            error_id=error_id,
        )
        # BATCH_FAILED en `etl_events` para dejar rastro auditable del fallo.
        # Best-effort: si el propio `log_event` fallase (BQ caido, red, etc.)
        # NO debe enmascarar el error original ni impedir el `finish_run`.
        try:
            control.log_event(
                run_id=effective_run_id,
                event_type="BATCH_FAILED",
                phase="finalize",
                entity=query_id,
                extras={"error_type": error_type, "error_id": error_id},
            )
        except Exception:  # noqa: BLE001
            log.error(
                "log_event_batch_failed_error",
                run_id=effective_run_id,
                error_id=error_id,
            )
        control.finish_run(
            run_id=effective_run_id,
            status=RunStatus.FAILED,
            error=error_type,
            extras={"error_id": error_id},
        )
        return 1

    typer.echo(json.dumps(dataclasses.asdict(outcome), sort_keys=True))
    control.finish_run(
        run_id=effective_run_id,
        status=RunStatus.SUCCESS,
        extras={"batch_id": outcome.batch_id, "final_status": outcome.status},
    )

    return 0 if outcome.status in _NON_FAILURE_BATCH_STATUSES else 1


@app.command("run-batch")
def run_batch(
    query_id: Annotated[str, typer.Option(help="ID del QueryDefinition, ej. articulos_v1.")],
    source_empresa: Annotated[str, typer.Option(help="Empresa FactorySoft, ej. tinito.")],
    dt: Annotated[str, typer.Option(help="Fecha logica YYYY-MM-DD.")],
    run_id: Annotated[
        str | None,
        typer.Option(help="UUID de la corrida (default: se genera uno nuevo)."),
    ] = None,
    parameter: Annotated[
        list[str] | None,
        typer.Option(
            "--parameter",
            "-p",
            help="Parametro k=v. Puede repetirse para multiples parametros.",
        ),
    ] = None,
) -> None:
    """Ejecuta un batch end-to-end y termina con exit code segun el resultado.

    Salida a stdout: JSON serializable del ``BatchOutcome`` (una linea).
    Errores inesperados: se registra ``type(exc).__name__`` mas un
    ``error_id`` corto. El mensaje del exception **no** se propaga a stdout
    ni a stderr para evitar filtrar datos sensibles del payload; solo se
    encuentra en los logs estructurados.
    """
    parameter_values = _parse_parameters(parameter or [])
    exit_code = _execute_batch(
        query_id=query_id,
        source_empresa=source_empresa,
        dt=dt,
        run_id=run_id,
        parameter_values=parameter_values,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command("run-task")
def run_task(
    manifest: Annotated[str, typer.Option(help="Manifest JSON con lista de tareas.")],
    dt: Annotated[str, typer.Option(help="Fecha logica YYYY-MM-DD.")],
    fec_des: Annotated[
        str | None,
        typer.Option("--fec-des", help="Fecha desde YYYY-MM-DD (para consultas con parametros)."),
    ] = None,
    fec_has: Annotated[
        str | None,
        typer.Option("--fec-has", help="Fecha hasta YYYY-MM-DD (para consultas con parametros)."),
    ] = None,
    task_index: Annotated[
        int | None,
        typer.Option(
            "--task-index",
            help="Indice de tarea (default: env CLOUD_RUN_TASK_INDEX o 0).",
        ),
    ] = None,
) -> None:
    """Ejecuta una tarea individual de un manifest en Cloud Run Jobs.

    Selecciona la consulta y empresa segun el indice de la tarea
    (provisto por la opcion o por la variable de entorno CLOUD_RUN_TASK_INDEX).
    """
    if task_index is None:
        raw_env_index = os.environ.get("CLOUD_RUN_TASK_INDEX")
        if raw_env_index is not None:
            try:
                effective_task_index = int(raw_env_index)
            except ValueError:
                raise typer.BadParameter(
                    f"CLOUD_RUN_TASK_INDEX invalido: {raw_env_index!r}"
                ) from None
        else:
            effective_task_index = 0
    else:
        effective_task_index = task_index

    raw_env_count = os.environ.get("CLOUD_RUN_TASK_COUNT")
    task_count: int | None = None
    if raw_env_count is not None:
        try:
            task_count = int(raw_env_count)
        except ValueError:
            raise typer.BadParameter(f"CLOUD_RUN_TASK_COUNT invalido: {raw_env_count!r}") from None

    spec = _select_task(
        manifest_json=manifest,
        task_index=effective_task_index,
        task_count=task_count,
        fec_des=fec_des,
        fec_has=fec_has,
    )

    exit_code = _execute_batch(
        query_id=spec.query_id,
        source_empresa=spec.source_empresa,
        dt=dt,
        run_id=None,
        parameter_values=spec.parameter_values,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command("list-queries")
def list_queries() -> None:
    """Lista los QueryDefinition registrados en el catalogo."""
    from factory_etl.factory_queries.catalog import list_query_ids

    for qid in list_query_ids():
        typer.echo(qid)


def _parse_parameters(items: list[str]) -> dict[str, object]:
    """Convierte ``["k=v", ...]`` en un dict. Ultima ocurrencia gana.

    Los valores se mantienen como str; el renderer se encarga de castear
    segun el tipo declarado en el ``QueryDefinition``.
    """
    result: dict[str, object] = {}
    for item in items:
        if "=" not in item:
            raise typer.BadParameter(f"parametro invalido {item!r}: se espera formato clave=valor")
        key, _, value = item.partition("=")
        key = key.strip()
        if not key:
            raise typer.BadParameter(f"parametro invalido {item!r}: clave vacia")
        result[key] = value
    return result


if __name__ == "__main__":
    app()
