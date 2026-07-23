"""Tests de la redaccion de campos sensibles en logging.

El invariante de seguridad es: **ningun log line debe contener** valores
en claro de API keys, credenciales, SQL renderizado, payloads crudos o
identificadores de usuario. Estos tests son la primera linea de defensa.
"""

from __future__ import annotations

import pytest

from factory_etl.logging_config import _REDACT_KEYS, _redact_sensitive


REDACTED = "***REDACTED***"


class TestRedactSensitive:
    @pytest.mark.parametrize("key", sorted(_REDACT_KEYS))
    def test_redacts_every_declared_key(self, key: str) -> None:
        event = {"event": "call", key: "supersecret"}

        result = _redact_sensitive(None, "info", dict(event))

        assert result[key] == REDACTED

    def test_redaction_is_case_insensitive(self) -> None:
        event = {"event": "call", "APIKEY": "supersecret", "Authorization": "Bearer x"}

        result = _redact_sensitive(None, "info", dict(event))

        assert result["APIKEY"] == REDACTED
        assert result["Authorization"] == REDACTED

    def test_preserves_non_sensitive_keys(self) -> None:
        event = {
            "event": "call",
            "run_id": "abc",
            "record_count": 42,
            "status": "SUCCESS",
        }

        result = _redact_sensitive(None, "info", dict(event))

        assert result == event

    def test_does_not_add_extra_keys(self) -> None:
        event = {"event": "call", "run_id": "abc"}

        result = _redact_sensitive(None, "info", dict(event))

        assert set(result.keys()) == {"event", "run_id"}

    def test_redacts_even_if_value_is_none(self) -> None:
        event = {"event": "call", "password": None}

        result = _redact_sensitive(None, "info", dict(event))

        assert result["password"] == REDACTED

    def test_redacts_even_if_value_is_int(self) -> None:
        event = {"event": "call", "token": 123456}

        result = _redact_sensitive(None, "info", dict(event))

        assert result["token"] == REDACTED

    def test_returns_same_dict_instance(self) -> None:
        """El contrato de un processor structlog es mutar el dict recibido."""
        event = {"event": "call", "api_key": "x"}

        result = _redact_sensitive(None, "info", event)

        assert result is event

    def test_original_secret_never_appears_in_output(self) -> None:
        secret_value = "SK-1234567890-DO-NOT-LEAK"
        event = {"event": "call", "apikey": secret_value, "sql": "select 1"}

        result = _redact_sensitive(None, "info", dict(event))

        for value in result.values():
            assert secret_value not in str(value)
            assert "select 1" not in str(value)


class TestRedactionCoverage:
    """Verifica que la lista de keys redactadas cubre las categorias esperadas."""

    def test_covers_authentication_keys(self) -> None:
        assert "apikey" in _REDACT_KEYS
        assert "api_key" in _REDACT_KEYS
        assert "authorization" in _REDACT_KEYS
        assert "token" in _REDACT_KEYS
        assert "password" in _REDACT_KEYS
        assert "secret" in _REDACT_KEYS

    def test_covers_sql_and_payload(self) -> None:
        assert "sql" in _REDACT_KEYS
        assert "sql_rendered" in _REDACT_KEYS
        assert "payload" in _REDACT_KEYS
        assert "raw_response" in _REDACT_KEYS

    def test_covers_factorysoft_user(self) -> None:
        assert "usuario" in _REDACT_KEYS
