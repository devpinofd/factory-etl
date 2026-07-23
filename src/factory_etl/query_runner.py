"""Cliente HTTP hacia la API generica de FactorySoft.

Contrato:

- Un ``QueryRunner`` recibe un SQL renderizado y devuelve el payload crudo
  (bytes) mas el ``payload_hash`` calculado sobre los bytes exactos.
- Aplica timeouts y retries con backoff exponencial + jitter para errores
  transitorios (5xx, timeouts, conexion). No reintenta 4xx.
- Nunca loguea el SQL, la API key, el usuario ni el payload.

Depende de ``SecretResolverProtocol``, no de la implementacion concreta:
en tests se puede inyectar un fake en memoria.

Implementacion pendiente: Fase 1 Etapa 4.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_etl.config import Settings
from factory_etl.protocols import SecretResolverProtocol


@dataclass(frozen=True)
class HttpResult:
    """Resultado de una llamada HTTP exitosa."""

    payload_bytes: bytes
    payload_hash: str
    status_code: int
    elapsed_ms: int


class QueryRunner:
    """Ejecuta un SQL renderizado contra la API generica de FactorySoft."""

    def __init__(self, settings: Settings, secrets: SecretResolverProtocol) -> None:
        self._settings = settings
        self._secrets = secrets

    def execute(self, *, sql_rendered: str, source_empresa: str) -> HttpResult:  # noqa: ARG002
        """Envia el POST y devuelve el payload crudo con su hash."""
        raise NotImplementedError(
            "QueryRunner.execute pendiente de implementar (Fase 1 Etapa 4)."
        )
