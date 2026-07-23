"""Tests unitarios del renderer.

Cubren:

- Sustitucion correcta por tipo (STRING_ENUM, DATE, INT).
- Rechazo de placeholders no declarados.
- Rechazo de parametros faltantes.
- Rechazo de parametros declarados pero no usados.
- Determinismo (mismo input -> mismo output).
"""

from __future__ import annotations

import pytest

from factory_etl.errors import (
    InvalidParameterValue,
    MissingParameter,
    RenderError,
    UndeclaredPlaceholder,
)
from factory_etl.factory_queries.models import ParamSpec, ParamType
from factory_etl.factory_queries.renderer import render


class TestSuccessfulRendering:
    def test_string_enum_sustituye_con_comillas(self) -> None:
        template = "select * from articulos where cod_empresa = {{empresa}}"
        specs = (
            ParamSpec(
                name="empresa",
                type=ParamType.STRING_ENUM,
                allowed_values=("tinito", "ctb", "ctm"),
            ),
        )
        rendered = render(template, specs, {"empresa": "tinito"})
        assert rendered == "select * from articulos where cod_empresa = 'tinito'"

    def test_date_sustituye_con_formato_iso(self) -> None:
        template = "select * from ventas where fecha >= {{desde}}"
        specs = (ParamSpec(name="desde", type=ParamType.DATE),)
        rendered = render(template, specs, {"desde": "2026-01-01"})
        assert rendered == "select * from ventas where fecha >= '2026-01-01'"

    def test_int_sustituye_sin_comillas(self) -> None:
        template = "select top {{limite}} * from articulos"
        specs = (ParamSpec(name="limite", type=ParamType.INT, min_value=1, max_value=100),)
        rendered = render(template, specs, {"limite": 10})
        assert rendered == "select top 10 * from articulos"

    def test_placeholder_con_espacios_es_valido(self) -> None:
        template = "select * from t where c = {{  empresa  }}"
        specs = (
            ParamSpec(name="empresa", type=ParamType.STRING_ENUM, allowed_values=("tinito",)),
        )
        rendered = render(template, specs, {"empresa": "tinito"})
        assert rendered == "select * from t where c = 'tinito'"

    def test_multiples_placeholders(self) -> None:
        template = "select * from ventas where empresa = {{e}} and fecha >= {{desde}}"
        specs = (
            ParamSpec(name="e", type=ParamType.STRING_ENUM, allowed_values=("tinito",)),
            ParamSpec(name="desde", type=ParamType.DATE),
        )
        rendered = render(template, specs, {"e": "tinito", "desde": "2026-01-01"})
        assert "'tinito'" in rendered
        assert "'2026-01-01'" in rendered

    def test_sin_parametros_pasa_intacto(self) -> None:
        template = "select cod_art from articulos"
        rendered = render(template, (), {})
        assert rendered == template


class TestDeterminism:
    def test_dos_renderizados_producen_el_mismo_output(self) -> None:
        template = "select * from t where c = {{empresa}} and f >= {{desde}}"
        specs = (
            ParamSpec(name="empresa", type=ParamType.STRING_ENUM, allowed_values=("tinito",)),
            ParamSpec(name="desde", type=ParamType.DATE),
        )
        params = {"empresa": "tinito", "desde": "2026-01-01"}
        a = render(template, specs, params)
        b = render(template, specs, params)
        assert a == b


class TestPlaceholderErrors:
    def test_placeholder_no_declarado_falla(self) -> None:
        template = "select * from t where c = {{no_declarado}}"
        with pytest.raises(UndeclaredPlaceholder, match="no_declarado"):
            render(template, (), {"no_declarado": "x"})

    def test_parametro_declarado_faltante_falla(self) -> None:
        template = "select * from t where c = {{empresa}}"
        specs = (
            ParamSpec(name="empresa", type=ParamType.STRING_ENUM, allowed_values=("tinito",)),
        )
        with pytest.raises(MissingParameter, match="empresa"):
            render(template, specs, {})

    def test_parametro_declarado_pero_no_usado_falla(self) -> None:
        template = "select * from articulos"
        specs = (
            ParamSpec(name="empresa", type=ParamType.STRING_ENUM, allowed_values=("tinito",)),
        )
        with pytest.raises(RenderError, match="empresa"):
            render(template, specs, {"empresa": "tinito"})


class TestTypeValidation:
    def test_string_enum_valor_fuera_del_dominio_falla(self) -> None:
        template = "{{e}}"
        specs = (ParamSpec(name="e", type=ParamType.STRING_ENUM, allowed_values=("tinito",)),)
        with pytest.raises(InvalidParameterValue, match="allowed_values"):
            render(template, specs, {"e": "otra_empresa"})

    def test_string_enum_sin_allowed_values_falla(self) -> None:
        template = "{{e}}"
        specs = (ParamSpec(name="e", type=ParamType.STRING_ENUM, allowed_values=None),)
        with pytest.raises(InvalidParameterValue, match="allowed_values"):
            render(template, specs, {"e": "tinito"})

    def test_date_formato_invalido_falla(self) -> None:
        template = "{{d}}"
        specs = (ParamSpec(name="d", type=ParamType.DATE),)
        with pytest.raises(InvalidParameterValue, match="YYYY-MM-DD"):
            render(template, specs, {"d": "01/01/2026"})

    def test_int_como_string_falla(self) -> None:
        template = "{{n}}"
        specs = (ParamSpec(name="n", type=ParamType.INT),)
        with pytest.raises(InvalidParameterValue, match="int"):
            render(template, specs, {"n": "10"})

    def test_bool_no_es_aceptado_como_int(self) -> None:
        template = "{{n}}"
        specs = (ParamSpec(name="n", type=ParamType.INT),)
        with pytest.raises(InvalidParameterValue, match="int"):
            render(template, specs, {"n": True})

    def test_int_fuera_de_rango_falla(self) -> None:
        template = "{{n}}"
        specs = (ParamSpec(name="n", type=ParamType.INT, min_value=1, max_value=10),)
        with pytest.raises(InvalidParameterValue, match="max_value"):
            render(template, specs, {"n": 100})
