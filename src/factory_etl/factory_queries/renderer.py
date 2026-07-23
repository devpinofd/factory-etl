"""Renderer seguro de SQL con parametros tipados.

Este es el modulo con mayor riesgo del sistema: **es el unico lugar
autorizado para materializar parametros dentro de una cadena SQL** que
luego se envia por HTTP a FactorySoft.

Reglas invariantes (no negociables):

1. Todo placeholder en el template debe estar declarado en ``parameters``
   del ``QueryDefinition``. Un placeholder no declarado es un error.
2. Todo parametro declarado debe usarse. Un parametro sin uso es un error.
3. Los valores se validan segun ``ParamType`` antes de sustituir.
4. Contenido peligroso (``;``, ``--``, ``/*``, ``*/``, control chars,
   ``xp_`` y otros) es rechazado incluso si tipo y dominio son validos.
5. Dos renderizados del mismo template con los mismos parametros producen
   exactamente el mismo hash.

**OCP**: el formateo por tipo se resuelve via ``_FORMATTERS``, un registry
inmutable que mapea ``ParamType`` a una funcion formatter. Agregar un tipo
nuevo se hace registrando una entrada, sin tocar el codigo existente.

Las excepciones de este modulo son sub-clases de ``RenderError`` (ver
``factory_etl.errors``).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from types import MappingProxyType

from factory_etl.errors import (
    ForbiddenContent,
    InvalidParameterValue,
    MissingParameter,
    RenderError,
    UndeclaredPlaceholder,
)
from factory_etl.factory_queries.models import ParamSpec, ParamType

# Placeholder: {{ name }} con espacios opcionales. Solo snake_case.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")

# Tokens de inyeccion prohibidos en cualquier valor string. Insensibles a mayusculas.
_FORBIDDEN_TOKENS: tuple[str, ...] = (
    ";",
    "--",
    "/*",
    "*/",
    "\x00",
    "xp_",
    "sp_",
    "0x",
    "..",
    "@@",
    "\\",
)

# Solo se permite ASCII imprimible + espacios/tab en valores de tipo STRING_ENUM.
_ALLOWED_STRING_RE = re.compile(r"^[\x20-\x7e]+$")

# Formato de fecha aceptado.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def render(
    sql_template: str,
    parameter_specs: tuple[ParamSpec, ...],
    parameter_values: Mapping[str, object],
) -> str:
    """Renderiza el template SQL sustituyendo placeholders.

    :param sql_template: contenido del ``.sql`` con placeholders ``{{name}}``.
    :param parameter_specs: especificaciones declaradas en el ``QueryDefinition``.
    :param parameter_values: valores concretos para esta ejecucion.

    :returns: SQL final listo para enviar por HTTP.

    :raises UndeclaredPlaceholder: el template referencia un nombre no declarado.
    :raises MissingParameter: falta el valor de un parametro declarado y usado.
    :raises InvalidParameterValue: el valor no cumple tipo o dominio.
    :raises ForbiddenContent: el valor contiene tokens de inyeccion.
    :raises RenderError: parametro declarado pero nunca referenciado en el template.
    """

    _preflight_forbidden_content(parameter_values)

    specs_by_name: dict[str, ParamSpec] = {spec.name: spec for spec in parameter_specs}
    referenced: set[str] = set()

    def _substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        referenced.add(name)
        if name not in specs_by_name:
            raise UndeclaredPlaceholder(name)
        if name not in parameter_values:
            raise MissingParameter(name)
        return _format_value(specs_by_name[name], parameter_values[name])

    rendered = _PLACEHOLDER_RE.sub(_substitute, sql_template)

    declared_but_unused = {spec.name for spec in parameter_specs} - referenced
    if declared_but_unused:
        raise RenderError(
            f"parametros declarados pero no usados en el template: "
            f"{sorted(declared_but_unused)}"
        )

    return rendered


def _preflight_forbidden_content(values: Mapping[str, object]) -> None:
    """Rechaza cualquier valor string con tokens peligrosos, antes de tipar."""

    for name, value in values.items():
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        for token in _FORBIDDEN_TOKENS:
            if token in lowered:
                raise ForbiddenContent(
                    f"parametro '{name}' contiene token prohibido: {token!r}"
                )


def _format_value(spec: ParamSpec, value: object) -> str:
    """Formatea un valor unico segun su tipo via el registry ``_FORMATTERS``."""

    formatter = _FORMATTERS.get(spec.type)
    if formatter is None:
        raise InvalidParameterValue(f"{spec.name}: tipo desconocido {spec.type}")
    return formatter(spec, value)


def _format_string_enum(spec: ParamSpec, value: object) -> str:
    if not isinstance(value, str):
        raise InvalidParameterValue(f"{spec.name}: se esperaba str")
    if spec.allowed_values is None:
        raise InvalidParameterValue(
            f"{spec.name}: STRING_ENUM requiere allowed_values"
        )
    if value not in spec.allowed_values:
        raise InvalidParameterValue(
            f"{spec.name}: '{value}' no esta en allowed_values"
        )
    if not _ALLOWED_STRING_RE.match(value):
        raise InvalidParameterValue(
            f"{spec.name}: contiene caracteres fuera de ASCII imprimible"
        )
    return f"'{value}'"


def _format_date(spec: ParamSpec, value: object) -> str:
    if not isinstance(value, str):
        raise InvalidParameterValue(f"{spec.name}: se esperaba str YYYY-MM-DD")
    if not _DATE_RE.match(value):
        raise InvalidParameterValue(
            f"{spec.name}: formato invalido, se esperaba YYYY-MM-DD"
        )
    return f"'{value}'"


def _format_int(spec: ParamSpec, value: object) -> str:
    # Bool es subclase de int en Python; explicitamente lo rechazamos.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidParameterValue(f"{spec.name}: se esperaba int")
    if spec.min_value is not None and value < spec.min_value:
        raise InvalidParameterValue(
            f"{spec.name}: {value} < min_value {spec.min_value}"
        )
    if spec.max_value is not None and value > spec.max_value:
        raise InvalidParameterValue(
            f"{spec.name}: {value} > max_value {spec.max_value}"
        )
    return str(value)


# Registry OCP: agregar un ParamType nuevo = agregar una entrada aqui.
# No requiere modificar codigo existente.
_Formatter = Callable[[ParamSpec, object], str]
_FORMATTERS: Mapping[ParamType, _Formatter] = MappingProxyType(
    {
        ParamType.STRING_ENUM: _format_string_enum,
        ParamType.DATE: _format_date,
        ParamType.INT: _format_int,
    }
)
