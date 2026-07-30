from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf")

sql_stg_count = "SELECT COUNT(*) as total FROM `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_renglones_almacenes`"
for r in client.query(sql_stg_count).result():
    print(f"Total en stg_renglones_almacenes: {r.total:,}")
