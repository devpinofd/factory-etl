"""Script para Validar la Sincronización Completa de Inventario (Bronze, Silver, Gold y Control Tables)"""

from google.cloud import bigquery, storage
from datetime import datetime

PROJECT_ID = "factory-etl-dev-0y1dhf"
BRONZE_BUCKET = "factory-etl-dev-0y1dhf-bronze"

def check_inventory():
    print("==========================================================================")
    print("  VALIDACIÓN DE SINCRONIZACIÓN DE TABLAS DE INVENTARIO EN GCP")
    print("==========================================================================")
    
    bq_client = bigquery.Client(project=PROJECT_ID, location="us-central1")
    gcs_client = storage.Client(project=PROJECT_ID)

    # 1. Verificar Capa Silver: sil_almacenes y sil_renglones_almacenes
    print("\n--- 1. CAPA SILVER: TABLAS DE INVENTARIO ---")
    
    q_alm = f"SELECT source_empresa, COUNT(*) as total_almacenes FROM `{PROJECT_ID}.factory_etl_silver.sil_almacenes` GROUP BY 1 ORDER BY 1"
    res_alm = list(bq_client.query(q_alm).result())
    print("  • sil_almacenes (Maestro de Almacenes):")
    for r in res_alm:
        print(f"    - Empresa '{r.source_empresa}': {r.total_almacenes} almacenes registrados.")

    q_reng_alm = f"""
    SELECT 
      source_empresa, 
      COUNT(*) as total_renglones_stock,
      COUNT(DISTINCT cod_alm) as almacenes_con_stock,
      COUNT(DISTINCT cod_art) as articulos_distintos_con_stock,
      ROUND(SUM(exi_act1), 2) as total_existencia_unidades
    FROM `{PROJECT_ID}.factory_etl_silver.sil_renglones_almacenes`
    GROUP BY 1
    ORDER BY total_renglones_stock DESC
    """
    res_reng = list(bq_client.query(q_reng_alm).result())
    print("\n  • sil_renglones_almacenes (Stock Físico por Almacén/SKU):")
    total_renglones_global = 0
    total_unidades_global = 0
    for r in res_reng:
        total_renglones_global += r.total_renglones_stock
        total_unidades_global += (r.total_existencia_unidades or 0)
        print(f"    - [{r.source_empresa.upper()}]: {r.total_renglones_stock:,} renglones stock | {r.almacenes_con_stock} almacenes | {r.articulos_distintos_con_stock:,} SKUs únicos | {r.total_existencia_unidades:,.2f} unidades")
    
    print(f"\n  👉 TOTAL GLOBAL SILVER INVENTARIO: {total_renglones_global:,} renglones de stock | {total_unidades_global:,.2f} unidades acumuladas")

    # 2. Verificar Capa Gold: vw_reporte_inventario
    print("\n--- 2. CAPA GOLD: VISTA REPORTE DE INVENTARIO (vw_reporte_inventario) ---")
    q_gold = f"""
    SELECT 
      COALESCE(nombre_empresa, empresa) AS nombre_empresa,
      empresa,
      COUNT(*) as total_registros_inventario,
      ROUND(SUM(stock_unidades), 2) as unidades_inventario,
      ROUND(SUM(stock_cajas), 2) as cajas_inventario,
      ROUND(SUM(peso_total_kg / 1000), 2) as toneladas_inventario
    FROM `{PROJECT_ID}.factory_etl_gold.vw_reporte_inventario`
    GROUP BY 1, 2
    ORDER BY cajas_inventario DESC
    """
    res_gold = list(bq_client.query(q_gold).result())
    for r in res_gold:
        print(f"    - {r.nombre_empresa} ({r.empresa}): {r.total_registros_inventario:,} SKUs en stock | {r.unidades_inventario:,.2f} unidades | {r.cajas_inventario:,.2f} cajas | {r.toneladas_inventario:,.2f} toneladas")

    # 3. Verificar Histórico de Ejecuciones en Control Tables (etl_batches)
    print("\n--- 3. CONTROL TABLES (etl_batches) - ÚLTIMAS EJECUCIONES DE INVENTARIO ---")
    q_control = f"""
    SELECT 
      query_id,
      source_empresa,
      dt,
      status,
      record_count,
      created_at
    FROM `{PROJECT_ID}.factory_etl_control_dev.etl_batches`
    WHERE query_id IN ('renglones_almacenes_v1', 'almacenes_v1')
    ORDER BY created_at DESC
    LIMIT 10
    """
    res_ctrl = list(bq_client.query(q_control).result())
    for r in res_ctrl:
        print(f"    • {r.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC | {r.query_id:<22} | {r.source_empresa:<8} | dt: {r.dt} | {r.status} ({r.record_count} filas)")

    # 4. Verificar GCS Bronze Bucket Storage
    print("\n--- 4. GCS BRONZE BUCKET: OBJETOS DE INVENTARIO ALMACENADOS ---")
    bucket = gcs_client.bucket(BRONZE_BUCKET)
    blobs = list(bucket.list_blobs(prefix="renglones_almacenes_v1/"))
    print(f"  • Total de archivos Parquet/JSONL.GZ en gs://{BRONZE_BUCKET}/renglones_almacenes_v1/: {len(blobs)}")
    for b in blobs[-5:]:
        print(f"    - {b.name} ({b.size:,} bytes | Modificado: {b.updated.strftime('%Y-%m-%d %H:%M:%S')} UTC)")

    print("\n==========================================================================")
    print("  VERIFICACIÓN FINALIZADA CON ÉXITO")
    print("==========================================================================")

if __name__ == "__main__":
    check_inventory()
