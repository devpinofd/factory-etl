"""Script para Desplegar el Flujo Rápido Nocturno (factory-etl-nightly-dev) y Actualizar Cloud Scheduler
- Corte de la Tarde (5:30 PM VET): Workflow Completo (19 Consultas: Maestras + Ventas + Inventarios)
- Corte de la Noche (11:45 PM VET): Workflow Rápido Nocturno (3 Consultas: Ventas + Inventarios + Monedas)
"""

import os
import subprocess

PROJECT_ID = "factory-etl-dev-0y1dhf"
REGION = "us-central1"

NIGHTLY_WORKFLOW_YAML = """main:
  params: [args]
  steps:
    - init:
        assign:
          - project_id: "factory-etl-dev-0y1dhf"
          - region: "us-central1"
          - job_name: "factory-etl-articulos-dev"
          - dt_param: ${default(map.get(args, "target_date"), default(map.get(args, "dt"), "TODAY"))}
          - empresas: ["tinito", "ctb", "daroan", "roldan", "ctm"]
          - queries_list:
              - id: "ventas_diarias_v2"
                has_param: true
              - id: "renglones_almacenes_v1"
                has_param: false
              - id: "renglones_monedas_v1"
                has_param: true

    # =========================================================================
    # CORTE RAPIDO NOCTURNO EXCLUSIVO DE VENTAS E INVENTARIOS (< 1 MINUTO)
    # =========================================================================

    - process_empresas_in_parallel:
        parallel:
          for:
            value: emp
            in: ${empresas}
            steps:
              - process_all_queries_flat_in_parallel:
                  parallel:
                    concurrency_limit: 10
                    for:
                      value: q
                      in: ${queries_list}
                      steps:
                        - prepare_default_args:
                            assign:
                              - cmd_args:
                                  - "run-batch"
                                  - "--query-id"
                                  - ${q.id}
                                  - "--source-empresa"
                                  - ${emp}
                                  - "--dt"
                                  - ${dt_param}
                        - check_param_switch:
                            switch:
                              - condition: ${q.has_param}
                                assign:
                                  - cmd_args:
                                      - "run-batch"
                                      - "--query-id"
                                      - ${q.id}
                                      - "--source-empresa"
                                      - ${emp}
                                      - "--dt"
                                      - ${dt_param}
                                      - "-p"
                                      - ${"fec_des=" + dt_param}
                                      - "-p"
                                      - ${"fec_has=" + dt_param}
                        - run_job:
                            call: googleapis.run.v2.projects.locations.jobs.run
                            args:
                              name: "projects/factory-etl-dev-0y1dhf/locations/us-central1/jobs/factory-etl-articulos-dev"
                              body:
                                overrides:
                                  containerOverrides:
                                    - args: ${cmd_args}

    - return_success:
        return:
          status: "SUCCESS"
          queries_processed: ${len(empresas) * len(queries_list)}
"""

def deploy_nightly_workflow():
    print("==========================================================================")
    print("  DESPLEGANDO WORKFLOW NOCTURNO RÁPIDO (factory-etl-nightly-dev)")
    print("==========================================================================")

    yaml_path = os.path.join(os.path.dirname(__file__), "rendered_nightly_workflow.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(NIGHTLY_WORKFLOW_YAML)

    # 1. Desplegar Workflow Nocturno
    cmd_wf = f"gcloud workflows deploy factory-etl-nightly-dev --location={REGION} --source={yaml_path}"
    print(f"  • Ejecutando: {cmd_wf}")
    res_wf = subprocess.run(cmd_wf, shell=True, capture_output=True, text=True)
    if res_wf.returncode == 0:
        print("  🎉 Workflow nocturno factory-etl-nightly-dev desplegado exitosamente.")
    else:
        print("  ❌ Error desplegando workflow nocturno:", res_wf.stderr)

    # 2. Configurar Scheduler Nocturno (11:45 PM VET / 03:45 UTC)
    print("\n--- CONFIGURANDO CLOUD SCHEDULER NOCTURNO ---")
    cmd_sch = (
        f"gcloud scheduler jobs create http factory-etl-nightly-scheduler-dev "
        f"--location={REGION} "
        f'--schedule="45 3 * * *" '
        f'--time-zone="Etc/UTC" '
        f'--uri="https://workflowexecutions.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/workflows/factory-etl-nightly-dev/executions" '
        f"--http-method=POST "
        f'--oauth-service-account-email="factory-etl-runtime-dev@{PROJECT_ID}.iam.gserviceaccount.com" '
        f'--message-body="{{}}" '
        f'--headers="Content-Type=application/json"'
    )
    print("  • Creando/Actualizando Job de Cloud Scheduler Nocturno...")
    res_sch = subprocess.run(cmd_sch, shell=True, capture_output=True, text=True)
    if res_sch.returncode == 0:
        print("  🎉 Cloud Scheduler Nocturno configurado a las 11:45 PM VET.")
    else:
        # Intentar update si ya existe
        cmd_sch_up = (
            f"gcloud scheduler jobs update http factory-etl-nightly-scheduler-dev "
            f"--location={REGION} "
            f'--schedule="45 3 * * *" '
            f'--uri="https://workflowexecutions.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/workflows/factory-etl-nightly-dev/executions"'
        )
        res_up = subprocess.run(cmd_sch_up, shell=True, capture_output=True, text=True)
        if res_up.returncode == 0:
            print("  🎉 Cloud Scheduler Nocturno actualizado a las 11:45 PM VET.")
        else:
            print("  ⚠️ Nota Scheduler:", res_sch.stderr or res_up.stderr)

if __name__ == "__main__":
    deploy_nightly_workflow()
