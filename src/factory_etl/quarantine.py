"""Ruta separada para aterrizar respuestas invalidas.

Cuarentena convive con Bronze pero NUNCA es leida por Silver/Gold. Sirve
para inspeccion manual: respuestas vacias con ``reject_empty=True``,
respuestas que violan el schema JSON, timeouts persistentes.

Layout::

    gs://<bucket>/quarantine/<entity>/source_empresa=<empresa>/dt=YYYY-MM-DD/run_id=<uuid>/

Implementacion pendiente: Fase 1 Etapa 4.
"""

from __future__ import annotations

from enum import StrEnum

from factory_etl.config import Settings


class QuarantineReason(StrEnum):
    EMPTY_REJECTED = "empty_rejected"
    SCHEMA_MISMATCH = "schema_mismatch"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


class Quarantine:
    """Escribe el payload sospechoso a la zona de cuarentena."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def dump(
        self,
        *,
        run_id: str,  # noqa: ARG002
        entity: str,  # noqa: ARG002
        source_empresa: str,  # noqa: ARG002
        dt: str,  # noqa: ARG002
        payload_bytes: bytes,  # noqa: ARG002
        reason: QuarantineReason,  # noqa: ARG002
    ) -> str:
        """Escribe el payload en cuarentena y devuelve el URI."""
        raise NotImplementedError("Quarantine.dump pendiente (Fase 1 Etapa 4).")
