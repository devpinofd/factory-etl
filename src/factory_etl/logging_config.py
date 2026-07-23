"""Configuracion de logging estructurado.

Usa `structlog` para producir logs JSON en produccion (compatibles con
Cloud Logging) y consola legible en dev. Todo log line incluye por defecto
las variables de contexto que hayan sido registradas con
``structlog.contextvars.bind_contextvars`` (ej. ``run_id``, ``lote_id``).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.typing import Processor


def configure_logging(env: str = "dev", level: int = logging.INFO) -> None:
    """Configura structlog para el proceso.

    :param env: ``dev`` usa renderer humano, cualquier otro valor JSON.
    :param level: nivel minimo global.
    """

    # Nivel del stdlib para librerias que loguean via logging estandar.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_sensitive,
    ]

    renderer: Processor
    if env == "dev":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_REDACT_KEYS = frozenset(
    {
        "apikey",
        "api_key",
        "authorization",
        "password",
        "secret",
        "token",
        "sql",
        "sql_rendered",
        "payload",
        "raw_response",
        "usuario",
    }
)


def _redact_sensitive(
    _logger: Any,  # noqa: ARG001
    _method: str,  # noqa: ARG001
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Elimina o enmascara campos sensibles antes de emitir el log.

    La firma coincide con `structlog.typing.Processor` (EventDict es
    `MutableMapping[str, Any]`, no `dict`).
    """

    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict
