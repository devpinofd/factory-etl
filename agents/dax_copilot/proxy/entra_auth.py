from __future__ import annotations

import base64
import json
import os
from typing import Any


class AuthenticationError(ValueError):
    """Raised when the Easy Auth principal is missing or not authorized."""


def _claims(principal: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for claim in principal.get("claims", []):
        if isinstance(claim, dict) and isinstance(claim.get("typ"), str):
            value = claim.get("val")
            if isinstance(value, str):
                result.setdefault(claim["typ"], []).append(value)
    return result


def _decode_principal(encoded: str) -> dict[str, Any]:
    try:
        padding = "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(encoded + padding)
        principal = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthenticationError("El principal de Entra ID no es valido.") from exc
    if not isinstance(principal, dict):
        raise AuthenticationError("El principal de Entra ID no es valido.")
    return principal


def validate_easy_auth_headers(headers: dict[str, str]) -> dict[str, str]:
    if os.getenv("REQUIRE_ENTRA_AUTH", "false").lower() not in {"1", "true", "yes"}:
        return {"subject": headers.get("x-ms-client-principal-id", "anonymous")}

    encoded = headers.get("x-ms-client-principal")
    if not encoded:
        raise AuthenticationError("Se requiere autenticacion Entra ID.")

    principal = _decode_principal(encoded)
    if principal.get("auth_typ") not in {"aad", "AzureAD"}:
        raise AuthenticationError("El proveedor de identidad no es Entra ID.")

    claims = _claims(principal)
    tenant_id = os.getenv("AZURE_TENANT_ID")
    tenant_claims = claims.get("http://schemas.microsoft.com/identity/claims/tenantid", [])
    if tenant_id and tenant_id not in tenant_claims:
        raise AuthenticationError("El tenant del token no esta autorizado.")

    required_scope = os.getenv("AZURE_REQUIRED_SCOPE")
    scopes = claims.get("http://schemas.microsoft.com/identity/claims/scope", [])
    if required_scope and required_scope not in " ".join(scopes).split():
        raise AuthenticationError("El token no contiene el scope requerido.")

    subject = headers.get("x-ms-client-principal-id")
    if not subject:
        subject_claims = claims.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier", [])
        subject = subject_claims[0] if subject_claims else None
    if not subject:
        raise AuthenticationError("El principal no contiene subject.")

    return {"subject": subject}
