"""Script para actualizar la Capa Gold (fct_ventas y vistas analíticas)
incorporando las columnas oficiales 'nombre_empresa' y 'razon_social' mediante JOIN con dim_empresa.
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

print("==========================================================================")
print("  ACTUALIZANDO MODELOS DE LA CAPA GOLD PARA INCLUIR NOMBRE_EMPRESA Y RAZON_SOCIAL")
print("==========================================================================")

# 1. Actualizar vw_reporte_inventario
sql_inv = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_reporte_inventario` AS
SELECT
  ra.source_empresa AS empresa,
  COALESCE(emp.nombre_empresa, ra.source_empresa) AS nombre_empresa,
  emp.razon_social,
  ra.cod_alm AS codigo_almacen,
  COALESCE(alm.nom_alm, ra.cod_alm) AS nombre_almacen,
  ra.cod_art AS codigo_articulo,
  COALESCE(art.nom_art, ra.cod_art) AS nombre_articulo,
  art.modelo,
  art.cod_mar AS marca,
  ra.exi_act1 AS stock_unidades,
  art.cap_bulto AS unidades_por_caja,
  SAFE_DIVIDE(ra.exi_act1, NULLIF(art.cap_bulto, 0)) AS stock_cajas,
  ROUND((ra.exi_act1 * COALESCE(art.peso, 0)), 2) AS peso_total_kg,
  ra.registro AS fecha_ultima_actualizacion
FROM `factory-etl-dev-0y1dhf.factory_etl_silver.sil_renglones_almacenes` ra
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` emp
  ON ra.source_empresa = emp.source_empresa
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_almacenes` alm
  ON ra.source_empresa = alm.source_empresa AND ra.cod_alm = alm.cod_alm
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_articulos` art
  ON ra.source_empresa = art.source_empresa AND ra.cod_art = art.cod_art
WHERE ra.exi_act1 > 0;
"""
client.query(sql_inv).result()
print("  ✓ Vista Gold 'vw_reporte_inventario' actualizada con nombre_empresa.")

# 2. Actualizar vw_base_activable_clientes_90d
sql_base_cli = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_clientes_90d` AS
SELECT
  v.source_empresa AS empresa,
  COALESCE(emp.nombre_empresa, v.source_empresa) AS nombre_empresa,
  v.cod_suc AS codigo_sucursal,
  COALESCE(suc.nom_suc, v.cod_suc) AS nombre_sucursal,
  v.cod_ven AS codigo_vendedor,
  v.nom_ven AS nombre_vendedor,
  v.cod_pro AS codigo_proveedor,
  v.nom_pro AS nombre_proveedor,
  v.cod_mar AS codigo_marca,
  v.nom_mar AS nombre_marca,
  COUNT(DISTINCT v.cod_cli) AS base_activable_clientes_90d,
  COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cod_cli END) AS clientes_activados_mes_actual,
  (COUNT(DISTINCT v.cod_cli) - COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cod_cli END)) AS clientes_pendientes_activacion_mes,
  ROUND(SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cod_cli END), NULLIF(COUNT(DISTINCT v.cod_cli), 0)) * 100, 2) AS pct_activacion_mes_actual,
  ROUND(SUM(CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cajas_vendidas ELSE 0 END), 2) AS cajas_vendidas_mes_actual,
  ROUND(SUM(CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.neto_dcto ELSE 0 END), 2) AS venta_usd_mes_actual,
  ROUND(SUM(v.cajas_vendidas), 2) AS total_cajas_90d,
  ROUND(SUM(v.neto_dcto), 2) AS monto_total_venta_usd_90d,
  MAX(v.fecha_registro) AS fecha_ultima_venta
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` emp
  ON v.source_empresa = emp.source_empresa
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
  ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc
