"""Script para crear las vistas de consumo de ConciliApp en el dataset factory_etl_shared.

Contrato de consumo para ConciliApp (dashboard de inteligencia de ventas):
- vw_conciliapp_ventas_kpi: ventas 2025-2026, grano diario agregado (sin
  documento/renglón ni RIF: mínima exposición de datos).
- vw_conciliapp_inventario: stock físico vigente por almacén y SKU.
- El backend de ConciliApp DEBE filtrar siempre por tenant (source_empresa) y,
  en ventas, por codigo_vendedor con query parameters según el usuario Firebase.
- Las vistas se registran como Authorized Views sobre factory_etl_gold y
  factory_etl_silver: la SA de ConciliApp solo necesita READER en factory_etl_shared.

Uso:
  uv run python scratch/create_conciliapp_ventas_view.py [sa-conciliapp@proyecto.iam.gserviceaccount.com]
"""

import sys

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
SHARED_DATASET = "factory_etl_shared"
VIEW_VENTAS = "vw_conciliapp_ventas_kpi"
VIEW_INVENTARIO = "vw_conciliapp_inventario"
# Las vistas leen tablas de estos datasets, por eso se autorizan en ambos
SOURCE_DATASETS = ("factory_etl_gold", "factory_etl_silver")

client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_ventas = f"""
CREATE OR REPLACE VIEW `{PROJECT_ID}.{SHARED_DATASET}.{VIEW_VENTAS}` AS
SELECT
  -- 🔑 CLAVES DE FILTRO OBLIGATORIAS PARA CONCILIAPP (tenant + vendedor)
  v.source_empresa AS tenant,
  v.nombre_empresa,
  v.cod_suc AS codigo_sucursal,
  v.cod_ven AS codigo_vendedor,
  v.nom_ven AS nombre_vendedor,

  -- 👤 CLIENTE (sin RIF: mínima exposición)
  v.cod_cli AS codigo_cliente,
  v.nom_cli AS nombre_cliente,
  v.nom_cla AS clase_cliente,
  v.nom_ciu AS ciudad_cliente,

  -- 🗓️ JERARQUÍA DE TIEMPO COMERCIAL
  v.fecha_registro AS fecha,
  v.anio,
  v.mes,
  v.nombre_mes,
  v.anio_mes,
  v.trimestre,
  v.anio_trimestre,
  v.semana_del_anio,
  v.anio_semana,
  v.quincena,
  v.quincena_nombre,

  -- 📦 PRODUCTO / MARCA / PROVEEDOR / DEPARTAMENTO / SECCIÓN
  v.cod_pro AS codigo_proveedor,
  v.nom_pro AS nombre_proveedor,
  v.cod_mar AS codigo_marca,
  v.nom_mar AS nombre_marca,
  v.cod_art AS codigo_articulo,
  v.nom_art AS nombre_articulo,
  v.nom_dep AS nombre_departamento,
  sec.nom_sec AS nombre_seccion,

  -- ⚖️ ATRIBUTOS FÍSICOS UNITARIOS DEL SKU
  art.fraccion AS fraccion_unitaria,
  art.peso AS peso_unitario_kg,

  -- 📊 MÉTRICAS AGREGADAS AL DÍA (para KPIs del dashboard)
  COUNT(DISTINCT v.documento) AS documentos_emitidos,
  SUM(v.unidades_vendidas) AS unidades_vendidas,
  ROUND(SUM(v.cajas_vendidas), 2) AS cajas_vendidas,
  ROUND(SUM(v.volumen_total_m3), 3) AS fraccion_total,
  ROUND(SUM(v.peso_total_kg), 2) AS peso_total_kg,
  ROUND(SUM(v.peso_total_toneladas), 3) AS toneladas_vendidas,
  ROUND(SUM(v.monto_bruto), 2) AS venta_bruta,
  ROUND(SUM(v.dcto), 2) AS descuentos,
  ROUND(SUM(v.neto_dcto), 2) AS venta_neta_usd
FROM `{PROJECT_ID}.factory_etl_gold.fct_ventas` v
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_articulos` art
  ON v.source_empresa = art.source_empresa AND v.cod_art = art.cod_art
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_secciones` sec
  ON v.source_empresa = sec.source_empresa AND v.cod_sec = sec.cod_sec
WHERE v.fecha_registro BETWEEN '2025-01-01' AND '2026-12-31'
GROUP BY
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
  16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30;
"""

