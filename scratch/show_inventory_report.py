from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf")

sql_inventario = """
SELECT
  ra.source_empresa AS empresa,
  ra.cod_alm,
  COALESCE(alm.nom_alm, ra.cod_alm) AS nombre_almacen,
  ra.cod_art,
  COALESCE(art.nom_art, ra.cod_art) AS nombre_articulo,
  art.modelo,
  art.cod_mar,
  ra.exi_act1 AS stock_unidades,
  art.cap_bulto AS unidades_por_caja,
  SAFE_DIVIDE(ra.exi_act1, NULLIF(art.cap_bulto, 0)) AS stock_cajas,
  (ra.exi_act1 * COALESCE(art.peso, 0)) AS peso_total_kg,
  ra.registro AS fecha_actualizacion
FROM `factory-etl-dev-0y1dhf.factory_etl_silver.sil_renglones_almacenes` ra
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_almacenes` alm
  ON ra.source_empresa = alm.source_empresa AND ra.cod_alm = alm.cod_alm
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_articulos` art
  ON ra.source_empresa = art.source_empresa AND ra.cod_art = art.cod_art
WHERE ra.exi_act1 > 0
ORDER BY ra.source_empresa, ra.cod_alm, ra.exi_act1 DESC
LIMIT 10;
"""

print("=== MUESTRA DEL REPORTE DE INVENTARIO CON STOCK > 0 EN BIGQUERY ===")
for r in client.query(sql_inventario).result():
    print(dict(r))