WHERE v.fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10;
"""
client.query(sql_base_cli).result()
print("  ✓ Vista Gold 'vw_base_activable_clientes_90d' actualizada con nombre_empresa.")

# 3. Actualizar vw_base_activable_rif_90d
sql_base_rif = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_rif_90d` AS
SELECT
  v.source_empresa AS empresa,
  COALESCE(emp.nombre_empresa, v.source_empresa) AS nombre_empresa,
  v.cod_suc AS codigo_sucursal,
  COALESCE(suc.nom_suc, v.cod_suc) AS nombre_sucursal,
  v.cod_ven AS codigo_vendedor,
  v.nom_ven AS nombre_vendedor,
  v.cod_pro AS codigo_proveedor,
  v.nom_pro AS nombre_proveedor,
  v.cod_mar AS codigo_marca,
  v.nom_mar AS nombre_marca,
  COUNT(DISTINCT NULLIF(TRIM(v.rif), '')) AS base_activable_rifs_90d,
  COUNT(DISTINCT v.cod_cli) AS total_puntos_de_venta_cod_cli,
  COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN NULLIF(TRIM(v.rif), '') END) AS rifs_activados_mes_actual,
  (COUNT(DISTINCT NULLIF(TRIM(v.rif), '')) - COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN NULLIF(TRIM(v.rif), '') END)) AS rifs_pendientes_activacion_mes,
  ROUND(SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN NULLIF(TRIM(v.rif), '') END), NULLIF(COUNT(DISTINCT NULLIF(TRIM(v.rif), '')), 0)) * 100, 2) AS pct_activacion_rif_mes_actual,
  ROUND(SUM(CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.cajas_vendidas ELSE 0 END), 2) AS cajas_vendidas_mes_actual,
  ROUND(SUM(CASE WHEN v.fecha_registro >= DATE_TRUNC(CURRENT_DATE(), MONTH) THEN v.neto_dcto ELSE 0 END), 2) AS venta_usd_mes_actual,
  ROUND(SUM(v.cajas_vendidas), 2) AS total_cajas_90d,
  ROUND(SUM(v.neto_dcto), 2) AS monto_total_venta_usd_90d,
  MAX(v.fecha_registro) AS fecha_ultima_venta
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` emp
  ON v.source_empresa = emp.source_empresa
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
  ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc
WHERE v.fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
  AND NULLIF(TRIM(v.rif), '') IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10;
"""
client.query(sql_base_rif).result()
print("  ✓ Vista Gold 'vw_base_activable_rif_90d' actualizada con nombre_empresa.")

# 4. Actualizar vw_detalle_facturacion_clientes
sql_det = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_detalle_facturacion_clientes` AS
SELECT
  v.source_empresa AS empresa,
  COALESCE(emp.nombre_empresa, v.source_empresa) AS nombre_empresa,
  emp.razon_social AS razon_social_empresa,
  v.cod_suc AS codigo_sucursal,
  COALESCE(suc.nom_suc, v.cod_suc) AS nombre_sucursal,
  v.cod_ven AS codigo_vendedor,
  v.nom_ven AS nombre_vendedor,
  v.cod_cli AS codigo_cliente,
  v.nom_cli AS nombre_cliente,
  NULLIF(TRIM(v.rif), '') AS rif_cliente,
  v.nom_cla AS clase_cliente,
  v.nom_est AS estado_cliente,
  v.nom_ciu AS ciudad_cliente,
  v.tipo_documento,
  v.documento AS numero_documento,
  v.renglon AS numero_renglon,
  v.registro AS timestamp_registro,
  v.fecha_registro AS fecha,
  v.anio, v.mes, v.nombre_mes, v.anio_mes,
  v.trimestre, v.trimestre_nombre, v.anio_trimestre,
  v.semana_del_anio, v.anio_semana, v.quincena, v.quincena_nombre,
  v.cod_pro AS codigo_proveedor, v.nom_pro AS nombre_proveedor,
  v.cod_mar AS codigo_marca, v.nom_mar AS nombre_marca,
  v.nom_dep AS departamento, v.cod_sec AS seccion,
  v.cod_art AS codigo_articulo, v.nom_art AS nombre_articulo, v.modelo, v.cod_uni1 AS unidad_medida,
  v.unidades_vendidas, v.cajas_vendidas, v.peso_total_kg, v.peso_total_toneladas, v.volumen_total_m3,
  v.monto_bruto, v.dcto AS monto_descuento, v.neto AS monto_neto, v.tasa AS tasa_cambio, v.neto_dcto AS monto_total_usd
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` emp
  ON v.source_empresa = emp.source_empresa
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
  ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc;
"""
client.query(sql_det).result()
print("  ✓ Vista Gold 'vw_detalle_facturacion_clientes' actualizada con nombre_empresa.")

print("\n  🎉 ¡TODAS LAS VISTAS DEL MODELO GOLD FUERON ACTUALIZADAS CON NOMBRE_EMPRESA!")
