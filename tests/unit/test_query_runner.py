"""Tests de QueryRunner (httpx + tenacity retry).

Usa el fixture ``respx_mock`` para interceptar httpx sin red.
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
import pytest
import respx

from factory_etl.config import Settings
from factory_etl.errors import AuthenticationError, TransportError
from factory_etl.query_runner import HttpResult, QueryRunner

_URL = "https://login.factorysoftve.com/api/generica/efactoryApiGenerica.asmx/Seleccionar"


def _make_settings(**overrides: Any) -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bronze",
        control_dataset="test_control",
        http_max_retries=2,
        http_retry_backoff_seconds=0.1,  # minimo permitido por Settings
        http_timeout_seconds=5,
        **overrides,
    )


class _FakeSecrets:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = values or {
            "factory-api-key": "test-api-key-value",
            "factory-api-user": "test-user",
        }
        self.calls: list[str] = []

    def get(self, secret_name: str) -> str:
        self.calls.append(secret_name)
        return self._values[secret_name]


@pytest.fixture
def runner() -> QueryRunner:
    return QueryRunner(_make_settings(), _FakeSecrets(), http_client=httpx.Client())


class TestExecuteSuccess:
    def test_devuelve_payload_bytes_y_hash_sha256(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        payload = b'{"d":{"laTablas":[[{"cod_art":"0001"}]]}}'
        respx_mock.post(_URL).mock(return_value=httpx.Response(200, content=payload))

        result = runner.execute(sql_rendered="select * from articulos", source_empresa="tinito")

        assert isinstance(result, HttpResult)
        assert result.payload_bytes == payload
        assert result.payload_hash == hashlib.sha256(payload).hexdigest()
        assert result.status_code == 200
        assert result.elapsed_ms >= 0

    def test_body_contiene_apikey_usuario_sql_empresa(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        route = respx_mock.post(_URL).mock(return_value=httpx.Response(200, content=b'{"ok":1}'))

        runner.execute(sql_rendered="select 1", source_empresa="tinito")

        assert route.called
        sent = route.calls.last.request.content.decode("utf-8")
        assert "test-api-key-value" in sent
        assert "test-user" in sent
        assert "select 1" in sent
        assert "tinito" in sent

    def test_endpoint_configurable_via_settings(self, respx_mock: respx.MockRouter) -> None:
        custom_url = "https://mi-otro-endpoint.example.com/api"
        respx_mock.post(custom_url).mock(return_value=httpx.Response(200, content=b"{}"))

        settings = _make_settings(factorysoft_base_url=custom_url)
        runner = QueryRunner(settings, _FakeSecrets(), http_client=httpx.Client())

        result = runner.execute(sql_rendered="select 1", source_empresa="tinito")
        assert result.status_code == 200

    def test_secretos_se_leen_via_resolver(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.post(_URL).mock(return_value=httpx.Response(200, content=b"{}"))
        secrets = _FakeSecrets()

        runner = QueryRunner(_make_settings(), secrets, http_client=httpx.Client())
        runner.execute(sql_rendered="select 1", source_empresa="tinito")

        assert "factory-api-key" in secrets.calls
        assert "factory-api-user" in secrets.calls


class TestExecuteAuthErrors:
    def test_401_dispara_authentication_error_sin_retry(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        route = respx_mock.post(_URL).mock(return_value=httpx.Response(401))

        with pytest.raises(AuthenticationError, match="401"):
            runner.execute(sql_rendered="select 1", source_empresa="tinito")

        assert route.call_count == 1

    def test_403_dispara_authentication_error_sin_retry(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        route = respx_mock.post(_URL).mock(return_value=httpx.Response(403))

        with pytest.raises(AuthenticationError):
            runner.execute(sql_rendered="select 1", source_empresa="tinito")

        assert route.call_count == 1


class TestExecuteClientErrors:
    def test_400_no_reintenta(self, respx_mock: respx.MockRouter, runner: QueryRunner) -> None:
        route = respx_mock.post(_URL).mock(return_value=httpx.Response(400, content=b"bad"))

        with pytest.raises(TransportError, match="400"):
            runner.execute(sql_rendered="select bogus", source_empresa="tinito")

        assert route.call_count == 1

    def test_404_no_reintenta(self, respx_mock: respx.MockRouter, runner: QueryRunner) -> None:
        route = respx_mock.post(_URL).mock(return_value=httpx.Response(404))

        with pytest.raises(TransportError, match="404"):
            runner.execute(sql_rendered="select 1", source_empresa="tinito")

        assert route.call_count == 1


class TestExecuteServerErrors:
    def test_500_persistente_agota_retries(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        # http_max_retries=2 -> total 3 intentos
        route = respx_mock.post(_URL).mock(return_value=httpx.Response(500))

        with pytest.raises(TransportError):
            runner.execute(sql_rendered="select 1", source_empresa="tinito")

        assert route.call_count == 3

    def test_500_luego_200_recupera(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        route = respx_mock.post(_URL).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, content=b'{"ok":1}'),
            ]
        )

        result = runner.execute(sql_rendered="select 1", source_empresa="tinito")

        assert result.status_code == 200
        assert route.call_count == 2


class TestExecuteNetworkErrors:
    def test_timeout_reintenta_hasta_agotar(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        route = respx_mock.post(_URL).mock(side_effect=httpx.TimeoutException("timed out"))

        with pytest.raises(httpx.TimeoutException):
            runner.execute(sql_rendered="select 1", source_empresa="tinito")

        assert route.call_count == 3

    def test_connection_error_reintenta(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        respx_mock.post(_URL).mock(
            side_effect=[
                httpx.ConnectError("refused"),
                httpx.Response(200, content=b'{"ok":1}'),
            ]
        )

        result = runner.execute(sql_rendered="select 1", source_empresa="tinito")
        assert result.status_code == 200


class TestExecuteEmptyResponse:
    def test_200_con_body_vacio_dispara_transport_error(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        respx_mock.post(_URL).mock(return_value=httpx.Response(200, content=b""))

        with pytest.raises(TransportError, match="vacia"):
            runner.execute(sql_rendered="select 1", source_empresa="tinito")


class TestExecuteSecurity:
    def test_error_no_expone_sql_ni_credenciales(
        self, respx_mock: respx.MockRouter, runner: QueryRunner
    ) -> None:
        respx_mock.post(_URL).mock(return_value=httpx.Response(500))

        sensitive_sql = "select * from tabla_secreta where password = 'super-secret'"
        with pytest.raises(TransportError) as exc_info:
            runner.execute(sql_rendered=sensitive_sql, source_empresa="tinito")

        assert "select" not in str(exc_info.value).lower()
        assert "super-secret" not in str(exc_info.value)
        assert "password" not in str(exc_info.value)
        assert "test-api-key-value" not in str(exc_info.value)


class TestHttpResultShape:
    def test_frozen(self) -> None:
        r = HttpResult(payload_bytes=b"x", payload_hash="h", status_code=200, elapsed_ms=1)
        try:
            r.status_code = 500  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            pass
        else:
            raise AssertionError("HttpResult debe ser frozen")
