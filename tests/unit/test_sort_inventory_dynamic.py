from .mondelez_sql import read_mondelez_sql


def test_sort_reads_the_gold_capture_without_another_publication() -> None:
    candidate = read_mondelez_sql("vw_mondelez_existencias_candidata")
    internal = read_mondelez_sql("vw_mondelez_existencias")
    assert 'FROM ${ref("fct_inventario_snapshot")}' in candidate
    assert "_ingested_at AS captura" in candidate
    assert "fct_inventario_diario_validado" not in candidate
    assert 'FROM ${ref("vw_mondelez_existencias_candidata")}' in internal
    assert "pub_mondelez_existencias" not in internal
    assert "* EXCEPT (FECHA_DATA, claves_publicas, _cod_art)" in internal
    assert "FORMAT_TIMESTAMP('%Y%m%d%H%M%S', _captured_at, 'America/Caracas')" in internal
    assert "CURRENT_TIMESTAMP()" not in internal
    assert "UPDATE " not in internal


def test_dynamic_inventory_keeps_capture_boundaries_and_explicit_contract_errors() -> None:
    candidate = read_mondelez_sql("vw_mondelez_existencias_candidata")
    internal = read_mondelez_sql("vw_mondelez_existencias")
    assert "GROUP BY i.source_empresa, i.dia_venezuela, i.run_id, i.captura" in candidate
    assert "PARTITION BY source_empresa, FECHA_SNAPSHOT, CODIGO_GRUPO, CODIGO_SKU" in internal
    assert "Maestro de articulo ambiguo" in candidate
    assert "Maestro de almacen ambiguo" in candidate
    assert "Maestro de articulo faltante" in candidate
    assert "Maestro de almacen faltante" in candidate
    assert "WHEN UPPER(TRIM(i.cod_alm)) = 'TRANSITO' THEN FALSE" in candidate
    assert "WHEN a.cod_pro IS DISTINCT FROM '0301' THEN FALSE" in candidate
    assert "ABS(DISPONIBLE) < 10000000000" in internal
    assert "DISPONIBLE * 100 = TRUNC(DISPONIBLE * 100)" in internal
    assert "UNIDAD_SIMPLE_X_EMPAQUE * 100 = TRUNC(UNIDAD_SIMPLE_X_EMPAQUE * 100)" in internal
    assert internal.count("ERROR(") == 2
