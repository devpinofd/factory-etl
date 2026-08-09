"""Script de Backfill Organizado por Empresa y Quincenas (2022 - 2026)

Queries objetivo:
  - ventas_diarias_v2
  - renglones_monedas_v1

Estrategia de Carga Quincenal Directa:
1. Agrupación por Empresa: Procesa una empresa completa a la vez
2. Petición por Bloque Quincenal Completo:
   - Q1: fec_des (01 del mes) a fec_has (15 del mes)
   - Q2: fec_des (16 del mes) a fec_has (fin del mes)
3. Rate Limiting & Pausas:
   - Delay entre peticiones HTTP (0.3s)
   - Pausa de enfriamiento entre Quincenas (1.5s)
   - Pausa de enfriamiento entre Empresas (5.0s)
"""

import sys
import time
import os
import calendar
from datetime import date, timedelta
from typing import List, Tuple

# Configurar variables de entorno por defecto si no existen
os.environ.setdefault("FACTORY_ETL_GCP_PROJECT", "factory-etl-dev-0y1dhf")
os.environ.setdefault("FACTORY_ETL_BRONZE_BUCKET", "factory-etl-dev-0y1dhf-bronze")
os.environ.setdefault("FACTORY_ETL_CONTROL_DATASET", "factory_etl_control_dev")
os.environ.setdefault("FACTORY_ETL_QUARANTINE_BUCKET", "factory-etl-dev-0y1dhf-quarantine")
os.environ.setdefault("FACTORY_ETL_ENV", "dev")

# Asegurar import de factory_etl
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from factory_etl.config import Settings
from factory_etl.bootstrap import build_extractor
from factory_etl.ids import new_run_id

EMPRESAS_DISPONIBLES = ["tinito", "ctb", "daroan", "roldan", "ctm"]

# Queries transaccionales de ventas y renglones monedas
QUERIES = ["ventas_diarias_v2", "renglones_monedas_v1"]

START_YEAR = 2022
END_YEAR = 2026

DELAY_PER_REQUEST = 0.3       # Segundos entre llamadas HTTP individuales
PAUSE_BETWEEN_QUINCENAS = 1.5 # Segundos entre quincenas
PAUSE_BETWEEN_EMPRESAS = 5.0  # Segundos entre empresas

def generate_quincenas(start_yr: int, end_yr: int) -> List[Tuple[date, date, int]]:
    """Genera pares (start_date, end_date, quincena_num) para cada mes."""
    quincenas = []
    today = date.today()

    for year in range(start_yr, end_yr + 1):
        for month in range(1, 13):
            if date(year, month, 1) > today:
                break

            # Q1: 1 al 15
            q1_start = date(year, month, 1)
            q1_end = min(date(year, month, 15), today)
            quincenas.append((q1_start, q1_end, 1))

            # Q2: 16 al fin de mes
            if date(year, month, 16) <= today:
                last_day = calendar.monthrange(year, month)[1]
                q2_start = date(year, month, 16)
                q2_end = min(date(year, month, last_day), today)
                quincenas.append((q2_start, q2_end, 2))

    return quincenas

def run_quincenal_backfill(
    empresa_target: str = None,
    year_target: int = None,
    month_target: int = None,
    quincena_target: int = None,
):
    print("==========================================================================", flush=True)
    print("  BACKFILL QUINCENAL DIRECTO (fec_des -> fec_has) (2022 - 2026)", flush=True)
    print("==========================================================================", flush=True)

    empresas = [empresa_target] if empresa_target else EMPRESAS_DISPONIBLES
    all_quincenas = generate_quincenas(START_YEAR, END_YEAR)

    # Filtrados opcionales
    if year_target:
        all_quincenas = [q for q in all_quincenas if q[0].year == year_target]
    if month_target:
        all_quincenas = [q for q in all_quincenas if q[0].month == month_target]
    if quincena_target:
        all_quincenas = [q for q in all_quincenas if q[2] == quincena_target]

    print(f"Empresas a procesar: {', '.join(empresas)}", flush=True)
    print(f"Queries: {', '.join(QUERIES)}", flush=True)
    print(f"Total de bloques quincenales por empresa: {len(all_quincenas)}", flush=True)
    print("--------------------------------------------------------------------------", flush=True)

    settings = Settings()
    extractor = build_extractor(settings)

    total_success = 0
    total_errors = 0

    for emp_idx, emp in enumerate(empresas, 1):
        print(f"\n>>>> INICIANDO EMPRESA [{emp_idx}/{len(empresas)}]: {emp.upper()} <<<<", flush=True)

        for q_idx, (q_start, q_end, q_num) in enumerate(all_quincenas, 1):
            fec_des = q_start.strftime("%Y-%m-%d")
            fec_has = q_end.strftime("%Y-%m-%d")
            q_label = f"Año {q_start.year} - Mes {q_start.month:02d} (Q{q_num}: {fec_des} al {fec_has})"
            print(f"\n--- [{emp}] Bloque {q_idx}/{len(all_quincenas)}: {q_label} ---", flush=True)

            for q_id in QUERIES:
                params = {"fec_des": fec_des, "fec_has": fec_has}
                run_id = new_run_id()

                try:
                    res = extractor.run_batch(
                        query_id=q_id,
                        source_empresa=emp,
                        dt=fec_has,
                        run_id=run_id,
                        parameter_values=params,
                    )
                    print(f"  [{fec_des} -> {fec_has}] {q_id:<22} -> OK ({res.record_count} filas | {res.status})", flush=True)
                    total_success += 1
                    time.sleep(DELAY_PER_REQUEST)
                except Exception as ex:
                    print(f"  [{fec_des} -> {fec_has}] {q_id:<22} -> ERROR: {ex}", flush=True)
                    total_errors += 1

            time.sleep(PAUSE_BETWEEN_QUINCENAS)

        if emp_idx < len(empresas):
            print(f"\n==== Empresa {emp.upper()} finalizada. Enfriamiento entre empresas ({PAUSE_BETWEEN_EMPRESAS}s)... ====", flush=True)
            time.sleep(PAUSE_BETWEEN_EMPRESAS)

    print("\n==========================================================================", flush=True)
    print(f"  BACKFILL FINALIZADO: {total_success} OK / {total_errors} errores", flush=True)
    print("==========================================================================", flush=True)

if __name__ == "__main__":
    emp = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "ALL" else None
    yr = int(sys.argv[2]) if len(sys.argv) > 2 else None
    mo = int(sys.argv[3]) if len(sys.argv) > 3 else None
    qn = int(sys.argv[4]) if len(sys.argv) > 4 else None

    run_quincenal_backfill(
        empresa_target=emp,
        year_target=yr,
        month_target=mo,
        quincena_target=qn,
    )
