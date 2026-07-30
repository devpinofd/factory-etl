import subprocess
import time
import json

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return res.stdout, res.stderr

def fix_and_trigger():
    print("==========================================================================")
    print("  CORRECCIÓN Y PRUEBA DE ACTIVACIÓN DE CLOUD SCHEDULER -> WORKFLOWS")
    print("==========================================================================")

    # 1. Add IAM Binding
    print("\n1. ASIGNANDO ROL roles/workflows.invoker A LA CUENTA DE SERVICIO:")
    cmd_iam = (
        'gcloud projects add-iam-policy-binding factory-etl-dev-0y1dhf '
        '--member="serviceAccount:factory-etl-runtime-dev@factory-etl-dev-0y1dhf.iam.gserviceaccount.com" '
        '--role="roles/workflows.invoker"'
    )
    out1, err1 = run_cmd(cmd_iam)
    print("  ✓ Rol roles/workflows.invoker asignado.")

    # 2. Update Cloud Scheduler to OAuth Token
    print("\n2. ACTUALIZANDO CONFIGURACIÓN DE AUTENTICACIÓN EN CLOUD SCHEDULER:")
    cmd_update = (
        'gcloud scheduler jobs update http factory-etl-daily-scheduler-dev '
        '--location=us-central1 '
        '--oauth-service-account-email="factory-etl-runtime-dev@factory-etl-dev-0y1dhf.iam.gserviceaccount.com" '
        '--oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"'
    )
    out2, err2 = run_cmd(cmd_update)
    print("  ✓ Cloud Scheduler actualizado con OAuth Token (scope: cloud-platform).")

    # 3. Trigger Scheduler Job
    print("\n3. FORZANDO ACTIVACIÓN MANUAL DEL SCHEDULER (gcloud scheduler jobs run):")
    cmd_run = "gcloud scheduler jobs run factory-etl-daily-scheduler-dev --location=us-central1"
    out3, err3 = run_cmd(cmd_run)
    print(f"  ✓ Disparo del Scheduler ejecutado.")

    # 4. Wait 5s and check Workflow executions
    time.sleep(5)
    print("\n4. VERIFICANDO EJECUCIONES EN CLOUD WORKFLOWS:")
    cmd_check = "gcloud workflows executions list factory-etl-daily-dev --location=us-central1 --format=json"
    out4, _ = run_cmd(cmd_check)
    try:
        execs = json.loads(out4)
        if not execs:
            print("  ⚠️ No se encontraron ejecuciones aún.")
        else:
            latest = execs[0]
            exec_id = latest.get("name", "").split("/")[-1]
            state = latest.get("state", "")
            start = latest.get("startTime", "")
            print(f"  🎉 ¡EJECUCIÓN DISPARADA EXITOSAMENTE POR EL SCHEDULER!")
            print(f"     - Execution ID: {exec_id}")
            print(f"     - Estado: {state}")
            print(f"     - Hora de Inicio: {start}")
    except Exception as ex:
        print(f"  Error leyendo ejecuciones: {ex}")

if __name__ == "__main__":
    fix_and_trigger()
