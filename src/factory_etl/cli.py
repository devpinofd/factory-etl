"""Interfaz CLI del ETL basada en typer."""

from __future__ import annotations

from typing import Annotated

import structlog
import typer

from factory_etl import __version__
from factory_etl.config import Settings
from factory_etl.logging_config import configure_logging

app = typer.Typer(
    name="factory-etl",
    help="ETL FactorySoft -> GCP data lake.",
    no_args_is_help=True,
    add_completion=False,
)

log = structlog.get_logger(__name__)


@app.callback()
def _root() -> None:
    """Punto de entrada. Configura logging antes de cualquier comando."""


@app.command()
def version() -> None:
    """Imprime la version del paquete."""
    typer.echo(__version__)


@app.command()
def run(
    query_id: Annotated[str, typer.Option(help="ID del QueryDefinition, ej. articulos_v1.")],
    source_empresa: Annotated[str, typer.Option(help="Empresa FactorySoft, ej. tinito.")],
    dt: Annotated[
        str | None,
        typer.Option(help="Fecha logica YYYY-MM-DD (default: hoy en zona local)."),
    ] = None,
) -> None:
    """Ejecuta el ETL para una consulta y una empresa.

    Esta implementacion es un esqueleto: la orquestacion real vive en
    `factory_etl.extractor.run_batch` (por implementar en Fase 1 Etapa 4).
    """
    settings = Settings.load()
    configure_logging(env=settings.env)
    log.info(
        "etl_invoked",
        query_id=query_id,
        source_empresa=source_empresa,
        dt=dt,
        env=settings.env,
    )
    # TODO(Fase 1 Etapa 4): usar bootstrap.build_extractor(settings) y
    # llamar extractor.run_batch(query_id=..., source_empresa=..., dt=..., run_id=...).
    # El CLI **no debe** importar clases concretas: siempre pasa por bootstrap.
    raise typer.Exit(code=0)


@app.command("list-queries")
def list_queries() -> None:
    """Lista los QueryDefinition registrados en el catalogo."""
    from factory_etl.factory_queries.catalog import list_query_ids

    for qid in list_query_ids():
        typer.echo(qid)


if __name__ == "__main__":
    app()
