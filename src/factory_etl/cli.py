"""Interfaz CLI del ETL basada en typer."""

from __future__ import annotations

import dataclasses
import json
import uuid
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
    settings = Settings.load()
    configure_logging(env=settings.env)
    effective_run_id = run_id or ids.new_run_id()

    parameter_values = _parse_parameters(parameter or [])

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
            parameter_values=parameter_values,
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
        control.finish_run(
            run_id=effective_run_id,
            status=RunStatus.FAILED,
            error=error_type,
            extras={"error_id": error_id},
        )
        raise typer.Exit(code=1) from None

    typer.echo(json.dumps(dataclasses.asdict(outcome), sort_keys=True))
    control.finish_run(
        run_id=effective_run_id,
        status=RunStatus.SUCCESS,
        extras={"batch_id": outcome.batch_id, "final_status": outcome.status},
    )

    exit_code = 0 if outcome.status in _NON_FAILURE_BATCH_STATUSES else 1
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
