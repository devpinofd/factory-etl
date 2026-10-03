"""Tests del comando CLI ``run-task`` y de la funcion ``_select_task``."""

from __future__ import annotations

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from factory_etl import cli as cli_module
from factory_etl.cli import TaskSpec, _select_task, app


class TestSelectTask:
    def test_seleccion_correcta_sin_parametros(self) -> None:
        manifest = json.dumps(
            [
                {"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False},
                {"query_id": "ventas_diarias_v3", "source_empresa": "ctb", "has_param": True},
            ]
        )
        spec = _select_task(manifest, task_index=0)
        assert spec == TaskSpec(
            query_id="articulos_v1",
            source_empresa="tinito",
            has_param=False,
            parameter_values={},
        )

    def test_seleccion_correcta_con_parametros(self) -> None:
        manifest = json.dumps(
            [
                {"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False},
                {"query_id": "ventas_diarias_v3", "source_empresa": "ctb", "has_param": True},
            ]
        )
        spec = _select_task(
            manifest,
            task_index=1,
            fec_des="2025-01-01",
            fec_has="2025-01-15",
        )
        assert spec == TaskSpec(
            query_id="ventas_diarias_v3",
            source_empresa="ctb",
            has_param=True,
            parameter_values={"fec_des": "2025-01-01", "fec_has": "2025-01-15"},
        )

    def test_sin_parametros_ignora_fechas_si_has_param_false(self) -> None:
        manifest = json.dumps(
            [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False}]
        )
        spec = _select_task(
            manifest,
            task_index=0,
            fec_des="2025-01-01",
            fec_has="2025-01-15",
        )
        assert spec.parameter_values == {}

    def test_indice_fuera_de_rango_menor_que_cero(self) -> None:
        manifest = json.dumps(
            [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False}]
        )
        with pytest.raises(typer.BadParameter, match="fuera de rango"):
            _select_task(manifest, task_index=-1)

    def test_indice_fuera_de_rango_mayor_o_igual_a_longitud(self) -> None:
        manifest = json.dumps(
            [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False}]
        )
        with pytest.raises(typer.BadParameter, match="fuera de rango"):
            _select_task(manifest, task_index=1)

    def test_json_invalido_es_error(self) -> None:
        with pytest.raises(typer.BadParameter, match="JSON valido"):
            _select_task("{invalido: true", task_index=0)

    def test_manifest_no_es_lista_es_error(self) -> None:
        with pytest.raises(typer.BadParameter, match="lista de tareas"):
            _select_task('{"query_id": "x"}', task_index=0)

    def test_lista_vacia_es_error(self) -> None:
        with pytest.raises(typer.BadParameter, match="no puede estar vacio"):
            _select_task("[]", task_index=0)

    def test_mismatch_con_task_count(self) -> None:
        manifest = json.dumps(
            [
                {"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False},
                {"query_id": "ventas_diarias_v3", "source_empresa": "ctb", "has_param": True},
            ]
        )
        with pytest.raises(typer.BadParameter, match="CLOUD_RUN_TASK_COUNT"):
            _select_task(manifest, task_index=0, task_count=5)

    def test_task_count_coincidente_es_valido(self) -> None:
        manifest = json.dumps(
            [
                {"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False},
                {"query_id": "ventas_diarias_v3", "source_empresa": "ctb", "has_param": True},
            ]
        )
        spec = _select_task(
            manifest,
            task_index=0,
            task_count=2,
        )
        assert spec.query_id == "articulos_v1"

    @pytest.mark.parametrize(
        ("fec_des", "fec_has"),
        [
            (None, "2025-01-15"),
            ("2025-01-01", None),
            (None, None),
            ("", "2025-01-15"),
            ("2025-01-01", ""),
        ],
    )
    def test_has_param_sin_fec_des_fec_has_es_error(
        self,
        fec_des: str | None,
        fec_has: str | None,
    ) -> None:
        manifest = json.dumps(
            [{"query_id": "ventas_diarias_v3", "source_empresa": "ctb", "has_param": True}]
        )
        with pytest.raises(typer.BadParameter, match="requiere parametros"):
            _select_task(manifest, task_index=0, fec_des=fec_des, fec_has=fec_has)

    def test_elemento_no_es_dict(self) -> None:
        with pytest.raises(typer.BadParameter, match="objeto JSON"):
            _select_task(json.dumps(["string_item"]), task_index=0)

    def test_campos_incompletos_o_invalidos(self) -> None:
        with pytest.raises(typer.BadParameter, match="query_id"):
            _select_task(
                json.dumps([{"query_id": "", "source_empresa": "tinito", "has_param": False}]),
                task_index=0,
            )

        with pytest.raises(typer.BadParameter, match="source_empresa"):
            _select_task(
                json.dumps(
                    [{"query_id": "articulos_v1", "source_empresa": "", "has_param": False}]
                ),
                task_index=0,
            )

        with pytest.raises(typer.BadParameter, match="has_param"):
            _select_task(
                json.dumps(
                    [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": "no"}]
                ),
                task_index=0,
            )


class TestRunTaskCommand:
    def test_run_task_invoca_ejecucion_con_argumentos_correctos(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest = json.dumps(
            [
                {"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False},
                {"query_id": "ventas_diarias_v3", "source_empresa": "ctb", "has_param": True},
            ]
        )
        captured_calls: list[dict[str, Any]] = []

        def _mock_execute_batch(**kwargs: Any) -> int:
            captured_calls.append(kwargs)
            return 0

        monkeypatch.setattr(cli_module, "_execute_batch", _mock_execute_batch)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run-task",
                "--manifest",
                manifest,
                "--dt",
                "2025-01-15",
                "--fec-des",
                "2025-01-01",
                "--fec-has",
                "2025-01-15",
                "--task-index",
                "1",
            ],
        )

        assert result.exit_code == 0, result.output
        assert len(captured_calls) == 1
        call = captured_calls[0]
        assert call["query_id"] == "ventas_diarias_v3"
        assert call["source_empresa"] == "ctb"
        assert call["dt"] == "2025-01-15"
        assert call["run_id"] is None
        assert call["parameter_values"] == {
            "fec_des": "2025-01-01",
            "fec_has": "2025-01-15",
        }

    def test_run_task_lee_cloud_run_task_index_de_entorno(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest = json.dumps(
            [
                {"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False},
                {"query_id": "ventas_diarias_v3", "source_empresa": "ctb", "has_param": True},
            ]
        )
        monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "1")
        monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "2")

        captured_calls: list[dict[str, Any]] = []

        def _mock_execute_batch(**kwargs: Any) -> int:
            captured_calls.append(kwargs)
            return 0

        monkeypatch.setattr(cli_module, "_execute_batch", _mock_execute_batch)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run-task",
                "--manifest",
                manifest,
                "--dt",
                "2025-01-15",
                "--fec-des",
                "2025-01-01",
                "--fec-has",
                "2025-01-15",
            ],
        )

        assert result.exit_code == 0, result.output
        assert len(captured_calls) == 1
        assert captured_calls[0]["query_id"] == "ventas_diarias_v3"

    def test_run_task_default_indice_cero_sin_entorno(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest = json.dumps(
            [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False}]
        )
        monkeypatch.delenv("CLOUD_RUN_TASK_INDEX", raising=False)
        monkeypatch.delenv("CLOUD_RUN_TASK_COUNT", raising=False)

        captured_calls: list[dict[str, Any]] = []

        def _mock_execute_batch(**kwargs: Any) -> int:
            captured_calls.append(kwargs)
            return 0

        monkeypatch.setattr(cli_module, "_execute_batch", _mock_execute_batch)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run-task",
                "--manifest",
                manifest,
                "--dt",
                "2025-01-15",
            ],
        )

        assert result.exit_code == 0, result.output
        assert len(captured_calls) == 1
        assert captured_calls[0]["query_id"] == "articulos_v1"

    def test_run_task_exit_2_con_mismatch_task_count(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest = json.dumps(
            [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False}]
        )
        monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "99")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run-task",
                "--manifest",
                manifest,
                "--dt",
                "2025-01-15",
            ],
        )

        assert result.exit_code == 2

    def test_run_task_error_si_cloud_run_task_index_no_es_entero(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest = json.dumps(
            [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False}]
        )
        monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "not-a-number")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run-task",
                "--manifest",
                manifest,
                "--dt",
                "2025-01-15",
            ],
        )

        assert result.exit_code == 2

    def test_run_task_error_si_cloud_run_task_count_no_es_entero(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest = json.dumps(
            [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False}]
        )
        monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "not-a-number")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run-task",
                "--manifest",
                manifest,
                "--dt",
                "2025-01-15",
            ],
        )

        assert result.exit_code == 2

    def test_run_task_propaga_fallo_de_execute_batch(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest = json.dumps(
            [{"query_id": "articulos_v1", "source_empresa": "tinito", "has_param": False}]
        )

        def _mock_execute_batch(**_: Any) -> int:
            return 1

        monkeypatch.setattr(cli_module, "_execute_batch", _mock_execute_batch)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run-task",
                "--manifest",
                manifest,
                "--dt",
                "2025-01-15",
            ],
        )

        assert result.exit_code == 1
