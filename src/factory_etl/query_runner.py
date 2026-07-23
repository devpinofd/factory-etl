"""Cliente HTTP hacia la API generica de FactorySoft.

Contrato:

- Un ``QueryRunner`` recibe un SQL renderizado y devuelve el payload crudo
  (bytes) mas el ``payload_hash`` calculado sobre los bytes exactos.
- Aplica timeouts y retries con backoff exponencial + jitter para errores
  transitorios (5xx, timeouts, conexion). No reintenta 4xx.
- Nunca loguea el SQL, la API key, el usuario ni el payload. Todos los
  campos sensibles ya estan en ``logging_config._REDACT_KEYS``.

Depende de ``SecretResolverProtocol``, no de la implementacion concreta:
en tests se puede inyectar un fake en memoria.

El cliente HTTP tambien es inyectable via keyword-only ``http_client``
para permitir tests con ``respx`` sin tocar red.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from factory_etl.config import Settings
from factory_etl.errors import AuthenticationError, TransportError
from factory_etl.protocols import SecretResolverProtocol

if TYPE_CHECKING:  # pragma: no cover
    pass


@dataclass(frozen=True)
class HttpResult:
    """Resultado de una llamada HTTP exitosa."""

    payload_bytes: bytes
    payload_hash: str
    status_code: int
    elapsed_ms: int


class _TransientServerError(TransportError):
    """Marker interno: 5xx u otro error del servidor que amerita retry.

    Se hereda de ``TransportError`` para que un caller que catche
    ``TransportError`` reciba tambien esta clase (transparente hacia afuera).
    Pero por ser una clase distinta permite que ``tenacity`` la use como
    condicion de retry sin marcar tambien los 4xx (que se levantan como
    ``TransportError`` puro).
    """


# Errores transitorios que sí ameritan retry. No incluye 4xx.
_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    _TransientServerError,
)


class QueryRunner:
    """Ejecuta un SQL renderizado contra la API generica de FactorySoft."""

    def __init__(
        self,
        settings: Settings,
        secrets: SecretResolverProtocol,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._secrets = secrets
        self._http_client = http_client  # se construye perezosamente

    def execute(self, *, sql_rendered: str, source_empresa: str) -> HttpResult:
        """Envia el POST y devuelve el payload crudo con su hash SHA-256.

        :raises AuthenticationError: 401/403 (no reintenta).
        :raises TransportError: 5xx persistente tras retries agotados,
            error de red persistente, o response body vacio.
        """
        api_key = self._secrets.get(self._settings.factorysoft_api_key_secret)
        api_user = self._secrets.get(self._settings.factorysoft_api_user_secret)

        # tenacity: retry con backoff exp + jitter para transitorios.
        # `stop_after_attempt` incluye el intento inicial (1 + max_retries).
        attempts = self._settings.http_max_retries + 1
        backoff = self._settings.http_retry_backoff_seconds

        @retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential_jitter(initial=backoff, max=backoff * 8),
            retry=retry_if_exception_type(_TRANSIENT_EXCEPTIONS),
            reraise=True,
        )
        def _do_request() -> HttpResult:
            return self._request_once(
                sql_rendered=sql_rendered,
                source_empresa=source_empresa,
                api_key=api_key,
                api_user=api_user,
            )

        try:
            return _do_request()
        except RetryError as exc:  # pragma: no cover - reraise=True lo evita
            raise TransportError("retries agotados") from exc

    # -- privados -------------------------------------------------------------

    def _request_once(
        self,
        *,
        sql_rendered: str,
        source_empresa: str,
        api_key: str,
        api_user: str,
    ) -> HttpResult:
        """Un solo intento. Levanta transitorios (retry) o definitivos."""
        body = {
            "apikey": api_key,
            "usuario": api_user,
            "sql": sql_rendered,
            "empresa": source_empresa,
        }

        started_ns = time.monotonic_ns()
        try:
            response = self._get_client().post(
                self._settings.factorysoft_base_url,
                json=body,
                timeout=self._settings.http_timeout_seconds,
            )
        except httpx.HTTPError:
            # httpx.TimeoutException, NetworkError, RemoteProtocolError caen
            # dentro de _TRANSIENT_EXCEPTIONS y tenacity los reintentara.
            raise
        elapsed_ms = int((time.monotonic_ns() - started_ns) / 1_000_000)

        payload_bytes = response.content

        # 401/403: no reintentar. Es error del caller (credenciales malas).
        if response.status_code in {401, 403}:
            raise AuthenticationError(
                f"FactorySoft rechazo la autenticacion (status={response.status_code})"
            )

        # 5xx: transitorio. Levantamos _TransientServerError para que tenacity reintente.
        if 500 <= response.status_code < 600:
            raise _TransientServerError(f"servidor FactorySoft devolvio {response.status_code}")

        # 4xx no-auth: bug del cliente (mal SQL, empresa invalida). No reintentar.
        if 400 <= response.status_code < 500:
            raise TransportError(f"FactorySoft rechazo la request (status={response.status_code})")

        if not payload_bytes:
            # 2xx con body vacio: lo consideramos error, pero no se reintenta
            # porque puede ser un rechazo semantico intencional.
            raise TransportError("respuesta vacia (2xx sin body)")

        payload_hash = hashlib.sha256(payload_bytes).hexdigest()
        return HttpResult(
            payload_bytes=payload_bytes,
            payload_hash=payload_hash,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )

    def _get_client(self) -> httpx.Client:
        if self._http_client is None:
            self._http_client = httpx.Client(
                timeout=self._settings.http_timeout_seconds,
            )
        return self._http_client
