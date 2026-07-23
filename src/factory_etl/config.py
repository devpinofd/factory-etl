"""Configuracion tipada del ETL, leida desde variables de entorno.

Todas las variables usan el prefijo ``FACTORY_ETL_``. Ejemplo:

.. code-block:: bash

    FACTORY_ETL_ENV=dev
    FACTORY_ETL_GCP_PROJECT=mi-proyecto-dev
    FACTORY_ETL_BRONZE_BUCKET=factory-datalake-dev-mi-proyecto

La configuracion es inmutable: se crea una vez por proceso y se pasa por
dependencia explicita, nunca como estado global mutable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Env = Literal["dev", "stage", "prod"]


class Settings(BaseSettings):
    """Configuracion del proceso.

    Se instancia con :meth:`load` para forzar lectura desde el entorno.
    """

    model_config = SettingsConfigDict(
        env_prefix="FACTORY_ETL_",
        case_sensitive=False,
        extra="forbid",
        frozen=True,
    )

    # --- Ambiente ------------------------------------------------------------

    env: Env = Field(default="dev", description="Ambiente logico: dev|stage|prod.")

    # --- GCP -----------------------------------------------------------------

    gcp_project: str = Field(description="ID del proyecto GCP donde vive el bucket y BQ.")
    gcp_region: str = Field(default="us-central1", description="Region primaria. Alineada con ConciliApp.")

    bronze_bucket: str = Field(description="Nombre del bucket GCS para Bronze.")
    quarantine_bucket: str = Field(
        default="",
        description="Bucket para cuarentena. Si vacio, se usa el mismo bronze_bucket con prefijo quarantine/.",
    )
    control_dataset: str = Field(
        description="Dataset BigQuery con etl_runs, etl_batches, etl_events, data_quality_results.",
    )

    # --- FactorySoft ---------------------------------------------------------

    factorysoft_base_url: str = Field(
        default="https://login.factorysoftve.com/api/generica/efactoryApiGenerica.asmx/Seleccionar",
        description="URL de la API generica de FactorySoft.",
    )
    factorysoft_api_key_secret: str = Field(
        default="factory-api-key",
        description="Nombre del secreto en Secret Manager que contiene la API key.",
    )
    factorysoft_api_user_secret: str = Field(
        default="factory-api-user",
        description="Nombre del secreto en Secret Manager que contiene el usuario.",
    )

    # --- HTTP ----------------------------------------------------------------

    http_timeout_seconds: int = Field(default=90, ge=1, le=600)
    http_max_retries: int = Field(default=3, ge=0, le=10)
    http_retry_backoff_seconds: float = Field(default=2.0, ge=0.1)

    # --- Horaria -------------------------------------------------------------

    local_tz: str = Field(
        default="America/Caracas",
        description="Zona horaria en la que se calcula la particion `dt` diaria.",
    )

    @classmethod
    def load(cls) -> Settings:
        """Fabrica documentada; equivale a ``Settings()`` pero deja el llamado explicito."""
        return cls()  # pyright: ignore[reportCallIssue]
