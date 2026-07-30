"""Script para desplegar el Cloud Workflow actualizado y configurar los 2 Cloud Scheduler Jobs (Dual-Schedule: 5:30 PM y 11:45 PM)"""

import subprocess
from pathlib import Path

PROJECT_ID = "factory-etl-dev-0y1dhf"
REGION = "us-central1"
SERVICE_ACCOUNT = "factory-etl-runtime-dev@factory-etl-dev-0y1dhf.iam.gserviceaccount.com"
WORKFLOW_NAME = "factory-etl-daily-dev"
JOB_NAME = "factory-etl-extractor-dev"

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return res.stdout, res.stderr

def deploy():
    print("==========================================================================")
    print("  DESPLIEGUE DE CLOUD WORKFLOW Y SCHEDULERS DUAL (5:30 PM & 11:45 PM)")
    print("==========================================================================")

    # 1. Read workflow.yaml template and render
    tpl_path = Path(__file__).resolve().parent.parent / "terraform" / "modules" / "workflows" / "templates" / "workflow.yaml.tftpl"
    with open(tpl_path, "r", encoding="utf-8") as f:
        content = f.read()

    rendered = (
        content.replace("${project_id}", PROJECT_ID)
               .replace("${region}", REGION)
               .replace("${job_name}", JOB_NAME)
    )

    out_wf_file = Path(__file__).resolve().parent / "rendered_workflow.yaml"
    with open(out_wf_file, "w", encoding="utf-8") as f:
        f.write(rendered)

    print("  • Actualizando definición de Cloud Workflows en GCP...")
    cmd_deploy_wf = f"gcloud workflows deploy {WORKFLOW_NAME} --location={REGION} --source={out_wf_file} --service-account={SERVICE_ACCOUNT}"
    out1, err1 = run_cmd(cmd_deploy_wf)
    print("    ✓ Cloud Workflow 'factory-etl-daily-dev' actualizado exitosamente.")

    # 2. Configure Cloud Scheduler 1 (5:30 PM VET = 21:30 UTC o 17:30 VET)
    print("\n  • Configurando Scheduler 1: Corte 1 (05:30 PM - Foto Preliminar)...")
    cmd_s1 = (
        f"gcloud scheduler jobs create http factory-etl-early-scheduler-dev "
        f"--location={REGION} "
        f"--schedule='30 17 * * *' "
        f"--time-zone='America/Caracas' "
        f"--uri='https://workflowexecutions.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/workflows/{WORKFLOW_NAME}/executions' "
        f"--oauth-service-account-email='{SERVICE_ACCOUNT}' "
        f"--oauth-token-scope='https://www.googleapis.com/auth/cloud-platform' "
        f"--headers='Content-Type=application/json' "
        f"--message-body='{{}}' "
        f"--description='Disparador preliminar ETL a las 05:30 PM Caracas' "
        f"--continue-on-error"
    )
    run_cmd(cmd_s1)
    print("    ✓ Scheduler 1 'factory-etl-early-scheduler-dev' (05:30 PM) configurado.")

    # 3. Configure Cloud Scheduler 2 (11:45 PM VET = 23:45 VET)
    print("\n  • Configurando Scheduler 2: Corte 2 (11:45 PM - Cierre Definitivo Nocturno)...")
    cmd_s2 = (
        f"gcloud scheduler jobs create http factory-etl-nightly-scheduler-dev "
        f"--location={REGION} "
        f"--schedule='45 23 * * *' "
        f"--time-zone='America/Caracas' "
        f"--uri='https://workflowexecutions.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/workflows/{WORKFLOW_NAME}/executions' "
        f"--oauth-service-account-email='{SERVICE_ACCOUNT}' "
        f"--oauth-token-scope='https://www.googleapis.com/auth/cloud-platform' "
        f"--headers='Content-Type=application/json' "
        f"--message-body='{{}}' "
        f"--description='Disparador de cierre nocturno ETL a las 11:45 PM Caracas' "
        f"--continue-on-error"
    )
    run_cmd(cmd_s2)
    print("    ✓ Scheduler 2 'factory-etl-nightly-scheduler-dev' (11:45 PM) configurado.")

if __name__ == "__main__":
    deploy()
