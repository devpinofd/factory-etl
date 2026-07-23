"""Escritor atomico de Bronze en Cloud Storage.

Contrato:

- Escribe SIEMPRE primero a ``gs://<bronze>/_staging/run_id=<uuid>/`` y
  solo mueve al prefijo final si toda la corrida termina bien.
- El prefijo final es::

    gs://<bronze>/bronze/<entity>/source_empresa=<empresa>/dt=YYYY-MM-DD/run_id=<uuid>/part-0.jsonl.gz

- Formato: **JSONL comprimido con gzip** (raw fidelity). Cada linea es un
  registro completo del array ``d.laTablas[0]`` sin transformacion de
  tipos. La conversion a Parquet columnar ocurre en Silver.
- Metadatos de GCS incluyen ``run_id``, ``entity``, ``source_empresa``,
  ``dt`` y ``record_count`` para facilitar auditoria y busqueda.
- El promote usa GCS copy + delete (atomico a nivel de objeto individual).
"""

from __future__ import annotations

import gzip
import io
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from factory_etl.config import Settings

if TYPE_CHECKING:  # pragma: no cover
    from google.cloud.storage import Bucket


class _StorageClient(Protocol):
    """Subset del SDK google-cloud-storage que consumimos. Inyectable en tests."""

    def bucket(self, bucket_name: str) -> Bucket: ...  # pragma: no cover


@dataclass(frozen=True)
class WriteResult:
    """Resumen de una escritura en Bronze."""

    object_uri: str
    record_count: int
    byte_count: int


class BronzeWriter:
    """Escribe JSONL+gzip a Bronze de forma atomica (staging + promote)."""

    _STAGING_PREFIX = "_staging"
    _FINAL_PREFIX = "bronze"

    def __init__(
        self,
        settings: Settings,
        *,
        client: _StorageClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client  # se construye perezosamente si es None

    def stage(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
        rows: list[dict[str, object]],
    ) -> WriteResult:
        """Escribe ``rows`` como JSONL+gzip a ``_staging/``.

        La ordenacion de claves (``sort_keys=True``) es determinista para
        que dos ejecuciones con los mismos datos produzcan el mismo blob.
        """
        object_name = self._staging_object(
            run_id=run_id, entity=entity, source_empresa=source_empresa, dt=dt
        )
        data = self._encode_jsonl_gz(rows)

        blob = self._bucket().blob(object_name)
        blob.metadata = {
            "run_id": run_id,
            "entity": entity,
            "source_empresa": source_empresa,
            "dt": dt,
            "record_count": str(len(rows)),
        }
        blob.upload_from_string(data, content_type="application/gzip")

        return WriteResult(
            object_uri=f"gs://{self._settings.bronze_bucket}/{object_name}",
            record_count=len(rows),
            byte_count=len(data),
        )

    def promote(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
    ) -> str:
        """Mueve el objeto de ``_staging/`` al prefijo final via copy + delete."""
        src_name = self._staging_object(
            run_id=run_id, entity=entity, source_empresa=source_empresa, dt=dt
        )
        dst_name = self._final_object(
            run_id=run_id, entity=entity, source_empresa=source_empresa, dt=dt
        )
        bucket = self._bucket()
        src_blob = bucket.blob(src_name)
        bucket.copy_blob(src_blob, bucket, dst_name)
        src_blob.delete()

        return f"gs://{self._settings.bronze_bucket}/{dst_name}"

    # -- helpers privados -----------------------------------------------------

    @staticmethod
    def _encode_jsonl_gz(rows: list[dict[str, object]]) -> bytes:
        """Codifica ``rows`` como JSONL en UTF-8 y comprime con gzip.

        ``mtime=0`` en gzip para que dos ejecuciones con los mismos rows
        produzcan bytes identicos (bit-a-bit).
        """
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0) as gz:
            for row in rows:
                line = json.dumps(
                    row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                gz.write(line)
                gz.write(b"\n")
        return buf.getvalue()

    def _staging_object(self, *, run_id: str, entity: str, source_empresa: str, dt: str) -> str:
        return (
            f"{self._STAGING_PREFIX}/{entity}"
            f"/source_empresa={source_empresa}/dt={dt}"
            f"/run_id={run_id}/part-0.jsonl.gz"
        )

    def _final_object(self, *, run_id: str, entity: str, source_empresa: str, dt: str) -> str:
        return (
            f"{self._FINAL_PREFIX}/{entity}"
            f"/source_empresa={source_empresa}/dt={dt}"
            f"/run_id={run_id}/part-0.jsonl.gz"
        )

    def _bucket(self) -> Bucket:
        return self._get_client().bucket(self._settings.bronze_bucket)

    def _get_client(self) -> _StorageClient:
        if self._client is None:
            from google.cloud import storage  # noqa: PLC0415

            self._client = storage.Client(project=self._settings.gcp_project)
        return self._client

    @staticmethod
    def _final_prefix(
        *, bucket: str, entity: str, source_empresa: str, dt: str, run_id: str
    ) -> str:
        """Calcula el prefijo GCS final segun el layout canonico (helper legacy)."""
        return (
            f"gs://{bucket}/bronze/{entity}"
            f"/source_empresa={source_empresa}/dt={dt}/run_id={run_id}/"
        )
