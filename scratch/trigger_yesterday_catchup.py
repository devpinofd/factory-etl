"""Script para disparar el Workflow con target_date='2026-07-29' y refrescar BigQuery Medallion"""

import subprocess
import json
import time

PROJECT_ID = "factory-etl-dev-0y1dhf"
REGION = "us-central1"
WORKFLOW_NAME = "factory-etl-daily-dev"

def run_catchup():
    print("==========================================================================")
    print("  EJECUTANDO RECUPERACIÓN / CATCH-UP PARA EL DÍA DE AYER (2026-07-29)")
    print("==========================================================================")

    # 1. Disparar Cloud Workflows pasando target_date='2026-07-29'
    print("\n1. DISPARANDO CLOUD WORKFLOW CON DATA: {'target_date': '2026-07-29'}...")
    cmd_str = f'gcloud workflows executions run {WORKFLOW_NAME} --location={REGION} --data="{{\\"target_date\\":\\"2026-07-29\\"}}" --format=json'
    res = subprocess.run(cmd_str, capture_output=True, text=True, shell=True)
    out_trig = res.stdout
    err_trig = res.stderr
    
    try:
        exec_info = json.loads(out_trig)
        exec_name = exec_info.get("name", "")
        exec_id = exec_name.split("/")[-1]
        print(f"  ✓ Workflow disparado exitosamente con ID: {exec_id}")
    except Exception as ex:
        print(f"  ❌ Error parseando respuesta de disparo: {ex}")
        print(f"  STDOUT: {out_trig}")
        print(f"  STDERR: {err_trig}")
        return

    # 2. Monitorear estado hasta terminar
    print("\n2. MONITOREANDO EJECUCIÓN EN CLOUD WORKFLOWS...")
    cmd_desc = f"gcloud workflows executions describe {exec_id} --workflow={WORKFLOW_NAME} --location={REGION} --format=json"
    
    state = "RUNNING"
    for i in range(40):
        time.sleep(10)
        res_d = subprocess.run(cmd_desc, capture_output=True, text=True, shell=True)
        try:
            d_info = json.loads(res_d.stdout)
            state = d_info.get("state", "")
            print(f"   • [{(i+1)*10}s] Estado actual: {state}")
            if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                break
        except Exception as ex:
            print(f"   • Error consultando estado: {ex}")

    if state != "SUCCEEDED":
        print(f"  ❌ La ejecución finalizó con estado: {state}")
        return

    print("  🎉 Ingesta Bronze finalizada con ÉXITO para 2026-07-29.")

    # 3. Consolidar en BigQuery Silver y Gold
    print("\n3. RECONSTRUYENDO Y DEDUPLICANDO CAPAS SILVER Y GOLD EN BIGQUERY...")
    cmd_build = "uv run python scratch/build_all_medallion_tables.py"
    res_b = subprocess.run(cmd_build, capture_output=True, text=True, shell=True)
    print(res_b.stdout)
    if res_b.stderr:
        print(res_b.stderr)

if __name__ == "__main__":
    run_catchup()
