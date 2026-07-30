from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf")

sql = """
SELECT
  registro,
  SAFE_CAST(registro AS TIMESTAMP) as raw_cast,
  SAFE_CAST(SUBSTR(registro, 1, 23) AS TIMESTAMP) as substr_cast,
  SAFE_CAST(REGEXP_REPLACE(registro, r'(\\.\\d{6})\\d+', r'\\1') AS TIMESTAMP) as regex_cast,
  PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S', registro) as parse_cast
FROM `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_ventas_diarias`
WHERE registro IS NOT NULL
LIMIT 5
"""

print("=== DEPURACIÓN DE CAST DE TIMESTAMP EN BIGQUERY ===")
for r in client.query(sql).result():
    print(dict(r))
