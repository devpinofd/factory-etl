"""Tests de la jerarquia de excepciones del dominio.

El contrato es que cualquier excepcion propia del ETL sea detectable con
``except FactoryEtlError``. Sub-jerarquias como ``RenderError`` permiten
manejo mas granular.
"""

from __future__ import annotations

import pytest

from factory_etl.errors import (
    AuthenticationError,
    CompanyNotAllowedError,
    ConfigError,
    DuplicateBatchError,
    EmptyResponseError,
    FactoryEtlError,
    ForbiddenContent,
    InvalidParameterValue,
    InvalidPayloadError,
    MissingParameter,
    QuarantineRequired,
    QueryNotFoundError,
    RenderError,
    TransportError,
    UndeclaredPlaceholder,
)


class TestFactoryEtlErrorIsRoot:
    @pytest.mark.parametrize(
        "cls",
        [
            ConfigError,
            QueryNotFoundError,
            CompanyNotAllowedError,
            RenderError,
            UndeclaredPlaceholder,
            MissingParameter,
            InvalidParameterValue,
            ForbiddenContent,
            TransportError,
            AuthenticationError,
            InvalidPayloadError,
            EmptyResponseError,
            DuplicateBatchError,
            QuarantineRequired,
        ],
    )
    def test_all_domain_errors_inherit_from_root(self, cls: type[Exception]) -> None:
        assert issubclass(cls, FactoryEtlError)


class TestRenderErrorSubHierarchy:
    @pytest.mark.parametrize(
        "cls",
        [
            UndeclaredPlaceholder,
            MissingParameter,
            InvalidParameterValue,
            ForbiddenContent,
        ],
    )
    def test_render_subtypes_inherit_from_render_error(self, cls: type[Exception]) -> None:
        assert issubclass(cls, RenderError)


class TestTransportSubHierarchy:
    def test_authentication_is_transport(self) -> None:
        assert issubclass(AuthenticationError, TransportError)


class TestCatchability:
    """Los handlers deben poder atrapar por categoria."""

    def test_catch_all_render_errors(self) -> None:
        for exc in (
            UndeclaredPlaceholder("x"),
            MissingParameter("x"),
            InvalidParameterValue("x"),
            ForbiddenContent("x"),
        ):
            with pytest.raises(RenderError):
                raise exc

    def test_catch_all_domain_errors(self) -> None:
        for exc in (
            ConfigError("x"),
            QueryNotFoundError("x"),
            AuthenticationError("x"),
            DuplicateBatchError("x"),
        ):
            with pytest.raises(FactoryEtlError):
                raise exc

    def test_domain_error_is_not_generic_exception_catcher(self) -> None:
        """Un ValueError externo NO debe ser atrapado por FactoryEtlError."""
        with pytest.raises(ValueError):
            try:
                raise ValueError("externo")
            except FactoryEtlError:
                pytest.fail("FactoryEtlError no debe atrapar excepciones no-dominio")


class TestExceptionMessages:
    def test_preserves_message(self) -> None:
        exc = InvalidParameterValue("empresa: valor invalido")
        assert str(exc) == "empresa: valor invalido"
