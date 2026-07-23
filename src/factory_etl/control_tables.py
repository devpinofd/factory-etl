"""Escritura de tablas de control en BigQuery.

Tablas destino en ``factory_control_<ambiente>``:

- ``etl_runs``: una fila por corrida completa.
- ``etl_batches``: una fila por (entidad, empresa, dt, run_id).
- ``etl_events``: eventos internos con fase y duracion.
- ``data_quality_results``: resultados de tests de calidad por batch.

Todas las escrituras usan streaming inserts (``insert_rows_json``) para
minimizar latencia. Los inserts son idempotentes por ``insertId`` derivado
del ``batch_id`` / ``run_id``.

Implementacion pendiente: Fase 1 Etapa 4.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from factory_etl.config import Settings


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class BatchStatus(StrEnum):
    WRITTEN = "written"
    SUCCESS = "success"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    QUARANTINED = "quarantined"


class ControlTables:
    """Interfaz para escribir eventos de auditoria."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def start_run(self, *, run_id: str, extras: dict[str, Any] | None = None) -> None:  # noqa: ARG002
        raise NotImplementedError("start_run pendiente (Fase 1 Etapa 4).")

    def finish_run(self, *, run_id: str, status: RunStatus, error: str | None = None) -> None:  # noqa: ARG002
        raise NotImplementedError("finish_run pendiente (Fase 1 Etapa 4).")

    def register_batch(
        self,
        *,
        batch_id: str,  # noqa: ARG002
        run_id: str,  # noqa: ARG002
        entity: str,  # noqa: ARG002
        source_empresa: str,  # noqa: ARG002
        dt: str,  # noqa: ARG002
        status: BatchStatus,  # noqa: ARG002
        record_count: int | None = None,  # noqa: ARG002
        object_uri: str | None = None,  # noqa: ARG002
        payload_hash: str | None = None,  # noqa: ARG002
    ) -> None:
        raise NotImplementedError("register_batch pendiente (Fase 1 Etapa 4).")

    def find_batch_by_hash(
        self,
        *,
        source_empresa: str,  # noqa: ARG002
        query_id: str,  # noqa: ARG002
        dt: str,  # noqa: ARG002
        payload_hash: str,  # noqa: ARG002
    ) -> str | None:
        """Devuelve el batch_id existente si ya se registro con exito, si no None."""
        raise NotImplementedError("find_batch_by_hash pendiente (Fase 1 Etapa 4).")
