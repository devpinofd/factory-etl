"""Script de verificación de ventas consolidadas de la Segunda Quincena de Julio 2026"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

query = """
SELECT 
  v.source_empresa,
  COALESCE(e.nombre_empresa, v.source_empresa) AS nombre_empresa,
  COUNT(*) as total_renglones_facturados,
  COUNT(DISTINCT v.documento) as total_facturas,
  COUNT(DISTINCT v.cod_cli) as clientes_unicos_compradores,
  ROUND(SUM(v.cajas_vendidas), 2) as cajas_vendidas,
  ROUND(SUM(v.neto_dcto), 2) as venta_usd
FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` v
LEFT JOIN `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` e
  ON v.source_empresa = e.source_empresa
WHERE v.fecha_registro BETWEEN '2026-07-16' AND '2026-07-31'
GROUP BY 1, 2
ORDER BY venta_usd DESC;
"""

def verify_q2():
    print("==========================================================================")
    print("  VERIFICACIÓN DE LA SEGUNDA QUINCENA DE JULIO 2026 EN BIGQUERY GOLD")
    print("==========================================================================")
    for r in client.query(query).result():
        print("  ", dict(r))

    total_q2 = list(client.query("SELECT COUNT(*) as cnt, ROUND(SUM(neto_dcto), 2) as total_usd FROM `factory-etl-dev-0y1dhf.factory_etl_gold.fct_ventas` WHERE fecha_registro BETWEEN '2026-07-16' AND '2026-07-31'").result())[0]
    print(f"\n  🎉 TOTAL SEGUNDA QUINCENA JULIO 2026: {total_q2.cnt:,} renglones | ${total_q2.total_usd:,.2f} USD")

if __name__ == "__main__":
    verify_q2()
