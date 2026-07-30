"""Script para crear la vista vw_clasificacion_clientes_frecuencia_semanal en BigQuery Gold:
Calcula la clasificación de clientes (Tipo 4, Tipo 3, Tipo 2, Tipo 1) basada en el número de semanas distintas en las que compraron durante el mes.
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_clasificacion_clientes_frecuencia_semanal` AS
WITH semanas_compradas AS (
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
    v.cod_cli AS codigo_cliente,
    v.nom_cli AS nombre_cliente,
    NULLIF(TRIM(v.rif), '') AS rif_cliente,
    v.anio_mes,
    v.nombre_mes,
    v.anio,
    
    -- 🗓️ Cantidad de semanas distintas en las que compró en ese mes
    COUNT(DISTINCT v.anio_semana) AS semanas_con_compra,
    COUNT(DISTINCT v.documento) AS total_facturas_mes,
    SUM(v.cajas_vendidas) AS cajas_compradas_mes,
    SUM(v.neto_dcto) AS venta_usd_mes,
    MAX(v.fecha_registro) AS fecha_ultima_compra_mes
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
  LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
    ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc
  GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
)
SELECT
  s.empresa,
  s.codigo_sucursal,
  s.nombre_sucursal,
  s.codigo_vendedor,
  s.nombre_vendedor,
  s.codigo_proveedor,
  s.nombre_proveedor,
  s.codigo_marca,
  s.nombre_marca,
  s.codigo_cliente,
  s.nombre_cliente,
  s.rif_cliente,
  s.anio_mes,
  s.nombre_mes,
  s.anio,
  s.semanas_con_compra,
  s.total_facturas_mes,
  ROUND(s.cajas_compradas_mes, 2) AS cajas_compradas_mes,
  ROUND(s.venta_usd_mes, 2) AS venta_usd_mes,
  s.fecha_ultima_compra_mes,
  
  -- 🏷️ CLASIFICACIÓN DEL TIPO DE CLIENTE SEGÚN FRECUENCIA SEMANAL EN EL MES
  CASE
    WHEN s.semanas_con_compra >= 4 THEN 'Tipo 4 (Todas las Semanas / Frecuente)'
    WHEN s.semanas_con_compra = 3 THEN 'Tipo 3 (3 Semanas / Regular)'
    WHEN s.semanas_con_compra = 2 THEN 'Tipo 2 (2 Semanas / Ocasional)'
    WHEN s.semanas_con_compra = 1 THEN 'Tipo 1 (1 Semana / Esporádico)'
    ELSE 'Tipo 0 (Inactivo)'
  END AS tipo_cliente_frecuencia_nombre,
  
  CASE
    WHEN s.semanas_con_compra >= 4 THEN 4
    WHEN s.semanas_con_compra = 3 THEN 3
    WHEN s.semanas_con_compra = 2 THEN 2
    WHEN s.semanas_con_compra = 1 THEN 1
    ELSE 0
  END AS tipo_cliente_frecuencia_num
FROM semanas_compradas s;
"""

def create_frecuencia_view():
    print("==========================================================================")
    print("  CREANDO VISTA EN BIGQUERY: vw_clasificacion_clientes_frecuencia_semanal")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_clasificacion_clientes_frecuencia_semanal' creada exitosamente.")

    # Consulta de distribución por Tipo de Cliente en el Mes Actual
    sql_distribucion = """
    SELECT
      anio_mes,
      tipo_cliente_frecuencia_nombre,
      tipo_cliente_frecuencia_num,
      COUNT(DISTINCT codigo_cliente) AS total_clientes,
      ROUND(SUM(venta_usd_mes), 2) AS total_venta_usd
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_clasificacion_clientes_frecuencia_semanal`
    WHERE anio_mes = '2026-07'
    GROUP BY 1, 2, 3
    ORDER BY tipo_cliente_frecuencia_num DESC;
    """
    print("\n  📊 DISTRIBUCIÓN DE CLIENTES POR TIPO (1 a 4) EN EL MES DE JULIO 2026:")
    for r in client.query(sql_distribucion).result():
        print("  ", dict(r))

    # Muestra detallada de Clientes Tipo 4
    sql_tipo4 = """
    SELECT
      empresa,
      nombre_sucursal,
      nombre_vendedor,
      nombre_cliente,
      nombre_marca,
      semanas_con_compra,
      tipo_cliente_frecuencia_nombre,
      cajas_compradas_mes,
      venta_usd_mes
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_clasificacion_clientes_frecuencia_semanal`
    WHERE tipo_cliente_frecuencia_num = 4 AND anio_mes = '2026-07'
    ORDER BY venta_usd_mes DESC
    LIMIT 5;
    """
    print("\n  ⭐ MUESTRA DE CLIENTES CLASIFICADOS COMO TIPO 4 (TODAS LAS SEMANAS DEL MES):")
    for r in client.query(sql_tipo4).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_frecuencia_view()
