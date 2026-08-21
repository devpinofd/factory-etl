from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

VALIDATION_PATH = (
    Path(__file__).parents[2] / "agents" / "dax_copilot" / "proxy" / "request_validation.py"
)
SPEC = importlib.util.spec_from_file_location("dax_request_validation", VALIDATION_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_accepts_valid_conversation() -> None:
    messages = MODULE.validate_request_body(
        {"messages": [{"role": "user", "content": "Ventas del mes"}]},
        body_size=100,
    )

    assert messages[0]["role"] == "user"


@pytest.mark.parametrize(
    ("body", "body_size", "message"),
    [
        ({}, 100, "messages"),
        ({"messages": [{"role": "developer", "content": "x"}]}, 100, "role"),
        ({"messages": [{"role": "user", "content": "x" * 12_001}]}, 100, "contenido"),
        ({"messages": [{"role": "user", "content": "x"}] * 21}, 100, "20"),
        ({"messages": [{"role": "user", "content": "x"}]}, 256 * 1024 + 1, "256"),
    ],
)
def test_rejects_invalid_conversation(body: object, body_size: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        MODULE.validate_request_body(body, body_size)
