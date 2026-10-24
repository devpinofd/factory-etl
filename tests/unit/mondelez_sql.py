import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "dataform"
QUERY = re.compile(r"\$\{mondelez_queries\.(\w+)\((ref(?:,\s*\"[^\"]+\")?)?\)\}")


@lru_cache
def _render_query(function: str, arguments: str) -> str:
    args = [value.strip() for value in arguments.split(",") if value.strip()]
    payload = {
        "function": function,
        "ref": bool(args and args[0] == "ref"),
        "arguments": [json.loads(value) for value in args[1:]],
    }
    script = """
const queries = require(process.argv[1]);
const call = JSON.parse(process.argv[2]);
const ref = name => '${ref(' + JSON.stringify(name) + ')}';
const args = call.ref ? [ref, ...call.arguments] : call.arguments;
process.stdout.write(queries[call.function](...args));
"""
    result = subprocess.run(
        ["node", "-e", script, str(ROOT / "includes" / "mondelez_queries.js"), json.dumps(payload)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def read_mondelez_sql(name: str) -> str:
    sql = (ROOT / "definitions" / "mondelez" / f"{name}.sqlx").read_text(encoding="utf-8")
    rendered = QUERY.sub(lambda match: _render_query(match[1], match[2] or ""), sql)
    if "${mondelez_queries." in rendered:
        raise ValueError(f"Unsupported shared SQL expression in {name}")
    return rendered
