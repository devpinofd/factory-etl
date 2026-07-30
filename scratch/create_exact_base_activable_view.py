"""Script para recrear la vista vw_base_activable_clientes_90d con la definición exacta requerida:
Base Activable = Clientes únicos que han comprado al menos 1 SKU en los últimos 90 días desde la fecha actual hacia atrás,
agrupado por Empresa, Sucursal, Vendedor, Proveedor y Marca.
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
  
  -- 📊 METRICA PRINCIPAL: BASE ACTIVABLE DE CLIENTES (ÚLTIMOS 90 DÍAS)
  COUNT(DISTINCT cod_cli) AS base_activable_clientes,
  
  -- 📦 Métricas Complementarias del Período
  COUNT(DISTINCT cod_art) AS skus_distintos_comprados,
  COUNT(DISTINCT documento) AS total_documentos,
  SUM(unidades_vendidas) AS total_unidades,
  ROUND(SUM(cajas_vendidas), 2) AS total_cajas,
  ROUND(SUM(peso_total_toneladas), 3) AS total_toneladas,
  ROUND(SUM(neto_dcto), 2) AS monto_total_venta_usd,
  MAX(fecha_registro) AS fecha_ultima_venta
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
WHERE fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8;
"""

def create_exact_view():
    print("==========================================================================")
    print("  ACTUALIZANDO VISTA EN BIGQUERY CON LA LÓGICA EXACTA DE BASE ACTIVABLE")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_base_activable_clientes_90d' actualizada exitosamente en BigQuery Gold.")

    # Consulta de prueba por Empresa, Sucursal, Vendedor, Proveedor y Marca
    sql_test = """
    SELECT
      empresa,
      codigo_sucursal,
      codigo_vendedor,
      nombre_vendedor,
      nombre_proveedor,
      nombre_marca,
      base_activable_clientes,
      skus_distintos_comprados,
      total_cajas,
      monto_total_venta_usd
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_clientes_90d`
    ORDER BY base_activable_clientes DESC
    LIMIT 8;
    """
    print("\n  📊 MUESTRA DE LA BASE ACTIVABLE POR MARCA / SUCURSAL / VENDEDOR / EMPRESA:")
    for r in client.query(sql_test).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_exact_view()
