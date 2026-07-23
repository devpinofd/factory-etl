"""Tests que documentan la extensibilidad OCP del renderer.

El renderer usa un registry ``_FORMATTERS`` para mapear ``ParamType`` a
funciones formatter. Estos tests verifican dos invariantes:

1. Todos los ``ParamType`` publicos tienen formatter registrado.
2. El registry es inmutable (``MappingProxyType``): intentar mutarlo lanza
   ``TypeError``. Esto garantiza que ninguna parte del codigo pueda
   sobrescribir un formatter en runtime.
"""

from __future__ import annotations

import pytest

from factory_etl.factory_queries.models import ParamType
from factory_etl.factory_queries.renderer import _FORMATTERS


class TestRegistryCompleteness:
    def test_every_param_type_has_formatter(self) -> None:
        missing = [pt for pt in ParamType if pt not in _FORMATTERS]
        assert not missing, f"ParamType sin formatter registrado: {missing}"

    def test_formatters_are_callable(self) -> None:
        for pt, fn in _FORMATTERS.items():
            assert callable(fn), f"formatter de {pt} no es callable"


class TestRegistryImmutability:
    def test_cannot_add_new_entry_at_runtime(self) -> None:
        with pytest.raises(TypeError):
            _FORMATTERS["hacked"] = lambda _s, _v: "'x'"  # type: ignore[index]

    def test_cannot_overwrite_existing_entry(self) -> None:
        with pytest.raises(TypeError):
            _FORMATTERS[ParamType.INT] = lambda _s, _v: "'evil'"  # type: ignore[index]

    def test_cannot_delete_entry(self) -> None:
        with pytest.raises(TypeError):
            del _FORMATTERS[ParamType.INT]  # type: ignore[misc]
