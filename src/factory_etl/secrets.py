"""Wrapper delgado sobre Google Cloud Secret Manager.

Contrato:

- Los secretos se identifican por el nombre corto (``factory-api-key``).
- La resolucion del path completo (``projects/<id>/secrets/<name>/versions/latest``)
  se hace internamente usando ``Settings.gcp_project``.
- Los valores se cachean en memoria durante la vida del proceso para
  minimizar llamadas a la API. El cache se invalida solo reiniciando el
  proceso; para rotacion inmediata, redesplegar el Cloud Run Job.
- El client de Secret Manager es inyectable para tests (patron
  Dependency Inversion aplicado al SDK de GCP).
"""

from __future__ import annotations

from typing import Any, Protocol

from factory_etl.config import Settings
from factory_etl.errors import ConfigError


class _SecretManagerClient(Protocol):
    """Subset del SDK de google-cloud-secret-manager que consumimos.

    El return type se declara como ``Any`` a proposito: el consumidor solo
    accede a ``response.payload.data`` estructuralmente. Declarar el tipo
    concreto del SDK forzaria a los fakes de test a devolver ese mismo
    tipo, lo que rompe la inyeccion de dependencias. Un tipo estructural
    (Protocol) mas estricto choca con la contravariancia de pyright para
    return types de metodos declarados en otro Protocol. ``Any`` mantiene
    el objetivo (no atar al SDK) sin las falsas alarmas del type checker.
    """

    def access_secret_version(self, *, name: str) -> Any: ...  # pragma: no cover


class SecretResolver:
    """Resuelve nombres logicos de secretos a su valor actual."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: _SecretManagerClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client  # se construye perezosamente si es None
        self._cache: dict[str, str] = {}

    def get(self, secret_name: str) -> str:
        """Devuelve el valor del secreto (UTF-8 decodificado).

        :raises ConfigError: si el secreto no existe o el proceso no tiene
            permisos para leerlo.
        """
        if secret_name in self._cache:
            return self._cache[secret_name]

        name = f"projects/{self._settings.gcp_project}" f"/secrets/{secret_name}/versions/latest"
        try:
            response = self._get_client().access_secret_version(name=name)
        except Exception as exc:
            # No incluir el nombre del secreto es aceptable porque es un
            # identificador, no un valor. El nombre del proyecto tampoco es
            # sensible en logs. NO incluimos la excepcion original en el
            # mensaje visible al usuario para evitar filtrar trazas del SDK.
            raise ConfigError(f"no se pudo acceder al secreto '{secret_name}'") from exc

        value: str = response.payload.data.decode("utf-8")
        self._cache[secret_name] = value
        return value

    def _get_client(self) -> _SecretManagerClient:
        """Construye el client real perezosamente (evita red en tests)."""
        if self._client is None:
            # Import diferido: la construccion del client real requiere ADC
            # y no queremos pagar ese costo cuando el consumidor inyecta
            # un mock.
            from google.cloud import secretmanager  # noqa: PLC0415

            self._client = secretmanager.SecretManagerServiceClient()
        return self._client
