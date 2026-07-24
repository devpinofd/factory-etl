"""Tests de validacion de esquema y drift en ``Extractor.run_batch``.

Se reusa la infraestructura de fakes definida en ``test_extractor``: los
fakes no viven en ``conftest.py`` para mantener explicitamente el contrato
de que cada modulo puede reemplazarlos si lo necesita.
"""

from __future__ import annotations

from typing import Any

from factory_etl.control_tables import BatchStatus
from factory_etl.quarantine import QuarantineReason

from .test_extractor import (
    _build_extractor,
    _envelope,
    _FakeControl,
    _FakeRunner,
    _ok_row,
)


def _events_of_type(control: _FakeControl, event_type: str) -> list[dict[str, Any]]:
    return [e for e in control.events if e["event_type"] == event_type]


class TestSchemaHappyPath:
    def test_todas_las_columnas_requeridas_presentes_batch_success(self) -> None:
        payload = _envelope([_ok_row("0001"), _ok_row("0002")])
        runner = _FakeRunner(payload)
        ex, _writer, control, quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert outcome.status == BatchStatus.SUCCESS.value
        assert quarantine.dumps == []
        # No debe haber SCHEMA_DRIFT porque las columnas son parte del esquema.
        assert _events_of_type(control, "SCHEMA_DRIFT") == []
        assert _events_of_type(control, "QUARANTINED_SCHEMA") == []


class TestSchemaMissingRequired:
    def test_fila_sin_required_va_a_cuarentena_con_evento(self) -> None:
        # Falta ``cod_uni1`` y ``status`` (ambos required).
        bad_row: dict[str, Any] = {"cod_art": "0001", "nom_art": "X"}
        runner = _FakeRunner(_envelope([bad_row]))
        ex, writer, control, quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert outcome.status == BatchStatus.QUARANTINED.value
        assert writer.stage_calls == []
        assert len(quarantine.dumps) == 1
        assert quarantine.dumps[0]["reason"] == QuarantineReason.SCHEMA_MISMATCH

        events = _events_of_type(control, "QUARANTINED_SCHEMA")
        assert len(events) == 1
        assert events[0]["phase"] == "validate"
        assert events[0]["entity"] == "articulos_v1"
        # El extras debe reportar cual fila e indice.
        extras = events[0]["extras"]
        assert extras is not None
        assert extras["row_index"] == 0
        assert set(extras["missing_columns"]) == {"cod_uni1", "status"}

    def test_segunda_fila_incompleta_tambien_dispara_cuarentena(self) -> None:
        rows = [_ok_row("0001"), {"cod_art": "0002"}]  # segunda sin required
        runner = _FakeRunner(_envelope(rows))
        ex, _writer, control, _quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )
        assert outcome.status == BatchStatus.QUARANTINED.value
        events = _events_of_type(control, "QUARANTINED_SCHEMA")
        assert len(events) == 1
        assert events[0]["extras"] is not None
        assert events[0]["extras"]["row_index"] == 1


class TestSchemaDrift:
    def test_columnas_extra_disparan_schema_drift_pero_batch_es_success(self) -> None:
        # Fila con todas las requeridas + una columna no declarada.
        row = _ok_row("0001", columna_nueva="valor", otra_extra=123)
        runner = _FakeRunner(_envelope([row]))
        ex, _writer, control, quarantine = _build_extractor(runner=runner)

        outcome = ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )

        assert outcome.status == BatchStatus.SUCCESS.value
        assert quarantine.dumps == []

        drift_events = _events_of_type(control, "SCHEMA_DRIFT")
        assert len(drift_events) == 1, "SCHEMA_DRIFT debe emitirse exactamente una vez por batch"
        assert drift_events[0]["phase"] == "validate"
        extras = drift_events[0]["extras"]
        assert extras is not None
        assert set(extras["extra_columns"]) == {"columna_nueva", "otra_extra"}

    def test_columnas_extra_repetidas_solo_disparan_un_evento(self) -> None:
        # Misma columna extra en 3 filas → 1 solo evento.
        rows = [
            _ok_row("0001", extra="a"),
            _ok_row("0002", extra="b"),
            _ok_row("0003", extra="c"),
        ]
        runner = _FakeRunner(_envelope(rows))
        ex, _writer, control, _quarantine = _build_extractor(runner=runner)

        ex.run_batch(
            query_id="articulos_v1",
            source_empresa="tinito",
            dt="2025-01-15",
            run_id="run-abc",
        )
        drift_events = _events_of_type(control, "SCHEMA_DRIFT")
        assert len(drift_events) == 1
        assert drift_events[0]["extras"] is not None
        assert drift_events[0]["extras"]["extra_columns"] == ["extra"]
