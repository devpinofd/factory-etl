"""Script para ejecutar el Workflow para 2026-07-29 y refrescar BigQuery Medallion"""

import subprocess
import json
import time

PROJECT_ID = "factory-etl-dev-0y1dhf"
REGION = "us-central1"
WORKFLOW_NAME = "factory-etl-daily-dev"

def execute():
    print("==========================================================================")
    print("  EJECUTANDO CATCH-UP EN CLOUD WORKFLOWS PARA EL DÍA 2026-07-29")
    print("==========================================================================")

    # 1. Disparar con gcloud workflows run
    cmd_run = f'gcloud workflows run {WORKFLOW_NAME} --location={REGION} --data="{{\\"target_date\\":\\"2026-07-29\\"}}" --format=json'
    print("  • Lanzando Workflow en GCP...")
    res = subprocess.run(cmd_run, capture_output=True, text=True, shell=True)
    
    try:
        data = json.loads(res.stdout)
        exec_name = data.get("name", "")
        exec_id = exec_name.split("/")[-1]
        state = data.get("state", "")
        print(f"    ✓ Execution ID: {exec_id}")
        print(f"    ✓ Estado Inicial: {state}")
    except Exception as ex:
        print(f"  ❌ Error parseando salida: {ex}")
        print(f"  STDOUT: {res.stdout}")
        print(f"  STDERR: {res.stderr}")
        return

    # 2. Monitorear estado hasta terminar
    print("\n  • Monitoreando avance del Workflow en GCP...")
    cmd_desc = f"gcloud workflows executions describe {exec_id} --workflow={WORKFLOW_NAME} --location={REGION} --format=json"
    
    current_state = state
    for i in range(40):
        time.sleep(10)
        res_d = subprocess.run(cmd_desc, capture_output=True, text=True, shell=True)
        try:
            d_info = json.loads(res_d.stdout)
            current_state = d_info.get("state", "")
            print(f"    - [{(i+1)*10}s] Estado: {current_state}")
            if current_state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                break
        except Exception:
            pass

    if current_state != "SUCCEEDED":
        print(f"  ❌ La ejecución en Cloud Workflows finalizó con estado: {current_state}")
        return

    print("\n  🎉 ¡Ingesta Bronze finalizada con ÉXITO en GCP para 2026-07-29!")

    # 3. Consolidar BigQuery Silver & Gold
    print("\n  • Reconstruyendo y Deduplicando Silver y Gold en BigQuery...")
    res_b = subprocess.run("uv run python scratch/build_all_medallion_tables.py", capture_output=True, text=True, shell=True)
    print(res_b.stdout)

if __name__ == "__main__":
    execute()
