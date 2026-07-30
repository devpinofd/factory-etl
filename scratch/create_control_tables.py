from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf", location="us-central1")

# Create etl_events
sql_events = """
CREATE TABLE IF NOT EXISTS `factory-etl-dev-0y1dhf.factory_etl_control_dev.etl_events` (
  event_id STRING,
  run_id STRING,
  batch_id STRING,
  entity STRING,
  phase STRING,
  event_type STRING,
  duration_ms INT64,
  extras STRING,
  inserted_at TIMESTAMP
)
"""
client.query(sql_events).result()
print("✓ Tabla etl_events creada exitosamente en us-central1.")
