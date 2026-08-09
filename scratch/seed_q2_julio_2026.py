"""Script de Seed para la Segunda Quincena de Julio 2026 (2026-07-16 a 2026-07-31)
1. Extrae de eFactory (ventas_diarias_v2, renglones_monedas_v1, etc.) para las 5 empresas.
2. Escribe los archivos JSONL.GZ a GCS Bronze.
3. Reconstruye e inserta las capas Staging, Silver y Gold (fct_ventas y dimensiones).
"""

import sys
import os
import time
from datetime import date

os.environ["FACTORY_ETL_GCP_PROJECT"] = "factory-etl-dev-0y1dhf"
os.environ["FACTORY_ETL_BRONZE_BUCKET"] = "factory-etl-dev-0y1dhf-bronze"
os.environ["FACTORY_ETL_CONTROL_DATASET"] = "factory_etl_control_dev"
os.environ["FACTORY_ETL_QUARANTINE_BUCKET"] = "factory-etl-dev-0y1dhf-quarantine"
os.environ["FACTORY_ETL_ENV"] = "dev"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from factory_etl.config import Settings
from factory_etl.bootstrap import build_extractor
from factory_etl.ids import new_run_id
from scratch.build_all_medallion_tables import build_all

EMPRESAS = ["tinito", "ctb", "daroan", "roldan", "ctm"]
QUERIES_TRANSACTIONAL = ["ventas_diarias_v2", "renglones_monedas_v1"]

FEC_DES = "2026-07-16"
FEC_HAS = "2026-07-31"

def run_seed_q2_julio_2026():
    print("==========================================================================", flush=True)
    print(f"  EJECUTANDO SEED: SEGUNDA QUINCENA DE JULIO 2026 ({FEC_DES} AL {FEC_HAS})", flush=True)
    print("==========================================================================", flush=True)

    settings = Settings()
    extractor = build_extractor(settings)

    total_success = 0
    total_errors = 0

    for emp_idx, emp in enumerate(EMPRESAS, 1):
        print(f"\n>>>> PROCESANDO EMPRESA [{emp_idx}/{len(EMPRESAS)}]: {emp.upper()} <<<<", flush=True)
        params = {"fec_des": FEC_DES, "fec_has": FEC_HAS, "registro": FEC_HAS}

        for q_id in QUERIES_TRANSACTIONAL:
            run_id = new_run_id()
            try:
                res = extractor.run_batch(
                    query_id=q_id,
                    source_empresa=emp,
                    dt=FEC_HAS,
                    run_id=run_id,
                    parameter_values=params,
                )
                print(f"  [{FEC_DES} -> {FEC_HAS}] {q_id:<22} -> OK ({res.record_count} filas | {res.status})", flush=True)
                total_success += 1
                time.sleep(0.3)
            except Exception as ex:
                print(f"  [{FEC_DES} -> {FEC_HAS}] {q_id:<22} -> ERROR: {ex}", flush=True)
                total_errors += 1

    print("\n==========================================================================", flush=True)
    print(f"  SEED BRONZE FINALIZADO: {total_success} OK / {total_errors} Errores", flush=True)
    print("  Reconstruyendo capas Staging, Silver y Gold en BigQuery...", flush=True)
    print("==========================================================================", flush=True)

    # Reconstruir la arquitectura Medallion completa en BigQuery
    build_all()

if __name__ == "__main__":
    run_seed_q2_julio_2026()
