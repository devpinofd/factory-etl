from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

import pytest

AUTH_PATH = Path(__file__).parents[2] / "agents" / "dax_copilot" / "proxy" / "entra_auth.py"
SPEC = importlib.util.spec_from_file_location("dax_entra_auth", AUTH_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _principal(tenant: str = "tenant-1", scope: str = "dax.execute") -> str:
    payload = {
        "auth_typ": "aad",
        "claims": [
            {
                "typ": "http://schemas.microsoft.com/identity/claims/tenantid",
                "val": tenant,
            },
            {
                "typ": "http://schemas.microsoft.com/identity/claims/scope",
                "val": scope,
            },
        ],
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


def test_auth_is_disabled_for_local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REQUIRE_ENTRA_AUTH", raising=False)

    result = MODULE.validate_easy_auth_headers({})

    assert result == {"subject": "anonymous"}


def test_accepts_authorized_easy_auth_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_ENTRA_AUTH", "true")
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-1")
    monkeypatch.setenv("AZURE_REQUIRED_SCOPE", "dax.execute")

    result = MODULE.validate_easy_auth_headers(
        {
            "x-ms-client-principal": _principal(),
            "x-ms-client-principal-id": "user-1",
        }
    )

    assert result == {"subject": "user-1"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-ms-client-principal": "not-base64"},
        {"x-ms-client-principal": _principal(tenant="other")},
    ],
)
def test_rejects_unauthorized_principal(
    monkeypatch: pytest.MonkeyPatch, headers: dict[str, str]
) -> None:
    monkeypatch.setenv("REQUIRE_ENTRA_AUTH", "true")
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-1")
    monkeypatch.setenv("AZURE_REQUIRED_SCOPE", "dax.execute")

    with pytest.raises(MODULE.AuthenticationError):
        MODULE.validate_easy_auth_headers(headers)
