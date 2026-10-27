import json
import subprocess
from pathlib import Path

import pytest

from factory_etl.factory_queries.catalog import get

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def helper_expressions() -> dict[str, str]:
    script = """
const helpers = require(process.argv[1]);
console.log(JSON.stringify({
  singleLine: helpers.singleLineStr("valor"),
  trim: helpers.trimStr("valor")
}));
"""
    result = subprocess.run(
        ["node", "-e", script, str(ROOT / "dataform" / "includes" / "helpers.js")],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_single_line_helper_replaces_line_break_runs_before_trimming(
    helper_expressions: dict[str, str],
) -> None:
    assert helper_expressions["singleLine"] == (
        "RTRIM(LTRIM(CAST(REGEXP_REPLACE(CAST(valor AS STRING), " "r'[\\r\\n]+', ' ') AS STRING)))"
    )
    assert "COALESCE" not in helper_expressions["singleLine"]


def test_existing_trim_helper_is_unchanged(helper_expressions: dict[str, str]) -> None:
    assert helper_expressions["trim"] == "RTRIM(LTRIM(CAST(valor AS STRING)))"


@pytest.mark.parametrize("column", ["nom_cli", "dir_fis", "dir_exa"])
def test_silver_cleans_only_approved_customer_text_columns(column: str) -> None:
    sql = (ROOT / "dataform" / "definitions" / "silver" / "sil_clientes.sqlx").read_text(
        encoding="utf-8"
    )
    assert f'${{helpers.singleLineStr("{column}")}} AS {column}' in sql
    assert sql.count("helpers.singleLineStr(") == 3
    assert 'FROM ${ref("stg_clientes_snapshot")}' in sql
    assert '${helpers.trimStr("rif")} AS rif' in sql


def test_customer_capture_contract_and_version_are_preserved() -> None:
    query = get("clientes_v1", source_empresa="tinito")
    schema = json.loads(query.schema_path.read_text(encoding="utf-8"))
    fields = {column["name"] for column in schema["columns"]}
    sql = query.read_sql().lower()
    assert query.version == schema["version"] == "1.0.0"
    assert {"nom_cli", "dir_fis", "dir_exa"} <= fields
    assert "dir_ent" not in fields
    assert "regexp_replace" not in sql
    for column in ("nom_cli", "dir_fis", "dir_exa"):
        assert f"cli.{column}" in sql


def test_current_customer_dimension_inherits_clean_silver_fields() -> None:
    sql = (ROOT / "dataform" / "definitions" / "gold" / "dim_cliente.sqlx").read_text(
        encoding="utf-8"
    )
    assert "c.* REPLACE (" in sql
    assert 'FROM ${ref("sil_clientes")} c' in sql
