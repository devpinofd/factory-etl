"""Script para Corregir y Desplegar el Cloud Workflow (factory-etl-daily-dev)
Asegura que renglones_almacenes_v1 tenga has_param: false para ejecutarse como Snapshot de Inventario diario junto con ventas_diarias_v2 en el Scheduler.
"""

import os
import subprocess

PROJECT_ID = "factory-etl-dev-0y1dhf"
REGION = "us-central1"
WORKFLOW_NAME = "factory-etl-daily-dev"

WORKFLOW_YAML = """main:
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
              - id: "renglones_monedas_v1"
                has_param: true
              - id: "renglones_aprecios_v1"
                has_param: true
              - id: "renglones_almacenes_v1"
                has_param: false
              - id: "articulos_v1"
                has_param: false
              - id: "impuestos_v1"
                has_param: false
              - id: "departamentos_v1"
                has_param: false
              - id: "marcas_v1"
                has_param: false
              - id: "secciones_v1"
                has_param: false
              - id: "proveedores_v1"
                has_param: false
              - id: "paises_v1"
                has_param: false
              - id: "estados_v1"
                has_param: false
              - id: "ciudades_v1"
                has_param: false
              - id: "vendedores_v1"
                has_param: false
              - id: "sucursales_v1"
                has_param: false
              - id: "almacenes_v1"
                has_param: false
              - id: "clientes_v1"
                has_param: false
              - id: "clases_clientes_v1"
                has_param: false
              - id: "conceptos_v1"
                has_param: false

    # =========================================================================
    # OPTIMIZACION CONCURRENCY 10 CON PARALELISMO PLANO (< 5 MINUTOS)
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

def deploy_workflow():
    print("==========================================================================")
    print("  DESPLEGANDO Y ACTUALIZANDO CLOUD WORKFLOW (factory-etl-daily-dev)")
    print("==========================================================================")

    yaml_path = os.path.join(os.path.dirname(__file__), "rendered_workflow.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(WORKFLOW_YAML)

    cmd = f"gcloud workflows deploy {WORKFLOW_NAME} --location={REGION} --source={yaml_path}"
    print(f"  • Ejecutando: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        print("  🎉 Workflow desplegado exitosamente en GCP.")
    else:
        print("  ❌ Error desplegando workflow:", res.stderr)

if __name__ == "__main__":
    deploy_workflow()
