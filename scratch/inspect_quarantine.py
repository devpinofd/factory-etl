import os
from google.cloud import storage, bigquery
import json

os.environ.setdefault("FACTORY_ETL_GCP_PROJECT", "factory-etl-dev-0y1dhf")

def inspect_all_quarantine():
    print("==========================================================================")
    print("  ANÁLISIS COMPLETO DE BATCHES EN CUARENTENA")
    print("==========================================================================")

    # 1. GCS Quarantine Bucket
    gcs = storage.Client(project="factory-etl-dev-0y1dhf")
    bucket = gcs.bucket("factory-etl-dev-0y1dhf-quarantine")
    blobs = list(bucket.list_blobs(prefix="quarantine/"))

    print(f"\n1. ARCHIVOS EN GCS CUARENTENA (Total archivos: {len(blobs)}):")
    for b in blobs:
        print(f"\n  • Ruta: gs://factory-etl-dev-0y1dhf-quarantine/{b.name}")
        print(f"    - Tamaño: {b.size} bytes | Fecha: {b.updated}")
        content = b.download_as_text()
        try:
            payload = json.loads(content)
            print(f"    - Estructura JSON: {list(payload.keys())}")
        except Exception:
            print(f"    - Contenido no JSON (primeros 200 caracteres):\n      {content[:200]}")

    # 2. BigQuery etl_batches (status = 'quarantined')
    print("\n2. BIGQUERY: BATCHES EN CUARENTENA (etl_batches):")
    bq = bigquery.Client(project="factory-etl-dev-0y1dhf")
    query_batches = """
    SELECT
      batch_id,
      run_id,
      entity,
      source_empresa,
      dt,
      status,
      object_uri,
      inserted_at
    FROM `factory-etl-dev-0y1dhf.factory_etl_control.etl_batches`
    WHERE status = 'quarantined'
    ORDER BY inserted_at DESC
    LIMIT 100
    """
    batch_rows = list(bq.query(query_batches).result())
    print(f"  Total batches en estado 'quarantined' en BigQuery: {len(batch_rows)}")
    for r in batch_rows:
        print(f"  • [{r.inserted_at}] empresa={r.source_empresa} | entity={r.entity} | dt={r.dt} | run_id={r.run_id}")
        print(f"    URI: {r.object_uri}")

    # 3. BigQuery etl_events (event_type LIKE '%QUARANTIN%')
    print("\n3. BIGQUERY: EVENTOS DE CUARENTENA (etl_events):")
    query_events = """
    SELECT
      run_id,
      event_type,
      phase,
      entity,
      extras,
      occurred_at
    FROM `factory-etl-dev-0y1dhf.factory_etl_control.etl_events`
    WHERE LOWER(event_type) LIKE '%quarantin%'
    ORDER BY occurred_at DESC
    LIMIT 100
    """
    event_rows = list(bq.query(query_events).result())
    print(f"  Total eventos de cuarentena en BigQuery: {len(event_rows)}")
    for r in event_rows:
        print(f"  • [{r.occurred_at}] event={r.event_type} | phase={r.phase} | entity={r.entity}")
        print(f"    extras={r.extras}")

if __name__ == "__main__":
    inspect_all_quarantine()