sql_create_inventario = f"""
CREATE OR REPLACE VIEW `{PROJECT_ID}.{SHARED_DATASET}.{VIEW_INVENTARIO}` AS
SELECT
  -- 🔑 CLAVE DE FILTRO OBLIGATORIA PARA CONCILIAPP (tenant; inventario no tiene vendedor)
  ra.source_empresa AS tenant,
  COALESCE(emp.nombre_empresa, ra.source_empresa) AS nombre_empresa,
  ra.cod_alm AS codigo_almacen,
  COALESCE(alm.nom_alm, ra.cod_alm) AS nombre_almacen,

  -- 📦 PRODUCTO / MARCA / PROVEEDOR / DEPARTAMENTO / SECCIÓN
  ra.cod_art AS codigo_articulo,
  COALESCE(art.nom_art, ra.cod_art) AS nombre_articulo,
  art.modelo,
  art.cod_mar AS codigo_marca,
  mar.nom_mar AS nombre_marca,
  art.cod_pro AS codigo_proveedor,
  dep.nom_dep AS nombre_departamento,
  sec.nom_sec AS nombre_seccion,

  -- ⚖️ ATRIBUTOS FÍSICOS UNITARIOS DEL SKU
  art.cap_bulto AS unidades_por_caja,
  art.fraccion AS fraccion_unitaria,
  art.peso AS peso_unitario_kg,

  -- 📊 STOCK FÍSICO
  ra.exi_act1 AS stock_unidades,
  ROUND(SAFE_DIVIDE(ra.exi_act1, NULLIF(art.cap_bulto, 0)), 2) AS stock_cajas,
  ROUND((ra.exi_act1 * COALESCE(art.fraccion, 0)), 3) AS fraccion_total,
  ROUND((ra.exi_act1 * COALESCE(art.peso, 0)), 2) AS peso_total_kg,
  ROUND((ra.exi_act1 * COALESCE(art.peso, 0)) / 1000, 3) AS peso_total_toneladas,

  ra.registro AS fecha_ultima_actualizacion
FROM `{PROJECT_ID}.factory_etl_silver.sil_renglones_almacenes` ra
LEFT JOIN `{PROJECT_ID}.factory_etl_gold.dim_empresa` emp
  ON ra.source_empresa = emp.source_empresa
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_almacenes` alm
  ON ra.source_empresa = alm.source_empresa AND ra.cod_alm = alm.cod_alm
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_articulos` art
  ON ra.source_empresa = art.source_empresa AND ra.cod_art = art.cod_art
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_marcas` mar
  ON art.source_empresa = mar.source_empresa AND art.cod_mar = mar.cod_mar
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_departamentos` dep
  ON art.source_empresa = dep.source_empresa AND art.cod_dep = dep.cod_dep
LEFT JOIN `{PROJECT_ID}.factory_etl_silver.sil_secciones` sec
  ON art.source_empresa = sec.source_empresa AND art.cod_sec = sec.cod_sec
WHERE ra.exi_act1 > 0;
"""


def authorize_views(dataset_id: str, view_names: list[str]):
    """Registra las vistas shared como authorized views sobre el dataset fuente."""
    ds = client.get_dataset(f"{PROJECT_ID}.{dataset_id}")
    entries = list(ds.access_entries)
    changed = False
    for view_name in view_names:
        view_ref = {"projectId": PROJECT_ID, "datasetId": SHARED_DATASET, "tableId": view_name}
        if not any(e.entity_type == "view" and e.entity_id == view_ref for e in entries):
            entries.append(bigquery.AccessEntry(None, "view", view_ref))
            changed = True
    if changed:
        ds.access_entries = entries
        client.update_dataset(ds, ["access_entries"])
        print(f"  ✓ Vistas autorizadas sobre '{dataset_id}' (authorized views).")
    else:
        print(f"  • Las vistas ya estaban autorizadas sobre '{dataset_id}'.")


