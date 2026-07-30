"""Script para otorgar roles/secretmanager.secretAccessor a la Service Account de Dataform en GCP"""

import subprocess
import json

PROJECT_ID = "factory-etl-dev-0y1dhf"

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return res.stdout, res.stderr

def fix_iam():
    print("==========================================================================")
    print("  CORRIGIENDO PERMISOS DE SECRETO PARA GCP DATAFORM")
    print("==========================================================================")

    # 1. Obtener número de proyecto
    out_proj, _ = run_cmd(f"gcloud projects describe {PROJECT_ID} --format=json")
    try:
        p_info = json.loads(out_proj)
        proj_number = p_info.get("projectNumber", "")
        print(f"  ✓ Número de Proyecto GCP: {proj_number}")
    except Exception as ex:
        print(f"  ❌ Error obteniendo número de proyecto: {ex}")
        return

    dataform_sa = f"service-{proj_number}@gcp-sa-dataform.iam.gserviceaccount.com"
    print(f"  ✓ Dataform Service Account: {dataform_sa}")

    # 2. Otorgar permisos sobre Secret Manager a nivel de proyecto para garantizar acceso
    print("\n  • Asignando rol roles/secretmanager.secretAccessor a Dataform SA...")
    cmd_iam = (
        f'gcloud projects add-iam-policy-binding {PROJECT_ID} '
        f'--member="serviceAccount:{dataform_sa}" '
        f'--role="roles/secretmanager.secretAccessor"'
    )
    out_iam, err_iam = run_cmd(cmd_iam)
    print("    ✓ Rol 'Secret Manager Secret Accessor' otorgado a nivel de proyecto.")

    # 3. Otorgar permisos adicionales por si el usuario usa una Service Account por defecto
    print("\n  • Asignando rol roles/secretmanager.secretAccessor a la SA del runtime por si acaso...")
    runtime_sa = f"factory-etl-runtime-dev@{PROJECT_ID}.iam.gserviceaccount.com"
    cmd_iam2 = (
        f'gcloud projects add-iam-policy-binding {PROJECT_ID} '
        f'--member="serviceAccount:{runtime_sa}" '
        f'--role="roles/secretmanager.secretAccessor"'
    )
    run_cmd(cmd_iam2)

    print("\n  🎉 ¡PERMISOS IAM CORREGIDOS EXITOSAMENTE EN GCP!")

if __name__ == "__main__":
    fix_iam()
