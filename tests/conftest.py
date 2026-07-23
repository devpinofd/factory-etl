"""Configuracion global de pytest y fixtures reutilizables."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_ROOT = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    """Ruta a la carpeta de fixtures."""
    return FIXTURES_ROOT


@pytest.fixture(scope="session")
def factorysoft_articulos_ok(fixtures_root: Path) -> bytes:
    """Payload real de FactorySoft para articulos (empresa tinito).

    Fixture derivado de la respuesta compartida el 2026-07-22. Se guarda como
    bytes (no dict) para preservar bit-a-bit el contenido: el ETL calcula el
    ``payload_hash`` sobre los bytes exactos, y cualquier normalizacion de
    JSON invalidaria los tests de idempotencia.
    """
    return (fixtures_root / "factorysoft" / "articulos_tinito_ok.json").read_bytes()
