"""Script para materializar dim_tiempo en BigQuery (factory_etl_gold.dim_tiempo)"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"

SQL = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_gold.dim_tiempo`
OPTIONS(
  description="Dimensión de tiempo y calendario comercial (2020-2030) con semanas ISO y quincenas"
) AS
SELECT
  CAST(FORMAT_DATE('%Y%m%d', d) AS INT64) AS fecha_key,
  d AS fecha,
  EXTRACT(YEAR FROM d) AS anio,
  EXTRACT(MONTH FROM d) AS mes,
  CASE EXTRACT(MONTH FROM d)
    WHEN 1 THEN 'Enero' WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo'
    WHEN 4 THEN 'Abril' WHEN 5 THEN 'Mayo' WHEN 6 THEN 'Junio'
    WHEN 7 THEN 'Julio' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Septiembre'
    WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' WHEN 12 THEN 'Diciembre'
  END AS nombre_mes,
  SUBSTR(
    CASE EXTRACT(MONTH FROM d)
      WHEN 1 THEN 'Enero' WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo'
      WHEN 4 THEN 'Abril' WHEN 5 THEN 'Mayo' WHEN 6 THEN 'Junio'
      WHEN 7 THEN 'Julio' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Septiembre'
      WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' WHEN 12 THEN 'Diciembre'
    END, 1, 3
  ) AS nombre_mes_corto,
  EXTRACT(DAY FROM d) AS dia,
  EXTRACT(DAYOFYEAR FROM d) AS dia_del_anio,
  EXTRACT(QUARTER FROM d) AS trimestre,
  CONCAT('Q', EXTRACT(QUARTER FROM d)) AS trimestre_nombre,
  FORMAT_DATE('%Y-Q%Q', d) AS anio_trimestre,

  -- 🗓️ SEGMENTACIÓN POR SEMANA-AÑO (ISO & Comercial)
  EXTRACT(ISOWEEK FROM d) AS semana_del_anio,
  FORMAT_DATE('%G-W%V', d) AS anio_semana,                   -- Ej: '2026-W31'
  CAST(FORMAT_DATE('%G%V', d) AS INT64) AS anio_semana_num,  -- Ej: 202631
  DATE_TRUNC(d, WEEK(MONDAY)) AS inicio_semana,              -- Lunes de la semana
  DATE_ADD(DATE_TRUNC(d, WEEK(MONDAY)), INTERVAL 6 DAY) AS fin_semana, -- Domingo

  EXTRACT(DAYOFWEEK FROM d) AS dia_de_semana,
  CASE EXTRACT(DAYOFWEEK FROM d)
    WHEN 1 THEN 'Domingo' WHEN 2 THEN 'Lunes' WHEN 3 THEN 'Martes'
    WHEN 4 THEN 'Miércoles' WHEN 5 THEN 'Jueves' WHEN 6 THEN 'Viernes' WHEN 7 THEN 'Sábado'
  END AS nombre_dia,
  (EXTRACT(DAYOFWEEK FROM d) IN (1, 7)) AS es_fin_de_semana,
  
  -- 📆 QUINCENAS OPERATIVAS (Q1: 1-15, Q2: 16-fin)
  CASE WHEN EXTRACT(DAY FROM d) <= 15 THEN 1 ELSE 2 END AS quincena,
  CASE WHEN EXTRACT(DAY FROM d) <= 15 THEN 'Q1' ELSE 'Q2' END AS quincena_nombre,
  
  FORMAT_DATE('%Y-%m', d) AS anio_mes,
  CAST(FORMAT_DATE('%Y%m', d) AS INT64) AS anio_mes_num,
  (EXTRACT(DAY FROM d) = 1) AS es_primer_dia_mes,
  (d = LAST_DAY(d)) AS es_fin_de_mes
FROM
  UNNEST(GENERATE_DATE_ARRAY('2020-01-01', '2030-12-31', INTERVAL 1 DAY)) AS d;
"""

def build():
    client = bigquery.Client(project=PROJECT_ID)
    print("Ejecutando creación de factory_etl_gold.dim_tiempo...")
    query_job = client.query(SQL)
    query_job.result()
    
    # Verificar recuento
    res = list(client.query("SELECT COUNT(*) AS total FROM `factory-etl-dev-0y1dhf.factory_etl_gold.dim_tiempo`").result())
    print(f"  ✓ Tabla dim_tiempo creada exitosamente en BigQuery. Total filas: {res[0].total}")

if __name__ == "__main__":
    build()
