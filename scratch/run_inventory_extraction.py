"""Script para ejecutar la extracción real de renglones_almacenes_v1 en las 5 empresas hacia GCS Bronze"""

import os
import uuid

os.environ["FACTORY_ETL_GCP_PROJECT"] = "factory-etl-dev-0y1dhf"
os.environ["FACTORY_ETL_BRONZE_BUCKET"] = "factory-etl-dev-0y1dhf-bronze"
os.environ["FACTORY_ETL_CONTROL_DATASET"] = "factory_etl_control_dev"

from factory_etl.bootstrap import build_extractor
from factory_etl.config import Settings

PROJECT_ID = "factory-etl-dev-0y1dhf"
EMPRESAS = ["tinito", "ctb", "daroan", "roldan", "ctm"]

def run_extraction():
    print("==========================================================================")
    print("  EXTRAYENDO RENGLONES_ALMACENES_V1 (INVENTARIO EN VIVO) PARA 5 EMPRESAS")
    print("==========================================================================")
    
    settings = Settings(
        gcp_project=PROJECT_ID,
        bronze_bucket="factory-etl-dev-0y1dhf-bronze",
        control_dataset="factory_etl_control_dev"
    )
    
    extractor = build_extractor(settings)
    run_id = str(uuid.uuid4())
    
    for emp in EMPRESAS:
        print(f"  • Extrayendo existencias para empresa '{emp}'...")
        res = extractor.run_batch(
            query_id="renglones_almacenes_v1",
            source_empresa=emp,
            dt="2026-07-30",
            run_id=run_id
        )
        print(f"    ✓ {emp}: Status '{res.status}', Filas extraídas: {res.record_count or 0:,}")

if __name__ == "__main__":
    run_extraction()
