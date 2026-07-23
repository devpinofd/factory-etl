"""Tests de Quarantine.

Verifica:

- Path construido con reason y hive partitioning
- Payload guardado byte-a-byte (raw)
- Metadatos GCS presentes
- Uso de quarantine_bucket dedicado si esta configurado
- Fallback a bronze_bucket con prefijo quarantine/ si no
"""

from __future__ import annotations

from typing import Any, cast

from factory_etl.config import Settings
from factory_etl.quarantine import Quarantine, QuarantineReason


def _make_settings(*, quarantine_bucket: str = "") -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bronze",
        quarantine_bucket=quarantine_bucket,
        control_dataset="test_control",
    )


class _FakeBlob:
    def __init__(self, name: str) -> None:
        self.name = name
        self.metadata: dict[str, str] | None = None
        self.uploaded_data: bytes | None = None
        self.uploaded_content_type: str | None = None

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        self.uploaded_data = data
        self.uploaded_content_type = content_type


class _FakeBucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.blobs: dict[str, _FakeBlob] = {}

    def blob(self, blob_name: str) -> _FakeBlob:
        if blob_name not in self.blobs:
            self.blobs[blob_name] = _FakeBlob(blob_name)
        return self.blobs[blob_name]


class _FakeClient:
    def __init__(self) -> None:
        self.buckets: dict[str, _FakeBucket] = {}

    def bucket(self, bucket_name: str) -> _FakeBucket:
        if bucket_name not in self.buckets:
            self.buckets[bucket_name] = _FakeBucket(bucket_name)
        return self.buckets[bucket_name]


class TestDumpPath:
    def test_path_incluye_reason_y_hive_partitioning(self) -> None:
        client = _FakeClient()
        q = Quarantine(_make_settings(), client=cast(Any, client))

        uri = q.dump(
            run_id="run-1",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            payload_bytes=b'{"d":null}',
            reason=QuarantineReason.EMPTY_REJECTED,
        )

        expected = (
            "gs://test-bronze/quarantine/articulos"
            "/source_empresa=tinito/dt=2026-07-22"
            "/run_id=run-1/reason=empty_rejected/payload.json"
        )
        assert uri == expected

    def test_usa_bucket_dedicado_si_esta_configurado(self) -> None:
        client = _FakeClient()
        settings = _make_settings(quarantine_bucket="test-quarantine")
        q = Quarantine(settings, client=cast(Any, client))

        uri = q.dump(
            run_id="r",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            payload_bytes=b"x",
            reason=QuarantineReason.UNKNOWN,
        )

        assert uri.startswith("gs://test-quarantine/quarantine/")
        assert "test-bronze" not in uri

    def test_usa_bronze_bucket_como_fallback(self) -> None:
        client = _FakeClient()
        q = Quarantine(_make_settings(), client=cast(Any, client))  # sin quarantine_bucket

        uri = q.dump(
            run_id="r",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            payload_bytes=b"x",
            reason=QuarantineReason.UNKNOWN,
        )

        assert uri.startswith("gs://test-bronze/quarantine/")


class TestDumpContent:
    def test_payload_se_guarda_byte_a_byte(self) -> None:
        client = _FakeClient()
        q = Quarantine(_make_settings(), client=cast(Any, client))
        original = b'{"d":{"laTablas":[[]]}, "malformed": "\xff\xfe binary noise"}'

        q.dump(
            run_id="r",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            payload_bytes=original,
            reason=QuarantineReason.SCHEMA_MISMATCH,
        )

        bucket = client.buckets["test-bronze"]
        blob = next(iter(bucket.blobs.values()))
        assert blob.uploaded_data == original

    def test_content_type_json(self) -> None:
        client = _FakeClient()
        q = Quarantine(_make_settings(), client=cast(Any, client))

        q.dump(
            run_id="r",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            payload_bytes=b"{}",
            reason=QuarantineReason.PARSE_ERROR,
        )

        bucket = client.buckets["test-bronze"]
        blob = next(iter(bucket.blobs.values()))
        assert blob.uploaded_content_type == "application/json"


class TestDumpMetadata:
    def test_metadata_completa(self) -> None:
        client = _FakeClient()
        q = Quarantine(_make_settings(), client=cast(Any, client))
        payload = b'{"d":null}'

        q.dump(
            run_id="run-42",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            payload_bytes=payload,
            reason=QuarantineReason.EMPTY_REJECTED,
        )

        bucket = client.buckets["test-bronze"]
        blob = next(iter(bucket.blobs.values()))
        assert blob.metadata is not None
        assert blob.metadata["run_id"] == "run-42"
        assert blob.metadata["entity"] == "articulos"
        assert blob.metadata["source_empresa"] == "tinito"
        assert blob.metadata["dt"] == "2026-07-22"
        assert blob.metadata["reason"] == "empty_rejected"
        assert blob.metadata["byte_count"] == str(len(payload))


class TestQuarantineReasonEnum:
    def test_todas_las_razones_son_string_snake_case(self) -> None:
        # StrEnum: values son strings usables en paths
        for r in QuarantineReason:
            assert r.value.islower()
            assert " " not in r.value

    def test_reason_unknown_disponible(self) -> None:
        # Ancla para casos no clasificados
        assert QuarantineReason.UNKNOWN.value == "unknown"
