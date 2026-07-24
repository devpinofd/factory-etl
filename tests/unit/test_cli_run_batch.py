"""Tests del comando CLI ``run-batch``.

Se usa ``typer.testing.CliRunner`` (basado en click) para invocar el
comando aisladamente. ``build_extractor`` es monkeypatched para inyectar
un ``Extractor`` con dependencias falsas: nunca se toca GCP.

Las variables de entorno ``FACTORY_ETL_*`` se establecen via ``monkeypatch``
para que ``Settings.load()`` no dependa del entorno del CI.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from typing import Any

import pytest
from typer.testing import CliRunner

from factory_etl import cli as cli_module
from factory_etl.cli import _parse_parameters, app
from factory_etl.config import Settings
from factory_etl.control_tables import BatchStatus, RunStatus
from factory_etl.extractor import BatchOutcome


@dataclass
class _FakeControlSpy:
    """Fake de ``ControlTablesProtocol`` que captura las llamadas."""

    starts: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    finishes: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    events: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    def start_run(self, *, run_id: str, extras: dict[str, Any] | None = None) -> None:
        self.starts.append({"run_id": run_id, "extras": extras})

    def finish_run(
        self,
        *,
        run_id: str,
        status: RunStatus,
        error: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> None:
        self.finishes.append({"run_id": run_id, "status": status, "error": error, "extras": extras})

    def register_batch(self, **_: Any) -> None:  # pragma: no cover
        pass

    def find_batch_by_hash(self, **_: Any) -> str | None:  # pragma: no cover
        return None

    def log_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)


class _FakeExtractor:
    """Fake que emula ``Extractor`` con una salida configurable."""

    def __init__(
        self,
        control: _FakeControlSpy,
        outcome: BatchOutcome | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.control = control
        self._outcome = outcome
        self._exc = exc
        self.run_calls: list[dict[str, Any]] = []

    def run_batch(self, **kwargs: Any) -> BatchOutcome:
        self.run_calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        assert self._outcome is not None
        return self._outcome


@pytest.fixture
def _env(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # noqa: PT005
    """Establece las variables ``FACTORY_ETL_*`` requeridas por ``Settings``."""
    monkeypatch.setenv("FACTORY_ETL_ENV", "dev")
    monkeypatch.setenv("FACTORY_ETL_GCP_PROJECT", "test-project")
    monkeypatch.setenv("FACTORY_ETL_BRONZE_BUCKET", "test-bronze")
    monkeypatch.setenv("FACTORY_ETL_CONTROL_DATASET", "test_control")


def _patch_build(monkeypatch: pytest.MonkeyPatch, extractor: _FakeExtractor) -> None:
    def _factory(_settings: Settings) -> _FakeExtractor:
        return extractor

    monkeypatch.setattr(cli_module, "build_extractor", _factory)


class TestParseParameters:
    def test_parametros_vacios_retorna_dict_vacio(self) -> None:
        assert _parse_parameters([]) == {}

    def test_multiples_parametros_forman_dict(self) -> None:
        result = _parse_parameters(["desde=2025-01-01", "hasta=2025-01-31"])
        assert result == {"desde": "2025-01-01", "hasta": "2025-01-31"}

    def test_parametro_sin_igual_es_error(self) -> None:
        # typer.BadParameter hereda de click.UsageError.
        import typer

        with pytest.raises(typer.BadParameter):
            _parse_parameters(["invalido"])

    def test_valor_con_igual_conserva_lado_derecho(self) -> None:
        # Un `=` en el valor no debe romper: partition() usa el primero.
        result = _parse_parameters(["filtro=a=b=c"])
        assert result == {"filtro": "a=b=c"}

    def test_clave_vacia_es_error(self) -> None:
        import typer

        with pytest.raises(typer.BadParameter):
            _parse_parameters(["=valor"])


class TestSideCommands:
    def test_version_imprime_version_del_paquete(self) -> None:
        result = CliRunner().invoke(app, ["version"])
        assert result.exit_code == 0
        assert cli_module.__version__ in result.stdout

    def test_list_queries_lista_catalogos_registrados(self) -> None:
        result = CliRunner().invoke(app, ["list-queries"])
        assert result.exit_code == 0
        # Al menos ``articulos_v1`` debe estar registrado en Fase 1.
        assert "articulos_v1" in result.stdout


class TestRunBatchCommand:
    def test_happy_path_exit_0_y_json_stdout(
        self,
        _env: None,  # noqa: PT019
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        control = _FakeControlSpy()
        outcome = BatchOutcome(
            batch_id="batch-xyz",
            status=BatchStatus.SUCCESS.value,
            object_uri="gs://test-bronze/bronze/x.jsonl.gz",
            record_count=3,
            was_duplicate=False,
        )
        extractor = _FakeExtractor(control=control, outcome=outcome)
        _patch_build(monkeypatch, extractor)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run-batch",
                "--query-id",
                "articulos_v1",
                "--source-empresa",
                "tinito",
                "--dt",
                "2025-01-15",
                "--run-id",
                "run-fixed",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout.strip())
        assert payload["status"] == BatchStatus.SUCCESS.value
        assert payload["batch_id"] == "batch-xyz"
        assert payload["record_count"] == 3

        assert control.starts == [
            {
                "run_id": "run-fixed",
                "extras": {
                    "query_id": "articulos_v1",
                    "source_empresa": "tinito",
                    "dt": "2025-01-15",
                    "cli_version": cli_module.__version__,
                },
            }
        ]
        assert len(control.finishes) == 1
        finish = control.finishes[0]
        assert finish["status"] == RunStatus.SUCCESS
        assert finish["error"] is None
        assert finish["extras"] == {
            "batch_id": "batch-xyz",
            "final_status": BatchStatus.SUCCESS.value,
        }

    def test_run_id_se_genera_si_no_se_pasa(
        self,
        _env: None,  # noqa: PT019
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        control = _FakeControlSpy()
        outcome = BatchOutcome(
            batch_id="b",
            status=BatchStatus.SUCCESS.value,
            object_uri=None,
            record_count=0,
            was_duplicate=False,
        )
        extractor = _FakeExtractor(control=control, outcome=outcome)
        _patch_build(monkeypatch, extractor)

        result = CliRunner().invoke(
            app,
            [
                "run-batch",
                "--query-id",
                "articulos_v1",
                "--source-empresa",
                "tinito",
                "--dt",
                "2025-01-15",
            ],
        )
        assert result.exit_code == 0, result.output
        assert len(control.starts) == 1
        # run_id generado: no vacio y coincide con el pasado a run_batch.
        generated = control.starts[0]["run_id"]
        assert generated
        assert extractor.run_calls[0]["run_id"] == generated

    def test_parametros_repetidos_llegan_como_dict(
        self,
        _env: None,  # noqa: PT019
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        control = _FakeControlSpy()
        outcome = BatchOutcome(
            batch_id="b",
            status=BatchStatus.SUCCESS.value,
            object_uri=None,
            record_count=0,
            was_duplicate=False,
        )
        extractor = _FakeExtractor(control=control, outcome=outcome)
        _patch_build(monkeypatch, extractor)

        result = CliRunner().invoke(
            app,
            [
                "run-batch",
                "--query-id",
                "articulos_v1",
                "--source-empresa",
                "tinito",
                "--dt",
                "2025-01-15",
                "--parameter",
                "desde=2025-01-01",
                "--parameter",
                "hasta=2025-01-31",
            ],
        )
        assert result.exit_code == 0, result.output
        assert extractor.run_calls[0]["parameter_values"] == {
            "desde": "2025-01-01",
            "hasta": "2025-01-31",
        }

    def test_excepcion_inesperada_exit_1_y_no_filtra_mensaje(
        self,
        _env: None,  # noqa: PT019
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sensitive_msg = "PASSWORD_LEAK=supersecret123"
        control = _FakeControlSpy()
        extractor = _FakeExtractor(control=control, exc=RuntimeError(sensitive_msg))
        _patch_build(monkeypatch, extractor)

        result = CliRunner().invoke(
            app,
            [
                "run-batch",
                "--query-id",
                "articulos_v1",
                "--source-empresa",
                "tinito",
                "--dt",
                "2025-01-15",
                "--run-id",
                "run-err",
            ],
        )

        assert result.exit_code == 1
        # El mensaje sensible NO debe aparecer en stdout.
        assert sensitive_msg not in result.stdout

        # finish_run debe registrarse con FAILED y solo el nombre del tipo.
        assert len(control.finishes) == 1
        finish = control.finishes[0]
        assert finish["status"] == RunStatus.FAILED
        assert finish["error"] == "RuntimeError"
        assert finish["extras"] is not None
        assert "error_id" in finish["extras"]
        assert sensitive_msg not in json.dumps(finish["extras"])

    def test_status_quarantined_es_exit_0(
        self,
        _env: None,  # noqa: PT019
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        control = _FakeControlSpy()
        outcome = BatchOutcome(
            batch_id="b",
            status=BatchStatus.QUARANTINED.value,
            object_uri="gs://test-bronze/quarantine/x.json",
            record_count=None,
            was_duplicate=False,
        )
        extractor = _FakeExtractor(control=control, outcome=outcome)
        _patch_build(monkeypatch, extractor)

        result = CliRunner().invoke(
            app,
            [
                "run-batch",
                "--query-id",
                "articulos_v1",
                "--source-empresa",
                "tinito",
                "--dt",
                "2025-01-15",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_status_skipped_duplicate_es_exit_0(
        self,
        _env: None,  # noqa: PT019
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        control = _FakeControlSpy()
        outcome = BatchOutcome(
            batch_id="b",
            status=BatchStatus.SKIPPED_DUPLICATE.value,
            object_uri=None,
            record_count=None,
            was_duplicate=True,
        )
        extractor = _FakeExtractor(control=control, outcome=outcome)
        _patch_build(monkeypatch, extractor)

        result = CliRunner().invoke(
            app,
            [
                "run-batch",
                "--query-id",
                "articulos_v1",
                "--source-empresa",
                "tinito",
                "--dt",
                "2025-01-15",
            ],
        )
        assert result.exit_code == 0, result.output
