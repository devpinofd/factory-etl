"""Registro global de QueryDefinition disponibles en el catalogo.

Uso::

    from factory_etl.factory_queries.catalog import get, list_query_ids

    qdef = get("articulos_v1", source_empresa="tinito")
    sql = qdef.read_sql()

Cada consulta se declara aqui explicitamente. No hay descubrimiento
automatico desde disco: registrar es una decision consciente que queda
trazable en el historial del repo.
"""

from __future__ import annotations

from pathlib import Path

from factory_etl.errors import CompanyNotAllowedError, QueryNotFoundError
from factory_etl.factory_queries.models import (
    Category,
    LoadStrategy,
    QueryDefinition,
    Transport,
)

_PACKAGE_ROOT = Path(__file__).parent

# --- Definicion de consultas -------------------------------------------------

ARTICULOS_V1 = QueryDefinition(
    query_id="articulos_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_art"),
    required_columns=("cod_art", "nom_art", "cod_uni1", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "articulos.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "articulos.json",
    allowed_companies=("tinito",),
    parameters=(),
    reject_empty=True,
)

# --- Registro ---------------------------------------------------------------

_REGISTRY: dict[str, QueryDefinition] = {
    ARTICULOS_V1.query_id: ARTICULOS_V1,
}


def list_query_ids() -> list[str]:
    """Devuelve los ids registrados, ordenados alfabeticamente."""
    return sorted(_REGISTRY.keys())


def get(query_id: str, *, source_empresa: str) -> QueryDefinition:
    """Resuelve un ``QueryDefinition`` validando que la empresa este autorizada.

    :raises QueryNotFoundError: el id no esta registrado.
    :raises CompanyNotAllowedError: la empresa no esta en ``allowed_companies``.
    """
    if query_id not in _REGISTRY:
        raise QueryNotFoundError(query_id)
    qdef = _REGISTRY[query_id]
    if source_empresa not in qdef.allowed_companies:
        raise CompanyNotAllowedError(
            f"'{source_empresa}' no autorizada para '{query_id}'; "
            f"permitidas: {qdef.allowed_companies}"
        )
    return qdef
