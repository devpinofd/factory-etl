"""Script para crear la Vista Guardada vw_reporte_inventario en el dataset factory_etl_gold en BigQuery"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_reporte_inventario` AS
SELECT
  ra.source_empresa AS empresa,
  ra.cod_alm AS codigo_almacen,
  COALESCE(alm.nom_alm, ra.cod_alm) AS nombre_almacen,
  ra.cod_art AS codigo_articulo,
  COALESCE(art.nom_art, ra.cod_art) AS nombre_articulo,
  art.modelo,
  art.cod_mar AS marca,
  ra.exi_act1 AS stock_unidades,
  art.cap_bulto AS unidades_por_caja,
  
  -- 📦 Cálculo Físico de Cajas y Kilogramos
  SAFE_DIVIDE(ra.exi_act1, NULLIF(art.cap_bulto, 0)) AS stock_cajas,
  ROUND((ra.exi_act1 * COALESCE(art.peso, 0)), 2) AS peso_total_kg,
  
  ra.registro AS fecha_ultima_actualizacion
FROM `factory-etl-dev-0y1dhf.factory_etl_silver.sil_renglones_almacenes` ra
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_almacenes` alm
  ON ra.source_empresa = alm.source_empresa AND ra.cod_alm = alm.cod_alm
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_articulos` art
  ON ra.source_empresa = art.source_empresa AND ra.cod_art = art.cod_art
WHERE ra.exi_act1 > 0;
"""

def create_view():
    print("==========================================================================")
    print("  CREANDO VISTA EN BIGQUERY: factory_etl_gold.vw_reporte_inventario")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_reporte_inventario' creada exitosamente en BigQuery Gold.")

    # Verificar conteo desde la vista
    res = list(client.query("SELECT COUNT(*) as total FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_reporte_inventario`").result())
    print(f"  ✓ Total filas accesibles en la vista: {res[0].total:,}")

if __name__ == "__main__":
    create_view()
