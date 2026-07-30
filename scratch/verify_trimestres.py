from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf")

sql = """
SELECT
  trimestre,
  trimestre_nombre,
  anio_trimestre,
  COUNT(*) as total_ventas
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
GROUP BY 1, 2, 3
ORDER BY 3 DESC
LIMIT 8
"""

print("=== VERIFICACIÓN DE TRIMESTRES EN FCT_VENTAS ===")
for r in client.query(sql).result():
    print(dict(r))
