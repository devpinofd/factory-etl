"""Tests unitarios de ``ControlTables.log_event`` con un ``_FakeBigQueryClient``.

Se inyecta el cliente por constructor para evitar la creacion perezosa
de un ``google.cloud.bigquery.Client`` real. Cubrimos:

- Estructura de la fila enviada a ``insert_rows_json``.
- Uso del ``event_id`` como ``insertId`` para deduplicacion.
- Truncado del campo ``extras`` cuando supera ``_EXTRAS_MAX_BYTES``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from factory_etl.config import Settings
from factory_etl.control_tables import (
    _EXTRAS_MAX_BYTES,
    ControlTables,
    ControlTablesError,
    RunStatus,
)


class _FakeBigQueryClient:
    """Captura de llamadas a ``insert_rows_json`` sin tocar la red."""

    def __init__(self, errors: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._errors = errors or []

    def insert_rows_json(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        row_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append({"table": table, "rows": rows, "row_ids": row_ids})
        return self._errors

    def query(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError("log_event no invoca query()")


def _make_settings() -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bronze",
        control_dataset="test_control",
    )


def _make_control(
    client: _FakeBigQueryClient | None = None,
) -> tuple[ControlTables, _FakeBigQueryClient]:
    c = client or _FakeBigQueryClient()
    return ControlTables(_make_settings(), client=c), c


class TestLogEventInsertion:
    def test_log_event_inserta_una_fila_en_tabla_events(self) -> None:
        control, client = _make_control()

        control.log_event(
            run_id="run-abc",
            event_type="BATCH_STAGED",
            phase="stage",
            batch_id="batch-xyz",
            entity="articulos_v1",
        )

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["table"].endswith(".etl_events")
        assert len(call["rows"]) == 1

    def test_row_contiene_los_campos_esperados(self) -> None:
        control, client = _make_control()

        control.log_event(
            run_id="run-abc",
            event_type="BATCH_SUCCESS",
            phase="finalize",
            batch_id="batch-xyz",
            entity="articulos_v1",
            duration_ms=42,
            extras={"foo": "bar"},
        )
        row = client.calls[0]["rows"][0]
        assert row["run_id"] == "run-abc"
        assert row["batch_id"] == "batch-xyz"
        assert row["entity"] == "articulos_v1"
        assert row["phase"] == "finalize"
        assert row["event_type"] == "BATCH_SUCCESS"
        assert row["duration_ms"] == 42
        assert "event_id" in row
        assert len(row["event_id"]) == 32  # uuid4().hex
        assert "inserted_at" in row
        # extras serializado como JSON estable (sort_keys=True).
        assert row["extras"] == '{"foo": "bar"}'

    def test_event_id_es_usado_como_row_id_para_dedup(self) -> None:
        control, client = _make_control()
        control.log_event(
            run_id="run-abc",
            event_type="BATCH_STAGED",
            phase="stage",
        )
        call = client.calls[0]
        row_ids = call["row_ids"]
        assert row_ids is not None
        assert len(row_ids) == 1
        assert row_ids[0] == call["rows"][0]["event_id"]

    def test_extras_none_se_serializa_como_objeto_vacio(self) -> None:
        control, client = _make_control()
        control.log_event(
            run_id="run-abc",
            event_type="SCHEMA_DRIFT",
            phase="validate",
        )
        assert client.calls[0]["rows"][0]["extras"] == "{}"

    def test_extras_mayor_a_2kb_se_trunca_con_marcador(self) -> None:
        control, client = _make_control()
        # Payload garantizado > 2 KB.
        big_value = "x" * (_EXTRAS_MAX_BYTES + 100)
        control.log_event(
            run_id="run-abc",
            event_type="SCHEMA_DRIFT",
            phase="validate",
            extras={"payload": big_value},
        )
        serialized = client.calls[0]["rows"][0]["extras"]
        decoded = json.loads(serialized)
        assert decoded["__truncated"] is True
        assert isinstance(decoded["size_bytes"], int)
        assert decoded["size_bytes"] > _EXTRAS_MAX_BYTES
        # El contenido original NO debe estar presente.
        assert "x" * 100 not in serialized

    def test_fallo_de_bigquery_propaga_control_tables_error(self) -> None:
        client = _FakeBigQueryClient(errors=[{"index": 0, "errors": ["oops"]}])
        control, _ = _make_control(client=client)
        with pytest.raises(ControlTablesError):
            control.log_event(
                run_id="run-abc",
                event_type="BATCH_STAGED",
                phase="stage",
            )


class TestFinishRunExtras:
    def test_finish_run_propaga_extras_al_row(self) -> None:
        control, client = _make_control()
        control.finish_run(
            run_id="run-abc",
            status=RunStatus.SUCCESS,
            extras={"batch_id": "b-1", "final_status": "success"},
        )
        row = client.calls[0]["rows"][0]
        assert row["extras"] == '{"batch_id": "b-1", "final_status": "success"}'

    def test_finish_run_sin_extras_deja_diccionario_vacio(self) -> None:
        control, client = _make_control()
        control.finish_run(run_id="run-abc", status=RunStatus.SUCCESS)
        assert client.calls[0]["rows"][0]["extras"] == "{}"
