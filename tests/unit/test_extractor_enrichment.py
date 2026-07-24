"""Tests unitarios directos de ``_enrich_rows``.

Se importa el helper privado (``_enrich_rows``) porque los tests tienen
``reportPrivateUsage=false`` en ``pyproject.toml``: es el patron acordado
para probar helpers de modulo sin exponerlos en la API publica.
"""

from __future__ import annotations

import pytest

from factory_etl.extractor import _enrich_rows

_SYSTEM_COLUMNS = frozenset(
    {
        "_ingested_at",
        "_source_empresa",
        "_dt",
        "_query_id",
        "_query_version",
        "_run_id",
        "_batch_id",
        "_sql_hash",
        "_payload_hash",
        "_row_hash",
    }
)


def _enrich(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Helper: llama a ``_enrich_rows`` con valores fijos por defecto."""
    return _enrich_rows(
        rows,
        entity="articulos_v1",
        source_empresa="tinito",
        dt="2025-01-15",
        run_id="run-abc",
        batch_id_str="batch-xyz",
        sql_hash_hex="a" * 64,
        payload_hash_hex="b" * 64,
        query_version="1.0.0",
    )


class TestEnrichRows:
    def test_agrega_las_nueve_columnas_de_sistema(self) -> None:
        rows: list[dict[str, object]] = [{"cod_art": "0001"}]
        result = _enrich(rows)
        assert len(result) == 1
        assert _SYSTEM_COLUMNS.issubset(result[0].keys())

    def test_preserva_las_columnas_originales(self) -> None:
        rows: list[dict[str, object]] = [{"cod_art": "0001", "nom_art": "Uno"}]
        result = _enrich(rows)
        assert result[0]["cod_art"] == "0001"
        assert result[0]["nom_art"] == "Uno"

    def test_no_muta_la_entrada(self) -> None:
        rows: list[dict[str, object]] = [{"cod_art": "0001"}]
        _enrich(rows)
        # La fila original no debe haber recibido columnas de sistema.
        assert "_row_hash" not in rows[0]
        assert set(rows[0].keys()) == {"cod_art"}

    def test_row_hash_es_estable_para_misma_fila(self) -> None:
        rows_a: list[dict[str, object]] = [{"cod_art": "0001", "nom_art": "X"}]
        rows_b: list[dict[str, object]] = [{"nom_art": "X", "cod_art": "0001"}]
        # Distinto orden de claves pero mismo contenido → mismo hash.
        hash_a = _enrich(rows_a)[0]["_row_hash"]
        hash_b = _enrich(rows_b)[0]["_row_hash"]
        assert hash_a == hash_b

    def test_row_hash_cambia_con_contenido(self) -> None:
        rows_a: list[dict[str, object]] = [{"cod_art": "0001"}]
        rows_b: list[dict[str, object]] = [{"cod_art": "0002"}]
        assert _enrich(rows_a)[0]["_row_hash"] != _enrich(rows_b)[0]["_row_hash"]

    def test_ingested_at_es_uniforme_para_todo_el_batch(self) -> None:
        rows: list[dict[str, object]] = [
            {"cod_art": "0001"},
            {"cod_art": "0002"},
            {"cod_art": "0003"},
        ]
        result = _enrich(rows)
        ingested = {row["_ingested_at"] for row in result}
        assert len(ingested) == 1

    def test_colision_de_row_hash_dispara_value_error(self) -> None:
        rows: list[dict[str, object]] = [
            {"cod_art": "0001"},
            {"cod_art": "0001"},  # duplicado exacto
        ]
        with pytest.raises(ValueError, match="colision de _row_hash"):
            _enrich(rows)

    def test_metadatos_estaticos_se_propagan(self) -> None:
        rows: list[dict[str, object]] = [{"cod_art": "0001"}]
        result = _enrich(rows)
        assert result[0]["_source_empresa"] == "tinito"
        assert result[0]["_dt"] == "2025-01-15"
        assert result[0]["_query_id"] == "articulos_v1"
        assert result[0]["_query_version"] == "1.0.0"
        assert result[0]["_run_id"] == "run-abc"
        assert result[0]["_batch_id"] == "batch-xyz"
        assert result[0]["_sql_hash"] == "a" * 64
        assert result[0]["_payload_hash"] == "b" * 64
