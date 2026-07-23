"""Tests de SecretResolver.

Inyectamos un client fake (Protocol structural typing) para probar sin red.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from factory_etl.config import Settings
from factory_etl.errors import ConfigError
from factory_etl.secrets import SecretResolver


def _make_settings() -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bucket",
        control_dataset="test_control",
    )


@dataclass
class _FakePayload:
    data: bytes


@dataclass
class _FakeResponse:
    payload: _FakePayload


class _FakeClient:
    """Client fake que registra llamadas para verificar path y cache."""

    def __init__(self, values: dict[str, bytes]) -> None:
        self._values = values
        self.calls: list[str] = []

    def access_secret_version(self, *, name: str) -> _FakeResponse:
        self.calls.append(name)
        if name not in self._values:
            raise RuntimeError(f"not found: {name}")
        return _FakeResponse(payload=_FakePayload(data=self._values[name]))


class TestSecretResolverGet:
    def test_devuelve_valor_utf8(self) -> None:
        client = _FakeClient(
            {
                "projects/test-project/secrets/factory-api-key/versions/latest": b"my-key-value",
            }
        )
        resolver = SecretResolver(_make_settings(), client=client)

        assert resolver.get("factory-api-key") == "my-key-value"

    def test_soporta_acentos_utf8(self) -> None:
        client = _FakeClient(
            {
                "projects/test-project/secrets/nombre/versions/latest": "usuário".encode(),
            }
        )
        resolver = SecretResolver(_make_settings(), client=client)

        assert resolver.get("nombre") == "usuário"

    def test_construye_path_con_gcp_project(self) -> None:
        client = _FakeClient(
            {
                "projects/test-project/secrets/factory-api-user/versions/latest": b"user",
            }
        )
        resolver = SecretResolver(_make_settings(), client=client)

        resolver.get("factory-api-user")

        assert client.calls == ["projects/test-project/secrets/factory-api-user/versions/latest"]


class TestSecretResolverCache:
    def test_llamadas_repetidas_no_golpean_api(self) -> None:
        client = _FakeClient({"projects/test-project/secrets/x/versions/latest": b"v"})
        resolver = SecretResolver(_make_settings(), client=client)

        assert resolver.get("x") == "v"
        assert resolver.get("x") == "v"
        assert resolver.get("x") == "v"

        assert len(client.calls) == 1

    def test_secretos_distintos_se_cachean_por_separado(self) -> None:
        client = _FakeClient(
            {
                "projects/test-project/secrets/a/versions/latest": b"va",
                "projects/test-project/secrets/b/versions/latest": b"vb",
            }
        )
        resolver = SecretResolver(_make_settings(), client=client)

        assert resolver.get("a") == "va"
        assert resolver.get("b") == "vb"
        assert resolver.get("a") == "va"

        assert len(client.calls) == 2


class TestSecretResolverErrors:
    def test_secreto_inexistente_dispara_config_error(self) -> None:
        client = _FakeClient({})  # sin ningun valor
        resolver = SecretResolver(_make_settings(), client=client)

        with pytest.raises(ConfigError, match="no se pudo acceder"):
            resolver.get("no-existe")

    def test_no_filtra_traza_del_sdk_en_mensaje(self) -> None:
        """El mensaje no debe incluir la excepcion original (posible fuga).

        La excepcion original queda en `__cause__` para debugging.
        """

        class _RaisingClient:
            def access_secret_version(self, *, name: str) -> Any:  # noqa: ARG002
                raise RuntimeError("token=abc123 leaked in error")

        resolver = SecretResolver(_make_settings(), client=_RaisingClient())

        with pytest.raises(ConfigError) as exc_info:
            resolver.get("x")

        assert "token" not in str(exc_info.value)
        assert "abc123" not in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    def test_error_no_cachea(self) -> None:
        """Un error transitorio no debe envenenar el cache."""

        raised = [False]

        class _FlakyClient:
            def access_secret_version(self, *, name: str) -> _FakeResponse:
                if not raised[0]:
                    raised[0] = True
                    raise RuntimeError("transient")
                return _FakeResponse(payload=_FakePayload(data=b"value"))

        resolver = SecretResolver(_make_settings(), client=_FlakyClient())

        with pytest.raises(ConfigError):
            resolver.get("x")

        # Segundo intento tiene exito y NO debe estar cacheado con basura.
        assert resolver.get("x") == "value"
