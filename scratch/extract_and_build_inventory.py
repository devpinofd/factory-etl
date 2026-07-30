"""Script para ejecutar la extracción de renglones_almacenes_v1 en las 5 empresas y consolidar la tabla Silver sil_renglones_almacenes"""

import os
import subprocess

os.environ["FACTORY_ETL_GCP_PROJECT"] = "factory-etl-dev-0y1dhf"
os.environ["FACTORY_ETL_BRONZE_BUCKET"] = "factory-etl-dev-0y1dhf-bronze"
os.environ["FACTORY_ETL_CONTROL_DATASET"] = "factory_etl_control_dev"

PROJECT_ID = "factory-etl-dev-0y1dhf"
EMPRESAS = ["tinito", "ctb", "daroan", "roldan", "ctm"]

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True, env=os.environ)
    return res.stdout, res.stderr

def extract_inventory():
    print("==========================================================================")
    print("  EXTRAYENDO INVENTARIO COMPLETO (renglones_almacenes_v1) PARA 5 EMPRESAS")
    print("==========================================================================")

    for emp in EMPRESAS:
        print(f"  • Ingestando inventario para empresa '{emp}'...")
        cmd_run = f"uv run python -m factory_etl.cli run-batch --query-id renglones_almacenes_v1 --source-empresa {emp} --dt 2026-07-30"
        out, err = run_cmd(cmd_run)
        print(f"    ✓ {emp}: finalizado.")

    print("\n  • Reconstruyendo tabla Silver sil_renglones_almacenes en BigQuery...")
    cmd_build = "uv run python scratch/build_all_medallion_tables.py"
    run_cmd(cmd_build)

    # Probar la consulta de reporte
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT_ID)
    
    sql_inventario = """
    SELECT
      ra.source_empresa,
      ra.cod_alm,
      COALESCE(alm.nom_alm, ra.cod_alm) AS nombre_almacen,
      ra.cod_art,
      COALESCE(art.nom_art, ra.cod_art) AS nombre_articulo,
      art.modelo,
      art.cod_mar,
      ra.exi_act1 AS stock_actual,
      art.cap_bulto,
      SAFE_DIVIDE(ra.exi_act1, NULLIF(art.cap_bulto, 0)) AS stock_cajas,
      (ra.exi_act1 * COALESCE(art.peso, 0)) AS peso_total_kg,
      ra.registro AS fecha_actualizacion
    FROM `factory-etl-dev-0y1dhf.factory_etl_silver.sil_renglones_almacenes` ra
    LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_almacenes` alm
      ON ra.source_empresa = alm.source_empresa AND ra.cod_alm = alm.cod_alm
    LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_articulos` art
      ON ra.source_empresa = art.source_empresa AND ra.cod_art = art.cod_art
    WHERE ra.exi_act1 > 0
    ORDER BY ra.source_empresa, ra.cod_alm, ra.exi_act1 DESC
    LIMIT 10;
    """
    print("\n  📊 MUESTRA DEL REPORTE EN BIGQUERY (STOCK > 0):")
    for r in client.query(sql_inventario).result():
        print("  ", dict(r))

if __name__ == "__main__":
    extract_inventory()
