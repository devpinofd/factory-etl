from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2] / "dataform" / "definitions" / "mondelez"


@pytest.mark.parametrize(
    ("name", "count"),
    [("clientes", 17), ("ventas", 24), ("existencias", 9)],
)
def test_sql_projection_has_only_company_and_business_fields(name: str, count: int) -> None:
    sql = (ROOT / f"sort_{name}.sqlx").read_text(encoding="utf-8")
    projection = sql.split("\nSELECT\n", 1)[1].split("\nFROM", 1)[0]
    fields = [field.strip() for field in projection.split(",")]
    assert fields[0] == "source_empresa"
    assert len(fields) == count + 1
    assert len(set(fields)) == len(fields)
    assert all(not field.startswith("_") for field in fields)
    assert "ID_LINEA" not in fields
    assert 'schema: "sort"' in sql
    assert f'ref("vw_mondelez_{name}_interna")' in sql


def test_publication_lock_uses_the_single_sort_dataset() -> None:
    sql = (ROOT / "pub_mondelez_existencias.sqlx").read_text(encoding="utf-8")
    assert "factory_etl_mondelez" not in sql
    assert sql.count(".sort.inventario_publication_lock`") == 2


@pytest.mark.parametrize(
    "filename",
    [
        "pub_mondelez_existencias",
        "sort_clientes",
        "sort_ventas",
        "sort_existencias",
        "vw_mondelez_articulos",
        "vw_mondelez_clientes",
        "vw_mondelez_ventas",
        "vw_mondelez_existencias",
        "vw_mondelez_existencias_candidata",
        "dim_mondelez_articulo_enriquecido",
        "fct_inventario_diario_validado",
    ],
)
def test_managed_dataform_gates_dependency_assertions(filename: str) -> None:
    sql = (ROOT / f"{filename}.sqlx").read_text(encoding="utf-8")
    assert "dependOnDependencyAssertions: true" in sql
