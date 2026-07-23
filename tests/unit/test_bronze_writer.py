"""Tests del BronzeWriter (JSONL+gzip a GCS).

Inyectamos un fake del client de GCS para probar sin red. Verificamos:

- Layout de rutas (_staging vs bronze)
- Contenido JSONL+gzip decodificable
- Deterministic: mismos inputs -> mismos bytes
- Metadatos GCS presentes
- promote: copy + delete llamado con paths correctos
"""

from __future__ import annotations

import gzip
import io
import json
from typing import Any, cast

from factory_etl.bronze_writer import BronzeWriter, WriteResult
from factory_etl.config import Settings


def _make_settings() -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bronze",
        control_dataset="test_control",
    )


class _FakeBlob:
    """Blob fake que registra uploads y metadatos."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.metadata: dict[str, str] | None = None
        self.uploaded_data: bytes | None = None
        self.uploaded_content_type: str | None = None
        self.deleted = False

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        self.uploaded_data = data
        self.uploaded_content_type = content_type

    def delete(self) -> None:
        self.deleted = True


class _FakeBucket:
    """Bucket fake que memoiza blobs por nombre y registra copy calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.blobs: dict[str, _FakeBlob] = {}
        self.copy_calls: list[tuple[str, str, str]] = []  # (src, dst_bucket, dst_name)

    def blob(self, blob_name: str) -> _FakeBlob:
        if blob_name not in self.blobs:
            self.blobs[blob_name] = _FakeBlob(blob_name)
        return self.blobs[blob_name]

    def copy_blob(
        self,
        source_blob: _FakeBlob,
        destination_bucket: _FakeBucket,
        new_name: str,
    ) -> _FakeBlob:
        self.copy_calls.append((source_blob.name, destination_bucket.name, new_name))
        # Simular la copia creando el destino
        dst_blob = destination_bucket.blob(new_name)
        dst_blob.uploaded_data = source_blob.uploaded_data
        dst_blob.metadata = source_blob.metadata
        return dst_blob


class _FakeClient:
    def __init__(self) -> None:
        self.buckets: dict[str, _FakeBucket] = {}

    def bucket(self, bucket_name: str) -> _FakeBucket:
        if bucket_name not in self.buckets:
            self.buckets[bucket_name] = _FakeBucket(bucket_name)
        return self.buckets[bucket_name]


def _decode_jsonl_gz(data: bytes) -> list[dict[str, Any]]:
    with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as gz:
        text = gz.read().decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


class TestStageLayout:
    def test_ruta_de_staging_correcta(self) -> None:
        client = _FakeClient()
        writer = BronzeWriter(_make_settings(), client=cast(Any, client))

        result = writer.stage(
            run_id="run-123",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            rows=[{"cod_art": "0001"}],
        )

        expected_uri = (
            "gs://test-bronze/_staging/articulos"
            "/source_empresa=tinito/dt=2026-07-22"
            "/run_id=run-123/part-0.jsonl.gz"
        )
        assert result.object_uri == expected_uri

    def test_metadata_contiene_run_id_y_record_count(self) -> None:
        client = _FakeClient()
        writer = BronzeWriter(_make_settings(), client=cast(Any, client))

        writer.stage(
            run_id="run-x",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            rows=[{"a": 1}, {"a": 2}, {"a": 3}],
        )

        bucket = client.buckets["test-bronze"]
        blob = next(iter(bucket.blobs.values()))
        assert blob.metadata is not None
        assert blob.metadata["run_id"] == "run-x"
        assert blob.metadata["entity"] == "articulos"
        assert blob.metadata["source_empresa"] == "tinito"
        assert blob.metadata["dt"] == "2026-07-22"
        assert blob.metadata["record_count"] == "3"

    def test_content_type_es_gzip(self) -> None:
        client = _FakeClient()
        writer = BronzeWriter(_make_settings(), client=cast(Any, client))

        writer.stage(
            run_id="r",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            rows=[{"x": 1}],
        )

        bucket = client.buckets["test-bronze"]
        blob = next(iter(bucket.blobs.values()))
        assert blob.uploaded_content_type == "application/gzip"


