"""Script para revisar los logs de Cloud Scheduler e inspeccionar su última ejecución"""

from google.cloud import logging

PROJECT_ID = "factory-etl-dev-0y1dhf"

def check_logs():
    client = logging.Client(project=PROJECT_ID)
    print("==========================================================================")
    print("  LOGS DE CLOUD SCHEDULER (factory-etl-daily-scheduler-dev)")
    print("==========================================================================")

    logger = client.logger("cloudscheduler.googleapis.com%2Fexecutions")
    
    # Query logs for cloud scheduler
    filter_str = 'resource.type="cloud_scheduler_job" AND resource.labels.job_id="factory-etl-daily-scheduler-dev"'
    entries = list(client.list_entries(filter_=filter_str, max_results=10))

    if not entries:
        print("  ⚠️ No se encontraron logs recientes de Cloud Scheduler con ese filtro.")
    else:
        print(f"  ✓ Se encontraron {len(entries)} eventos de ejecución en Cloud Scheduler:")
        for e in entries:
            payload = e.payload if isinstance(e.payload, dict) else e.payload
            print(f"  • [{e.timestamp}] Severity: {e.severity} | Message/Payload: {payload}")

if __name__ == "__main__":
    check_logs()
