"""Ruta separada para aterrizar respuestas invalidas.

Cuarentena convive con Bronze pero NUNCA es leida por Silver/Gold. Sirve
para inspeccion manual: respuestas vacias con ``reject_empty=True``,
respuestas que violan el schema JSON, timeouts persistentes.

Layout::

    gs://<bucket>/quarantine/<entity>/source_empresa=<empresa>/dt=YYYY-MM-DD/run_id=<uuid>/payload.json

Si ``settings.quarantine_bucket`` esta vacio, se usa el mismo
``bronze_bucket`` con el prefijo ``quarantine/`` (bucket compartido).

El contenido escrito es el ``payload_bytes`` **crudo** recibido de
FactorySoft, sin transformacion. La razon del descarte se guarda como
metadata GCS y en el nombre del archivo para busqueda por prefijo.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from factory_etl.config import Settings

if TYPE_CHECKING:  # pragma: no cover
    from google.cloud.storage import Bucket


class _StorageClient(Protocol):
    """Subset del SDK google-cloud-storage. Inyectable en tests."""

    def bucket(self, bucket_name: str) -> Bucket: ...  # pragma: no cover


class QuarantineReason(StrEnum):
    EMPTY_REJECTED = "empty_rejected"
    SCHEMA_MISMATCH = "schema_mismatch"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


class Quarantine:
    """Escribe el payload sospechoso a la zona de cuarentena."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: _StorageClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client

        # Si no hay bucket dedicado, usamos bronze_bucket con prefijo quarantine/.
        self._bucket_name = settings.quarantine_bucket or settings.bronze_bucket

    def dump(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
        payload_bytes: bytes,
        reason: QuarantineReason,
    ) -> str:
        """Escribe el payload crudo en cuarentena y devuelve el URI ``gs://``.

        El payload se guarda **sin transformar** (mismo cuerpo que devolvio
        FactorySoft). Los metadatos GCS incluyen ``reason`` para triage.
        """
        object_name = (
            f"quarantine/{entity}"
            f"/source_empresa={source_empresa}/dt={dt}"
            f"/run_id={run_id}/reason={reason.value}/payload.json"
        )

        blob = self._get_bucket().blob(object_name)
        blob.metadata = {
            "run_id": run_id,
            "entity": entity,
            "source_empresa": source_empresa,
            "dt": dt,
            "reason": reason.value,
            "byte_count": str(len(payload_bytes)),
        }
        # content_type=application/json porque el payload original de
        # FactorySoft es JSON aunque haya fallado la validacion.
        blob.upload_from_string(payload_bytes, content_type="application/json")

        return f"gs://{self._bucket_name}/{object_name}"

    def _get_bucket(self) -> Bucket:
        return self._get_client().bucket(self._bucket_name)

    def _get_client(self) -> _StorageClient:
        if self._client is None:
            from google.cloud import storage  # noqa: PLC0415

            self._client = storage.Client(project=self._settings.gcp_project)
        return self._client
