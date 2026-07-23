"""Tests del fixture real de FactorySoft.

Validan que la estructura de respuesta que asumimos en el diseño coincide
con lo que efectivamente entrega la API. Si esto falla despues de un
cambio en FactorySoft, tenemos alerta temprana antes de tocar el
extractor.
"""

from __future__ import annotations

import json


class TestArticulosFixtureShape:
    def test_raiz_es_d_laTablas(self, factorysoft_articulos_ok: bytes) -> None:
        payload = json.loads(factorysoft_articulos_ok)
        assert "d" in payload
        assert "laTablas" in payload["d"]

    def test_laTablas_es_lista_de_listas(self, factorysoft_articulos_ok: bytes) -> None:
        payload = json.loads(factorysoft_articulos_ok)
        tablas = payload["d"]["laTablas"]
        assert isinstance(tablas, list)
        assert len(tablas) >= 1
        assert isinstance(tablas[0], list)

    def test_primer_registro_tiene_columnas_requeridas(
        self, factorysoft_articulos_ok: bytes
    ) -> None:
        payload = json.loads(factorysoft_articulos_ok)
        row = payload["d"]["laTablas"][0][0]
        # Las mismas required_columns declaradas en el catalogo.
        for col in ("cod_art", "nom_art", "cod_uni1", "status"):
            assert col in row, f"columna requerida ausente: {col}"

    def test_strings_vienen_con_padding_como_esperado(
        self, factorysoft_articulos_ok: bytes
    ) -> None:
        """Confirma que Bronze recibira strings con padding CHAR (no RTRIM)."""
        payload = json.loads(factorysoft_articulos_ok)
        row = payload["d"]["laTablas"][0][0]
        # El registro plantilla tiene padding a la derecha en cod_art (CHAR(30)).
        assert row["cod_art"].endswith(" "), "se esperaba padding de espacios"

    def test_numericos_vienen_como_number(self, factorysoft_articulos_ok: bytes) -> None:
        """Confirma que los numeros llegan como float/int, no como string."""
        payload = json.loads(factorysoft_articulos_ok)
        row = payload["d"]["laTablas"][0][0]
        for col in ("peso", "fraccion", "cap_bulto", "gra_lic", "precio", "cos_ult1"):
            assert isinstance(row[col], int | float), f"{col} no es numerico: {type(row[col])}"

    def test_fec_ini_formato_iso_dotnet(self, factorysoft_articulos_ok: bytes) -> None:
        payload = json.loads(factorysoft_articulos_ok)
        row = payload["d"]["laTablas"][0][0]
        # Formato .NET DateTime.ToString("o"): YYYY-MM-DDTHH:MM:SS.fffffff
        assert "T" in row["fec_ini"]
        assert row["fec_ini"].count(":") == 2

    def test_status_esta_en_dominio(self, factorysoft_articulos_ok: bytes) -> None:
        payload = json.loads(factorysoft_articulos_ok)
        row = payload["d"]["laTablas"][0][0]
        assert row["status"] in ("A", "I")
