"""Script para crear la vista analítica granular vw_detalle_facturacion_clientes en BigQuery Gold
Permite hacer drill-down desde Empresa -> Sucursal -> Vendedor -> Cliente (con RIF) -> Factura / Documento -> Renglón -> SKU / Marca / Proveedor
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_view = """
CREATE OR REPLACE VIEW `factory-etl-dev-0y1dhf.factory_etl_gold.vw_detalle_facturacion_clientes` AS
SELECT
  v.source_empresa AS empresa,
  v.cod_suc AS codigo_sucursal,
  COALESCE(suc.nom_suc, v.cod_suc) AS nombre_sucursal,
  v.cod_ven AS codigo_vendedor,
  v.nom_ven AS nombre_vendedor,
  
  -- 👤 GRANULARIDAD DE CLIENTE Y RIF
  v.cod_cli AS codigo_cliente,
  v.nom_cli AS nombre_cliente,
  NULLIF(TRIM(v.rif), '') AS rif_cliente,
  v.nom_cla AS clase_cliente,
  v.nom_est AS estado_cliente,
  v.nom_ciu AS ciudad_cliente,
  
  -- 🧾 GRANULARIDAD TRANSACCIONAL: DOCUMENTO Y RENGLÓN
  v.tipo_documento,
  v.documento AS numero_documento,
  v.renglon AS numero_renglon,
  v.registro AS timestamp_registro,
  v.fecha_registro AS fecha,
  
  -- 🗓️ DIMENSIÓN DE TIEMPO COMERCIAL
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
  
  -- 📦 PRODUCTO / SKU / MARCA / PROVEEDOR
  v.cod_pro AS codigo_proveedor,
  v.nom_pro AS nombre_proveedor,
  v.cod_mar AS codigo_marca,
  v.nom_mar AS nombre_marca,
  v.nom_dep AS departamento,
  v.cod_sec AS seccion,
  v.cod_art AS codigo_articulo,
  v.nom_art AS nombre_articulo,
  v.modelo,
  v.cod_uni1 AS unidad_medida,
  
  -- 📊 MÉTRICAS FÍSICAS Y FINANCIERAS DEL RENGLÓN
  v.unidades_vendidas,
  v.cajas_vendidas,
  v.peso_total_kg,
  v.peso_total_toneladas,
  v.volumen_total_m3,
  v.monto_bruto,
  v.dcto AS monto_descuento,
  v.neto AS monto_neto,
  v.tasa AS tasa_cambio,
  v.neto_dcto AS monto_total_usd
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_silver.sil_sucursales` suc
  ON v.source_empresa = suc.source_empresa AND v.cod_suc = suc.cod_suc;
"""

def create_detalle_view():
    print("==========================================================================")
    print("  CREANDO VISTA DE GRANULARIDAD DETALLADA DE FACTURACIÓN EN BIGQUERY GOLD")
    print("==========================================================================")
    client.query(sql_create_view).result()
    print("  ✓ Vista 'vw_detalle_facturacion_clientes' creada exitosamente en BigQuery Gold.")

    # Consulta de prueba mostrando la granularidad Vendedor -> Cliente -> Documento -> SKU
    sql_test = """
    SELECT
      empresa,
      nombre_sucursal,
      nombre_vendedor,
      codigo_cliente,
      nombre_cliente,
      tipo_documento,
      numero_documento,
      numero_renglon,
      nombre_marca,
      nombre_articulo,
      unidades_vendidas,
      cajas_vendidas,
      monto_total_usd,
      fecha
    FROM `factory-etl-dev-0y1dhf.factory_etl_gold.vw_detalle_facturacion_clientes`
    WHERE monto_total_usd > 100
    ORDER BY timestamp_registro DESC
    LIMIT 6;
    """
    print("\n  📊 MUESTRA DE GRANULARIDAD TRANSACCIONAL (VENDEDOR -> CLIENTE -> FACTURA -> SKU):")
    for r in client.query(sql_test).result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_detalle_view()
