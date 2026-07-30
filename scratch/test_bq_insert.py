from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf", location="us-central1")
table_id = "factory-etl-dev-0y1dhf.factory_etl_control_dev.etl_events"

rows = [{
    "event_id": "test12345",
    "run_id": "run123",
    "batch_id": "batch123",
    "entity": "test",
    "phase": "test",
    "event_type": "test",
    "duration_ms": 10,
    "extras": "{}",
    "inserted_at": "2026-07-30T14:00:00Z"
}]

print("=== PROBANDO INSERT_ROWS_JSON DIRECTO ===")
errors = client.insert_rows_json(table_id, rows)
print("Errors:", errors)
