"""Tests del orquestador ``Extractor`` con fakes en memoria.

Todas las dependencias del ``Extractor`` son ``Protocol``, asi que estos
tests usan fakes ad-hoc (sin heredar de nada) para verificar el flujo
end-to-end sin tocar GCS, BigQuery ni FactorySoft.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from factory_etl import ids
from factory_etl.bronze_writer import WriteResult
from factory_etl.config import Settings
from factory_etl.control_tables import BatchStatus
from factory_etl.errors import CompanyNotAllowedError, QueryNotFoundError
from factory_etl.extractor import BatchOutcome, Extractor
from factory_etl.quarantine import QuarantineReason
from factory_etl.query_runner import HttpResult


def _make_settings() -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bronze",
        control_dataset="test_control",
    )


def _envelope(rows: list[dict[str, Any]]) -> bytes:
    """Sobre valido de FactorySoft: ``{"d": {"laTablas": [[...]]}}``."""
    return json.dumps({"d": {"laTablas": [rows]}}).encode("utf-8")


class _FakeRunner:
    """Runner en memoria: retorna el ``HttpResult`` configurado."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[dict[str, str]] = []

    def execute(self, *, sql_rendered: str, source_empresa: str) -> HttpResult:
        self.calls.append({"sql": sql_rendered, "empresa": source_empresa})
        return HttpResult(
            payload_bytes=self.payload,
            payload_hash=hashlib.sha256(self.payload).hexdigest(),
            status_code=200,
            elapsed_ms=1,
        )


class _FakeWriter:
    """Bronze en memoria: registra las llamadas a stage/promote."""

    def __init__(self) -> None:
        self.stage_calls: list[dict[str, Any]] = []
        self.promote_calls: list[dict[str, Any]] = []
        self._staging_uri = "gs://test-bronze/_staging/x/part-0.jsonl.gz"
        self._final_uri = "gs://test-bronze/bronze/x/part-0.jsonl.gz"

    def stage(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
        rows: list[dict[str, object]],
    ) -> WriteResult:
        self.stage_calls.append(
            {
                "run_id": run_id,
                "entity": entity,
                "source_empresa": source_empresa,
                "dt": dt,
                "record_count": len(rows),
            }
        )
        return WriteResult(
            object_uri=self._staging_uri,
            record_count=len(rows),
            byte_count=42,
        )

    def promote(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
    ) -> str:
        self.promote_calls.append(
            {
                "run_id": run_id,
                "entity": entity,
                "source_empresa": source_empresa,
                "dt": dt,
            }
        )
        return self._final_uri


class _FakeControl:
    """Tablas de control en memoria."""

    def __init__(self, existing_batch_id: str | None = None) -> None:
        self.existing = existing_batch_id
        self.starts: list[str] = []
        self.finishes: list[dict[str, Any]] = []
        self.registered: list[dict[str, Any]] = []
        self.find_calls: list[dict[str, str]] = []

    def start_run(self, *, run_id: str, extras: dict[str, Any] | None = None) -> None:
        self.starts.append(run_id)

    def finish_run(
        self,
        *,
        run_id: str,
        status: Any,
        error: str | None = None,
    ) -> None:
        self.finishes.append({"run_id": run_id, "status": status, "error": error})

    def register_batch(
        self,
        *,
        batch_id: str,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
        status: BatchStatus,
        record_count: int | None = None,
        object_uri: str | None = None,
        payload_hash: str | None = None,
    ) -> None:
        self.registered.append(
            {
                "batch_id": batch_id,
                "run_id": run_id,
                "entity": entity,
                "source_empresa": source_empresa,
                "dt": dt,
                "status": status,
                "record_count": record_count,
                "object_uri": object_uri,
                "payload_hash": payload_hash,
            }
        )

    def find_batch_by_hash(
        self,
        *,
        source_empresa: str,
        query_id: str,
        dt: str,
        payload_hash: str,
    ) -> str | None:
        self.find_calls.append(
            {
                "source_empresa": source_empresa,
                "query_id": query_id,
                "dt": dt,
                "payload_hash": payload_hash,
            }
        )
        return self.existing


