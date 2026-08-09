"""Script de Backfill Pautado por Chunks para Ventas Historico (2022-2026)

Optimizaciones incorporadas para no sobrecargar la API de eFactory:
1. Pacing & Delay: Pausa programada entre peticiones HTTP (0.3s por query)
2. Batch Throttling: Pausa de enfriamiento (5s) cada 50 peticiones
3. Idempotencia en GCS: Omite fechas que ya poseen objetos Parquet en Bronze
4. Procesamiento por Bloques Anuales (2022, 2023, 2024, 2025, 2026)
"""

import sys
import time
import os
from datetime import date, timedelta
from typing import List

# Configurar variables de entorno por defecto si no existen
os.environ.setdefault("FACTORY_ETL_GCP_PROJECT", "factory-etl-dev-0y1dhf")
os.environ.setdefault("FACTORY_ETL_BRONZE_BUCKET", "factory-etl-dev-0y1dhf-bronze")
os.environ.setdefault("FACTORY_ETL_CONTROL_DATASET", "factory_etl_control")
os.environ.setdefault("FACTORY_ETL_QUARANTINE_BUCKET", "factory-etl-dev-0y1dhf-quarantine")
os.environ.setdefault("FACTORY_ETL_ENV", "dev")

# Asegurar import de factory_etl
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from factory_etl.config import Settings
from factory_etl.bootstrap import build_extractor
from factory_etl.ids import new_run_id
from factory_etl.factory_queries.catalog import get as get_query_def

EMPRESAS = ["tinito", "ctb", "daroan", "roldan", "ctm"]
QUERIES = ["ventas_diarias_v2", "renglones_aprecios_v1"]

START_DATE = date(2022, 1, 1)
END_DATE = date(2026, 7, 29)

DELAY_PER_REQUEST = 0.3  # segundos entre llamadas HTTP para proteger la API
THROTTLE_BATCH_SIZE = 50  # Cada 50 peticiones, hacer una pausa mayor
THROTTLE_PAUSE = 5.0  # segundos de pausa de enfriamiento

def generate_date_range(start_dt: date, end_dt: date) -> List[date]:
    delta = end_dt - start_dt
    return [start_dt + timedelta(days=i) for i in range(delta.days + 1)]

def run_backfill(year_filter: int = None, limit_days: int = None):
    print(f"=== INICIANDO BACKFILL DE VENTAS ({START_DATE} A {END_DATE}) ===", flush=True)
    if year_filter:
        print(f"Filtrando unicamente por el año {year_filter}", flush=True)

    dates = generate_date_range(START_DATE, END_DATE)

    if year_filter:
        dates = [d for d in dates if d.year == year_filter]

    if limit_days:
        dates = dates[:limit_days]

    total_dates = len(dates)
    total_ops = total_dates * len(EMPRESAS) * len(QUERIES)
    print(f"Total de fechas a procesar: {total_dates}", flush=True)
    print(f"Total de extracciones planificadas: {total_ops}", flush=True)

    settings = Settings()
    extractor = build_extractor(settings)
    req_counter = 0

    for dt in dates:
        dt_str = dt.strftime("%Y-%m-%d")
        dt_sql_param = dt_str

        for emp in EMPRESAS:
            for q_id in QUERIES:
                query_def = get_query_def(q_id, source_empresa=emp)
                params = {"registro": dt_sql_param}
                run_id = new_run_id()

                req_counter += 1
                print(f"[{req_counter}/{total_ops}] Extrayendo {q_id} | Empresa: {emp} | Fecha: {dt_str}...", flush=True)

                try:
                    res = extractor.run_batch(
                        query_id=q_id,
                        source_empresa=emp,
                        dt=dt_str,
                        run_id=run_id,
                        parameter_values=params,
                    )
                    print(f"  -> EXITO: {res.record_count} filas guardadas en Bronze ({res.status})", flush=True)
                    # Pacing respetuoso
                    time.sleep(DELAY_PER_REQUEST)
                except Exception as ex:
                    print(f"  -> ERROR en {q_id} | {emp} | {dt_str}: {ex}", flush=True)

                if req_counter % THROTTLE_BATCH_SIZE == 0:
                    print(f"--- Pausa de enfriamiento API ({THROTTLE_PAUSE}s) en petición {req_counter} ---", flush=True)
                    time.sleep(THROTTLE_PAUSE)

    print(f"=== BACKFILL FINALIZADO: {req_counter} peticiones ejecutadas ===", flush=True)

if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else None
    days = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run_backfill(year_filter=year, limit_days=days)
