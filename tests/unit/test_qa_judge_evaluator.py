from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

QA_JUDGE_DIR = Path(__file__).resolve().parents[2] / "agents" / "dax_copilot" / "qa_judge"

_qa_contracts_spec = importlib.util.spec_from_file_location(
    "qa_contracts", QA_JUDGE_DIR / "qa_contracts.py"
)
assert _qa_contracts_spec and _qa_contracts_spec.loader
_qa_contracts_mod = importlib.util.module_from_spec(_qa_contracts_spec)
_qa_contracts_spec.loader.exec_module(_qa_contracts_mod)
validate_proposal_schema: Any = _qa_contracts_mod.validate_proposal_schema

_run_regression_spec = importlib.util.spec_from_file_location(
    "run_regression_suite", QA_JUDGE_DIR / "run_regression_suite.py"
)
assert _run_regression_spec and _run_regression_spec.loader
_run_regression_mod = importlib.util.module_from_spec(_run_regression_spec)
_run_regression_spec.loader.exec_module(_run_regression_mod)

analyze_dax: Any = _run_regression_mod.analyze_dax
evaluate_result: Any = _run_regression_mod.evaluate_result
generate_dax_from_agent: Any = _run_regression_mod.generate_dax_from_agent
load_tests: Any = _run_regression_mod.load_tests
select_test_batch: Any = _run_regression_mod.select_test_batch
validate_query_contract: Any = _run_regression_mod.validate_query_contract


class _AgentResponse:
    def __enter__(self) -> _AgentResponse:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(
            {
                "tool_calls": [
                    {
                        "function": {
                            "name": "execute_dax_query",
                            "arguments": json.dumps({"dax_query": 'EVALUATE ROW("value", 1)'}),
                        }
                    }
                ]
            }
        ).encode()


def test_generate_dax_from_agent_sends_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAX_COPILOT_PROXY_URL", "https://proxy.example/api/chat-stream")
    monkeypatch.setenv("DAX_COPILOT_AGENT_TOKEN", "test-token")

    with patch(
        "urllib.request.urlopen",
        return_value=_AgentResponse(),
    ) as urlopen:
        dax = generate_dax_from_agent("Pregunta")

    request = urlopen.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer test-token"
    messages = json.loads(request.data)["messages"]
    assert messages[0]["role"] == "system"
    assert "execute_dax_query" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "Pregunta"}
    assert dax == 'EVALUATE ROW("value", 1)'


def test_exact_numeric_honors_absolute_tolerance() -> None:
    ok, _ = evaluate_result(
        [{"value": 100.4}],
        {"columna": "value", "valor": 100, "tolerancia": 0.5},
        "ExactNumeric",
    )
    assert ok

    not_ok, reason = evaluate_result(
        [{"value": 100.6}],
        {"columna": "value", "valor": 100, "tolerancia": 0.5},
        "ExactNumeric",
    )
    assert not not_ok
    assert "obtenido 100.6" in reason


def test_exact_numeric_honors_relative_tolerance() -> None:
    ok, _ = evaluate_result(
        [{"value": 102}],
        {"columna": "value", "valor": 100, "tolerancia_relativa": 0.05},
        "ExactNumeric",
    )
    assert ok

    not_ok, reason = evaluate_result(
        [{"value": 106}],
        {"columna": "value", "valor": 100, "tolerancia_relativa": 0.05},
        "ExactNumeric",
    )
    assert not not_ok
    assert "obtenido 106" in reason


def test_percentage_range_and_row_counts() -> None:
    ok, _ = evaluate_result(
        [{"pct": 0.75}],
        {"columna": "pct", "rango": [0.0, 1.0]},
        "PercentageRange",
    )
    assert ok

    ok_rows, _ = evaluate_result(
        [{"id": 1}, {"id": 2}, {"id": 3}],
        {"min_filas": 2},
        "RowCountMinimum",
    )
    assert ok_rows


def test_dax_ast_static_analysis_extracts_metadata() -> None:
    analysis = analyze_dax(
        """
        EVALUATE
        TOPN(
            10,
            CALCULATETABLE(
                SUMMARIZECOLUMNS('vw_ventas_bi_consumo'[cod_art]),
                'vw_ventas_bi_consumo'[fecha] = DATE(2026, 8, 20)
            )
        )
        """
    )
    assert analysis["dates"] == ["2026-08-20"]
    assert analysis["top_n"] == [10]
    assert "CALCULATETABLE" in analysis["functions"]
    assert "TOPN" in analysis["functions"]


def test_validate_query_contract_checks_dimensions_and_temporal_filters() -> None:
    contract = {
        "required_measures": ["Ventas_USD"],
        "required_dates": ["2026-08-20"],
        "required_scope": {"cod_pro": "0301"},
        "forbidden_fragments": ["SELECTCOLUMNS"],
    }
    valid_query = """
    EVALUATE
    CALCULATETABLE(
        ADDCOLUMNS(
            SUMMARIZE('vw_ventas_bi_consumo', 'vw_ventas_bi_consumo'[cod_art]),
            "Ventas", [Ventas_USD]
        ),
        'vw_ventas_bi_consumo'[cod_pro] = "0301",
        'vw_ventas_bi_consumo'[fecha_registro] = DATE(2026, 8, 20)
    )
    """

    assert validate_query_contract(valid_query, contract) == (True, "")

    ok, reason = validate_query_contract(
        valid_query.replace('"0301"', '"9999"'),
        contract,
    )
    assert not ok
    assert "cod_pro=0301" in reason


def test_load_tests_accepts_utf8_bom_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    dataset = [{"id": "TC-1", "criterio": "NonNegativeNumeric"}]
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset), encoding="utf-8-sig")

    assert load_tests(path)[0]["id"] == "TC-1"

    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(
        json.dumps(dataset + dataset),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicados"):
        load_tests(duplicate_path)


def test_select_test_batch_is_deterministic_and_rejects_empty_batch() -> None:
    tests = [{"id": f"TC-{index}"} for index in range(1, 13)]

    assert [case["id"] for case in select_test_batch(tests, 4, 2)] == [
        "TC-5",
        "TC-6",
        "TC-7",
        "TC-8",
    ]
    assert select_test_batch(tests) == tests
    with pytest.raises(ValueError, match="no contiene casos"):
        select_test_batch(tests, 4, 4)


def test_qa_judge_proposal_requires_reproducible_regression_case() -> None:
    proposal = {
        "titulo_pr": "Regla",
        "diagnostico": "Diagnóstico",
        "regla_propuesta": "Regla DAX",
        "categoria": "GUARDRAIL",
        "test_caso_regresion": {
            "pregunta": "Pregunta",
            "dax_correcto": 'EVALUATE ROW("x", 1)',
            "criterio": "ExpectedRejection",
        },
    }

    assert validate_proposal_schema(proposal) == proposal

    with pytest.raises(ValueError, match="falta"):
        validate_proposal_schema({**proposal, "test_caso_regresion": {}})
