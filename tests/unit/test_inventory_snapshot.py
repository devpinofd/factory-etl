from pathlib import Path

DEFINITIONS = Path(__file__).resolve().parents[2] / "dataform" / "definitions"
GOLD = DEFINITIONS / "gold"


def test_gold_selects_the_whole_capture_before_joining_its_detail() -> None:
    sql = (GOLD / "fct_inventario_snapshot.sqlx").read_text(encoding="utf-8")
    assert "disabled:" not in sql
    assert "WHERE estado = 'COMPLETA'" in sql
    assert "PARTITION BY source_empresa, dia_venezuela" in sql
    assert "ORDER BY captura DESC, run_id DESC" in sql
    assert sql.index("QUALIFY ROW_NUMBER()") < sql.index("JOIN ganadoras g")
    assert "h.source_empresa = g.source_empresa AND h.run_id = g.run_id" in sql
    assert "g.dia_venezuela AS snapshot_date" in sql
    assert "h._ingested_at," in sql
    assert "snapshot_date = DATE(_ingested_at, 'America/Caracas')" in sql
    assert "PARTITION BY h.source_empresa, h.snapshot_date, h.cod_alm" not in sql
    assert "COALESCE(h._ingested_at, h.registro" not in sql


def test_capture_quality_is_generic_and_available_in_regular_consolidation() -> None:
    sql = (GOLD / "vw_inventario_capturas_qa.sqlx").read_text(encoding="utf-8")
    assert "enableMondelez" not in sql
    assert "source_empresa IN" not in sql
    assert "DATE(c.captura, 'America/Caracas')" in sql
    for condition in (
        "r.status IS DISTINCT FROM 'success'",
        "c.filas_cargadas != r.record_count",
        "c.claves_distintas != c.filas_cargadas",
        "c.marcas_ingesta != 1",
    ):
        assert condition in sql


def test_capture_receipts_are_declared_without_sort_models() -> None:
    sql = (GOLD / "etl_batches.sqlx").read_text(encoding="utf-8")
    assert 'type: "declaration"' in sql
    assert 'name: "etl_batches"' in sql
    assert 'dataform.projectConfig.vars.controlDataset || "factory_etl_control"' in sql
    assert not (DEFINITIONS / "mondelez" / "mondelez_etl_batches.sqlx").exists()


def test_gold_assertion_reconciles_capture_identity_and_row_count() -> None:
    sql = (GOLD / "assert_inventario_snapshot_captura_unica.sqlx").read_text(encoding="utf-8")
    assert "disabled:" not in sql
    assert "COUNT(DISTINCT run_id)" in sql
    assert "FULL JOIN actuales" in sql
    assert "a.run_id != e.run_id" in sql
    assert "a.filas != e.filas_cargadas" in sql


def test_silver_retains_utc_partitions_and_all_capture_ids() -> None:
    sql = (DEFINITIONS / "silver" / "sil_renglones_almacenes_historico.sqlx").read_text(
        encoding="utf-8"
    )
    assert 'type: "incremental"' in sql
    assert 'uniqueKey: ["source_empresa", "snapshot_date", "run_id", "cod_alm", "cod_art"]' in sql
    assert 'partitionBy: "snapshot_date"' in sql
    assert "SAFE_CAST(DATE(_ingested_at) AS DATE) AS snapshot_date" in sql
