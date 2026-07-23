"""Tests de ControlTables (BQ streaming inserts + query por hash).

Inyecta un fake del client de BQ. Verifica:

- FQN de tabla con project.dataset.table
- insert_rows_json con row_ids para idempotencia
- Manejo de errores retornados por BQ
- find_batch_by_hash usa query parametrizado (no concatena)
- Retorno None cuando no hay match
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from factory_etl.config import Settings
from factory_etl.control_tables import (
    BatchStatus,
    ControlTables,
    ControlTablesError,
    RunStatus,
)


def _make_settings() -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bronze",
        control_dataset="factory_etl_control",
    )


class _FakeClient:
    """Fake BQ client. Captura llamadas para aserciones."""

    def __init__(self, insert_errors: list[dict[str, Any]] | None = None) -> None:
        self.insert_calls: list[tuple[str, list[dict[str, Any]], list[str] | None]] = []
        self.query_calls: list[tuple[str, Any]] = []
        self._insert_errors = insert_errors or []
        self._query_result: list[tuple[str, ...]] = []

    def insert_rows_json(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        row_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self.insert_calls.append((table, rows, row_ids))
        return self._insert_errors

    def query(self, query: str, *, job_config: Any = None) -> list[tuple[str, ...]]:
        self.query_calls.append((query, job_config))
        return self._query_result

    def set_query_result(self, rows: list[tuple[str, ...]]) -> None:
        self._query_result = rows


class TestStartRun:
    def test_inserta_en_etl_runs_con_status_running(self) -> None:
        client = _FakeClient()
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        ct.start_run(run_id="run-1")

        assert len(client.insert_calls) == 1
        table, rows, row_ids = client.insert_calls[0]
        assert table == "test-project.factory_etl_control.etl_runs"
        assert rows[0]["run_id"] == "run-1"
        assert rows[0]["status"] == "running"
        assert rows[0]["started_at"] is not None
        assert rows[0]["ended_at"] is None
        assert row_ids == ["run-1"]

    def test_extras_se_incluyen(self) -> None:
        client = _FakeClient()
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        ct.start_run(run_id="run-1", extras={"trigger": "cli", "user": "francisco"})

        _, rows, _ = client.insert_calls[0]
        assert rows[0]["extras"] == {"trigger": "cli", "user": "francisco"}


class TestFinishRun:
    def test_status_success(self) -> None:
        client = _FakeClient()
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        ct.finish_run(run_id="run-1", status=RunStatus.SUCCESS)

        _, rows, row_ids = client.insert_calls[0]
        assert rows[0]["run_id"] == "run-1"
        assert rows[0]["status"] == "success"
        assert rows[0]["ended_at"] is not None
        assert rows[0]["error"] is None
        # row_id distinto al start para permitir la segunda insercion
        assert row_ids == ["run-1:finish"]

    def test_status_failed_con_error(self) -> None:
        client = _FakeClient()
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        ct.finish_run(run_id="run-1", status=RunStatus.FAILED, error="timeout")

        _, rows, _ = client.insert_calls[0]
        assert rows[0]["status"] == "failed"
        assert rows[0]["error"] == "timeout"


class TestRegisterBatch:
    def test_inserta_todos_los_campos(self) -> None:
        client = _FakeClient()
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        ct.register_batch(
            batch_id="batch-abc",
            run_id="run-1",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            status=BatchStatus.SUCCESS,
            record_count=1234,
            object_uri="gs://test-bronze/bronze/articulos/...",
            payload_hash="abcd" * 16,
        )

        table, rows, row_ids = client.insert_calls[0]
        assert table == "test-project.factory_etl_control.etl_batches"
        row = rows[0]
        assert row["batch_id"] == "batch-abc"
        assert row["run_id"] == "run-1"
        assert row["entity"] == "articulos"
        assert row["source_empresa"] == "tinito"
        assert row["dt"] == "2026-07-22"
        assert row["status"] == "success"
        assert row["record_count"] == 1234
        assert row["object_uri"] == "gs://test-bronze/bronze/articulos/..."
        assert row["payload_hash"] == "abcd" * 16
        # row_id incluye status para permitir progresion written -> success
        assert row_ids == ["batch-abc:success"]

    def test_progresion_written_a_success_usa_row_ids_distintos(self) -> None:
        client = _FakeClient()
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        ct.register_batch(
            batch_id="b1",
            run_id="r1",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            status=BatchStatus.WRITTEN,
        )
        ct.register_batch(
            batch_id="b1",
            run_id="r1",
            entity="e",
            source_empresa="s",
            dt="2026-07-22",
            status=BatchStatus.SUCCESS,
        )

        _, _, row_ids_1 = client.insert_calls[0]
        _, _, row_ids_2 = client.insert_calls[1]
        assert row_ids_1 == ["b1:written"]
        assert row_ids_2 == ["b1:success"]


class TestInsertErrors:
    def test_bq_errores_disparan_control_tables_error(self) -> None:
        client = _FakeClient(insert_errors=[{"index": 0, "errors": ["type mismatch"]}])
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        with pytest.raises(ControlTablesError, match="fallo"):
            ct.start_run(run_id="run-1")

    def test_mensaje_de_error_no_incluye_contenido_de_las_filas(self) -> None:
        """No filtrar payload en errores es defensa contra PII."""
        client = _FakeClient(
            insert_errors=[
                {"index": 0, "errors": ["some sensitive detail token=SECRETO"]},
            ]
        )
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        with pytest.raises(ControlTablesError) as exc_info:
            ct.start_run(run_id="run-1")

        assert "SECRETO" not in str(exc_info.value)
        assert "token" not in str(exc_info.value)


class TestFindBatchByHash:
    def test_devuelve_batch_id_si_existe(self) -> None:
        client = _FakeClient()
        client.set_query_result([("batch-encontrado",)])
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        result = ct.find_batch_by_hash(
            source_empresa="tinito",
            query_id="articulos",
            dt="2026-07-22",
            payload_hash="hash-x",
        )

        assert result == "batch-encontrado"

    def test_devuelve_none_si_no_existe(self) -> None:
        client = _FakeClient()  # query_result vacio por default
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        result = ct.find_batch_by_hash(
            source_empresa="tinito",
            query_id="articulos",
            dt="2026-07-22",
            payload_hash="hash-x",
        )

        assert result is None

    def test_query_no_concatena_hash_en_sql(self) -> None:
        """El hash es fuente externa: DEBE ir como parametro, no concatenado."""
        client = _FakeClient()
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        malicious = "'; DROP TABLE etl_batches; --"
        ct.find_batch_by_hash(
            source_empresa="tinito",
            query_id="articulos",
            dt="2026-07-22",
            payload_hash=malicious,
        )

        sql, _ = client.query_calls[0]
        # El hash malicioso NO debe aparecer literal en el SQL
        assert malicious not in sql
        # Debe haber placeholders parametrizados
        assert "@payload_hash" in sql

    def test_query_filtra_por_status_success_o_written(self) -> None:
        client = _FakeClient()
        ct = ControlTables(_make_settings(), client=cast(Any, client))

        ct.find_batch_by_hash(
            source_empresa="s",
            query_id="q",
            dt="2026-07-22",
            payload_hash="h",
        )

        sql, _ = client.query_calls[0]
        assert "success" in sql
        assert "written" in sql
