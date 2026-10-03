"""Tests del comando CLI ``run-task`` y de la funcion ``_select_tasks``."""

from __future__ import annotations

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from factory_etl import cli as cli_module
from factory_etl.cli import TaskSpec, _select_tasks, app


def _entry(query_id: str, empresa: str, has_param: bool = False) -> dict[str, Any]:
    return {"query_id": query_id, "source_empresa": empresa, "has_param": has_param}


def _manifest(n: int) -> str:
    """Manifest de ``n`` entradas sin parametros: q0..q{n-1} para la empresa ``e``."""
    return json.dumps([_entry(f"q{i}", "e") for i in range(n)])


class TestSelectTasks:
    def test_una_tarea_procesa_todo_el_manifest(self) -> None:
        specs = _select_tasks(_manifest(3))
        assert [s.query_id for s in specs] == ["q0", "q1", "q2"]

    def test_reparto_strided(self) -> None:
        manifest = _manifest(7)
        assert [s.query_id for s in _select_tasks(manifest, 0, 3)] == ["q0", "q3", "q6"]
        assert [s.query_id for s in _select_tasks(manifest, 1, 3)] == ["q1", "q4"]
        assert [s.query_id for s in _select_tasks(manifest, 2, 3)] == ["q2", "q5"]

    def test_reparto_cubre_todo_sin_duplicados(self) -> None:
        n, t = 95, 20
        manifest = _manifest(n)
        seen = [s.query_id for i in range(t) for s in _select_tasks(manifest, i, t)]
        assert sorted(seen) == sorted(f"q{i}" for i in range(n))
        assert len(seen) == n

    def test_lote_maximo_por_tarea_95_entre_20(self) -> None:
        manifest = _manifest(95)
        sizes = [len(_select_tasks(manifest, i, 20)) for i in range(20)]
        assert max(sizes) == 5
        assert min(sizes) == 4

    def test_mas_tareas_que_entradas_devuelve_lote_vacio(self) -> None:
        assert _select_tasks(_manifest(2), task_index=3, task_count=5) == []

    def test_parametros_solo_si_has_param(self) -> None:
        manifest = json.dumps([_entry("articulos_v1", "tinito"), _entry("ventas", "ctb", True)])
        specs = _select_tasks(manifest, fec_des="2025-01-01", fec_has="2025-01-15")
        assert specs == [
            TaskSpec("articulos_v1", "tinito", False, {}),
            TaskSpec("ventas", "ctb", True, {"fec_des": "2025-01-01", "fec_has": "2025-01-15"}),
        ]

    @pytest.mark.parametrize(("index", "count"), [(-1, 3), (3, 3), (0, 0)])
    def test_indice_o_count_invalidos(self, index: int, count: int) -> None:
        with pytest.raises(typer.BadParameter):
            _select_tasks(_manifest(5), task_index=index, task_count=count)

    def test_json_invalido_es_error(self) -> None:
        with pytest.raises(typer.BadParameter, match="JSON valido"):
            _select_tasks("{invalido: true")

    def test_manifest_no_es_lista_es_error(self) -> None:
        with pytest.raises(typer.BadParameter, match="lista de entradas"):
            _select_tasks('{"query_id": "x"}')

    def test_lista_vacia_es_error(self) -> None:
        with pytest.raises(typer.BadParameter, match="no puede estar vacio"):
            _select_tasks("[]")

    def test_valida_todo_el_manifest_no_solo_el_lote(self) -> None:
        # La entrada invalida (posicion 1) no pertenece al lote de la tarea 0,
        # pero igual debe fallar para que el error no sea parcial.
        manifest = json.dumps([_entry("q0", "e"), {"query_id": "", "source_empresa": "e"}])
        with pytest.raises(typer.BadParameter, match="query_id"):
            _select_tasks(manifest, task_index=0, task_count=2)

    @pytest.mark.parametrize(
        ("fec_des", "fec_has"),
        [(None, "2025-01-15"), ("2025-01-01", None), (None, None), ("", "2025-01-15")],
    )
    def test_has_param_sin_fechas_es_error(self, fec_des: str | None, fec_has: str | None) -> None:
        manifest = json.dumps([_entry("ventas", "ctb", True)])
        with pytest.raises(typer.BadParameter, match="requiere parametros"):
            _select_tasks(manifest, fec_des=fec_des, fec_has=fec_has)

    def test_entradas_mal_formadas(self) -> None:
        with pytest.raises(typer.BadParameter, match="objeto JSON"):
            _select_tasks(json.dumps(["string_item"]))
        with pytest.raises(typer.BadParameter, match="source_empresa"):
            _select_tasks(json.dumps([_entry("q", "")]))
        with pytest.raises(typer.BadParameter, match="has_param"):
            _select_tasks(json.dumps([{"query_id": "q", "source_empresa": "e", "has_param": "no"}]))


