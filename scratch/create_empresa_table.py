"""Script para crear la Tabla Maestra dim_empresa en BigQuery Gold y sil_empresas en Silver
Mapea los códigos de base de datos source_empresa (tinito, ctb, daroan, roldan, ctm) con sus nombres comerciales y razones sociales.
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_create_table_gold = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa`
(
  source_empresa STRING OPTIONS(description="Código único de la base de datos de origen"),
  nombre_empresa STRING OPTIONS(description="Nombre comercial de la empresa"),
  razon_social STRING OPTIONS(description="Razón social fiscal completa"),
  rif_empresa STRING OPTIONS(description="RIF fiscal de la empresa"),
  region_operacion STRING OPTIONS(description="Región o zona geográfica principal de operaciones"),
  status STRING OPTIONS(description="Estatus de la empresa (ACTIVO)"),
  fecha_actualizacion TIMESTAMP OPTIONS(description="Fecha de última actualización del catálogo")
);

INSERT INTO `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` 
(source_empresa, nombre_empresa, razon_social, rif_empresa, region_operacion, status, fecha_actualizacion)
VALUES
  ('tinito', 'El Tinito', 'Distribuidora El Tinito, C.A.', 'J-00000000-1', 'Región Centro / Apure / Guárico / Carabobo', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('ctb', 'Comercial Tiobello', 'Comercial Tiobello, C.A.', 'J-00000000-2', 'Región Anzoátegui / Barcelona / Puerto La Cruz', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('daroan', 'Daroan', 'Inversiones Daroan, C.A.', 'J-00000000-3', 'Región Anzoátegui / Barcelona / Sucre', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('roldan', 'Distribuidora Roldan', 'Distribuidora Roldan, C.A.', 'J-00000000-4', 'Región Monagas / Maturín / Caicara', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('ctm', 'CTM Maturín', 'Comercial Tiobello Maturín, C.A.', 'J-00000000-5', 'Región Monagas / Delta Amacuro / Tucupita', 'ACTIVO', CURRENT_TIMESTAMP());
"""

sql_create_table_silver = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_silver.sil_empresas` AS
SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa`;
"""

def create_empresa_tables():
    print("==========================================================================")
    print("  CREANDO TABLA MAESTRA DE EMPRESAS EN BIGQUERY (dim_empresa / sil_empresas)")
    print("==========================================================================")
    client.query(sql_create_table_gold).result()
    print("  ✓ Tabla 'factory_etl_gold.dim_empresa' creada e insertada exitosamente.")
    
    client.query(sql_create_table_silver).result()
    print("  ✓ Tabla 'factory_etl_silver.sil_empresas' creada e insertada exitosamente.")

    # Consulta de verificación
    print("\n  📊 CATÁLOGO MAESTRO DE EMPRESAS REGISTRADO EN BIGQUERY:")
    for r in client.query("SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` ORDER BY source_empresa").result():
        print("  ", dict(r))

if __name__ == "__main__":
    create_empresa_tables()
