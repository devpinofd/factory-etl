from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path

TELEMETRY_PATH = (
    Path(__file__).parents[2]
    / "agents"
    / "dax_copilot"
    / "proxy"
    / "telemetry.py"
)
SPEC = importlib.util.spec_from_file_location("dax_telemetry", TELEMETRY_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_subject_is_pseudonymized() -> None:
    assert MODULE.pseudonymize_subject("User@Example.com") == MODULE.pseudonymize_subject(
        "user@example.com"
    )
    assert "user@example.com" not in MODULE.pseudonymize_subject("user@example.com")


def test_event_is_structured_and_does_not_log_subject(caplog, monkeypatch) -> None:
    monkeypatch.setenv("DAX_COPILOT_SUCCESS_SAMPLE_PERCENT", "100")
    with caplog.at_level(logging.INFO):
        event_id = MODULE.emit_event(
            logging.getLogger("test.telemetry"),
            event_name="chat_completion",
            request_id="req-1",
            subject="user@example.com",
            status="SUCCESS",
            duration_ms=42,
            attributes={"tool_count": 1},
        )

    record = next(record for record in caplog.records if "dax_copilot_event=" in record.message)
    payload = json.loads(record.message.split("=", 1)[1])
    assert payload["event_id"] == event_id
    assert payload["request_id"] == "req-1"
    assert payload["duration_ms"] == 42
    assert "user@example.com" not in record.message


def test_success_sampling_rules() -> None:
    assert MODULE.should_sample_success("ERROR") is True
    assert MODULE.should_sample_success("UNAUTHORIZED") is True
    assert MODULE.should_sample_success("SUCCESS", sample_percent=100) is True
    assert MODULE.should_sample_success("SUCCESS", sample_percent=0) is False


def test_build_dcr_record_maps_suffixes() -> None:
    event = {
        "event_type": "dax_copilot",
        "event_id": "evt-1",
        "event_name": "chat_completion",
        "request_id": "req-1",
        "subject_hash": "usr_abc",
        "status": "SUCCESS",
        "duration_ms": 42,
        "error_code": None,
        "attributes": {"tool_count": 1},
    }
    record = MODULE.build_dcr_record(event)
    assert "TimeGenerated" in record
    assert record["event_id_s"] == "evt-1"
    assert record["subject_hash_s"] == "usr_abc"
    assert record["status_s"] == "SUCCESS"
    assert record["duration_ms_d"] == 42.0
    assert "error_code_s" not in record
    assert "event_type" not in record
    assert "attributes_s" in record


def test_dcr_url_requires_configuration(monkeypatch) -> None:
    monkeypatch.delenv("DAX_COPILOT_DCE_INGESTION_ENDPOINT", raising=False)
    monkeypatch.delenv("DAX_COPILOT_DCR_IMMUTABLE_ID", raising=False)
    MODULE._DCR_INGESTION_URL = None
    assert MODULE._dcr_ingestion_url() is None
    monkeypatch.setenv("DAX_COPILOT_DCE_INGESTION_ENDPOINT", "https://dce.example.ingest.monitor.azure.com")
    monkeypatch.setenv("DAX_COPILOT_DCR_IMMUTABLE_ID", "dcr-abc123")
    MODULE._DCR_INGESTION_URL = None
    url = MODULE._dcr_ingestion_url()
    assert url and "dcr-abc123" in url and "Custom-DaxCopilotEvent_CL" in url
    MODULE._DCR_INGESTION_URL = None
