"""Jerarquia de excepciones tipadas del dominio.

Toda excepcion propia del ETL hereda de :class:`FactoryEtlError`. Esto
permite distinguir en los handlers entre errores del dominio y errores
inesperados (bugs).
"""

from __future__ import annotations


class FactoryEtlError(Exception):
    """Base de todas las excepciones del dominio."""


# --- Configuracion y arranque ------------------------------------------------


class ConfigError(FactoryEtlError):
    """Falta o es invalida la configuracion via variables de entorno."""


# --- Catalogo de consultas ---------------------------------------------------


class QueryNotFoundError(FactoryEtlError):
    """El identificador de consulta no existe en el catalogo."""


class CompanyNotAllowedError(FactoryEtlError):
    """La empresa solicitada no esta en `allowed_companies` de la consulta."""


class RenderError(FactoryEtlError):
    """Error al materializar el SQL desde template + parametros."""


class UndeclaredPlaceholder(RenderError):
    """El template referencia un placeholder no declarado en `parameters`."""


class MissingParameter(RenderError):
    """Falta un parametro requerido para renderizar."""


class InvalidParameterValue(RenderError):
    """El valor del parametro no cumple el tipo o dominio declarado."""


class ForbiddenContent(RenderError):
    """El valor contiene tokens prohibidos (inyeccion SQL, path traversal)."""


# --- Transporte y validacion de respuesta ------------------------------------


class TransportError(FactoryEtlError):
    """Error de red o HTTP al hablar con FactorySoft."""


class AuthenticationError(TransportError):
    """FactorySoft rechazo la autenticacion (API key invalida o expirada)."""


class InvalidPayloadError(FactoryEtlError):
    """La respuesta de FactorySoft no cumple el contrato esperado."""


class EmptyResponseError(FactoryEtlError):
    """La respuesta esta vacia y la consulta tiene `reject_empty=True`."""


class SchemaValidationError(FactoryEtlError):
    """Una fila del payload no cumple el schema (columnas requeridas ausentes).

    El mensaje es intencionalmente neutro: no incluye valores de la fila
    para evitar fuga de PII en logs. Solo se expone el conjunto de columnas
    faltantes y el indice posicional de la primera fila ofensora.
    """

    def __init__(self, *, missing_columns: frozenset[str], row_index: int) -> None:
        self.missing_columns = missing_columns
        self.row_index = row_index
        super().__init__(f"fila {row_index} omite columnas requeridas: {sorted(missing_columns)}")


# --- Ciclo de vida del batch -------------------------------------------------


class DuplicateBatchError(FactoryEtlError):
    """El batch ya existe con el mismo payload_hash; no se debe reescribir."""


class QuarantineRequired(FactoryEtlError):
    """El batch debe aterrizar en `quarantine/`, no en `bronze/`."""
