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
    """Especificacion de una entrada (empresa x consulta) dentro de un manifest de fan-out."""

    query_id: str
    source_empresa: str
    has_param: bool
    parameter_values: dict[str, object] = dataclasses.field(default_factory=dict)


def _parse_manifest_entry(
    entry: object,
    position: int,
    fec_des: str | None,
    fec_has: str | None,
) -> TaskSpec:
    """Valida una entrada del manifest y la convierte en ``TaskSpec``."""
    if not isinstance(entry, dict):
        raise typer.BadParameter(f"Entrada en posicion {position} debe ser un objeto JSON.")

    query_id = entry.get("query_id")
    source_empresa = entry.get("source_empresa")
    has_param = entry.get("has_param")

    if not isinstance(query_id, str) or not query_id.strip():
        raise typer.BadParameter(f"query_id invalido o ausente en entrada {position}.")
    if not isinstance(source_empresa, str) or not source_empresa.strip():
        raise typer.BadParameter(f"source_empresa invalido o ausente en entrada {position}.")
    if not isinstance(has_param, bool):
        raise typer.BadParameter(f"has_param debe ser booleano en entrada {position}.")

    parameter_values: dict[str, object] = {}
    if has_param:
        if not fec_des or not fec_has:
            raise typer.BadParameter(
                "La entrada requiere parametros (has_param=True), pero faltan fec_des y/o fec_has."
            )
        parameter_values = {"fec_des": fec_des, "fec_has": fec_has}

    return TaskSpec(
        query_id=query_id,
        source_empresa=source_empresa,
        has_param=has_param,
        parameter_values=parameter_values,
    )


def _select_tasks(
    manifest_json: str,
    task_index: int = 0,
    task_count: int | None = None,
    fec_des: str | None = None,
    fec_has: str | None = None,
) -> list[TaskSpec]:
    """Valida el manifest completo y devuelve las entradas asignadas a esta tarea.

    Reparto *strided*: la tarea ``i`` de ``T`` procesa las entradas
    ``i, i+T, i+2T, ...``. Asi una ejecucion de Cloud Run con
    ``taskCount = min(len(manifest), parallelism)`` corre en una sola ola
    (un solo arranque en frio por tarea) y nunca supera ``T`` llamadas
    concurrentes a la API de FactorySoft.

    Todo el manifest se valida (no solo el slice propio) para que un manifest
    defectuoso falle igual en todas las tareas y no de forma parcial.

    Es una funcion pura (sin efectos colaterales ni acceso a variables de entorno)
    para permitir pruebas unitarias exhaustivas.
    """
    try:
        items = json.loads(manifest_json)
    except Exception:
        raise typer.BadParameter("Manifest no es un JSON valido.") from None

    if not isinstance(items, list):
        raise typer.BadParameter("Manifest debe ser una lista de entradas.")
    if not items:
        raise typer.BadParameter("Manifest no puede estar vacio.")

    effective_count = 1 if task_count is None else task_count
    if effective_count < 1:
        raise typer.BadParameter(f"task_count invalido: {effective_count}.")
    if not (0 <= task_index < effective_count):
        raise typer.BadParameter(
            f"task_index {task_index} fuera de rango para task_count {effective_count}."
        )

    specs = [
        _parse_manifest_entry(entry, position, fec_des, fec_has)
        for position, entry in enumerate(items)
    ]
    return specs[task_index::effective_count]


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
    manifest: Annotated[str, typer.Option(help="Manifest JSON con lista de entradas.")],
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
    task_count: Annotated[
        int | None,
        typer.Option(
            "--task-count",
            help="Total de tareas de la ejecucion (default: env CLOUD_RUN_TASK_COUNT o 1).",
        ),
    ] = None,
) -> None:
    """Ejecuta el lote de entradas del manifest asignado a esta tarea de Cloud Run.

    La tarea ``i`` de ``T`` procesa las entradas ``i, i+T, i+2T, ...`` en serie.
    Un fallo en una entrada no impide procesar las siguientes; el exit code es
    1 si alguna entrada fallo (Cloud Run reintenta la tarea segun maxRetries;
    los batches ya exitosos se deduplican por ``payload_hash``).
    """
    effective_task_index = (
        task_index if task_index is not None else _int_from_env("CLOUD_RUN_TASK_INDEX", 0)
    )
    effective_task_count = (
        task_count if task_count is not None else _int_from_env("CLOUD_RUN_TASK_COUNT", 1)
    )

    specs = _select_tasks(
        manifest_json=manifest,
        task_index=effective_task_index,
        task_count=effective_task_count,
        fec_des=fec_des,
        fec_has=fec_has,
    )

    failures = 0
    for spec in specs:
        try:
            exit_code = _execute_batch(
                query_id=spec.query_id,
                source_empresa=spec.source_empresa,
                dt=dt,
                run_id=None,
                parameter_values=spec.parameter_values,
            )
        except Exception as exc:  # noqa: BLE001
            # Fallo fuera del manejo interno de _execute_batch (p.ej. start_run
            # contra BigQuery). Se registra solo el tipo, nunca el mensaje.
            log.error(
                "run_task_entry_failed",
                query_id=spec.query_id,
                source_empresa=spec.source_empresa,
                error_type=type(exc).__name__,
            )
            exit_code = 1
        if exit_code != 0:
            failures += 1

    log.info(
        "run_task_finished",
        task_index=effective_task_index,
        task_count=effective_task_count,
        entries=len(specs),
        failures=failures,
    )
    if failures:
        raise typer.Exit(code=1)


def _int_from_env(name: str, default: int) -> int:
    """Lee un entero de una variable de entorno; ``default`` si no existe."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise typer.BadParameter(f"{name} invalido: {raw!r}") from None


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
