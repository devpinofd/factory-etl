"""Script para actualizar la Vista Gold vw_reporte_inventario con todas las métricas solicitadas:
- fraccion_unitaria (Fracciones unitarias / Unidades por caja)
- unidades_totales (Unidades totales / Existencias totales)
- peso_unitario (Peso unitario en kg)
- kg_totales (Kilogramos totales)
- toneladas_totales (Toneladas totales)
- capacidad_bultos (Capacidad bultos / Unidades por bulto)
- bultos_totales (Bultos totales)
- cajas_totales (Cajas totales)
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"

CREATE_VIEW_SQL = f"""
CREATE OR REPLACE VIEW `{PROJECT_ID}.factory_etl_gold.vw_reporte_inventario` AS
SELECT
  ra.source_empresa AS empresa,
  COALESCE(emp.nombre_empresa, ra.source_empresa) AS nombre_empresa,
  emp.razon_social AS razon_social,
  ra.cod_alm AS codigo_almacen,
  COALESCE(alm.nom_alm, ra.cod_alm) AS nombre_almacen,
  ra.cod_art AS codigo_articulo,
  COALESCE(art.nom_art, ra.cod_art) AS nombre_articulo,
  art.modelo,
  art.cod_mar AS marca,
  art.cod_pro AS proveedor,
  
  -- 📦 Métricas Solicitadas de Fracciones, Pesos, Bultos y Cajas
  COALESCE(NULLIF(art.fraccion, 0), 1) AS fraccion_unitaria,
  COALESCE(ra.exi_act1, 0) AS unidades_totales,
  ROUND(SAFE_DIVIDE(ra.exi_act1, NULLIF(art.fraccion, 0)), 2) AS cajas_totales,
  
  COALESCE(art.peso, 0) AS peso_unitario,
  ROUND(COALESCE(ra.exi_act1, 0) * COALESCE(art.peso, 0), 2) AS kg_totales,
  ROUND(SAFE_DIVIDE(COALESCE(ra.exi_act1, 0) * COALESCE(art.peso, 0), 1000), 3) AS toneladas_totales,
  
  COALESCE(NULLIF(art.cap_bulto, 0), NULLIF(art.fraccion, 0), 1) AS capacidad_bultos,
  ROUND(SAFE_DIVIDE(ra.exi_act1, COALESCE(NULLIF(art.cap_bulto, 0), NULLIF(art.fraccion, 0), 1)), 2) AS bultos_totales,
  
  -- Compatibilidad con nombres anteriores
  ra.exi_act1 AS stock_unidades,
  ROUND(SAFE_DIVIDE(ra.exi_act1, NULLIF(art.fraccion, 0)), 2) AS stock_cajas,
  ROUND(COALESCE(ra.exi_act1, 0) * COALESCE(art.peso, 0), 2) AS peso_total_kg,
  
  ra.registro AS fecha_ultima_actualizacion
FROM `{PROJECT_ID}.factory_etl_silver.sil_renglones_almacenes` ra
LEFT JOIN `{PROJECT_ID}.factory_etl_gold.dim_empresa` emp
  ON ra.source_empresa = emp.source_empresa
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_almacenes` alm
  ON ra.source_empresa = alm.source_empresa AND ra.cod_alm = alm.cod_alm
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_articulos` art
  ON ra.source_empresa = art.source_empresa AND ra.cod_art = art.cod_art
WHERE ra.exi_act1 > 0;
"""

def update_inventory_view():
    print("==========================================================================")
    print("  ACTUALIZANDO VISTA GOLD: factory_etl_gold.vw_reporte_inventario")
    print("==========================================================================")

    bq_client = bigquery.Client(project=PROJECT_ID, location="us-central1")
    bq_client.query(CREATE_VIEW_SQL).result()
    print("  ✓ Vista vw_reporte_inventario actualizada exitosamente en BigQuery.")

    # Muestra de Verificación
    q_sample = f"""
    SELECT 
      nombre_empresa,
      codigo_articulo,
      nombre_articulo,
      fraccion_unitaria,
      unidades_totales,
      cajas_totales,
      peso_unitario,
      kg_totales,
      capacidad_bultos,
      bultos_totales
    FROM `{PROJECT_ID}.factory_etl_gold.vw_reporte_inventario`
    LIMIT 5
    """
    print("\n--- MUESTRA DE VERIFICACIÓN DE VISTA INVENTARIOS ---")
    for r in bq_client.query(q_sample).result():
        print(" ", dict(r))

if __name__ == "__main__":
    update_inventory_view()
