"""Enums y dataclass de definicion de consultas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Transport(StrEnum):
    """Transporte fisico hacia FactorySoft.

    Fijado a un solo valor por decision de arquitectura (ver
    ``PLAN_IMPLEMENTACION_FASE_1.md`` seccion 1: "Decision de ingesta").
    """

    GENERIC_SQL_API = "generic_sql_api"


class Category(StrEnum):
    MASTER = "master"
    TRANSACTION = "transaction"


class LoadStrategy(StrEnum):
    FULL_SNAPSHOT = "full_snapshot"
    INCREMENTAL_BY_DATE = "incremental_by_date"
    SNAPSHOT_BY_DATE = "snapshot_by_date"


class ParamType(StrEnum):
    """Tipos de parametro soportados por el renderer.

    Restringido a un conjunto pequeno y conocido para minimizar la
    superficie de ataque. Ampliar aqui es una decision consciente.
    """

    STRING_ENUM = "string_enum"
    DATE = "date"
    INT = "int"


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """Especificacion de un parametro de consulta.

    :param name: nombre del placeholder en el SQL (``{{name}}``).
    :param type: tipo esperado.
    :param allowed_values: obligatorio para ``STRING_ENUM``, ignorado en el resto.
    :param min_value: opcional, aplica a ``INT``.
    :param max_value: opcional, aplica a ``INT``.
    """

    name: str
    type: ParamType
    allowed_values: tuple[str, ...] | None = None
    min_value: int | None = None
    max_value: int | None = None


@dataclass(frozen=True, slots=True)
class QueryDefinition:
    """Definicion inmutable de una consulta versionada.

    :param query_id: identificador estable, ej. ``articulos_v1``.
    :param version: SemVer, ej. ``1.0.0``.
    :param category: MASTER o TRANSACTION.
    :param transport: transporte fisico (fijo a GENERIC_SQL_API).
    :param load_strategy: FULL_SNAPSHOT | INCREMENTAL_BY_DATE | SNAPSHOT_BY_DATE.
    :param natural_key: tupla de columnas que forman la clave natural.
    :param required_columns: columnas obligatorias segun el schema.
    :param sql_path: ruta al archivo ``.sql`` (relativa al paquete).
    :param schema_path: ruta al archivo ``.json`` de schema.
    :param allowed_companies: whitelist de empresas para las que la
        consulta puede ejecutarse. Rechaza cualquier otra.
    :param parameters: lista de ``ParamSpec``; vacia si la consulta es
        constante.
    :param reject_empty: si True, respuesta vacia va a cuarentena.
    """

    query_id: str
    version: str
    category: Category
    transport: Transport
    load_strategy: LoadStrategy
    natural_key: tuple[str, ...]
    required_columns: tuple[str, ...]
    sql_path: Path
    schema_path: Path
    allowed_companies: tuple[str, ...]
    parameters: tuple[ParamSpec, ...] = field(default_factory=tuple)
    reject_empty: bool = True

    def full_id(self) -> str:
        """``articulos_v1@1.0.0`` para uso en logs y tablas de control."""
        return f"{self.query_id}@{self.version}"

    def read_sql(self) -> str:
        """Lee el SQL desde disco. La lectura falla ruidosamente si el archivo no existe."""
        return self.sql_path.read_text(encoding="utf-8")
