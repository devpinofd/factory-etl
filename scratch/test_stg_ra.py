from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf")

sql = """
CREATE OR REPLACE EXTERNAL TABLE `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_test_ra`
(
  cod_alm STRING,
  cod_art STRING,
  exi_act1 FLOAT64,
  registro STRING
)
WITH PARTITION COLUMNS (source_empresa STRING, dt STRING, run_id STRING)
OPTIONS(
  format = 'NEWLINE_DELIMITED_JSON',
  uris = ['gs://factory-etl-dev-0y1dhf-bronze/bronze/renglones_almacenes_v1/*'],
  hive_partition_uri_prefix = 'gs://factory-etl-dev-0y1dhf-bronze/bronze/renglones_almacenes_v1/'
);
"""
print("=== CREANDO EXTERNAL TABLE STG_TEST_RA CON 3 PARTITION KEYS ===")
client.query(sql).result()

sql_count = "SELECT source_empresa, dt, COUNT(*) as total FROM `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_test_ra` GROUP BY 1, 2"
for r in client.query(sql_count).result():
    print(dict(r))

sql_sample = "SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_test_ra` WHERE exi_act1 > 0 LIMIT 5"
print("\n=== MUESTRA DE STOCK > 0 EN STG_TEST_RA ===")
for r in client.query(sql_sample).result():
    print(dict(r))
