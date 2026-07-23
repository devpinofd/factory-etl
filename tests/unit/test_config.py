"""Tests de :class:`factory_etl.config.Settings`.

Verifican:

- Lee variables con prefijo ``FACTORY_ETL_``.
- Es inmutable (``frozen=True``): no se puede mutar despues de construida.
- Rechaza campos extra (``extra="forbid"``).
- Falla si faltan campos requeridos sin default.
- Aplica validadores numericos (``ge``, ``le``).
- Defaults documentados se mantienen (contrato observable).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory_etl.config import Settings


REQUIRED_ENV: dict[str, str] = {
    "FACTORY_ETL_GCP_PROJECT": "test-project",
    "FACTORY_ETL_BRONZE_BUCKET": "test-bucket",
    "FACTORY_ETL_CONTROL_DATASET": "test_control",
}


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Limpia todas las variables FACTORY_ETL_ del entorno de test."""
    import os

    for key in list(os.environ):
        if key.startswith("FACTORY_ETL_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


class TestEnvPrefix:
    def test_reads_prefixed_variables(self, clean_env: pytest.MonkeyPatch) -> None:
        for k, v in REQUIRED_ENV.items():
            clean_env.setenv(k, v)
        clean_env.setenv("FACTORY_ETL_ENV", "prod")

        settings = Settings.load()

        assert settings.env == "prod"
        assert settings.gcp_project == "test-project"
        assert settings.bronze_bucket == "test-bucket"
        assert settings.control_dataset == "test_control"

    def test_case_insensitive(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("factory_etl_gcp_project", "test-project")
        clean_env.setenv("factory_etl_bronze_bucket", "test-bucket")
        clean_env.setenv("factory_etl_control_dataset", "test_control")

        settings = Settings.load()

        assert settings.gcp_project == "test-project"


class TestFrozen:
    def test_cannot_mutate_after_construction(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        for k, v in REQUIRED_ENV.items():
            clean_env.setenv(k, v)
        settings = Settings.load()

        with pytest.raises(ValidationError):
            settings.env = "prod"  # type: ignore[misc]


class TestExtraForbidden:
    def test_rejects_unknown_fields(self, clean_env: pytest.MonkeyPatch) -> None:
        for k, v in REQUIRED_ENV.items():
            clean_env.setenv(k, v)

        with pytest.raises(ValidationError):
            Settings(unknown_field="x")  # pyright: ignore[reportCallIssue]


class TestRequiredFields:
    def test_fails_without_gcp_project(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("FACTORY_ETL_BRONZE_BUCKET", "b")
        clean_env.setenv("FACTORY_ETL_CONTROL_DATASET", "d")

        with pytest.raises(ValidationError):
            Settings.load()

    def test_fails_without_bronze_bucket(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("FACTORY_ETL_GCP_PROJECT", "p")
        clean_env.setenv("FACTORY_ETL_CONTROL_DATASET", "d")

        with pytest.raises(ValidationError):
            Settings.load()

    def test_fails_without_control_dataset(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        clean_env.setenv("FACTORY_ETL_GCP_PROJECT", "p")
        clean_env.setenv("FACTORY_ETL_BRONZE_BUCKET", "b")

        with pytest.raises(ValidationError):
            Settings.load()


class TestNumericValidators:
    def test_http_timeout_seconds_rejects_zero(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        for k, v in REQUIRED_ENV.items():
            clean_env.setenv(k, v)
        clean_env.setenv("FACTORY_ETL_HTTP_TIMEOUT_SECONDS", "0")

        with pytest.raises(ValidationError):
            Settings.load()

    def test_http_timeout_seconds_rejects_above_600(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        for k, v in REQUIRED_ENV.items():
            clean_env.setenv(k, v)
        clean_env.setenv("FACTORY_ETL_HTTP_TIMEOUT_SECONDS", "601")

        with pytest.raises(ValidationError):
            Settings.load()

    def test_http_max_retries_rejects_negative(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        for k, v in REQUIRED_ENV.items():
            clean_env.setenv(k, v)
        clean_env.setenv("FACTORY_ETL_HTTP_MAX_RETRIES", "-1")

        with pytest.raises(ValidationError):
            Settings.load()


class TestDefaults:
    def test_defaults_are_documented_contract(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        for k, v in REQUIRED_ENV.items():
            clean_env.setenv(k, v)

        settings = Settings.load()

        assert settings.env == "dev"
        assert settings.gcp_region == "us-central1"
        assert settings.local_tz == "America/Caracas"
        assert settings.http_timeout_seconds == 90
        assert settings.http_max_retries == 3
        assert settings.factorysoft_api_key_secret == "factory-api-key"

    def test_env_rejects_invalid_literal(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        for k, v in REQUIRED_ENV.items():
            clean_env.setenv(k, v)
        clean_env.setenv("FACTORY_ETL_ENV", "production")

        with pytest.raises(ValidationError):
            Settings.load()