class TestStageContent:
    def test_jsonl_decodificable_y_ordenado(self) -> None:
        client = _FakeClient()
        writer = BronzeWriter(_make_settings(), client=cast(Any, client))

        rows: list[dict[str, object]] = [
            {"cod_art": "0001", "descripcion": "Tinito 500ml"},
            {"cod_art": "0002", "descripcion": "Tinito 1L"},
        ]
        writer.stage(
            run_id="r",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            rows=rows,
        )

        bucket = client.buckets["test-bronze"]
        blob = next(iter(bucket.blobs.values()))
        assert blob.uploaded_data is not None

        decoded = _decode_jsonl_gz(blob.uploaded_data)
        assert decoded == rows

    def test_batch_vacio_produce_gzip_valido_de_cero_lineas(self) -> None:
        client = _FakeClient()
        writer = BronzeWriter(_make_settings(), client=cast(Any, client))

        result = writer.stage(
            run_id="r",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            rows=[],
        )

        assert result.record_count == 0
        bucket = client.buckets["test-bronze"]
        blob = next(iter(bucket.blobs.values()))
        assert blob.uploaded_data is not None
        assert _decode_jsonl_gz(blob.uploaded_data) == []

    def test_utf8_preservado_para_acentos(self) -> None:
        client = _FakeClient()
        writer = BronzeWriter(_make_settings(), client=cast(Any, client))

        writer.stage(
            run_id="r",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            rows=[{"nombre": "Piña Colada"}, {"nombre": "Ñandú"}],
        )

        bucket = client.buckets["test-bronze"]
        blob = next(iter(bucket.blobs.values()))
        assert blob.uploaded_data is not None
        decoded = _decode_jsonl_gz(blob.uploaded_data)
        assert decoded[0]["nombre"] == "Piña Colada"
        assert decoded[1]["nombre"] == "Ñandú"


class TestStageDeterminism:
    def test_mismos_rows_mismos_bytes(self) -> None:
        """Reproducibilidad byte-a-byte para permitir hash-comparison."""
        rows: list[dict[str, object]] = [
            {"z": 1, "a": 2, "m": 3},
            {"z": 4, "a": 5, "m": 6},
        ]

        def _write(client: _FakeClient) -> bytes:
            writer = BronzeWriter(_make_settings(), client=cast(Any, client))
            writer.stage(run_id="r", entity="e", source_empresa="s", dt="2026-07-22", rows=rows)
            blob = next(iter(client.buckets["test-bronze"].blobs.values()))
            assert blob.uploaded_data is not None
            return blob.uploaded_data

        bytes_1 = _write(_FakeClient())
        bytes_2 = _write(_FakeClient())
        assert bytes_1 == bytes_2


class TestPromote:
    def test_copia_de_staging_a_bronze_y_borra_origen(self) -> None:
        client = _FakeClient()
        writer = BronzeWriter(_make_settings(), client=cast(Any, client))

        # Primero stagear algo
        writer.stage(
            run_id="run-1",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            rows=[{"cod_art": "0001"}],
        )

        # Ahora promover
        final_uri = writer.promote(
            run_id="run-1",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
        )

        expected = (
            "gs://test-bronze/bronze/articulos"
            "/source_empresa=tinito/dt=2026-07-22"
            "/run_id=run-1/part-0.jsonl.gz"
        )
        assert final_uri == expected

        bucket = client.buckets["test-bronze"]
        assert len(bucket.copy_calls) == 1
        src, _, dst = bucket.copy_calls[0]
        assert "_staging" in src
        assert dst.startswith("bronze/")

        # El blob de staging debe estar marcado como borrado
        staging_blob = next(b for b in bucket.blobs.values() if b.name == src)
        assert staging_blob.deleted


class TestWriteResultShape:
    def test_write_result_es_frozen(self) -> None:
        r = WriteResult(object_uri="x", record_count=1, byte_count=2)
        try:
            r.record_count = 999  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            pass
        else:
            raise AssertionError("WriteResult debe ser frozen")
