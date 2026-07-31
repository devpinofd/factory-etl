"""Script para verificar ejecuciones de Workflows y Cloud Scheduler usando BigQuery y gcloud CLI"""

import subprocess
import json
from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
LOCATION = "us-central1"
WORKFLOW_NAME = "factory-etl-workflow-dev"

bq_client = bigquery.Client(project=PROJECT_ID, location=LOCATION)

def check_bigquery_control_logs():
    print("==========================================================================")
    print("  1. VERIFICANDO REGISTROS EN CONTROL TABLES (etl_runs & etl_batches)")
    print("==========================================================================")
    
    query_runs = """
    SELECT
      run_id,
      status,
      triggered_by,
      start_time,
      end_time,
      total_batches,
      successful_batches,
      failed_batches
    FROM `factory-etl-dev-0y1dhf.factory_etl_control_dev.etl_runs`
    ORDER BY start_time DESC
    LIMIT 10;
    """
    
    try:
        runs = list(bq_client.query(query_runs).result())
        if not runs:
            print("  ℹ️ No se encontraron registros en etl_runs.")
        else:
            print(f"  ✓ Registros en etl_runs ({len(runs)} ejecuciones):")
            for r in runs:
                print("  ", dict(r))
    except Exception as e:
        print(f"  ⚠️ Error en etl_runs: {e}")

def check_gcloud_workflows_executions():
    print("\n==========================================================================")
    print("  2. CONSULTANDO EJECUCIONES EN CLOUD WORKFLOWS (gcloud CLI)")
    print("==========================================================================")
    
    cmd = f"gcloud workflows executions list {WORKFLOW_NAME} --location={LOCATION} --format=json --limit=10"
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            items = json.loads(res.stdout)
            print(f"  ✓ Se encontraron {len(items)} ejecuciones de Workflows:")
            for item in items:
                name = item.get("name", "").split("/")[-1]
                state = item.get("state")
                start = item.get("startTime")
                end = item.get("endTime")
                print(f"  • Execution ID: {name} | Estado: {state} | Inicio: {start} | Fin: {end}")
        else:
            print(f"  ⚠️ Mensaje de gcloud: {res.stderr or res.stdout}")
    except Exception as e:
        print(f"  ⚠️ Error ejecutando gcloud workflows: {e}")

def check_gcloud_scheduler_jobs():
    print("\n==========================================================================")
    print("  3. CONSULTANDO TRABAJOS DE CLOUD SCHEDULER (gcloud CLI)")
    print("==========================================================================")
    
    cmd = f"gcloud scheduler jobs list --location={LOCATION} --format=json"
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            jobs = json.loads(res.stdout)
            print(f"  ✓ Se encontraron {len(jobs)} cron jobs configurados en Cloud Scheduler:")
            for job in jobs:
                name = job.get("name", "").split("/")[-1]
                schedule = job.get("schedule")
                state = job.get("state")
                last_attempt = job.get("lastAttemptTime")
                status = job.get("status", {})
                print(f"  • Job: {name} | Horario: '{schedule}' | Estado: {state} | Último intento: {last_attempt} | Resultado: {status}")
        else:
            print(f"  ⚠️ Mensaje de gcloud: {res.stderr or res.stdout}")
    except Exception as e:
        print(f"  ⚠️ Error ejecutando gcloud scheduler: {e}")

if __name__ == "__main__":
    check_bigquery_control_logs()
    check_gcloud_workflows_executions()
    check_gcloud_scheduler_jobs()