class _FakeQuarantine:
    def __init__(self) -> None:
        self.dumps: list[dict[str, Any]] = []

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
        self.dumps.append(
            {
                "run_id": run_id,
                "entity": entity,
                "source_empresa": source_empresa,
                "dt": dt,
                "reason": reason,
                "size": len(payload_bytes),
            }
        )
        return f"gs://test-bronze/quarantine/{entity}/{reason.value}/payload.json"


def _build_extractor(
    *,
    runner: _FakeRunner,
    writer: _FakeWriter | None = None,
    control: _FakeControl | None = None,
    quarantine: _FakeQuarantine | None = None,
) -> tuple[Extractor, _FakeWriter, _FakeControl, _FakeQuarantine]:
    w = writer or _FakeWriter()
    c = control or _FakeControl()
    q = quarantine or _FakeQuarantine()
    ex = Extractor(
        settings=_make_settings(),
        runner=runner,
        writer=w,
        control=c,
        quarantine=q,
    )
    return ex, w, c, q


class TestHappyPath:
    def test_flujo_completo_end_to_end(self) -> None:
        rows = [{"cod_art": "0001", "nom_art": "Uno"}, {"cod_art": "0002", "nom_art": "Dos"}]
        runner = _FakeRunner(_envelope(rows))
        ex, _writer, _control, _quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert isinstance(outcome, BatchOutcome)
        assert outcome.status == BatchStatus.SUCCESS.value
        assert outcome.record_count == 2
        assert outcome.was_duplicate is False
        assert outcome.object_uri is not None
        assert "bronze/" in outcome.object_uri

    def test_registra_written_luego_success_en_ese_orden(self) -> None:
        runner = _FakeRunner(_envelope([{"cod_art": "0001"}]))
        ex, _, control, _ = _build_extractor(runner=runner)

        ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        statuses = [r["status"] for r in control.registered]
        assert statuses == [BatchStatus.WRITTEN, BatchStatus.SUCCESS]

    def test_writer_stage_recibe_rows_parseadas(self) -> None:
        rows = [{"cod_art": "0001"}, {"cod_art": "0002"}, {"cod_art": "0003"}]
        runner = _FakeRunner(_envelope(rows))
        ex, writer, _, _ = _build_extractor(runner=runner)

        ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert len(writer.stage_calls) == 1
        assert writer.stage_calls[0]["record_count"] == 3
        assert len(writer.promote_calls) == 1

    def test_batch_id_deterministico_por_hash(self) -> None:
        rows = [{"cod_art": "0001"}]
        payload = _envelope(rows)
        runner = _FakeRunner(payload)
        ex, _, _, _ = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )
        expected = ids.batch_id(
            source_empresa="tinito",
            query_id="articulos_v1",
            dt="2025-01-15",
            payload_hash_hex=hashlib.sha256(payload).hexdigest(),
        )
        assert outcome.batch_id == expected

    def test_soporta_sobre_heredado_con_datos(self) -> None:
        # sobre viejo con clave "datos" en lugar de "d"
        payload = json.dumps({"datos": {"laTablas": [[{"cod_art": "0001"}]]}}).encode("utf-8")
        runner = _FakeRunner(payload)
        ex, _, _, _ = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )
        assert outcome.status == BatchStatus.SUCCESS.value
        assert outcome.record_count == 1

    def test_utf8_bom_en_payload(self) -> None:
        payload = b"\xef\xbb\xbf" + _envelope([{"cod_art": "0001"}])
        runner = _FakeRunner(payload)
        ex, _, _, _ = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )
        assert outcome.status == BatchStatus.SUCCESS.value


class TestDuplicate:
    def test_hash_ya_existente_retorna_skipped_sin_escribir(self) -> None:
        rows = [{"cod_art": "0001"}]
        runner = _FakeRunner(_envelope(rows))
        control = _FakeControl(existing_batch_id="batch-previo")
        ex, writer, _, quarantine = _build_extractor(runner=runner, control=control)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert outcome.status == BatchStatus.SKIPPED_DUPLICATE.value
        assert outcome.batch_id == "batch-previo"
        assert outcome.was_duplicate is True
        assert writer.stage_calls == []
        assert writer.promote_calls == []
        assert control.registered == []  # no se registra un nuevo batch
        assert quarantine.dumps == []


