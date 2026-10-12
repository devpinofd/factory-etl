"""Script para construir la arquitectura Medallion COMPLETA en GCP BigQuery (19 Entidades)"""

import os
import json
from pathlib import Path
from google.cloud import bigquery

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "src" / "factory_etl" / "factory_queries" / "schemas"

# 19 Entidades registradas en el catálogo
ENTITIES = [
    ("articulos_v1", "articulos", ["source_empresa", "cod_art"], "articulos.json"),
    ("impuestos_v1", "impuestos", ["source_empresa", "cod_imp"], "impuestos.json"),
    ("departamentos_v1", "departamentos", ["source_empresa", "cod_dep"], "departamentos.json"),
    ("marcas_v1", "marcas", ["source_empresa", "cod_mar"], "marcas.json"),
    ("secciones_v1", "secciones", ["source_empresa", "cod_sec"], "secciones.json"),
    ("proveedores_v1", "proveedores", ["source_empresa", "cod_pro"], "proveedores.json"),
    ("paises_v1", "paises", ["source_empresa", "cod_pai"], "paises.json"),
    ("estados_v1", "estados", ["source_empresa", "cod_est"], "estados.json"),
    ("ciudades_v1", "ciudades", ["source_empresa", "cod_ciu"], "ciudades.json"),
    ("vendedores_v1", "vendedores", ["source_empresa", "cod_ven"], "vendedores.json"),
    ("sucursales_v1", "sucursales", ["source_empresa", "cod_suc"], "sucursales.json"),
    ("almacenes_v1", "almacenes", ["source_empresa", "cod_alm"], "almacenes.json"),
    ("clientes_v1", "clientes", ["source_empresa", "cod_cli"], "clientes.json"),
    ("clases_clientes_v1", "clases_clientes", ["source_empresa", "cod_cla"], "clases_clientes.json"),
    ("conceptos_v1", "conceptos", ["source_empresa", "cod_con"], "conceptos.json"),
    ("renglones_almacenes_v1", "renglones_almacenes", ["source_empresa", "cod_alm", "cod_art"], "renglones_almacenes.json"),
    ("renglones_monedas_v1", "renglones_monedas", ["source_empresa", "cod_mon", "renglon"], "renglones_monedas.json"),
    ("renglones_aprecios_v1", "renglones_aprecios", ["source_empresa", "documento", "renglon"], "renglones_aprecios.json"),
    ("ventas_diarias_v2", "ventas_diarias", ["source_empresa", "tipo_documento", "cod_suc", "documento", "renglon"], "ventas_diarias_v2.json"),
]

