"""Genera las declaraciones .sqlx faltantes de staging/silver/gold en el repo Dataform,
a partir de los esquemas reales en src/factory_etl/factory_queries/schemas/*.json.

Uso: uv run python scratch/generate_dataform_declarations.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT / "src" / "factory_etl" / "factory_queries" / "schemas"
STAGING_DIR = ROOT / "dataform" / "definitions" / "staging"
SILVER_DIR = ROOT / "dataform" / "definitions" / "silver"
GOLD_DIR = ROOT / "dataform" / "definitions" / "gold"

DATABASE = "factory-etl-dev-0y1dhf"

# entity_name -> (schema_json, already_has_staging, already_has_silver)
ENTITIES = [
    "almacenes", "articulos", "ciudades", "clases_clientes", "clientes",
    "conceptos", "departamentos", "estados", "impuestos", "marcas",
    "paises", "proveedores", "renglones_almacenes", "renglones_aprecios",
    "renglones_monedas", "secciones", "sucursales", "vendedores", "ventas_diarias",
]

# Dimensiones Gold que deben existir: dim_name -> (sil_table, entity para natural_key)
GOLD_DIMS = [
    ("dim_articulo", "sil_articulos", "articulos"),
    ("dim_almacen", "sil_almacenes", "almacenes"),
    ("dim_marca", "sil_marcas", "marcas"),
    ("dim_proveedor", "sil_proveedores", "proveedores"),
    ("dim_seccion", "sil_secciones", "secciones"),
    ("dim_departamento", "sil_departamentos", "departamentos"),
    ("dim_sucursal", "sil_sucursales", "sucursales"),
    ("dim_vendedor", "sil_vendedores", "vendedores"),
]


def load_schema(entity: str) -> dict:
    with open(SCHEMAS_DIR / f"{entity}.json", "r", encoding="utf-8") as f:
        return json.load(f)


def col_expr(col: dict) -> str:
    name = col["name"]
    c_type = col.get("type", "string").lower()
    s_type = col.get("silver_type", "").lower()

    if s_type == "timestamp":
        return f'${{helpers.toTimestamp("{name}")}} AS {name}'
    if s_type.startswith("decimal") or c_type == "number":
        return f'${{helpers.toNumeric("{name}")}} AS {name}'
    if c_type == "integer":
        return f"SAFE_CAST({name} AS INT64) AS {name}"
    if c_type == "boolean":
        return f"SAFE_CAST({name} AS BOOL) AS {name}"
    return f'${{helpers.trimStr("{name}")}} AS {name}'


def staging_declaration(entity: str) -> str:
    return f'''config {{
  type: "declaration",
  database: "{DATABASE}",
  schema: "factory_etl_bronze_stg",
  name: "stg_{entity}",
  description: "Tabla nativa cargada via BQ load job (WRITE_TRUNCATE) desde Bronze GCS con tipos exactos"
}}
'''


def silver_table(entity: str, schema: dict) -> str:
    natural_key = schema["natural_key"]
    columns = schema["columns"]
    has_registro = any(c["name"] == "registro" for c in columns)

    select_lines = ["  _source_empresa,"]
    for col in columns:
        select_lines.append(f"  {col_expr(col)},")
    if has_registro:
        select_lines.append("  DATE(${helpers.toTimestamp(\"registro\")}) AS fecha_registro,")
    select_lines.append("  _ingested_at")
    select_sql = "\n".join(select_lines)

    # bigquery block
    secondary_keys = [k for k in natural_key if k != "_source_empresa"]
    cluster_cols = ", ".join(f'"{k}"' if k != "_source_empresa" else '"_source_empresa"' for k in (["_source_empresa"] + secondary_keys[:2]))
    if has_registro:
        bq_block = f'''  bigquery: {{
    partitionBy: "DATE(registro)",
    clusterBy: [{cluster_cols}]
  }},'''
    else:
        bq_block = f'''  bigquery: {{
    clusterBy: [{cluster_cols}]
  }},'''

    unique_key = ", ".join(f'"{k}"' for k in natural_key)
    non_null = ", ".join(f'"{k}"' for k in (natural_key + (["registro"] if has_registro else [])))

    partition_by_clause = ",\n  ".join(natural_key)

    return f'''config {{
  type: "table",
  database: "{DATABASE}",
  schema: "factory_etl_silver",
  name: "sil_{entity}",
  description: "Tabla Silver de {entity} (limpia, tipada y deduplicada) generada desde stg_{entity}",
{bq_block}
  assertions: {{
    uniqueKey: [{unique_key}],
    nonNull: [{non_null}]
  }}
}}

SELECT
{select_sql}
FROM ${{ref("stg_{entity}")}}
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY {", ".join(natural_key)}
  ORDER BY _ingested_at DESC
) = 1
'''


def gold_dim(dim_name: str, sil_table: str, entity: str, schema: dict) -> str:
    natural_key = schema["natural_key"]
    cluster_cols = ", ".join(f'"{k}"' for k in natural_key)
    unique_key = ", ".join(f'"{k}"' for k in natural_key)
    return f'''config {{
  type: "table",
  database: "{DATABASE}",
  schema: "factory_etl_gold",
  name: "{dim_name}",
  description: "Dimensión Gold de {entity} (pass-through de {sil_table})",
  bigquery: {{
    clusterBy: [{cluster_cols}]
  }},
  assertions: {{
    uniqueKey: [{unique_key}],
    nonNull: [{unique_key}]
  }}
}}

SELECT * FROM ${{ref("{sil_table}")}}
'''


def main():
    existing_staging = {p.stem.replace("stg_", "") for p in STAGING_DIR.glob("stg_*.sqlx")}
    existing_silver = {p.stem.replace("sil_", "") for p in SILVER_DIR.glob("sil_*.sqlx")}
    existing_gold = {p.stem for p in GOLD_DIR.glob("*.sqlx")}

    created = {"staging": [], "silver": [], "gold": []}

    for entity in ENTITIES:
        if entity not in existing_staging:
            path = STAGING_DIR / f"stg_{entity}.sqlx"
            path.write_text(staging_declaration(entity), encoding="utf-8")
            created["staging"].append(path.name)

        if entity not in existing_silver:
            schema = load_schema(entity)
            path = SILVER_DIR / f"sil_{entity}.sqlx"
            path.write_text(silver_table(entity, schema), encoding="utf-8")
            created["silver"].append(path.name)

    for dim_name, sil_table, entity in GOLD_DIMS:
        if dim_name not in existing_gold:
            schema = load_schema(entity)
            path = GOLD_DIR / f"{dim_name}.sqlx"
            path.write_text(gold_dim(dim_name, sil_table, entity, schema), encoding="utf-8")
            created["gold"].append(path.name)

    print("Staging creados:", len(created["staging"]))
    for f in created["staging"]:
        print("  -", f)
    print("Silver creados:", len(created["silver"]))
    for f in created["silver"]:
        print("  -", f)
    print("Gold creados:", len(created["gold"]))
    for f in created["gold"]:
        print("  -", f)


if __name__ == "__main__":
    main()
