"""Script para crear la vista vw_reporte_venta_cero_sku_mes_actual en BigQuery Gold (Optimizado por Empresa + Marca)"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_reporte_venta_cero_sku_mes_actual` AS
WITH cartera_vendedor_clientes AS (
  -- Clientes y las marcas activas que compran/maneja su vendedor
  SELECT DISTINCT
    source_empresa AS empresa,
    cod_suc AS codigo_sucursal,
    cod_ven AS codigo_vendedor,
    nom_ven AS nombre_vendedor,
    cod_cli AS codigo_cliente,
    nom_cli AS nombre_cliente,
    NULLIF(TRIM(rif), '') AS rif_cliente,
    cod_pro AS codigo_proveedor,
    nom_pro AS nombre_proveedor,
    cod_mar AS codigo_marca,
    nom_mar AS nombre_marca
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
  WHERE fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
),
catalogo_skus AS (
  -- SKUs activos por marca y proveedor
  SELECT DISTINCT
    source_empresa AS empresa,
    cod_pro AS codigo_proveedor,
    cod_mar AS codigo_marca,
    cod_art AS codigo_articulo,
    nom_art AS nombre_articulo,
    modelo
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
  WHERE fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
),
matriz_esperada AS (
  -- Matriz Cliente x SKU de la misma Empresa y Marca
  SELECT
    c.empresa,
    c.codigo_sucursal,
    c.codigo_vendedor,
    c.nombre_vendedor,
    c.codigo_cliente,
    c.nombre_cliente,
    c.rif_cliente,
    c.codigo_proveedor,
    c.nombre_proveedor,
    c.codigo_marca,
    c.nombre_marca,
    p.codigo_articulo,
    p.nombre_articulo,
    p.modelo
  FROM cartera_vendedor_clientes c
  INNER JOIN catalogo_skus p
    ON c.empresa = p.empresa
   AND c.codigo_proveedor = p.codigo_proveedor
   AND c.codigo_marca = p.codigo_marca
),
ventas_mes_actual AS (
  -- Ventas reales del mes actual (Julio 2026)
  SELECT
    source_empresa AS empresa,
    cod_suc AS codigo_sucursal,
    cod_ven AS codigo_vendedor,
    cod_cli AS codigo_cliente,
    cod_art AS codigo_articulo,
    SUM(unidades_vendidas) AS unidades_vendidas_mes,
    SUM(cajas_vendidas) AS cajas_vendidas_mes,
    SUM(neto_dcto) AS venta_usd_mes,
    MAX(fecha_registro) AS fecha_ultima_compra_sku
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
  WHERE fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH)
  GROUP BY 1, 2, 3, 4, 5
)
SELECT
  m.empresa,
  m.codigo_sucursal,
  COALESCE(suc.nom_suc, m.codigo_sucursal) AS nombre_sucursal,
  m.codigo_vendedor,
  m.nombre_vendedor,
  m.codigo_cliente,
  m.nombre_cliente,
  m.rif_cliente,
  m.codigo_proveedor,
  m.nombre_proveedor,
  m.codigo_marca,
  m.nombre_marca,
  m.codigo_articulo,
  m.nombre_articulo,
  m.modelo,
  
  -- 📊 ESTATUS EN EL MES ACTUAL (JULIO 2026)
  COALESCE(v.unidades_vendidas_mes, 0) AS unidades_vendidas_mes_actual,
  COALESCE(ROUND(v.cajas_vendidas_mes, 2), 0) AS cajas_vendidas_mes_actual,
  COALESCE(ROUND(v.venta_usd_mes, 2), 0) AS venta_usd_mes_actual,
  v.fecha_ultima_compra_sku,
  
  -- 🏷️ CLASIFICACIÓN DE VENTA CERO
  CASE
    WHEN v.venta_usd_mes IS NOT NULL AND v.venta_usd_mes > 0 THEN 'SKU COMPRADO'
    ELSE 'VENTA CERO (OPORTUNIDAD EN SKU)'
  END AS estatus_venta_sku,
  
  (v.venta_usd_mes IS NULL OR v.venta_usd_mes <= 0) AS es_venta_cero
FROM matriz_esperada m
LEFT JOIN ventas_mes_actual v
  ON m.empresa = v.empresa
 AND m.codigo_sucursal = v.codigo_sucursal
 AND m.codigo_vendedor = v.codigo_vendedor
 AND m.codigo_cliente = v.codigo_cliente
 AND m.codigo_articulo = v.codigo_articulo
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
  ON m.empresa = suc.source_empresa AND m.codigo_sucursal = suc.cod_suc;
"""

def create_venta_cero_view():
    print("==========================================================================")
    print("  CREANDO VISTA OPTIMIZADA EN BIGQUERY: vw_reporte_venta_cero_sku_mes_actual")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_reporte_venta_cero_sku_mes_actual' creada exitosamente.")

    # Consulta de resumen por Vendedor y Marca de Oportunidades de Venta Cero por SKU
    sql_summary = """
    SELECT
      empresa,
      nombre_sucursal,
      nombre_vendedor,
      nombre_marca,
      COUNT(DISTINCT codigo_cliente) AS cartera_clientes,
      COUNT(DISTINCT codigo_articulo) AS skus_marca,
      COUNT(DISTINCT CASE WHEN es_venta_cero THEN CONCAT(codigo_cliente, '-', codigo_articulo) END) AS brechas_venta_cero_sku,
      COUNT(DISTINCT CASE WHEN NOT es_venta_cero THEN CONCAT(codigo_cliente, '-', codigo_articulo) END) AS skus_activados_comprados,
      ROUND(
        SAFE_DIVIDE(
          COUNT(DISTINCT CASE WHEN NOT es_venta_cero THEN CONCAT(codigo_cliente, '-', codigo_articulo) END),
          COUNT(DISTINCT CONCAT(codigo_cliente, '-', codigo_articulo))
        ) * 100, 2
      ) AS pct_penetracion_sku_mes
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_reporte_venta_cero_sku_mes_actual`
    WHERE empresa = 'tinito'
    GROUP BY 1, 2, 3, 4
    ORDER BY brechas_venta_cero_sku DESC
    LIMIT 6;
    """
    print("\n  📊 MUESTRA DE RESUMEN DE BRECHAS DE VENTA CERO POR SKU (JULIO 2026):")
    for r in client.query(sql_summary).result():
        print("  ", dict(r))

    # Muestra individual de brechas Venta Cero por SKU
    sql_detail = """
    SELECT
      nombre_vendedor,
      nombre_cliente,
      nombre_marca,
      nombre_articulo,
      estatus_venta_sku
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_reporte_venta_cero_sku_mes_actual`
    WHERE es_venta_cero = TRUE AND empresa = 'tinito' AND nombre_marca = 'PARMALAT'
    LIMIT 5;
    """
    print("\n  🎯 MUESTRA DETALLADA DE VENTA CERO POR SKU (PARMALAT EN TINITO):")
    for r in client.query(sql_detail).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_venta_cero_view()
