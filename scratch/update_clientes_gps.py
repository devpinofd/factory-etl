"""Script para actualizar sil_clientes y dim_cliente en BigQuery derivando latitud y longitud a partir de la columna gps"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"

SQL_SILVER_CLIENTES = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_silver.sil_clientes`
CLUSTER BY source_empresa
AS
SELECT
  source_empresa,
  RTRIM(LTRIM(CAST(cod_cli AS STRING))) AS cod_cli,
  RTRIM(LTRIM(CAST(nom_cli AS STRING))) AS nom_cli,
  RTRIM(LTRIM(CAST(rif AS STRING))) AS rif,
  RTRIM(LTRIM(CAST(dir_fis AS STRING))) AS dir_fis,
  RTRIM(LTRIM(CAST(dir_exa AS STRING))) AS dir_exa,
  RTRIM(LTRIM(CAST(cod_pai AS STRING))) AS cod_pai,
  RTRIM(LTRIM(CAST(cod_est AS STRING))) AS cod_est,
  RTRIM(LTRIM(CAST(cod_ciu AS STRING))) AS cod_ciu,
  RTRIM(LTRIM(CAST(nom_mun AS STRING))) AS nom_mun,
  RTRIM(LTRIM(CAST(nom_par AS STRING))) AS nom_par,
  
  -- 📍 LIMPIEZA Y DERIVACIÓN DE GPS (LATITUD Y LONGITUD)
  RTRIM(LTRIM(CAST(gps AS STRING))) AS gps,
  SAFE_CAST(TRIM(SPLIT(RTRIM(LTRIM(CAST(gps AS STRING))), ',')[SAFE_OFFSET(0)]) AS FLOAT64) AS latitud,
  SAFE_CAST(TRIM(SPLIT(RTRIM(LTRIM(CAST(gps AS STRING))), ',')[SAFE_OFFSET(1)]) AS FLOAT64) AS longitud,
  
  RTRIM(LTRIM(CAST(cod_ven AS STRING))) AS cod_ven,
  RTRIM(LTRIM(CAST(segmentacion1 AS STRING))) AS segmentacion1,
  RTRIM(LTRIM(CAST(segmentacion2 AS STRING))) AS segmentacion2,
  SAFE_CAST(mon_sal AS NUMERIC) AS mon_sal,
  RTRIM(LTRIM(CAST(cod_suc AS STRING))) AS cod_suc,
  RTRIM(LTRIM(CAST(tip_con AS STRING))) AS tip_con,
  RTRIM(LTRIM(CAST(crm_pos AS STRING))) AS crm_pos,
  RTRIM(LTRIM(CAST(tip_cli AS STRING))) AS tip_cli,
  RTRIM(LTRIM(CAST(abc AS STRING))) AS abc,
  RTRIM(LTRIM(CAST(status AS STRING))) AS status
FROM `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_clientes`
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY source_empresa, cod_cli
  ORDER BY dt DESC
) = 1;
"""

SQL_GOLD_CLIENTE = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_gold.dim_cliente`
CLUSTER BY source_empresa, cod_cli
AS
SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_silver.sil_clientes`;
"""

def update_gps():
    client = bigquery.Client(project=PROJECT_ID)
    print("==========================================================================")
    print("  LIMPIEZA DE GPS Y DERIVACIÓN DE LATITUD / LONGITUD EN BIGQUERY")
    print("==========================================================================")
    
    print("  • Actualizando sil_clientes con latitud y longitud...")
    client.query(SQL_SILVER_CLIENTES).result()
    print("    ✓ sil_clientes actualizada.")

    print("  • Actualizando dim_cliente en Gold...")
    client.query(SQL_GOLD_CLIENTE).result()
    print("    ✓ dim_cliente actualizada.")

    # Conteo de clientes con GPS válido
    check_sql = """
    SELECT
      COUNT(*) AS total_clientes,
      COUNTIF(gps IS NOT NULL AND gps != '') AS con_gps_texto,
      COUNTIF(latitud IS NOT NULL AND longitud IS NOT NULL) AS con_lat_long_validas
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.dim_cliente`
    """
    rows = list(client.query(check_sql).result())[0]
    print(f"\n  📊 RESULTADOS EN dim_cliente:")
    print(f"     - Total Clientes: {rows.total_clientes:,}")
    print(f"     - Clientes con texto GPS: {rows.con_gps_texto:,}")
    print(f"     - Clientes con Latitud y Longitud procesadas: {rows.con_lat_long_validas:,}")

if __name__ == "__main__":
    update_gps()
