import subprocess
import json

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return res.stdout, res.stderr

def check_all():
    print("==========================================================================")
    print("  ESTADO DE CLOUD SCHEDULER Y CLOUD WORKFLOWS EN GCP")
    print("==========================================================================")

    # 1. Scheduler Job
    out, _ = run_cmd("gcloud scheduler jobs list --location=us-central1 --format=json")
    try:
        jobs = json.loads(out)
        for j in jobs:
            name = j.get("name", "").split("/")[-1]
            schedule = j.get("schedule", "")
            state = j.get("state", "")
            last_attempt = j.get("lastAttemptTime", "")
            print(f"1. CLOUD SCHEDULER JOB:")
            print(f"   • Nombre: {name}")
            print(f"   • Expresión Cron: '{schedule}'")
            print(f"   • Estado: {state}")
            print(f"   • Última Ejecución: {last_attempt}")
    except Exception as e:
        print(f"Error parseando scheduler: {e}")

    # 2. Logs de Cloud Scheduler
    print("\n2. ÚLTIMOS LOGS DE CLOUD SCHEDULER (gcloud logging):")
    out_logs, _ = run_cmd('gcloud logging read "resource.type=cloud_scheduler_job" --limit 5 --format=json')
    try:
        logs = json.loads(out_logs)
        if not logs:
            print("   ⚠️ No hay logs recientes registrados para Cloud Scheduler.")
        else:
            for l in logs:
                ts = l.get("timestamp", "")
                severity = l.get("severity", "")
                text = l.get("textPayload", "") or l.get("jsonPayload", "")
                print(f"   • [{ts}] {severity}: {text}")
    except Exception as e:
        print(f"   Error al leer logs: {e}")

    # 3. Workflows Executions
    print("\n3. CLOUD WORKFLOWS (factory-etl-daily-dev):")
    out_wf, _ = run_cmd("gcloud workflows executions list factory-etl-daily-dev --location=us-central1 --format=json")
    try:
        wf_list = json.loads(out_wf)
        print(f"   ✓ Total ejecuciones encontradas: {len(wf_list)}")
        for w in wf_list[:5]:
            e_id = w.get("name", "").split("/")[-1]
            st = w.get("state", "")
            s_time = w.get("startTime", "")
            e_time = w.get("endTime", "")
            print(f"   • ID: {e_id} | Estado: {st} | Inicio: {s_time} | Fin: {e_time}")
    except Exception as e:
        print(f"   Error al leer ejecuciones de workflow: {e}")

if __name__ == "__main__":
    check_all()
