"""Script para crear la vista analítica vw_evolucion_inventario_sellin en BigQuery Gold
Permite analizar la evolución temporal de existencias y Sell-In cruzando con dim_tiempo (Año, Mes, Trimestre, Semana, Quincena)
por Empresa, Sucursal, Proveedor, Marca y SKU.
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_evolucion_inventario_sellin` AS
SELECT
  ra.source_empresa AS empresa,
  ra.cod_alm AS codigo_sucursal,
  COALESCE(alm.nom_alm, ra.cod_alm) AS nombre_sucursal,
  ra.cod_art AS codigo_articulo,
  COALESCE(art.nom_art, ra.cod_art) AS nombre_articulo,
  art.modelo,
  art.cod_mar AS marca,
  art.cod_pro AS codigo_proveedor,
  COALESCE(pro.nom_pro, art.cod_pro) AS nombre_proveedor,
  
  -- 🗓️ DIMENSIÓN DE TIEMPO COMERCIAL
  t.fecha,
  t.anio,
  t.mes,
  t.nombre_mes,
  t.anio_mes,
  t.trimestre,
  t.trimestre_nombre,
  t.anio_trimestre,
  t.semana_del_anio,
  t.anio_semana,
  t.quincena_nombre,
  
  -- 📊 EXISTENCIAS EN ESA FECHA COMERCIAL (SNAPSHOT DIARIO / HISTÓRICO)
  ra.exi_act1 AS stock_unidades_snapshot,
  art.cap_bulto AS unidades_por_caja,
  ROUND(SAFE_DIVIDE(ra.exi_act1, NULLIF(art.cap_bulto, 0)), 2) AS stock_cajas_snapshot,
  ROUND((ra.exi_act1 * COALESCE(art.peso, 0)), 2) AS peso_total_kg_snapshot,
  
  ra.registro AS fecha_ultima_actualizacion
FROM `factory-etl-dev-0y1dhf.factory_etl_silver.sil_renglones_almacenes` ra
INNER JOIN `factory-etl-dev-0y1dhf.factory_etl_gold.dim_tiempo` t
  ON DATE(ra.registro) = t.fecha
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_almacenes` alm
  ON ra.source_empresa = alm.source_empresa AND ra.cod_alm = alm.cod_alm
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_articulos` art
  ON ra.source_empresa = art.source_empresa AND ra.cod_art = art.cod_art
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_proveedores` pro
  ON art.source_empresa = pro.source_empresa AND art.cod_pro = pro.cod_pro;
"""

def create_evolucion_view():
    print("==========================================================================")
    print("  CREANDO VISTA EN BIGQUERY: vw_evolucion_inventario_sellin")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_evolucion_inventario_sellin' creada exitosamente en BigQuery Gold.")

    # Consulta de prueba por Trimestre, Mes y Semana
    sql_test = """
    SELECT
      empresa,
      nombre_sucursal,
      anio_trimestre,
      anio_mes,
      nombre_mes,
      nombre_proveedor,
      marca,
      codigo_articulo,
      nombre_articulo,
      stock_unidades_snapshot,
      stock_cajas_snapshot
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_evolucion_inventario_sellin`
    WHERE stock_unidades_snapshot > 0
    ORDER BY fecha DESC, stock_unidades_snapshot DESC
    LIMIT 8;
    """
    print("\n  📊 MUESTRA DE EVOLUCIÓN TEMPORAL DE INVENTARIOS EN FECHA COMERCIAL:")
    for r in client.query(sql_test).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_evolucion_view()
