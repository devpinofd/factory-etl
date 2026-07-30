"""Script para crear la vista maestra vw_maestro_clientes_activables en BigQuery Gold:
Lista individualmente a cada cliente de la cartera por Empresa (Nombre), Sucursal (Nombre), Vendedor y Proveedor,
detallando su estatus de activación a 90 días, compras en el mes actual, días sin comprar y volumen en USD.
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_maestro_clientes_activables` AS
WITH cartera_clientes AS (
  SELECT DISTINCT
    v.source_empresa AS empresa,
    COALESCE(emp.nombre_empresa, v.source_empresa) AS nombre_empresa,
    v.cod_suc AS codigo_sucursal,
    COALESCE(suc.nom_suc, v.cod_suc) AS nombre_sucursal,
    v.cod_ven AS codigo_vendedor,
    v.nom_ven AS nombre_vendedor,
    v.cod_pro AS codigo_proveedor,
    v.nom_pro AS nombre_proveedor,
    v.cod_cli AS codigo_cliente,
    v.nom_cli AS nombre_cliente,
    NULLIF(TRIM(v.rif), '') AS rif_cliente,
    v.nom_cla AS clase_cliente,
    v.nom_est AS estado_cliente,
    v.nom_ciu AS ciudad_cliente
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
  LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` emp
    ON v.source_empresa = emp.source_empresa
  LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
    ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc
),
metricas_90d AS (
  SELECT
    source_empresa AS empresa,
    cod_suc AS codigo_sucursal,
    cod_ven AS codigo_vendedor,
    cod_pro AS codigo_proveedor,
    cod_cli AS codigo_cliente,
    MAX(fecha_registro) AS fecha_ultima_compra,
    SUM(cajas_vendidas) AS cajas_90d,
    SUM(neto_dcto) AS venta_usd_90d
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
  WHERE fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
  GROUP BY 1, 2, 3, 4, 5
),
metricas_mes_actual AS (
  SELECT
    source_empresa AS empresa,
    cod_suc AS codigo_sucursal,
    cod_ven AS codigo_vendedor,
    cod_pro AS codigo_proveedor,
    cod_cli AS codigo_cliente,
    MAX(fecha_registro) AS fecha_ultima_compra_mes,
    SUM(cajas_vendidas) AS cajas_mes_actual,
    SUM(neto_dcto) AS venta_usd_mes_actual
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
  WHERE fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH)
  GROUP BY 1, 2, 3, 4, 5
)
SELECT
  c.empresa,
  c.nombre_empresa,
  c.codigo_sucursal,
  c.nombre_sucursal,
  c.codigo_vendedor,
  c.nombre_vendedor,
  c.codigo_proveedor,
  c.nombre_proveedor,
  c.codigo_cliente,
  c.nombre_cliente,
  c.rif_cliente,
  c.clase_cliente,
  c.estado_cliente,
  c.ciudad_cliente,
  
  -- 🗓️ FECHA Y DÍAS SIN COMPRAR
  m90.fecha_ultima_compra,
  COALESCE(DATE_DIFF(CURRENT_DATE(), m90.fecha_ultima_compra, DAY), 999) AS dias_sin_comprar,
  
  -- 🏷️ ESTATUS DE ACTIVACIÓN (90 DÍAS)
  CASE
    WHEN m90.fecha_ultima_compra IS NOT NULL THEN 'ACTIVADO (<=90d)'
    ELSE 'PENDIENTE POR ACTIVAR (>90d)'
  END AS estatus_activacion_90d,
  (m90.fecha_ultima_compra IS NOT NULL) AS es_cliente_activado_90d,
  
  -- 🏷️ ESTATUS EN EL MES ACTUAL (JULIO 2026)
  (mes.fecha_ultima_compra_mes IS NOT NULL) AS compro_en_mes_actual,
  COALESCE(ROUND(mes.cajas_mes_actual, 2), 0) AS cajas_mes_actual,
  COALESCE(ROUND(mes.venta_usd_mes_actual, 2), 0) AS venta_usd_mes_actual,
  
  -- 📦 TOTALES DE 90 DÍAS
  COALESCE(ROUND(m90.cajas_90d, 2), 0) AS cajas_totales_90d,
  COALESCE(ROUND(m90.venta_usd_90d, 2), 0) AS venta_usd_totales_90d
FROM cartera_clientes c
LEFT JOIN metricas_90d m90
  ON c.empresa = m90.empresa
 AND c.codigo_sucursal = m90.codigo_sucursal
 AND c.codigo_vendedor = m90.codigo_vendedor
 AND c.codigo_proveedor = m90.codigo_proveedor
 AND c.codigo_cliente = m90.codigo_cliente
LEFT JOIN metricas_mes_actual mes
  ON c.empresa = mes.empresa
 AND c.codigo_sucursal = mes.codigo_sucursal
 AND c.codigo_vendedor = mes.codigo_vendedor
 AND c.codigo_proveedor = mes.codigo_proveedor
 AND c.codigo_cliente = mes.codigo_cliente;
"""

def create_maestro_view():
    print("==========================================================================")
    print("  CREANDO VISTA EN BIGQUERY: vw_maestro_clientes_activables")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_maestro_clientes_activables' creada exitosamente en BigQuery Gold.")

    # Consulta muestra del listado de clientes
    sql_sample = """
    SELECT
      nombre_empresa,
      nombre_sucursal,
      nombre_vendedor,
      nombre_proveedor,
      codigo_cliente,
      nombre_cliente,
      rif_cliente,
      estatus_activacion_90d,
      compro_en_mes_actual,
      dias_sin_comprar,
      venta_usd_mes_actual,
      venta_usd_totales_90d
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_maestro_clientes_activables`
    WHERE es_cliente_activado_90d = TRUE
    ORDER BY venta_usd_mes_actual DESC
    LIMIT 6;
    """
    print("\n  📊 MUESTRA DEL LISTADO DEL MAESTRO DE CLIENTES ACTIVABLES:")
    for r in client.query(sql_sample).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_maestro_view()
