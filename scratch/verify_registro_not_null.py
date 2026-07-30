from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf")

sql = """
SELECT
  COUNT(*) as total_filas,
  COUNTIF(registro IS NULL) as registro_nulls,
  COUNTIF(fecha_registro IS NULL) as fecha_registro_nulls,
  MIN(registro) as fecha_minima,
  MAX(registro) as fecha_maxima
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
"""

print("=== VERIFICACIÓN FINAL DE LA COLUMNA REGISTRO EN GOLD ===")
for r in client.query(sql).result():
    print(dict(r))
