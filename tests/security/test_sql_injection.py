"""Tests de seguridad del renderer contra inyeccion SQL.

Estos tests son mas importantes que los unitarios: fallar aqui es un
incidente de seguridad, no un bug funcional. Un cambio que haga pasar
un test que antes fallaba requiere revision de seguridad explicita.
"""

from __future__ import annotations

import pytest

from factory_etl.errors import ForbiddenContent, InvalidParameterValue
from factory_etl.factory_queries.models import ParamSpec, ParamType
from factory_etl.factory_queries.renderer import render


class TestForbiddenTokensInStringParams:
    """Tokens de inyeccion en un STRING_ENUM valido de tipo, pero peligroso."""

    @pytest.mark.parametrize(
        "malicious_value",
        [
            "tinito'; drop table articulos--",
            "tinito' or '1'='1",
            "tinito';--",
            "tinito/*comment*/",
            "tinito;delete from etl_runs",
            "xp_cmdshell",
            "sp_executesql",
            "tinito\x00null",
            "0xdeadbeef",
            "tinito@@version",
            "..\\..\\etc\\passwd",
        ],
    )
    def test_rechaza_token_prohibido(self, malicious_value: str) -> None:
        """Cualquier token peligroso dispara ForbiddenContent aun con dominio abierto."""
        specs = (
            ParamSpec(name="e", type=ParamType.STRING_ENUM, allowed_values=(malicious_value,)),
        )
        with pytest.raises(ForbiddenContent):
            render("{{e}}", specs, {"e": malicious_value})


class TestPlaceholderNameRestrictions:
    """El propio nombre del placeholder solo puede ser snake_case ASCII."""

    def test_placeholder_con_caracteres_extra_no_matchea(self) -> None:
        # Placeholders con caracteres invalidos simplemente no matchean el regex
        # y por tanto no se sustituyen, dejando el template literal.
        template = "select {{cod-art}} from t"
        rendered = render(template, (), {})
        assert rendered == template  # el placeholder no se toca

    def test_placeholder_con_mayusculas_no_matchea(self) -> None:
        template = "select {{CodArt}} from t"
        rendered = render(template, (), {})
        assert rendered == template


class TestStringEnumCharsetHardening:
    """Solo ASCII imprimible en STRING_ENUM incluso si esta en allowed_values."""

    def test_rechaza_caracteres_no_ascii(self) -> None:
        # Aunque el valor este en allowed_values, un no-ASCII se rechaza para
        # evitar sorpresas por normalizacion unicode o characters de control.
        specs = (ParamSpec(name="e", type=ParamType.STRING_ENUM, allowed_values=("tinito\u200b",)),)
        with pytest.raises(InvalidParameterValue, match="ASCII"):
            render("{{e}}", specs, {"e": "tinito\u200b"})


class TestReDoSResilience:
    """El regex de placeholder no debe ser vulnerable a input degenerado."""

    def test_template_muy_largo_no_bloquea(self) -> None:
        template = "select " + ("x," * 5000) + "y from t"
        rendered = render(template, (), {})
        assert rendered == template

    def test_muchos_placeholders_no_declarados_fallan_rapido(self) -> None:
        template = "".join(f"{{{{p{i}}}}} " for i in range(100))
        # Deberia fallar en el primer placeholder no declarado, no explorar los 100.
        with pytest.raises(Exception):  # noqa: B017 - cualquier RenderError es aceptable
            render(template, (), {})
