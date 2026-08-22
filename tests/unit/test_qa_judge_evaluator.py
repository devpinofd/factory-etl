import json
from unittest.mock import patch

import pytest

from agents.dax_copilot.qa_judge.run_regression_suite import (
    analyze_dax,
    evaluate_result,
    generate_dax_from_agent,
    load_tests,
    select_test_batch,
    validate_query_contract,
)
from agents.dax_copilot.qa_judge.qa_contracts import validate_proposal_schema


class _AgentResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(
            {
                "tool_calls": [
                    {
                        "function": {
                            "name": "execute_dax_query",
                            "arguments": json.dumps(
                                {"dax_query": 'EVALUATE ROW("value", 1)'}
                            ),
                        }
                    }
                ]
            }
        ).encode()


def test_generate_dax_from_agent_sends_bearer_token(monkeypatch):
    monkeypatch.setenv("DAX_COPILOT_PROXY_URL", "https://proxy.example/api/chat-stream")
    monkeypatch.setenv("DAX_COPILOT_AGENT_TOKEN", "test-token")

    with patch(
        "agents.dax_copilot.qa_judge.run_regression_suite.urllib.request.urlopen",
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


def test_exact_numeric_honors_absolute_tolerance():
    ok, reason = evaluate_result(
        [{"value": 100.4}],
        {"columna": "value", "valor": 100, "tolerancia": 0.5},
        "ExactNumeric",
    )

    assert ok
    assert "Esperado" in reason


def test_missing_column_fails_instead_of_defaulting():
    ok, reason = evaluate_result(
        [{"other": 1}],
        {"columna": "value"},
        "NonNegativeNumeric",
    )

    assert not ok
    assert "Columna ausente" in reason


def test_dax_alias_with_brackets_matches_expected_column():
    ok, reason = evaluate_result(
        [{"[Ventas_Netas]": 100.0}],
        {"columna": "Ventas_Netas", "minimo": 0},
        "NonZeroNumeric",
    )

    assert ok
    assert reason == "Valor 100.0 es mayor a 0.0"


def test_single_numeric_alias_fallback_requires_explicit_opt_in():
    data = [{"[Total_Ventas_Netas]": 100.0}]

    ok, reason = evaluate_result(
        data,
        {"columna": "Ventas_Netas"},
        "NonZeroNumeric",
    )
    assert not ok
    assert "Columna ausente" in reason

    ok, _ = evaluate_result(
        data,
        {
            "columna": "Ventas_Netas",
            "allow_single_numeric_fallback": True,
        },
        "NonZeroNumeric",
    )
    assert ok


def test_row_count_exact_enforces_upper_bound():
    ok, reason = evaluate_result(
        [{"id": 1}, {"id": 2}],
        {"min_filas": 1, "max_filas": 1},
        "RowCountExact",
    )

    assert not ok
    assert "obtenidas 2" in reason


def test_unknown_criterion_fails():
    ok, reason = evaluate_result([{"value": 1}], {}, "Unknown")

    assert not ok
    assert "no soportado" in reason


def test_query_contract_requires_measure_and_rejects_forbidden_fragment():
    ok, reason = validate_query_contract(
        'EVALUATE ROW("x", [RequiredMeasure])',
        {
            "required_measures": ["RequiredMeasure"],
            "required_fragments": ["EVALUATE"],
            "forbidden_fragments": ["REMOVEFILTERS"],
        },
    )
    assert ok
    assert reason == ""

    ok, reason = validate_query_contract(
        "EVALUATE REMOVEFILTERS(Table)",
        {"forbidden_fragments": ["REMOVEFILTERS"]},
    )
    assert not ok
    assert "prohibido" in reason


def test_query_contract_normalizes_dates_whitespace_and_topn():
    query = """
    EVALUATE
    TOPN (
        5,
        SUMMARIZECOLUMNS (
            dim_tiempo[fec_ini],
            "Ventas", [Total_Ventas_Netas]
        )
    )
    """
    contract = {
        "required_measures": ["Total_Ventas_Netas"],
        "required_fragments": ["dim_tiempo[fec_ini]"],
        "top_n": 5,
    }

    assert validate_query_contract(query, contract) == (True, "")
    assert analyze_dax(query)["top_n"] == [5]

    ok, reason = validate_query_contract(
        "EVALUATE ROW(\"x\", CALCULATE([M], TREATAS({DATE (2026, 7, 1)}, T[d])))",
        {"required_dates": ["2026-07-01"]},
    )
    assert ok
    assert reason == ""


def test_query_contract_requires_exact_scope_filters():
    contract = {
        "required_scope": {
            "source_empresa": "ctb",
            "cod_pro": "0301",
        }
    }
    valid_query = """
    EVALUATE CALCULATETABLE(
        ROW("x", 1),
        TREATAS({"ctb"}, ventas[source_empresa]),
        TREATAS({"0301"}, ventas[cod_pro])
    )
    """

    assert validate_query_contract(valid_query, contract) == (True, "")

    ok, reason = validate_query_contract(
        valid_query.replace('"0301"', '"9999"'),
        contract,
    )
    assert not ok
    assert "cod_pro=0301" in reason


def test_load_tests_accepts_utf8_bom_and_rejects_duplicate_ids(tmp_path):
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


def test_select_test_batch_is_deterministic_and_rejects_empty_batch():
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


def test_qa_judge_proposal_requires_reproducible_regression_case():
    proposal = {
        "titulo_pr": "Regla",
        "diagnostico": "Diagnóstico",
        "regla_propuesta": "Regla DAX",
        "categoria": "GUARDRAIL",
        "test_caso_regresion": {
            "pregunta": "Pregunta",
            "dax_correcto": "EVALUATE ROW(\"x\", 1)",
            "criterio": "ExpectedRejection",
        },
    }

    assert validate_proposal_schema(proposal) == proposal

    with pytest.raises(ValueError, match="falta"):
        validate_proposal_schema({**proposal, "test_caso_regresion": {}})
