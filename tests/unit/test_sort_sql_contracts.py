import re
from pathlib import Path

import pytest

from tests.unit.mondelez_sql import read_mondelez_sql

ROOT = Path(__file__).parents[2] / "dataform" / "definitions" / "mondelez"
REPO_ROOT = Path(__file__).resolve().parents[2]


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
    assert f'dependencies: ["vw_mondelez_{name}_interna"]' in sql
    assert f'ref("vw_mondelez_{name}_interna")' not in sql


@pytest.mark.parametrize(
    ("name", "sources"),
    [
        ("sort_clientes", {"dim_cliente", "dim_pais", "dim_estado", "dim_ciudad", "dim_vendedor"}),
        (
            "sort_ventas",
            {
                "fct_ventas_gold",
                "dim_cliente",
                "dim_pais",
                "dim_estado",
                "dim_ciudad",
                "dim_articulo",
                "dim_proveedor",
            },
        ),
        ("sort_existencias", {"fct_inventario_snapshot", "dim_articulo", "dim_almacen"}),
        ("vw_mondelez_articulos", {"dim_articulo", "dim_mondelez_producto_canonico"}),
    ],
)
def test_public_sql_reads_only_gold_sources(name: str, sources: set[str]) -> None:
    sql = read_mondelez_sql(name)
    assert set(re.findall(r'\$\{ref\("([^"]+)"\)\}', sql)) == sources
    assert "pub_mondelez_existencias" not in sql
    assert "inventario_publication_lock" not in sql


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
    sql = read_mondelez_sql(filename)
    assert "dependOnDependencyAssertions: true" in sql


def test_active_deployment_contains_only_the_sql_integration() -> None:
    terraform = REPO_ROOT / "terraform"
    files = [
        *terraform.glob("*.tf"),
        *terraform.glob("envs/*.tfvars"),
        *terraform.glob("envs/*.tfvars.example"),
        *terraform.glob("tests/*.hcl"),
        *terraform.glob("modules/**/*.tf"),
        *terraform.glob("modules/**/*.tftpl"),
    ]
    forbidden = (
        "mondelez_api",
        "mondelez-api",
        "mondelez_dataform_editor",
        "google_bigquery_dataset.mondelez",
        "factory_etl_mondelez",
        "archive/mondelez",
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        for reference in forbidden:
            assert reference not in text, f"{path}: {reference}"


def test_views_use_the_sort_runtime_dependency_and_remain_paused() -> None:
    terraform = REPO_ROOT / "terraform"
    main = (terraform / "main.tf").read_text(encoding="utf-8")
    consolidation = main.split('module "workflows_consolidation" {', 1)[1].split("\n}", 1)[0]
    assert "enable_mondelez       = var.enable_mondelez_views" in consolidation
    assert "google_bigquery_dataset_iam_member.sort_runtime_editor" in consolidation

    for path in (terraform / "envs").glob("*.tfvars"):
        assert "enable_mondelez_views" not in path.read_text(encoding="utf-8")


def test_current_deployment_documentation_has_no_http_scope() -> None:
    for relative in (
        "docs/despliegue-vistas-sort-mondelez.md",
        "docs/handoff-sort-mondelez.md",
    ):
        text = (REPO_ROOT / relative).read_text(encoding="utf-8").lower()
        assert not re.search(r"\bapi\b|https?://|mondelez[_-]api", text)


@pytest.mark.parametrize(
    ("filename", "timestamp", "field"),
    [
        ("vw_mondelez_ventas", "v.registro", "FECHA_ACTUALIZACION"),
        ("vw_mondelez_existencias_candidata", "i.captura", "FECHA_DATA"),
        ("vw_mondelez_existencias", "_captured_at", "FECHA_DATA"),
    ],
)
def test_contract_datetimes_use_venezuela_time(filename: str, timestamp: str, field: str) -> None:
    sql = read_mondelez_sql(filename)
    assert f"FORMAT_TIMESTAMP('%Y%m%d%H%M%S', {timestamp}, 'America/Caracas') AS {field}" in sql
    assert f"FORMAT_TIMESTAMP('%Y%m%d%H%M%S', {timestamp}, 'UTC') AS {field}" not in sql
    assert "CURRENT_TIMESTAMP()" not in sql


def test_inventory_reads_dynamic_gold_without_rewriting_published_history() -> None:
    sql = read_mondelez_sql("vw_mondelez_existencias")
    candidate = read_mondelez_sql("vw_mondelez_existencias_candidata")
    assert 'FROM ${ref("vw_mondelez_existencias_candidata")}' in sql
    assert 'FROM ${ref("fct_inventario_snapshot")}' in candidate
    assert "_ingested_at AS captura" in candidate
    assert "PARTITION BY source_empresa, FECHA_SNAPSHOT, CODIGO_GRUPO, CODIGO_SKU" in sql
    assert "* EXCEPT (FECHA_DATA, claves_publicas, _cod_art)" in sql
    assert "pub_mondelez_existencias" not in sql
    assert "fct_inventario_diario_validado" not in candidate
    assert "PARSE_TIMESTAMP" not in sql
    assert "UPDATE " not in sql
    assert "Contrato inventario invalido" in sql
    assert "Maestro de articulo faltante" in candidate
    assert "Maestro de almacen faltante" in candidate
    assert "Maestro de articulo ambiguo" in candidate
    assert "Maestro de almacen ambiguo" in candidate
    assert "ERROR(" in sql


def test_sales_calendar_and_datetime_origin_are_not_changed() -> None:
    sql = read_mondelez_sql("vw_mondelez_ventas")
    assert "FORMAT_DATE('%Y%m%d', DATE(v.registro)) AS FECHA" in sql
    assert "AND DATE(v.registro) >= DATE '2025-01-01'" in sql
