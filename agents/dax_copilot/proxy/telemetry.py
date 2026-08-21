from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from collections.abc import Mapping
from typing import Any

_DCR_INGESTION_URL: str | None = None


def pseudonymize_subject(subject: str) -> str:
    digest = hashlib.sha256(subject.strip().lower().encode("utf-8")).hexdigest()
    return f"usr_{digest[:16]}"


def _dcr_ingestion_url() -> str | None:
    global _DCR_INGESTION_URL
    if _DCR_INGESTION_URL is not None:
        return _DCR_INGESTION_URL or None
    dce = os.getenv("DAX_COPILOT_DCE_INGESTION_ENDPOINT", "").rstrip("/")
    dcr = os.getenv("DAX_COPILOT_DCR_IMMUTABLE_ID", "")
    stream = os.getenv("DAX_COPILOT_DCR_STREAM", "Custom-DaxCopilotEvent_CL")
    if dce and dcr:
        _DCR_INGESTION_URL = (
            f"{dce}/dataCollectionRules/{dcr}/streams/{stream}?api-version=2023-01-01"
        )
    else:
        _DCR_INGESTION_URL = ""
    return _DCR_INGESTION_URL or None


def build_dcr_record(event: Mapping[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {"TimeGenerated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for key, value in event.items():
        if key in {"event_type"}:
            continue
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int | float):
            record[f"{key}_d"] = float(value)
        else:
            record[f"{key}_s"] = value if isinstance(value, str) else json.dumps(value)
    return record


def send_to_dcr(event: Mapping[str, Any], credential: Any) -> bool:
    """Ingesta el evento a Log Analytics vía DCR. Devuelve True si se aceptó (HTTP 204)."""
    import urllib.request

    url = _dcr_ingestion_url()
    if not url:
        return False
    try:
        token = credential.get_token("https://monitor.azure.com/.default").token
    except Exception:
        logging.getLogger(__name__).warning("No se pudo obtener token para ingesta DCR.")
        return False

    if not url.startswith("https://"):
        logging.getLogger(__name__).warning("Endpoint DCR rechazado: debe ser HTTPS.")
        return False
    body = json.dumps([build_dcr_record(event)]).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 - endpoint validado como HTTPS
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return resp.status in (200, 202, 204)
    except Exception:
        logging.getLogger(__name__).warning("Fallo la ingesta DCR; el evento quedó solo en App Insights.")
        return False


def should_sample_success(status: str, sample_percent: float | None = None) -> bool:
    if status != "SUCCESS":
        return True
    configured_percent = sample_percent
    if configured_percent is None:
        try:
            configured_percent = float(os.getenv("DAX_COPILOT_SUCCESS_SAMPLE_PERCENT", "10"))
        except ValueError:
            configured_percent = 10.0
    configured_percent = min(max(configured_percent, 0.0), 100.0)
    return secrets.randbelow(100) < configured_percent


def emit_event(
    logger: logging.Logger,
    *,
    event_name: str,
    request_id: str,
    subject: str,
    status: str,
    duration_ms: int | None = None,
    error_code: str | None = None,
    attributes: Mapping[str, Any] | None = None,
) -> str:
    if not should_sample_success(status):
        return ""

    event_id = str(uuid.uuid4())
    event: dict[str, Any] = {
        "event_type": "dax_copilot",
        "event_id": event_id,
        "event_name": event_name,
        "request_id": request_id,
        "subject_hash": pseudonymize_subject(subject),
        "status": status,
        "duration_ms": duration_ms,
    }
    if error_code:
        event["error_code"] = error_code
    if attributes:
        event["attributes"] = dict(attributes)
    logger.info("dax_copilot_event=%s", json.dumps(event, separators=(",", ":")))

    if _dcr_ingestion_url():
        try:
            from azure.identity import DefaultAzureCredential

            send_to_dcr(event, DefaultAzureCredential())
        except Exception:
            logger.warning("Ingesta DCR no disponible; evento conservado en App Insights.")
    return event_id


class Stopwatch:
    def __enter__(self) -> Stopwatch:
        self._started = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.duration_ms = int((time.perf_counter() - self._started) * 1000)

    duration_ms: int = 0
