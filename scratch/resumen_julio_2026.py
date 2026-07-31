"""Script para obtener el Resumen Consolidado del Mes de Julio 2026 por Empresa en BigQuery Gold"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

query = """
SELECT 
  v.source_empresa,
  COALESCE(e.nombre_empresa, v.source_empresa) AS nombre_empresa,
  e.razon_social AS razon_social_empresa,
  COUNT(*) as total_renglones,
  COUNT(DISTINCT v.documento) as total_facturas,
  COUNT(DISTINCT v.cod_cli) as clientes_compradores,
  COUNT(DISTINCT v.cod_ven) as vendedores_activos,
  ROUND(SUM(v.cajas_vendidas), 2) as cajas_vendidas,
  ROUND(SUM(v.peso_total_toneladas), 2) as toneladas_vendidas,
  ROUND(SUM(v.neto_dcto), 2) as venta_usd
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` e
  ON v.source_empresa = e.source_empresa
WHERE v.fecha_registro BETWEEN '2026-07-01' AND '2026-07-31'
GROUP BY 1, 2, 3
ORDER BY venta_usd DESC;
"""

def resumen_julio():
    print("==========================================================================")
    print("  RESUMEN DE REGISTROS POR EMPRESA EN EL MES DE JULIO 2026")
    print("==========================================================================")
    for r in client.query(query).result():
        print("  ", dict(r))

    total = list(client.query("SELECT COUNT(*) as renglones, COUNT(DISTINCT documento) as facturas, COUNT(DISTINCT cod_cli) as clientes, ROUND(SUM(cajas_vendidas), 2) as cajas, ROUND(SUM(neto_dcto), 2) as total_usd FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` WHERE fecha_registro BETWEEN '2026-07-01' AND '2026-07-31'").result())[0]
    print(f"\n  🎉 TOTAL MES DE JULIO 2026: {total.renglones:,} renglones | {total.facturas:,} facturas | {total.clientes:,} clientes | {total.cajas:,.2f} cajas | ${total.total_usd:,.2f} USD")

if __name__ == "__main__":
    resumen_julio()
