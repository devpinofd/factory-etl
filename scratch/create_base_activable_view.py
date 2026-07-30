"""Script para crear la vista de Base Activable de Clientes (90 días) en BigQuery Gold"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_clientes_90d` AS
WITH cartera_total AS (
  SELECT DISTINCT
    source_empresa AS empresa,
    cod_ven,
    nom_ven,
    cod_cli,
    nom_cli,
    cod_pro,
    nom_pro
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
),
compras_90d AS (
  SELECT
    source_empresa AS empresa,
    cod_ven,
    cod_cli,
    cod_pro,
    MAX(fecha_registro) AS fecha_ultima_compra,
    SUM(neto_dcto) AS monto_total_90d
  FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas`
  WHERE fecha_registro >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
  GROUP BY 1, 2, 3, 4
)
SELECT
  c.empresa,
  c.cod_ven AS codigo_vendedor,
  c.nom_ven AS nombre_vendedor,
  c.cod_pro AS codigo_proveedor,
  c.nom_pro AS nombre_proveedor,
  c.cod_cli AS codigo_cliente,
  c.nom_cli AS nombre_cliente,
  p.fecha_ultima_compra,
  COALESCE(DATE_DIFF(CURRENT_DATE(), p.fecha_ultima_compra, DAY), 999) AS dias_sin_comprar,
  
  -- 📊 Clasificación de Negocio
  CASE 
    WHEN p.fecha_ultima_compra IS NOT NULL THEN 'ACTIVADO'
    ELSE 'BASE ACTIVABLE (INACTIVO)'
  END AS estatus_cliente,
  
  (p.fecha_ultima_compra IS NOT NULL) AS es_activado,
  (p.fecha_ultima_compra IS NULL) AS es_base_activable
FROM cartera_total c
LEFT JOIN compras_90d p
  ON c.empresa = p.empresa
 AND c.cod_ven = p.cod_ven
 AND c.cod_cli = p.cod_cli
 AND c.cod_pro = p.cod_pro;
"""

def create_base_activable_view():
    print("==========================================================================")
    print("  CREANDO VISTA EN BIGQUERY: vw_base_activable_clientes_90d")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_base_activable_clientes_90d' creada exitosamente en BigQuery Gold.")

    # Consulta resumida de prueba
    sql_summary = """
    SELECT
      empresa,
      codigo_vendedor,
      nombre_vendedor,
      COUNT(DISTINCT codigo_cliente) AS cartera_total_clientes,
      COUNT(DISTINCT CASE WHEN es_activado THEN codigo_cliente END) AS clientes_activados,
      COUNT(DISTINCT CASE WHEN es_base_activable THEN codigo_cliente END) AS base_activable_inactivos,
      ROUND(SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN es_activado THEN codigo_cliente END), COUNT(DISTINCT codigo_cliente)) * 100, 2) AS pct_activacion
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_base_activable_clientes_90d`
    GROUP BY 1, 2, 3
    ORDER BY cartera_total_clientes DESC
    LIMIT 5;
    """
    print("\n  📊 MUESTRA DE LA MEDIDA POR VENDEDOR EN BIGQUERY:")
    for r in client.query(sql_summary).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_base_activable_view()
