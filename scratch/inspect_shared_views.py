"""Script para inspeccionar las Vistas de ConciliApp en factory_etl_shared"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

def inspect_views():
    for view_name in ['vw_conciliapp_inventario', 'vw_conciliapp_ventas_kpi']:
        t = client.get_table(f"{PROJECT_ID}.factory_etl_shared.{view_name}")
        print(f"\n==========================================================================")
        print(f"  VISTA: factory_etl_shared.{view_name}")
        print(f"==========================================================================")
        print("Esquema de Columnas:")
        for f in t.schema:
            print(f"  • {f.name:<30} ({f.field_type})")
            
        print("\nMuestra de Filas:")
        q = f"SELECT * FROM `{PROJECT_ID}.factory_etl_shared.{view_name}` LIMIT 3"
        for r in client.query(q).result():
            print(" ", dict(r))

if __name__ == "__main__":
    inspect_views()
