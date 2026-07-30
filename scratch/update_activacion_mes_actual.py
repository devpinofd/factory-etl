"""Script para actualizar la vista vw_base_activable_clientes_90d en BigQuery Gold
incorporando el NOMBRE DE LA SUCURSAL (nombre_sucursal):
- JOIN con sil_sucursales para obtener nom_suc
- Muestra el nombre descriptivo de la sucursal junto a cod_suc
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_clientes_90d` AS
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
  
  -- 🎯 DENOMINADOR: BASE ACTIVABLE DE CLIENTES (ÚLTIMOS 90 DÍAS)
  COUNT(DISTINCT v.cod_cli) AS base_activable_clientes_90d,
  
  -- 🎯 NUMERADOR: CLIENTES ACTIVADOS EN EL MES ACTUAL (JULIO 2026)
  COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cod_cli END) AS clientes_activados_mes_actual,
  
  -- ⏳ CLIENTES PENDIENTES POR ACTIVAR EN EL MES ACTUAL
  (COUNT(DISTINCT v.cod_cli) - COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cod_cli END)) AS clientes_pendientes_activacion_mes,
  
  -- 📈 % PORCENTAJE DE ACTIVACIÓN DEL MES ACTUAL
  ROUND(
    SAFE_DIVIDE(
      COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cod_cli END),
      NULLIF(COUNT(DISTINCT v.cod_cli), 0)
    ) * 100, 2
  ) AS pct_activacion_mes_actual,
  
  -- 📦 Métricas de Volumen del Mes Actual (Julio 2026)
  ROUND(SUM(CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cajas_vendidas ELSE 0 END), 2) AS cajas_vendidas_mes_actual,
  ROUND(SUM(CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.neto_dcto ELSE 0 END), 2) AS venta_usd_mes_actual,
  
  -- 📦 Métricas Totales de los 90 Días
  ROUND(SUM(v.cajas_vendidas), 2) AS total_cajas_90d,
  ROUND(SUM(v.neto_dcto), 2) AS monto_total_venta_usd_90d,
  MAX(v.fecha_registro) AS fecha_ultima_venta
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
  ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc
WHERE v.fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9;
"""

def update_view():
    print("==========================================================================")
    print("  ACTUALIZANDO VISTA INCLUYENDO NOMBRE_SUCURSAL EN BIGQUERY GOLD")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_base_activable_clientes_90d' actualizada exitosamente con nombre_sucursal.")

    # Consulta de prueba por Empresa, Sucursal (Nombre), Vendedor, Proveedor y Marca
    sql_test = """
    SELECT
      empresa,
      codigo_sucursal,
      nombre_sucursal,
      codigo_vendedor,
      nombre_vendedor,
      nombre_proveedor,
      nombre_marca,
      base_activable_clientes_90d,
      clientes_activados_mes_actual,
      pct_activacion_mes_actual,
      cajas_vendidas_mes_actual,
      venta_usd_mes_actual
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_clientes_90d`
    WHERE base_activable_clientes_90d > 10
    ORDER BY pct_activacion_mes_actual DESC, base_activable_clientes_90d DESC
    LIMIT 8;
    """
    print("\n  📊 MUESTRA DE LA BASE ACTIVABLE CON NOMBRE DE SUCURSAL:")
    for r in client.query(sql_test).result():
        print("  ", dict(r))

if __name__ == "__main__":
    update_view()
