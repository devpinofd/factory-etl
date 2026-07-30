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
    ParamSpec,
    ParamType,
    QueryDefinition,
    Transport,
)

_PACKAGE_ROOT = Path(__file__).parent
_ALLOWED_COMPANIES: tuple[str, ...] = ("tinito", "ctb", "daroan", "roldan", "ctm")

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
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

IMPUESTOS_V1 = QueryDefinition(
    query_id="impuestos_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_imp"),
    required_columns=("cod_imp", "nom_imp", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "impuestos.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "impuestos.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

DEPARTAMENTOS_V1 = QueryDefinition(
    query_id="departamentos_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_dep"),
    required_columns=("cod_dep", "nom_dep", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "departamentos.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "departamentos.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

MARCAS_V1 = QueryDefinition(
    query_id="marcas_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_mar"),
    required_columns=("cod_mar", "nom_mar", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "marcas.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "marcas.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

SECCIONES_V1 = QueryDefinition(
    query_id="secciones_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_sec"),
    required_columns=("cod_sec", "nom_sec", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "secciones.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "secciones.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

PROVEEDORES_V1 = QueryDefinition(
    query_id="proveedores_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_pro"),
    required_columns=("cod_pro", "nom_pro", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "proveedores.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "proveedores.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

PAISES_V1 = QueryDefinition(
    query_id="paises_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_pai"),
    required_columns=("cod_pai", "nom_pai", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "paises.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "paises.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

ESTADOS_V1 = QueryDefinition(
    query_id="estados_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_est"),
    required_columns=("cod_est", "nom_est", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "estados.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "estados.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

CIUDADES_V1 = QueryDefinition(
    query_id="ciudades_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_ciu"),
    required_columns=("cod_ciu", "nom_ciu", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "ciudades.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "ciudades.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

VENDEDORES_V1 = QueryDefinition(
    query_id="vendedores_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_ven"),
    required_columns=("cod_ven", "nom_ven", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "vendedores.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "vendedores.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

SUCURSALES_V1 = QueryDefinition(
    query_id="sucursales_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_suc"),
    required_columns=("cod_suc", "nom_suc", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "sucursales.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "sucursales.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

ALMACENES_V1 = QueryDefinition(
    query_id="almacenes_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_alm"),
    required_columns=("cod_alm", "nom_alm", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "almacenes.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "almacenes.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

CLIENTES_V1 = QueryDefinition(
    query_id="clientes_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_cli"),
    required_columns=("cod_cli", "nom_cli", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "clientes.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "clientes.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

CLASES_CLIENTES_V1 = QueryDefinition(
    query_id="clases_clientes_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_cla"),
    required_columns=("cod_cla", "nom_cla", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "clases_clientes.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "clases_clientes.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

CONCEPTOS_V1 = QueryDefinition(
    query_id="conceptos_v1",
    version="1.0.0",
    category=Category.MASTER,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.FULL_SNAPSHOT,
    natural_key=("_source_empresa", "cod_con"),
    required_columns=("cod_con", "nom_con", "status"),
    sql_path=_PACKAGE_ROOT / "masters" / "conceptos.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "conceptos.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(),
    reject_empty=True,
)

RENGLONES_ALMACENES_V1 = QueryDefinition(
    query_id="renglones_almacenes_v1",
    version="1.0.0",
    category=Category.TRANSACTION,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.INCREMENTAL_BY_DATE,
    natural_key=("_source_empresa", "cod_alm", "cod_art"),
    required_columns=("cod_alm", "cod_art", "exi_act1"),
    sql_path=_PACKAGE_ROOT / "transactions" / "renglones_almacenes.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "renglones_almacenes.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(
        ParamSpec(name="fec_des", type=ParamType.DATE),
        ParamSpec(name="fec_has", type=ParamType.DATE),
    ),
    reject_empty=False,
)

VENTAS_DIARIAS_V1 = QueryDefinition(
    query_id="ventas_diarias_v1",
    version="1.0.0",
    category=Category.TRANSACTION,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.INCREMENTAL_BY_DATE,
    natural_key=("_source_empresa", "tipo_documento", "cod_suc", "documento", "renglon"),
    required_columns=("tipo_documento", "cod_suc", "documento", "renglon"),
    sql_path=_PACKAGE_ROOT / "transactions" / "ventas_diarias.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "ventas_diarias.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(
        ParamSpec(name="fec_des", type=ParamType.DATE),
        ParamSpec(name="fec_has", type=ParamType.DATE),
    ),
    reject_empty=False,
)

RENGLONES_MONEDAS_V1 = QueryDefinition(
    query_id="renglones_monedas_v1",
    version="1.0.0",
    category=Category.TRANSACTION,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.INCREMENTAL_BY_DATE,
    natural_key=("_source_empresa", "cod_mon", "renglon"),
    required_columns=("cod_mon", "renglon"),
    sql_path=_PACKAGE_ROOT / "transactions" / "renglones_monedas.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "renglones_monedas.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(
        ParamSpec(name="fec_des", type=ParamType.DATE),
        ParamSpec(name="fec_has", type=ParamType.DATE),
    ),
    reject_empty=False,
)

RENGLONES_APRECIOS_V1 = QueryDefinition(
    query_id="renglones_aprecios_v1",
    version="1.0.0",
    category=Category.TRANSACTION,
    transport=Transport.GENERIC_SQL_API,
    load_strategy=LoadStrategy.INCREMENTAL_BY_DATE,
    natural_key=("_source_empresa", "documento", "renglon"),
    required_columns=("documento", "renglon"),
    sql_path=_PACKAGE_ROOT / "transactions" / "renglones_aprecios.sql",
    schema_path=_PACKAGE_ROOT / "schemas" / "renglones_aprecios.json",
    allowed_companies=_ALLOWED_COMPANIES,
    parameters=(
        ParamSpec(name="fec_des", type=ParamType.DATE),
        ParamSpec(name="fec_has", type=ParamType.DATE),
    ),
    reject_empty=False,
)

# --- Registro ---------------------------------------------------------------

_REGISTRY: dict[str, QueryDefinition] = {
    ARTICULOS_V1.query_id: ARTICULOS_V1,
    IMPUESTOS_V1.query_id: IMPUESTOS_V1,
    DEPARTAMENTOS_V1.query_id: DEPARTAMENTOS_V1,
    MARCAS_V1.query_id: MARCAS_V1,
    SECCIONES_V1.query_id: SECCIONES_V1,
    PROVEEDORES_V1.query_id: PROVEEDORES_V1,
    PAISES_V1.query_id: PAISES_V1,
    ESTADOS_V1.query_id: ESTADOS_V1,
    CIUDADES_V1.query_id: CIUDADES_V1,
    VENDEDORES_V1.query_id: VENDEDORES_V1,
    SUCURSALES_V1.query_id: SUCURSALES_V1,
    ALMACENES_V1.query_id: ALMACENES_V1,
    CLIENTES_V1.query_id: CLIENTES_V1,
    CLASES_CLIENTES_V1.query_id: CLASES_CLIENTES_V1,
    CONCEPTOS_V1.query_id: CONCEPTOS_V1,
    RENGLONES_ALMACENES_V1.query_id: RENGLONES_ALMACENES_V1,
    VENTAS_DIARIAS_V1.query_id: VENTAS_DIARIAS_V1,
    RENGLONES_MONEDAS_V1.query_id: RENGLONES_MONEDAS_V1,
    RENGLONES_APRECIOS_V1.query_id: RENGLONES_APRECIOS_V1,
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
