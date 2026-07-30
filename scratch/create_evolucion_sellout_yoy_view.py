"""Script para crear la vista analítica vw_evolucion_sellout_yoy en BigQuery Gold
Permite analizar la evolución de Sell-Out (Ventas Diarias) agrupado por:
- Empresa, Sucursal (Nombre), Vendedor, Proveedor, Marca, SKU / Artículo
- Jerarquías de Tiempo: Día, Semana ISO, Quincena, Mes, Trimestre, Año
- Comparativa vs Mismo Período del Año Anterior (YoY - Year over Year) y % Crecimiento
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_evolucion_sellout_yoy` AS
WITH ventas_diarias AS (
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
    v.cod_art AS codigo_articulo,
    v.nom_art AS nombre_articulo,
    v.modelo,
    
    -- 🗓️ JERARQUÍAS DE TIEMPO COMERCIAL
    v.fecha_registro AS fecha,
    v.anio,
    v.mes,
    v.nombre_mes,
    v.anio_mes,
    v.trimestre,
    v.trimestre_nombre,
    v.anio_trimestre,
    v.semana_del_anio,
    v.anio_semana,
    v.quincena,
    v.quincena_nombre,
    
    -- 📊 MÉTRICAS DEL PERÍODO ACTUAL
    COUNT(DISTINCT v.documento) AS total_documentos,
    COUNT(DISTINCT v.cod_cli) AS clientes_unicos_compradores,
    SUM(v.unidades_vendidas) AS unidades_vendidas_actual,
    ROUND(SUM(v.cajas_vendidas), 2) AS cajas_vendidas_actual,
    ROUND(SUM(v.peso_total_toneladas), 3) AS toneladas_vendidas_actual,
    ROUND(SUM(v.neto_dcto), 2) AS venta_usd_actual
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
  LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
    ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc
  GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24
),
ventas_prev_year AS (
  SELECT
    v.source_empresa AS empresa,
    v.cod_suc AS codigo_sucursal,
    v.cod_ven AS codigo_vendedor,
    v.cod_pro AS codigo_proveedor,
    v.cod_mar AS codigo_marca,
    v.cod_art AS codigo_articulo,
    
    -- Mismo día del año anterior (+1 año en fecha)
    DATE_ADD(v.fecha_registro, INTERVAL 1 YEAR) AS fecha_equivalente,
    
    ROUND(SUM(v.cajas_vendidas), 2) AS cajas_vendidas_prev_year,
    ROUND(SUM(v.neto_dcto), 2) AS venta_usd_prev_year
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
  act.empresa,
  act.codigo_sucursal,
  act.nombre_sucursal,
  act.codigo_vendedor,
  act.nombre_vendedor,
  act.codigo_proveedor,
  act.nombre_proveedor,
  act.codigo_marca,
  act.nombre_marca,
  act.codigo_articulo,
  act.nombre_articulo,
  act.modelo,
  
  -- 🗓️ TIEMPO COMERCIAL
  act.fecha,
  act.anio,
  act.mes,
  act.nombre_mes,
  act.anio_mes,
  act.trimestre,
  act.trimestre_nombre,
  act.anio_trimestre,
  act.semana_del_anio,
  act.anio_semana,
  act.quincena,
  act.quincena_nombre,
  
  -- 📊 MÉTRICAS DEL PERÍODO ACTUAL
  act.total_documentos,
  act.clientes_unicos_compradores,
  act.unidades_vendidas_actual,
  act.cajas_vendidas_actual,
  act.toneladas_vendidas_actual,
  act.venta_usd_actual,
  
  -- 📈 COMPARATIVA AÑO ANTERIOR (YoY - Same Day Last Year)
  COALESCE(prev.cajas_vendidas_prev_year, 0) AS cajas_vendidas_anio_anterior,
  COALESCE(prev.venta_usd_prev_year, 0) AS venta_usd_anio_anterior,
  
  -- 🧮 VARIACIÓN Y % CRECIMIENTO YoY
  ROUND((act.venta_usd_actual - COALESCE(prev.venta_usd_prev_year, 0)), 2) AS variacion_venta_usd_yoy,
  ROUND(
    SAFE_DIVIDE(
      (act.venta_usd_actual - COALESCE(prev.venta_usd_prev_year, 0)),
      NULLIF(prev.venta_usd_prev_year, 0)
    ) * 100, 2
  ) AS pct_crecimiento_yoy
FROM ventas_diarias act
LEFT JOIN ventas_prev_year prev
  ON act.empresa = prev.empresa
 AND act.codigo_sucursal = prev.codigo_sucursal
 AND act.codigo_vendedor = prev.codigo_vendedor
 AND act.codigo_proveedor = prev.codigo_proveedor
 AND act.codigo_marca = prev.codigo_marca
 AND act.codigo_articulo = prev.codigo_articulo
 AND act.fecha = prev.fecha_equivalente;
"""

def create_sellout_yoy_view():
    print("==========================================================================")
    print("  CREANDO VISTA EN BIGQUERY: vw_evolucion_sellout_yoy")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_evolucion_sellout_yoy' creada exitosamente en BigQuery Gold.")

    # Consulta de prueba de Sell-Out con comparativa YoY por Trimestre/Mes
    sql_test = """
    SELECT
      empresa,
      nombre_sucursal,
      nombre_vendedor,
      nombre_marca,
      nombre_articulo,
      anio_trimestre,
      anio_mes,
      venta_usd_actual,
      venta_usd_anio_anterior,
      variacion_venta_usd_yoy,
      pct_crecimiento_yoy
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_evolucion_sellout_yoy`
    WHERE venta_usd_actual > 500
    ORDER BY fecha DESC, venta_usd_actual DESC
    LIMIT 8;
    """
    print("\n  📊 MUESTRA DE EVOLUCIÓN SELL-OUT CON COMPARATIVA AÑO ANTERIOR (YoY):")
    for r in client.query(sql_test).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_sellout_yoy_view()
