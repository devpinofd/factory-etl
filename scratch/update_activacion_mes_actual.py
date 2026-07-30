"""Script para actualizar la vista vw_base_activable_clientes_90d en BigQuery Gold
con la Tasa de Activación del Mes Actual (Julio 2026):
- Numerador: Clientes únicos que han comprado en lo transcurrido del mes actual (Julio 2026)
- Denominador: Base Activable (clientes únicos que compraron en los últimos 90 días)
- % Tasa de Activación del Mes Actual = (Clientes Activados Mes Actual / Base Activable 90d) * 100
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_clientes_90d` AS
SELECT
  source_empresa AS empresa,
  cod_suc AS codigo_sucursal,
  cod_ven AS codigo_vendedor,
  nom_ven AS nombre_vendedor,
  cod_pro AS codigo_proveedor,
  nom_pro AS nombre_proveedor,
  cod_mar AS codigo_marca,
  nom_mar AS nombre_marca,
  
  -- 🎯 DENOMINADOR: BASE ACTIVABLE DE CLIENTES (ÚLTIMOS 90 DÍAS)
  COUNT(DISTINCT cod_cli) AS base_activable_clientes_90d,
  
  -- 🎯 NUMERADOR: CLIENTES ACTIVADOS EN LO QUE VA DEL MES ACTUAL (JULIO 2026)
  COUNT(DISTINCT CASE WHEN fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN cod_cli END) AS clientes_activados_mes_actual,
  
  -- ⏳ CLIENTES PENDIENTES POR ACTIVAR EN EL MES ACTUAL
  (COUNT(DISTINCT cod_cli) - COUNT(DISTINCT CASE WHEN fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN cod_cli END)) AS clientes_pendientes_activacion_mes,
  
  -- 📈 % PORCENTAJE DE ACTIVACIÓN DEL MES ACTUAL
  ROUND(
    SAFE_DIVIDE(
      COUNT(DISTINCT CASE WHEN fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN cod_cli END),
      NULLIF(COUNT(DISTINCT cod_cli), 0)
    ) * 100, 2
  ) AS pct_activacion_mes_actual,
  
  -- 📦 Métricas de Volumen del Mes Actual (Julio 2026)
  ROUND(SUM(CASE WHEN fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN cajas_vendidas ELSE 0 END), 2) AS cajas_vendidas_mes_actual,
  ROUND(SUM(CASE WHEN fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN neto_dcto ELSE 0 END), 2) AS venta_usd_mes_actual,
  
  -- 📦 Métricas Totales de los 90 Días
  ROUND(SUM(cajas_vendidas), 2) AS total_cajas_90d,
  ROUND(SUM(neto_dcto), 2) AS monto_total_venta_usd_90d,
  MAX(fecha_registro) AS fecha_ultima_venta
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
WHERE fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8;
"""

def update_view():
    print("==========================================================================")
    print("  ACTUALIZANDO VISTA CON PORCENTAJE DE ACTIVACIÓN DEL MES ACTUAL")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_base_activable_clientes_90d' actualizada exitosamente con Tasa de Activación del Mes Actual.")

    # Consulta de prueba por Empresa, Sucursal, Vendedor, Proveedor y Marca
    sql_test = """
    SELECT
      empresa,
      codigo_sucursal,
      codigo_vendedor,
      nombre_vendedor,
      nombre_proveedor,
      nombre_marca,
      base_activable_clientes_90d,
      clientes_activados_mes_actual,
      clientes_pendientes_activacion_mes,
      pct_activacion_mes_actual,
      cajas_vendidas_mes_actual,
      venta_usd_mes_actual
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_clientes_90d`
    WHERE base_activable_clientes_90d > 10
    ORDER BY pct_activacion_mes_actual DESC, base_activable_clientes_90d DESC
    LIMIT 10;
    """
    print("\n  📊 MUESTRA DE ACTIVACIÓN EN LO QUE VA DE MES (JULIO 2026):")
    for r in client.query(sql_test).result():
        print("  ", dict(r))

if __name__ == "__main__":
    update_view()
