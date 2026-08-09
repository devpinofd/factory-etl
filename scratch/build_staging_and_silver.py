"""Script para crear las tablas externas en BigQuery (factory_etl_bronze_stg) 
con esquemas explícitos cargados desde schemas/*.json y Hive Partitioning,
y consolidar la capa Silver (factory_etl_silver) y Gold (factory_etl_gold).
"""

import json
from pathlib import Path
from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
BRONZE_BUCKET = "factory-etl-dev-0y1dhf-bronze"
SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "src" / "factory_etl" / "factory_queries" / "schemas"

def load_bq_schema(schema_filename: str) -> list[bigquery.SchemaField]:
    json_path = SCHEMAS_DIR / schema_filename
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    fields = []
    for col in data.get("columns", []):
        c_name = col["name"]
        c_type = col.get("type", "string").lower()
        
        bq_type = "STRING"
        if c_type == "number":
            bq_type = "FLOAT64"
        elif c_type == "integer":
            bq_type = "INT64"
        elif c_type == "boolean":
            bq_type = "BOOL"
            
        fields.append(bigquery.SchemaField(c_name, bq_type, mode="NULLABLE"))
    return fields

def build_staging_and_silver():
    client = bigquery.Client(project=PROJECT_ID)
    print("==========================================================================")
    print("  1. CREANDO TABLAS EXTERNAS EN STAGING (factory_etl_bronze_stg)")
    print("==========================================================================")

    # 1. External Table stg_ventas_diarias
    table_id_ventas = f"{PROJECT_ID}.factory_etl_bronze_stg.stg_ventas_diarias"
    table_ventas = bigquery.Table(table_id_ventas)
    
    schema_ventas = load_bq_schema("ventas_diarias.json")
    
    external_config_ventas = bigquery.ExternalConfig("NEWLINE_DELIMITED_JSON")
    external_config_ventas.source_uris = [f"gs://{BRONZE_BUCKET}/bronze/ventas_diarias_v2/*"]
    external_config_ventas.schema = schema_ventas
    external_config_ventas.ignore_unknown_values = True
    
    # Hive Partitioning
    hive_options = bigquery.HivePartitioningOptions()
    hive_options.mode = "AUTO"
    hive_options.source_uri_prefix = f"gs://{BRONZE_BUCKET}/bronze/ventas_diarias_v2/"
    external_config_ventas.hive_partitioning = hive_options
    
    table_ventas.external_data_configuration = external_config_ventas
    
    print("  • Creando external table stg_ventas_diarias con esquema explícito...")
    client.create_table(table_ventas, exists_ok=True)
    print("    ✓ Tabla externa stg_ventas_diarias creada.")

    # 2. External Table stg_renglones_monedas
    table_id_monedas = f"{PROJECT_ID}.factory_etl_bronze_stg.stg_renglones_monedas"
    table_monedas = bigquery.Table(table_id_monedas)
    
    schema_monedas = load_bq_schema("renglones_monedas.json")
    
    external_config_monedas = bigquery.ExternalConfig("NEWLINE_DELIMITED_JSON")
    external_config_monedas.source_uris = [f"gs://{BRONZE_BUCKET}/bronze/renglones_monedas_v1/*"]
    external_config_monedas.schema = schema_monedas
    external_config_monedas.ignore_unknown_values = True
    
    hive_options_m = bigquery.HivePartitioningOptions()
    hive_options_m.mode = "AUTO"
    hive_options_m.source_uri_prefix = f"gs://{BRONZE_BUCKET}/bronze/renglones_monedas_v1/"
    external_config_monedas.hive_partitioning = hive_options_m
    
    table_monedas.external_data_configuration = external_config_monedas
    
    print("  • Creando external table stg_renglones_monedas con esquema explícito...")
    client.create_table(table_monedas, exists_ok=True)
    print("    ✓ Tabla externa stg_renglones_monedas creada.")

    print("\n==========================================================================")
    print("  2. CONSOLIDANDO CAPA SILVER (factory_etl_silver)")
    print("==========================================================================")

    # 3. Silver sil_renglones_monedas
    sql_sil_monedas = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.factory_etl_silver.sil_renglones_monedas`
    PARTITION BY DATE(registro)
    CLUSTER BY source_empresa, cod_mon
    AS
    SELECT
      source_empresa,
      RTRIM(LTRIM(CAST(cod_mon AS STRING))) AS cod_mon,
      SAFE_CAST(renglon AS INT64) AS renglon,
      SAFE_CAST(fecha AS TIMESTAMP) AS fecha,
      SAFE_CAST(tasa AS NUMERIC) AS tasa,
      RTRIM(LTRIM(CAST(comentario AS STRING))) AS comentario,
      SAFE_CAST(registro AS TIMESTAMP) AS registro,
      DATE(SAFE_CAST(registro AS TIMESTAMP)) AS fecha_registro
    FROM `{PROJECT_ID}.factory_etl_bronze_stg.stg_renglones_monedas`
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY source_empresa, cod_mon, renglon
      ORDER BY SAFE_CAST(registro AS TIMESTAMP) DESC
    ) = 1;
    """
    print("  • Ejecutando consolidación en sil_renglones_monedas...")
    j1 = client.query(sql_sil_monedas)
    j1.result()
    
    count_monedas = list(client.query(f"SELECT COUNT(*) as total FROM `{PROJECT_ID}.factory_etl_silver.sil_renglones_monedas`").result())[0].total
    print(f"    ✓ Tabla sil_renglones_monedas creada. Filas consolidadas: {count_monedas}")

    # 4. Silver sil_ventas_diarias
    sql_sil_ventas = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.factory_etl_silver.sil_ventas_diarias`
    PARTITION BY DATE(registro)
    CLUSTER BY source_empresa, cod_pro, cod_suc
    AS
    SELECT
      source_empresa,
      RTRIM(LTRIM(CAST(tipo_documento AS STRING))) AS tipo_documento,
      RTRIM(LTRIM(CAST(cod_suc AS STRING))) AS cod_suc,
      RTRIM(LTRIM(CAST(documento AS STRING))) AS documento,
      SAFE_CAST(renglon AS INT64) AS renglon,
      SAFE_CAST(registro AS TIMESTAMP) AS registro,
      DATE(SAFE_CAST(registro AS TIMESTAMP)) AS fecha_registro,
      RTRIM(LTRIM(CAST(cod_ven AS STRING))) AS cod_ven,
      RTRIM(LTRIM(CAST(nom_ven AS STRING))) AS nom_ven,
      RTRIM(LTRIM(CAST(cod_cli AS STRING))) AS cod_cli,
      RTRIM(LTRIM(CAST(nom_cli AS STRING))) AS nom_cli,
      RTRIM(LTRIM(CAST(nom_cla AS STRING))) AS nom_cla,
      RTRIM(LTRIM(CAST(nom_est AS STRING))) AS nom_est,
      RTRIM(LTRIM(CAST(nom_ciu AS STRING))) AS nom_ciu,
      RTRIM(LTRIM(CAST(cod_art AS STRING))) AS cod_art,
      RTRIM(LTRIM(CAST(cod_mar AS STRING))) AS cod_mar,
      RTRIM(LTRIM(CAST(nom_mar AS STRING))) AS nom_mar,
      RTRIM(LTRIM(CAST(nom_dep AS STRING))) AS nom_dep,
      RTRIM(LTRIM(CAST(cod_sec AS STRING))) AS cod_sec,
      RTRIM(LTRIM(CAST(modelo AS STRING))) AS modelo,
      RTRIM(LTRIM(CAST(cod_pro AS STRING))) AS cod_pro,
      RTRIM(LTRIM(CAST(nom_pro AS STRING))) AS nom_pro,
      RTRIM(LTRIM(CAST(nom_art AS STRING))) AS nom_art,
      RTRIM(LTRIM(CAST(cod_uni1 AS STRING))) AS cod_uni1,
      SAFE_CAST(can_ven AS NUMERIC) AS can_ven,
      SAFE_CAST(monto_bruto AS NUMERIC) AS monto_bruto,
      RTRIM(LTRIM(CAST(cod_mon AS STRING))) AS cod_mon,
      RTRIM(LTRIM(CAST(rif AS STRING))) AS rif, -- INCLUIDO PARA RLS
      RTRIM(LTRIM(CAST(cod_imp AS STRING))) AS cod_imp,
      SAFE_CAST(neto AS NUMERIC) AS neto,
      SAFE_CAST(dcto AS NUMERIC) AS dcto,
      SAFE_CAST(tasa AS NUMERIC) AS tasa,
      SAFE_CAST(neto_dcto AS NUMERIC) AS neto_dcto
    FROM `{PROJECT_ID}.factory_etl_bronze_stg.stg_ventas_diarias`
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY source_empresa, tipo_documento, cod_suc, documento, renglon
      ORDER BY SAFE_CAST(registro AS TIMESTAMP) DESC
    ) = 1;
    """
    print("  • Ejecutando consolidación en sil_ventas_diarias (Limpieza + TRIM + QUALIFY Dedup)...")
    j2 = client.query(sql_sil_ventas)
    j2.result()

    count_ventas = list(client.query(f"SELECT COUNT(*) as total FROM `{PROJECT_ID}.factory_etl_silver.sil_ventas_diarias`").result())[0].total
    print(f"    ✓ Tabla sil_ventas_diarias creada. Filas consolidadas: {count_ventas}")

    print("\n==========================================================================")
    print("  3. CONSOLIDANDO CAPA GOLD (factory_etl_gold.fct_ventas)")
    print("==========================================================================")

    # 5. Gold fct_ventas
    sql_fct_ventas = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.factory_etl_gold.fct_ventas`
    PARTITION BY DATE(registro)
    CLUSTER BY source_empresa, cod_pro, cod_suc
    AS
    SELECT
      v.source_empresa,
      v.tipo_documento,
      v.cod_suc,
      v.documento,
      v.renglon,
      v.registro,
      v.fecha_registro,
      t.fecha_key,
      t.anio,
      t.mes,
      t.nombre_mes,
      t.anio_mes,
      t.semana_del_anio,
      t.anio_semana,
      t.quincena,
      t.quincena_nombre,
      v.cod_ven,
      v.nom_ven,
      v.cod_cli,
      v.nom_cli,
      v.nom_cla,
      v.nom_est,
      v.nom_ciu,
      v.cod_art,
      v.cod_mar,
      v.nom_mar,
      v.nom_dep,
      v.cod_sec,
      v.modelo,
      v.cod_pro,
      v.nom_pro,
      v.nom_art,
      v.cod_uni1,
      v.can_ven,
      v.monto_bruto,
      v.cod_mon,
      v.rif, -- RIF DISPONIBLE PARA RLS
      v.cod_imp,
      v.neto,
      v.dcto,
      v.tasa,
      v.neto_dcto
    FROM `{PROJECT_ID}.factory_etl_silver.sil_ventas_diarias` v
    LEFT JOIN `{PROJECT_ID}.factory_etl_gold.dim_tiempo` t
      ON v.fecha_registro = t.fecha;
    """
    print("  • Construyendo fct_ventas en Gold unida con dim_tiempo...")
    j3 = client.query(sql_fct_ventas)
    j3.result()

    count_fct = list(client.query(f"SELECT COUNT(*) as total FROM `{PROJECT_ID}.factory_etl_gold.fct_ventas`").result())[0].total
    print(f"    ✓ Tabla fct_ventas creada exitosamente en Gold. Total filas: {count_fct}")

    print("\n==========================================================================")
    print("  PROCESO COMPLETADO EXITOSAMENTE")
    print("==========================================================================")

if __name__ == "__main__":
    build_staging_and_silver()
