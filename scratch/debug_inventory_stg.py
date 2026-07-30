from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf")

sql = "SELECT source_empresa, dt, COUNT(*) as total FROM `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_renglones_almacenes` GROUP BY 1, 2"
print("=== REGISTROS EN STG_RENGLONES_ALMACENES ===")
for r in client.query(sql).result():
    print(dict(r))

sql_sil = "SELECT source_empresa, COUNT(*) as total FROM `factory-etl-dev-0y1dhf.factory_etl_silver.sil_renglones_almacenes` GROUP BY 1"
print("\n=== REGISTROS EN SIL_RENGLONES_ALMACENES ===")
for r in client.query(sql_sil).result():
    print(dict(r))
