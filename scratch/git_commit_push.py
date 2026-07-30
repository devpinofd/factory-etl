"""Script para realizar git add, commit y push al repositorio remoto origin/main"""

import subprocess

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    print(f"=== CMD: {cmd}")
    if res.stdout:
        print("STDOUT:\n", res.stdout)
    if res.stderr:
        print("STDERR:\n", res.stderr)
    return res.returncode

def commit_and_push():
    print("==========================================================================")
    print("  EJECUTANDO GIT ADD, COMMIT Y PUSH EN origin/main")
    print("==========================================================================")

    # 1. git add .
    run_cmd("git add .")

    # 2. git commit
    msg = (
        "feat: Medallion 19 entities, Dataform, GPS derivation, Quarters, Dual Schedule & Bugfixes\n\n"
        "- Added 19 master and transaction SQL queries & JSON schemas to catalog\n"
        "- Built BigQuery Medallion Architecture (19 Staging, 19 Silver, 9 Gold Dimensions & fct_ventas)\n"
        "- Derived GPS latitude & longitude columns in sil_clientes and dim_cliente\n"
        "- Added quarterly time segmentation (trimestre, trimestre_nombre, anio_trimestre) to dim_tiempo & fct_ventas\n"
        "- Fixed .NET DateTime subsecond timestamp parsing (COALESCE + PARSE_TIMESTAMP)\n"
        "- Added Dataform project structure in dataform/ (staging, silver, gold, helpers.js)\n"
        "- Updated Cloud Workflows to support date parameterization (target_date / dt)\n"
        "- Configured Cloud Scheduler dual-schedule (5:30 PM & 11:45 PM VET) for early cut & late sales\n"
        "- Updated Terraform modules (Artifact Registry, Cloud Run Jobs, Cloud Scheduler, Workflows)\n"
    )
    
    commit_code = run_cmd(f'git commit -m "{msg}"')

    # 3. git push
    print("\n  • Enviando cambios al repositorio remoto (git push origin main)...")
    push_code = run_cmd("git push origin main")
    
    if push_code == 0:
        print("\n  🎉 ¡PUSH COMPLETADO EXITOSAMENTE A origin/main!")
    else:
        print("\n  ❌ Ocurrió un error al hacer git push.")

if __name__ == "__main__":
    commit_and_push()