def create_conciliapp_view(sa_email: str | None = None):
    print("==========================================================================")
    print("  CREANDO CONTRATO DE CONSUMO PARA CONCILIAPP (factory_etl_shared)")
    print("==========================================================================")

    # 1. Dataset dedicado para consumidores externos
    dataset = bigquery.Dataset(f"{PROJECT_ID}.{SHARED_DATASET}")
    dataset.location = "us-central1"
    dataset.description = (
        "Contratos de consumo para aplicaciones externas (ConciliApp). "
        "Vistas acotadas y autorizadas sobre Gold/Silver; sin acceso directo a las capas."
    )
    client.create_dataset(dataset, exists_ok=True)
    print(f"  ✓ Dataset '{SHARED_DATASET}' listo.")

    # 2. Vistas de consumo
    client.query(sql_create_ventas).result()
    print(f"  ✓ Vista '{VIEW_VENTAS}' creada (ventas 2025-2026, grano diario agregado).")
    client.query(sql_create_inventario).result()
    print(f"  ✓ Vista '{VIEW_INVENTARIO}' creada (stock físico vigente por almacén y SKU).")

    # 3. Registrar como Authorized Views sobre los datasets fuente
    for source_ds in SOURCE_DATASETS:
        authorize_views(source_ds, [VIEW_VENTAS, VIEW_INVENTARIO])

    # 4. Grant READER a la SA de ConciliApp (opcional, por argumento)
    if sa_email:
        shared_ds = client.get_dataset(f"{PROJECT_ID}.{SHARED_DATASET}")
        entries = list(shared_ds.access_entries)
        if not any(e.entity_type == "userByEmail" and e.entity_id == sa_email for e in entries):
            entries.append(bigquery.AccessEntry("READER", "userByEmail", sa_email))
            shared_ds.access_entries = entries
            client.update_dataset(shared_ds, ["access_entries"])
            print(f"  ✓ READER otorgado a '{sa_email}' sobre '{SHARED_DATASET}'.")
        else:
            print(f"  • '{sa_email}' ya tenía READER sobre '{SHARED_DATASET}'.")
    else:
        print("  • Sin SA indicada: ejecutar de nuevo con el email de la SA para el grant.")

    # 5. Consultas de prueba simulando el patrón de ConciliApp (parametrizado)
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("tenant", "STRING", "tinito")]
    )

    sql_test_ventas = f"""
    SELECT tenant, codigo_vendedor, nombre_vendedor, nombre_departamento, nombre_seccion,
           ROUND(AVG(fraccion_unitaria), 4) AS fraccion_unit_prom,
           ROUND(AVG(peso_unitario_kg), 3) AS peso_unit_prom_kg,
           ROUND(SUM(fraccion_total), 2) AS fraccion_total,
           ROUND(SUM(cajas_vendidas), 2) AS cajas,
           ROUND(SUM(venta_neta_usd), 2) AS venta_usd
    FROM `{PROJECT_ID}.{SHARED_DATASET}.{VIEW_VENTAS}`
    WHERE tenant = @tenant
    GROUP BY 1, 2, 3, 4, 5
    ORDER BY venta_usd DESC
    LIMIT 5;
    """
    print("\n  📊 MUESTRA KPIs DE VENTAS (con departamento/sección/fracción/peso):")
    for r in client.query(sql_test_ventas, job_config=job_config).result():
        print("  ", dict(r))

    sql_test_inv = f"""
    SELECT tenant, nombre_almacen, nombre_marca, nombre_departamento, nombre_seccion,
           COUNT(DISTINCT codigo_articulo) AS skus,
           ROUND(SUM(stock_cajas), 2) AS cajas,
           ROUND(SUM(peso_total_toneladas), 3) AS toneladas
    FROM `{PROJECT_ID}.{SHARED_DATASET}.{VIEW_INVENTARIO}`
    WHERE tenant = @tenant
    GROUP BY 1, 2, 3, 4, 5
    ORDER BY toneladas DESC
    LIMIT 5;
    """
    print("\n  📦 MUESTRA DE INVENTARIO (stock por almacén/marca/departamento/sección):")
    for r in client.query(sql_test_inv, job_config=job_config).result():
        print("  ", dict(r))


if __name__ == "__main__":
    create_conciliapp_view(sys.argv[1] if len(sys.argv) > 1 else None)
