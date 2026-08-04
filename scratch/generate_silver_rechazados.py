"""Agrega validacion de campos requeridos + tabla de rechazados a cada sil_<entity>.sqlx.

Para cada entidad:
  1. Inserta un WHERE de validez (columnas requeridas del schema no nulas/vacias) en
     sil_<entity>.sqlx, antes del QUALIFY de deduplicacion.
  2. Crea sil_<entity>_rechazados.sqlx con las filas que fallan esa validacion y un
     campo motivo_rechazo listando que columnas fallaron.

Uso: uv run python scratch/generate_silver_rechazados.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT / "src" / "factory_etl" / "factory_queries" / "schemas"
SILVER_DIR = ROOT / "dataform" / "definitions" / "silver"
DATABASE = "factory-etl-dev-0y1dhf"

ENTITIES = [
    "almacenes", "articulos", "ciudades", "clases_clientes", "clientes",
    "conceptos", "departamentos", "estados", "impuestos", "marcas",
    "paises", "proveedores", "renglones_almacenes", "renglones_aprecios",
    "renglones_monedas", "secciones", "sucursales", "vendedores", "ventas_diarias",
]


def load_schema(entity: str) -> dict:
    with open(SCHEMAS_DIR / f"{entity}.json", "r", encoding="utf-8") as f:
        return json.load(f)


def required_columns(schema: dict) -> list[str]:
    """Columnas que deben venir no-nulas/no-vacias: natural_key (menos _source_empresa) + required:true."""
    cols = []
    for k in schema["natural_key"]:
        if k != "_source_empresa" and k not in cols:
            cols.append(k)
    for col in schema["columns"]:
        if col.get("required") and col["name"] not in cols:
            cols.append(col["name"])
    return cols


def col_type(schema: dict, name: str) -> str:
    for col in schema["columns"]:
        if col["name"] == name:
            return col.get("type", "string").lower()
    return "string"


def validity_condition(schema: dict, req_cols: list[str]) -> str:
    checks = []
    for name in req_cols:
        if col_type(schema, name) in ("number", "integer"):
            checks.append(f"{name} IS NOT NULL")
        else:
            checks.append(f"({name} IS NOT NULL AND TRIM(CAST({name} AS STRING)) != '')")
    return "\n  AND ".join(checks)


def motivo_rechazo_expr(schema: dict, req_cols: list[str]) -> str:
    items = []
    for name in req_cols:
        if col_type(schema, name) in ("number", "integer"):
            cond = f"{name} IS NULL"
        else:
            cond = f"({name} IS NULL OR TRIM(CAST({name} AS STRING)) = '')"
        items.append(f"IF({cond}, '{name}', NULL)")
    array_literal = ",\n      ".join(items)
    return f'''(
    SELECT STRING_AGG(motivo, ', ')
    FROM UNNEST([
      {array_literal}
    ]) AS motivo
  ) AS motivo_rechazo'''


def rechazados_table(entity: str, schema: dict, req_cols: list[str]) -> str:
    validity = validity_condition(schema, req_cols)
    motivo = motivo_rechazo_expr(schema, req_cols)
    return f'''config {{
  type: "table",
  database: "{DATABASE}",
  schema: "factory_etl_silver",
  name: "sil_{entity}_rechazados",
  description: "Filas de stg_{entity} que no cumplen validacion de campos requeridos ({', '.join(req_cols)}); cuarentena de calidad de datos en Silver",
  bigquery: {{
    clusterBy: ["_source_empresa"]
  }}
}}

SELECT
  *,
  CURRENT_TIMESTAMP() AS _rechazado_en,
{motivo}
FROM ${{ref("stg_{entity}")}}
WHERE NOT (
  {validity}
)
'''


def insert_where_clause(sqlx_text: str, validity: str) -> str | None:
    """Inserta WHERE antes del QUALIFY. Devuelve None si ya existe un WHERE de validez."""
    if "-- 🔒 Filtro de calidad" in sqlx_text:
        return None
    match = re.search(r"\nQUALIFY ROW_NUMBER\(\)", sqlx_text)
    if not match:
        return None
    insert_at = match.start()
    where_block = f"\n-- 🔒 Filtro de calidad: excluye filas que no cumplen campos requeridos (ver sil_*_rechazados)\nWHERE\n  {validity}\n"
    return sqlx_text[:insert_at] + where_block + sqlx_text[insert_at:]


def main():
    updated_where = []
    created_rechazados = []
    skipped = []

    for entity in ENTITIES:
        schema = load_schema(entity)
        req_cols = required_columns(schema)
        if not req_cols:
            skipped.append(entity)
            continue

        sqlx_path = SILVER_DIR / f"sil_{entity}.sqlx"
        if not sqlx_path.exists():
            skipped.append(entity)
            continue

        text = sqlx_path.read_text(encoding="utf-8")
        validity = validity_condition(schema, req_cols)
        new_text = insert_where_clause(text, validity)
        if new_text is not None:
            sqlx_path.write_text(new_text, encoding="utf-8")
            updated_where.append(sqlx_path.name)

        rechazados_path = SILVER_DIR / f"sil_{entity}_rechazados.sqlx"
        rechazados_path.write_text(rechazados_table(entity, schema, req_cols), encoding="utf-8")
        created_rechazados.append(rechazados_path.name)

    print("WHERE de validez insertado en:", len(updated_where))
    for f in updated_where:
        print("  -", f)
    print("Tablas de rechazados creadas:", len(created_rechazados))
    for f in created_rechazados:
        print("  -", f)
    print("Omitidas (sin campos requeridos o sin sil_*.sqlx):", skipped)


if __name__ == "__main__":
    main()
