"""Tests del catalogo de consultas."""

from __future__ import annotations

import pytest

from factory_etl.errors import CompanyNotAllowedError, QueryNotFoundError
from factory_etl.factory_queries.catalog import ARTICULOS_V1, ARTICULOS_V2, get, list_query_ids
from factory_etl.factory_queries.models import Category, LoadStrategy, Transport


class TestListQueryIds:
    def test_incluye_articulos_v1(self) -> None:
        assert "articulos_v1" in list_query_ids()

    def test_incluye_articulos_v2(self) -> None:
        assert "articulos_v2" in list_query_ids()


class TestGet:
    def test_devuelve_query_definition_para_empresa_autorizada(self) -> None:
        qdef = get("articulos_v1", source_empresa="tinito")
        assert qdef is ARTICULOS_V1

    def test_devuelve_query_definition_v2_para_empresa_autorizada(self) -> None:
        qdef = get("articulos_v2", source_empresa="tinito")
        assert qdef is ARTICULOS_V2

    def test_rechaza_query_inexistente(self) -> None:
        with pytest.raises(QueryNotFoundError):
            get("no_existe", source_empresa="tinito")

    def test_rechaza_empresa_no_autorizada(self) -> None:
        with pytest.raises(CompanyNotAllowedError):
            get("articulos_v1", source_empresa="empresa_invalida")


class TestArticulosV1:
    """Snapshot de las propiedades declaradas de la consulta piloto."""

    def test_metadata(self) -> None:
        assert ARTICULOS_V1.query_id == "articulos_v1"
        assert ARTICULOS_V1.category is Category.MASTER
        assert ARTICULOS_V1.transport is Transport.GENERIC_SQL_API
        assert ARTICULOS_V1.load_strategy is LoadStrategy.FULL_SNAPSHOT
        assert ARTICULOS_V1.natural_key == ("source_empresa", "cod_art")
        assert "tinito" in ARTICULOS_V1.allowed_companies
        assert "ctb" in ARTICULOS_V1.allowed_companies
        assert ARTICULOS_V1.reject_empty is True
        assert ARTICULOS_V1.parameters == ()

    def test_required_columns_matchean_diseño(self) -> None:
        assert set(ARTICULOS_V1.required_columns) == {"cod_art", "nom_art", "cod_uni1", "status"}

    def test_sql_existe_y_menciona_la_tabla(self) -> None:
        sql = ARTICULOS_V1.read_sql()
        assert "from articulos" in sql.lower()
        assert "tipo" in sql.lower()

    def test_sql_no_contiene_cast_ni_rtrim(self) -> None:
        """Regla de arquitectura: limpieza de tipos y padding vive en Silver, no aqui."""
        sql = ARTICULOS_V1.read_sql().lower()
        assert "cast(" not in sql
        assert "rtrim(" not in sql

    def test_schema_json_existe(self) -> None:
        assert ARTICULOS_V1.schema_path.exists()


class TestArticulosV2:
    """Snapshot de las propiedades de la consulta articulos_v2."""

    def test_metadata(self) -> None:
        assert ARTICULOS_V2.query_id == "articulos_v2"
        assert ARTICULOS_V2.category is Category.MASTER
        assert ARTICULOS_V2.transport is Transport.GENERIC_SQL_API
        assert ARTICULOS_V2.load_strategy is LoadStrategy.FULL_SNAPSHOT
        assert ARTICULOS_V2.natural_key == ("source_empresa", "cod_art")
        assert "tinito" in ARTICULOS_V2.allowed_companies
        assert "ctb" in ARTICULOS_V2.allowed_companies
        assert ARTICULOS_V2.reject_empty is True

    def test_sql_incluye_tipo(self) -> None:
        sql = ARTICULOS_V2.read_sql()
        assert "from articulos" in sql.lower()
        assert "tipo" in sql.lower()