class TestQuarantine:
    def test_payload_vacio_con_reject_empty_va_a_cuarentena(self) -> None:
        # articulos_v1 tiene reject_empty=True
        runner = _FakeRunner(_envelope([]))
        ex, writer, control, quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert outcome.status == BatchStatus.QUARANTINED.value
        assert outcome.record_count is None
        assert len(quarantine.dumps) == 1
        assert quarantine.dumps[0]["reason"] == QuarantineReason.EMPTY_REJECTED
        # No debe haber intentado escribir Bronze
        assert writer.stage_calls == []
        assert writer.promote_calls == []
        # Debe registrar QUARANTINED en control
        assert len(control.registered) == 1
        assert control.registered[0]["status"] == BatchStatus.QUARANTINED

    def test_payload_no_json_va_a_cuarentena_schema_mismatch(self) -> None:
        runner = _FakeRunner(b"esto no es json")
        ex, writer, _control, quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert outcome.status == BatchStatus.QUARANTINED.value
        assert quarantine.dumps[0]["reason"] == QuarantineReason.SCHEMA_MISMATCH
        assert writer.stage_calls == []

    def test_payload_sin_latablas_va_a_cuarentena(self) -> None:
        runner = _FakeRunner(b'{"d": {"otra_cosa": "x"}}')
        ex, _, _, quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert outcome.status == BatchStatus.QUARANTINED.value
        assert quarantine.dumps[0]["reason"] == QuarantineReason.SCHEMA_MISMATCH

    def test_payload_con_llerror_va_a_cuarentena(self) -> None:
        payload = json.dumps({"llError": True, "d": {"laTablas": [[]]}}).encode("utf-8")
        runner = _FakeRunner(payload)
        ex, _, _, quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert outcome.status == BatchStatus.QUARANTINED.value
        assert quarantine.dumps[0]["reason"] == QuarantineReason.SCHEMA_MISMATCH


class TestCatalogValidation:
    def test_query_id_desconocido_dispara_error(self) -> None:
        runner = _FakeRunner(_envelope([]))
        ex, _, _, _ = _build_extractor(runner=runner)

        with pytest.raises(QueryNotFoundError):
            ex.run_batch(
                query_id="no_existe_v1",
                source_empresa="tinito",
                dt="2025-01-15",
                run_id="run-abc",
            )

    def test_empresa_no_autorizada_dispara_error(self) -> None:
        runner = _FakeRunner(_envelope([{"cod_art": "0001"}]))
        ex, _, _, _ = _build_extractor(runner=runner)

        with pytest.raises(CompanyNotAllowedError):
            ex.run_batch(
                query_id="articulos_v1",
                source_empresa="ctb",  # articulos_v1 solo permite "tinito"
                dt="2025-01-15",
                run_id="run-abc",
            )


class TestRequestShape:
    def test_runner_recibe_source_empresa_correcto(self) -> None:
        runner = _FakeRunner(_envelope([{"cod_art": "0001"}]))
        ex, _, _, _ = _build_extractor(runner=runner)

        ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )
        assert runner.calls[0]["empresa"] == "tinito"

    def test_find_batch_by_hash_recibe_hash_correcto(self) -> None:
        payload = _envelope([{"cod_art": "0001"}])
        runner = _FakeRunner(payload)
        ex, _, control, _ = _build_extractor(runner=runner)

        ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )
        assert control.find_calls[0]["payload_hash"] == hashlib.sha256(payload).hexdigest()
        assert control.find_calls[0]["source_empresa"] == "tinito"
        assert control.find_calls[0]["query_id"] == "articulos_v1"
        assert control.find_calls[0]["dt"] == "2025-01-15"


class TestBatchOutcomeShape:
    def test_frozen(self) -> None:
        o = BatchOutcome(
            batch_id="b1",
            status="success",
            object_uri="gs://x",
            record_count=1,
            was_duplicate=False,
        )
        try:
            o.status = "changed"  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            pass
        else:
            raise AssertionError("BatchOutcome debe ser frozen")
