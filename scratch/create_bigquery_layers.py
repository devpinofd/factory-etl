"""Script para crear los Datasets de Medallion y Seguridad en BigQuery si no existen"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
LOCATION = "us-central1"

DATASETS = [
    ("factory_etl_bronze_stg", "Staging External Tables sobre GCS Bronze"),
    ("factory_etl_silver", "Capa Silver: Tablas limpias, deduplicadas y tipadas"),
    ("factory_etl_gold", "Capa Gold: Modelo Dimensional (fct_ventas, dim_tiempo, etc.)"),
    ("factory_etl_security", "Capa de Gobierno y Seguridad RLS (sec_principals, sec_access_scopes)"),
]

def create_datasets():
    client = bigquery.Client(project=PROJECT_ID)
    print("==========================================================================")
    print("  CREACIÓN DE DATASETS BIGQUERY (MEDALLION & SECURITY)")
    print("==========================================================================")

    for ds_id, description in DATASETS:
        full_id = f"{PROJECT_ID}.{ds_id}"
        dataset = bigquery.Dataset(full_id)
        dataset.location = LOCATION
        dataset.description = description

        try:
            dataset = client.create_dataset(dataset, exists_ok=True)
            print(f"  ✓ Dataset '{ds_id}' listo en BigQuery ({LOCATION})")
        except Exception as ex:
            print(f"  ❌ Error creando dataset '{ds_id}': {ex}")

if __name__ == "__main__":
    create_datasets()
