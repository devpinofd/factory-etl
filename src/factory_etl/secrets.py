"""Wrapper delgado sobre Google Cloud Secret Manager.

Contrato:

- Los secretos se identifican por el nombre corto (``factory-api-key``).
- La resolucion del path completo (``projects/<id>/secrets/<name>/versions/latest``)
  se hace internamente usando ``Settings.gcp_project``.
- Los valores se cachean en memoria durante la vida del proceso para
  minimizar llamadas a la API. El cache se invalida solo reiniciando el
  proceso; para rotacion inmediata, redesplegar el Cloud Run Job.

Implementacion pendiente: Fase 1 Etapa 4.
"""

from __future__ import annotations

from factory_etl.config import Settings


class SecretResolver:
    """Resuelve nombres logicos de secretos a su valor actual."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, str] = {}

    def get(self, secret_name: str) -> str:
        """Devuelve el valor del secreto. Lanza si no existe o no hay permisos."""
        if secret_name in self._cache:
            return self._cache[secret_name]
        raise NotImplementedError("SecretResolver.get pendiente de implementar (Fase 1 Etapa 4).")
