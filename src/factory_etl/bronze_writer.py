"""Escritor atomico de Bronze en Cloud Storage.

Contrato:

- Escribe SIEMPRE primero a ``gs://<bronze>/_staging/run_id=<uuid>/`` y
  solo mueve al prefijo final si toda la corrida termina bien.
- El prefijo final es::

    gs://<bronze>/bronze/<entity>/source_empresa=<empresa>/dt=YYYY-MM-DD/run_id=<uuid>/part-*.parquet

- El formato es Parquet columnar con compresion Zstd por default.
- Nunca sobreescribe una particion ``dt`` ya cerrada segun `etl_runs`.

Implementacion pendiente: Fase 1 Etapa 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from factory_etl.config import Settings


@dataclass(frozen=True)
class WriteResult:
    """Resumen de una escritura en Bronze."""

    object_uri: str
    record_count: int
    byte_count: int


class BronzeWriter:
    """Escribe Parquet a Bronze de forma atomica."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def stage(
        self,
        *,
        run_id: str,  # noqa: ARG002
        entity: str,  # noqa: ARG002
        source_empresa: str,  # noqa: ARG002
        dt: str,  # noqa: ARG002
        rows: list[dict[str, object]],  # noqa: ARG002
    ) -> WriteResult:
        """Escribe el batch a ``_staging/`` sin publicar aun."""
        raise NotImplementedError("BronzeWriter.stage pendiente (Fase 1 Etapa 4).")

    def promote(self, *, run_id: str, entity: str, source_empresa: str, dt: str) -> str:  # noqa: ARG002
        """Mueve los objetos desde ``_staging/`` al prefijo final. Devuelve el URI final."""
        raise NotImplementedError("BronzeWriter.promote pendiente (Fase 1 Etapa 4).")

    @staticmethod
    def _final_prefix(*, bucket: str, entity: str, source_empresa: str, dt: str, run_id: str) -> str:
        """Calcula el prefijo GCS final segun el layout canonico."""
        path = PurePosixPath("bronze") / entity / f"source_empresa={source_empresa}" / f"dt={dt}" / f"run_id={run_id}"
        return f"gs://{bucket}/{path}/"