def load_schema_def(schema_filename: str):
    json_path = SCHEMAS_DIR / schema_filename
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_all(project_id=None):
    if not project_id:
        project_id = os.environ.get("FACTORY_ETL_GCP_PROJECT", "factory-etl-dev-0y1dhf")
    
    bronze_bucket = os.environ.get("FACTORY_ETL_BRONZE_BUCKET", f"{project_id}-bronze")
    client = bigquery.Client(project=project_id)
    
    print("==========================================================================")
    print(f"  1. CONSTRUYENDO 19 TABLAS EXTERNAS EN STAGING EN {project_id}")
    print("==========================================================================")

    for query_id, entity_name, natural_key, schema_file in ENTITIES:
        table_id = f"{project_id}.factory_etl_bronze_stg.stg_{entity_name}"
        table = bigquery.Table(table_id)
        
        schema_def = load_schema_def(schema_file)
        bq_fields = []
        for col in schema_def.get("columns", []):
            c_name = col["name"]
            c_type = col.get("type", "string").lower()
            bq_t = "STRING"
            if c_type == "number":
                bq_t = "FLOAT64"
            elif c_type == "integer":
                bq_t = "INT64"
            elif c_type == "boolean":
                bq_t = "BOOL"
            bq_fields.append(bigquery.SchemaField(c_name, bq_t, mode="NULLABLE"))
            
        ext_cfg = bigquery.ExternalConfig("NEWLINE_DELIMITED_JSON")
        ext_cfg.source_uris = [f"gs://{bronze_bucket}/bronze/{query_id}/*"]
        ext_cfg.schema = bq_fields
        ext_cfg.ignore_unknown_values = True
        
        hive_opts = bigquery.HivePartitioningOptions()
        hive_opts.mode = "AUTO"
        hive_opts.source_uri_prefix = f"gs://{bronze_bucket}/bronze/{query_id}/"
        ext_cfg.hive_partitioning = hive_opts
        
        table.external_data_configuration = ext_cfg
        client.create_table(table, exists_ok=True)
        print(f"  ✓ Staging stg_{entity_name:<20} -> Creada sobre gs://.../{query_id}/")

    print("\n==========================================================================")
    print(f"  2. CONSOLIDANDO 19 TABLAS EN SILVER EN {project_id}")
    print("==========================================================================")

    for query_id, entity_name, natural_key, schema_file in ENTITIES:
        schema_def = load_schema_def(schema_file)
        select_exprs = []
        select_exprs.append("source_empresa")
        
        for col in schema_def.get("columns", []):
            c_name = col["name"]
            c_type = col.get("type", "string").lower()
            s_type = col.get("silver_type", "").lower()
            
            if s_type == "timestamp":
                expr = f"COALESCE(PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S', {c_name}), SAFE_CAST({c_name} AS TIMESTAMP)) AS {c_name}"
            elif s_type.startswith("decimal") or c_type == "number":
                expr = f"SAFE_CAST({c_name} AS NUMERIC) AS {c_name}"
            elif c_type == "integer":
                expr = f"SAFE_CAST({c_name} AS INT64) AS {c_name}"
            else:
                expr = f"RTRIM(LTRIM(CAST({c_name} AS STRING))) AS {c_name}"
            select_exprs.append(expr)

        nat_key_str = ", ".join(natural_key).replace("source_empresa", "source_empresa")
        
        options_clause = ""
        if entity_name in ["ventas_diarias", "renglones_monedas", "renglones_almacenes", "renglones_aprecios"]:
            options_clause = "PARTITION BY DATE(registro)\n"
            if entity_name == "ventas_diarias":
                options_clause += "CLUSTER BY source_empresa, cod_pro, cod_suc\n"
            elif entity_name == "renglones_monedas":
                options_clause += "CLUSTER BY source_empresa, cod_mon\n"
            else:
                options_clause += "CLUSTER BY source_empresa\n"
        else:
            options_clause = "CLUSTER BY source_empresa\n"

        client.query(f"DROP TABLE IF EXISTS `{project_id}.factory_etl_silver.sil_{entity_name}`").result()

        sql_silver = f"""
        CREATE OR REPLACE TABLE `{project_id}.factory_etl_silver.sil_{entity_name}`
        {options_clause}AS
        SELECT
          {', '.join(select_exprs)}
        FROM `{project_id}.factory_etl_bronze_stg.stg_{entity_name}`
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY {nat_key_str}
          ORDER BY dt DESC
        ) = 1;
        """
        try:
            client.query(sql_silver).result()
            count = list(client.query(f"SELECT COUNT(*) as total FROM `{project_id}.factory_etl_silver.sil_{entity_name}`").result())[0].total
            print(f"  ✓ Silver sil_{entity_name:<22} -> OK ({count:,} filas consolidadas)")
        except Exception as ex:
            print(f"  ❌ Silver sil_{entity_name:<22} -> ERROR: {ex}")

    print("\n==========================================================================")
    print(f"  3. CONSTRUYENDO DIMENSIONES Y HECHOS EN GOLD EN {project_id}")
    print("==========================================================================")

    dim_queries = [
        ("dim_articulo", "sil_articulos", "source_empresa, cod_art"),
        ("dim_cliente", "sil_clientes", "source_empresa, cod_cli"),
        ("dim_vendedor", "sil_vendedores", "source_empresa, cod_ven"),
        ("dim_proveedor", "sil_proveedores", "source_empresa, cod_pro"),
        ("dim_sucursal", "sil_sucursales", "source_empresa, cod_suc"),
        ("dim_marca", "sil_marcas", "source_empresa, cod_mar"),
        ("dim_departamento", "sil_departamentos", "source_empresa, cod_dep"),
        ("dim_seccion", "sil_secciones", "source_empresa, cod_sec"),
        ("dim_almacen", "sil_almacenes", "source_empresa, cod_alm"),
    ]

    for dim_name, sil_table, cluster_cols in dim_queries:
        sql_dim = f"""
        CREATE OR REPLACE TABLE `{project_id}.factory_etl_gold.{dim_name}`
        CLUSTER BY {cluster_cols}
        AS
        SELECT * FROM `{project_id}.factory_etl_silver.{sil_table}`;
        """
        try:
            client.query(sql_dim).result()
            c = list(client.query(f"SELECT COUNT(*) as total FROM `{project_id}.factory_etl_gold.{dim_name}`").result())[0].total
            print(f"  ✓ Gold {dim_name:<25} -> Creada ({c:,} filas)")
        except Exception as ex:
            print(f"  ❌ Gold {dim_name:<25} -> ERROR: {ex}")

    print("\n==========================================================================")
    print(f"  MIGRACIÓN COMPLETA MEDALLION CONSTRUIDA Y VERIFICADA EN {project_id}")
    print("==========================================================================")

if __name__ == "__main__":
    build_all()
