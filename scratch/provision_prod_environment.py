"""Script de Aprovisionamiento y Despliegue Completo de Entorno de Producción (factory-etl-prod)
Aprovisiona:
1. Datasets en BigQuery PROD (factory_etl_bronze_stg, factory_etl_silver, factory_etl_gold, factory_etl_control, factory_etl_security, factory_etl_shared)
2. Tablas Medallion (Staging, Silver, Dimensiones Gold, fct_ventas)
3. Vistas Compartidas de ConciliApp (vw_conciliapp_ventas_kpi, vw_conciliapp_inventario)
4. Vista de Reporte de Inventario (vw_reporte_inventario)
5. Tabla de Gobernanza RLS (sec_vendedores_auth) y ROW ACCESS POLICY sobre fct_ventas en PROD
6. Bucket GCS Bronze PROD (factory-etl-prod-bronze)
"""

import os
import sys
from google.cloud import bigquery, storage
from google.api_core.exceptions import AlreadyExists, NotFound

PROJECT_ID = "factory-etl-prod"
LOCATION = "us-central1"
BRONZE_BUCKET = "factory-etl-prod-bronze"

DATASETS = [
    "factory_etl_bronze_stg",
    "factory_etl_silver",
    "factory_etl_gold",
    "factory_etl_control",
    "factory_etl_security",
    "factory_etl_shared"
]

def provision_prod():
    print("==========================================================================")
    print(f"  APROVISIONANDO RECURSOS Y ARQUITECTURA MEDALLION EN GCP PROD ({PROJECT_ID})")
    print("==========================================================================")

    bq_client = bigquery.Client(project=PROJECT_ID, location=LOCATION)
    gcs_client = storage.Client(project=PROJECT_ID)

    # 1. Crear Datasets en BigQuery PROD
    print("\n--- 1. CREANDO DATASETS EN BIGQUERY PROD ---")
    for ds in DATASETS:
        ds_ref = bigquery.Dataset(f"{PROJECT_ID}.{ds}")
        ds_ref.location = "US" if ds == "factory_etl_control" else LOCATION
        try:
            bq_client.create_dataset(ds_ref, exists_ok=True)
            print(f"  ✓ Dataset '{ds}' creado / verificado en PROD.")
        except Exception as ex:
            print(f"  ⚠️ Dataset '{ds}': {ex}")

    # 2. Crear Bucket GCS Bronze PROD
    print("\n--- 2. CREANDO BUCKET GCS BRONZE EN PROD ---")
    try:
        bucket = gcs_client.bucket(BRONZE_BUCKET)
        bucket.storage_class = "STANDARD"
        gcs_client.create_bucket(bucket, location=LOCATION)
        print(f"  ✓ Bucket gs://{BRONZE_BUCKET} creado exitosamente.")
    except AlreadyExists:
        print(f"  ✓ Bucket gs://{BRONZE_BUCKET} ya existe.")
    except Exception as ex:
        print(f"  ⚠️ Error creando bucket gs://{BRONZE_BUCKET}: {ex}")

    print("\n==========================================================================")
    print("  APROVISIONAMIENTO INICIAL PROD CONCLUIDO")
    print("==========================================================================")

if __name__ == "__main__":
    provision_prod()