class TestRunTaskCommand:
    @pytest.fixture
    def calls(self, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
        captured: list[dict[str, Any]] = []

        def _mock(**kwargs: Any) -> int:
            captured.append(kwargs)
            return 0

        monkeypatch.setattr(cli_module, "_execute_batch", _mock)
        monkeypatch.delenv("CLOUD_RUN_TASK_INDEX", raising=False)
        monkeypatch.delenv("CLOUD_RUN_TASK_COUNT", raising=False)
        return captured

    def _invoke(self, *extra: str, manifest: str | None = None) -> Any:
        return CliRunner().invoke(
            app,
            ["run-task", "--manifest", manifest or _manifest(5), "--dt", "2025-01-15", *extra],
        )

    def test_procesa_lote_desde_entorno(
        self, calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "1")
        monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "2")
        result = self._invoke()
        assert result.exit_code == 0, result.output
        assert [c["query_id"] for c in calls] == ["q1", "q3"]
        assert all(c["dt"] == "2025-01-15" and c["run_id"] is None for c in calls)

    def test_opciones_tienen_prioridad_sobre_entorno(
        self, calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "1")
        monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "2")
        result = self._invoke("--task-index", "2", "--task-count", "3")
        assert result.exit_code == 0, result.output
        assert [c["query_id"] for c in calls] == ["q2"]

    def test_sin_entorno_procesa_todo(self, calls: list[dict[str, Any]]) -> None:
        result = self._invoke()
        assert result.exit_code == 0, result.output
        assert len(calls) == 5

    def test_pasa_parametros_de_fecha(self, calls: list[dict[str, Any]]) -> None:
        manifest = json.dumps([_entry("ventas", "ctb", True)])
        result = self._invoke(
            "--fec-des", "2025-01-01", "--fec-has", "2025-01-15", manifest=manifest
        )
        assert result.exit_code == 0, result.output
        assert calls[0]["parameter_values"] == {"fec_des": "2025-01-01", "fec_has": "2025-01-15"}

    def test_fallo_de_una_entrada_no_detiene_las_demas(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLOUD_RUN_TASK_INDEX", raising=False)
        monkeypatch.delenv("CLOUD_RUN_TASK_COUNT", raising=False)
        seen: list[str] = []

        def _mock(**kwargs: Any) -> int:
            seen.append(kwargs["query_id"])
            if kwargs["query_id"] == "q1":
                return 1
            if kwargs["query_id"] == "q2":
                raise RuntimeError("boom")
            return 0

        monkeypatch.setattr(cli_module, "_execute_batch", _mock)
        result = self._invoke()
        assert result.exit_code == 1
        assert seen == ["q0", "q1", "q2", "q3", "q4"]

    @pytest.mark.parametrize(
        ("var", "value"),
        [("CLOUD_RUN_TASK_INDEX", "x"), ("CLOUD_RUN_TASK_COUNT", "x")],
    )
    def test_entorno_no_entero_es_exit_2(
        self, calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch, var: str, value: str
    ) -> None:
        monkeypatch.setenv(var, value)
        result = self._invoke()
        assert result.exit_code == 2
        assert calls == []

    def test_manifest_invalido_es_exit_2(self, calls: list[dict[str, Any]]) -> None:
        result = self._invoke(manifest="[]")
        assert result.exit_code == 2
        assert calls == []
