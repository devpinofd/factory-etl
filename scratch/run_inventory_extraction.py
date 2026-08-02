"""Script para ejecutar la extracción real de renglones_almacenes_v1 y almacenes_v1 en las 5 empresas hacia GCS Bronze y reconstruir Silver/Gold"""

import os
import sys
import uuid
from datetime import date

os.environ["FACTORY_ETL_GCP_PROJECT"] = "factory-etl-dev-0y1dhf"
os.environ["FACTORY_ETL_BRONZE_BUCKET"] = "factory-etl-dev-0y1dhf-bronze"
os.environ["FACTORY_ETL_CONTROL_DATASET"] = "factory_etl_control_dev"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from factory_etl.bootstrap import build_extractor
from factory_etl.config import Settings
from scratch.build_all_medallion_tables import build_all

PROJECT_ID = "factory-etl-dev-0y1dhf"
EMPRESAS = ["tinito", "ctb", "daroan", "roldan", "ctm"]
DT_TODAY = date.today().strftime("%Y-%m-%d")

def run_inventory_full_sync():
    print("==========================================================================")
    print(f"  SINCRONIZANDO INVENTARIO Y ALMACENES (dt={DT_TODAY}) PARA LAS 5 EMPRESAS")
    print("==========================================================================")
    
    settings = Settings(
        gcp_project=PROJECT_ID,
        bronze_bucket="factory-etl-dev-0y1dhf-bronze",
        control_dataset="factory_etl_control_dev"
    )
    
    extractor = build_extractor(settings)
    
    for q_id in ["almacenes_v1", "renglones_almacenes_v1"]:
        run_id = str(uuid.uuid4())
        print(f"\n>>>> PROCESANDO {q_id.upper()} <<<<")
        for emp in EMPRESAS:
            try:
                res = extractor.run_batch(
                    query_id=q_id,
                    source_empresa=emp,
                    dt=DT_TODAY,
                    run_id=run_id
                )
                print(f"    ✓ [{emp.upper()}]: Status '{res.status}', Filas: {res.record_count or 0:,}")
            except Exception as ex:
                print(f"    ❌ [{emp.upper()}]: Error: {ex}")

    print("\n==========================================================================")
    print("  RECONSTRUYENDO CAPAS STAGING, SILVER Y GOLD (INVENTARIO) EN BIGQUERY")
    print("==========================================================================")
    build_all()

if __name__ == "__main__":
    run_inventory_full_sync()
