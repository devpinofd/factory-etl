"""Script para crear la vista vw_base_activable_rif_90d en BigQuery Gold
que consolida la cartera activable a nivel de RIF FISCAL (grupos económicos / razones sociales):
- Agrupa múltiples cod_cli con el mismo RIF
- Muestra rifs_activados vs puntos_de_venta_sucursales
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_rif_90d` AS
SELECT
  v.source_empresa AS empresa,
  v.cod_suc AS codigo_sucursal,
  COALESCE(suc.nom_suc, v.cod_suc) AS nombre_sucursal,
  v.cod_ven AS codigo_vendedor,
  v.nom_ven AS nombre_vendedor,
  v.cod_pro AS codigo_proveedor,
  v.nom_pro AS nombre_proveedor,
  v.cod_mar AS codigo_marca,
  v.nom_mar AS nombre_marca,
  
  -- 🎯 DENOMINADOR: RIFs FISCALES ÚNICOS (GRUPO ECONÓMICO EN ÚLTIMOS 90 DÍAS)
  COUNT(DISTINCT NULLIF(TRIM(v.rif), '')) AS base_activable_rifs_90d,
  
  -- 🏢 PUNTOS DE VENTA / SUCURSALES FÍSICAS ASOCIADAS (COD_CLI ÚNICOS)
  COUNT(DISTINCT v.cod_cli) AS total_puntos_de_venta_cod_cli,
  
  -- 🎯 NUMERADOR: RIFs ACTIVADOS EN EL MES ACTUAL (JULIO 2026)
  COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN NULLIF(TRIM(v.rif), '') END) AS rifs_activados_mes_actual,
  
  -- ⏳ RIFs PENDIENTES POR ACTIVAR EN EL MES ACTUAL
  (COUNT(DISTINCT NULLIF(TRIM(v.rif), '')) - COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN NULLIF(TRIM(v.rif), '') END)) AS rifs_pendientes_activacion_mes,
  
  -- 📈 % PORCENTAJE DE ACTIVACIÓN A NIVEL DE RIF FISCAL
  ROUND(
    SAFE_DIVIDE(
      COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN NULLIF(TRIM(v.rif), '') END),
      NULLIF(COUNT(DISTINCT NULLIF(TRIM(v.rif), '')), 0)
    ) * 100, 2
  ) AS pct_activacion_rif_mes_actual,
  
  -- 📦 Métricas de Volumen del Mes Actual
  ROUND(SUM(CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cajas_vendidas ELSE 0 END), 2) AS cajas_vendidas_mes_actual,
  ROUND(SUM(CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.neto_dcto ELSE 0 END), 2) AS venta_usd_mes_actual,
  
  -- 📦 Métricas Totales de 90 Días
  ROUND(SUM(v.cajas_vendidas), 2) AS total_cajas_90d,
  ROUND(SUM(v.neto_dcto), 2) AS monto_total_venta_usd_90d,
  MAX(v.fecha_registro) AS fecha_ultima_venta
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
  ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc
WHERE v.fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
  AND NULLIF(TRIM(v.rif), '') IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9;
"""

def create_rif_view():
    print("==========================================================================")
    print("  CREANDO VISTA EN BIGQUERY: vw_base_activable_rif_90d")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_base_activable_rif_90d' creada exitosamente en BigQuery Gold.")

    # Consulta de prueba por Empresa, Sucursal, Vendedor, Proveedor y Marca
    sql_test = """
    SELECT
      empresa,
      nombre_sucursal,
      nombre_vendedor,
      nombre_proveedor,
      nombre_marca,
      base_activable_rifs_90d,
      total_puntos_de_venta_cod_cli,
      rifs_activados_mes_actual,
      pct_activacion_rif_mes_actual,
      venta_usd_mes_actual
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_rif_90d`
    WHERE base_activable_rifs_90d > 5
    ORDER BY total_puntos_de_venta_cod_cli DESC
    LIMIT 8;
    """
    print("\n  📊 MUESTRA DE ACTIVACIÓN A NIVEL DE RIF FISCAL EN BIGQUERY:")
    for r in client.query(sql_test).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_rif_view()
