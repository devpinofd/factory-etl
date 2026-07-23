"""Tests de los helpers de identificadores y hashes."""

from __future__ import annotations

import uuid

from factory_etl.ids import (
    batch_id,
    new_run_id,
    payload_hash,
    row_hash,
    sha256_hex,
    sql_hash,
)


class TestRunId:
    def test_es_uuid_valido(self) -> None:
        rid = new_run_id()
        parsed = uuid.UUID(rid)
        assert str(parsed) == rid

    def test_dos_llamadas_producen_ids_distintos(self) -> None:
        assert new_run_id() != new_run_id()


class TestSha256Hex:
    def test_string_y_bytes_producen_mismo_hash(self) -> None:
        assert sha256_hex("hola") == sha256_hex(b"hola")

    def test_hash_es_hex_de_64_caracteres(self) -> None:
        h = sha256_hex("x")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestSqlHash:
    def test_mismo_sql_mismo_hash(self) -> None:
        assert sql_hash("select 1") == sql_hash("select 1")

    def test_sql_distinto_hash_distinto(self) -> None:
        assert sql_hash("select 1") != sql_hash("select 2")


class TestPayloadHash:
    def test_bytes_identicos_mismo_hash(self) -> None:
        b = b'{"d": {"laTablas": [[]]}}'
        assert payload_hash(b) == payload_hash(b)

    def test_bom_afecta_el_hash(self) -> None:
        # Diseno intencional: bytes distintos -> hash distinto. La normalizacion
        # de BOM ocurre downstream, no en payload_hash.
        without_bom = b'{"a": 1}'
        with_bom = b"\xef\xbb\xbf" + without_bom
        assert payload_hash(without_bom) != payload_hash(with_bom)


class TestBatchId:
    def test_es_deterministico(self) -> None:
        common = {
            "source_empresa": "tinito",
            "query_id": "articulos_v1",
            "dt": "2026-07-22",
            "payload_hash_hex": "a" * 64,
        }
        assert batch_id(**common) == batch_id(**common)

    def test_cambio_de_empresa_cambia_el_id(self) -> None:
        a = batch_id(
            source_empresa="tinito",
            query_id="articulos_v1",
            dt="2026-07-22",
            payload_hash_hex="a" * 64,
        )
        b = batch_id(
            source_empresa="ctb",
            query_id="articulos_v1",
            dt="2026-07-22",
            payload_hash_hex="a" * 64,
        )
        assert a != b

    def test_cambio_de_payload_cambia_el_id(self) -> None:
        a = batch_id(
            source_empresa="tinito",
            query_id="articulos_v1",
            dt="2026-07-22",
            payload_hash_hex="a" * 64,
        )
        b = batch_id(
            source_empresa="tinito",
            query_id="articulos_v1",
            dt="2026-07-22",
            payload_hash_hex="b" * 64,
        )
        assert a != b


class TestRowHash:
    def test_valores_iguales_mismo_hash(self) -> None:
        row = ["0000000001", "REGISTRO", 0.0, "A"]
        assert row_hash(row) == row_hash(row)

    def test_orden_distinto_hash_distinto(self) -> None:
        a = row_hash(["a", "b", "c"])
        b = row_hash(["b", "a", "c"])
        assert a != b

    def test_null_se_distingue_del_string_none(self) -> None:
        # Muy importante: la fila (None,) no debe colisionar con la fila ("None",).
        assert row_hash([None]) != row_hash(["None"])

    def test_null_se_distingue_de_string_vacio(self) -> None:
        assert row_hash([None]) != row_hash([""])
