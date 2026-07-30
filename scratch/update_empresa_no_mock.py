"""Script para actualizar dim_empresa y sil_empresas eliminando datos simulables de RIF 
y dejándolos en NULL hasta que sean suministrados oficialmente por el usuario.
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_update_gold = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa`
(
  source_empresa STRING OPTIONS(description="Código único de la base de datos de origen"),
  nombre_empresa STRING OPTIONS(description="Nombre comercial de la empresa"),
  razon_social STRING OPTIONS(description="Razón social fiscal de la empresa"),
  rif_empresa STRING OPTIONS(description="RIF fiscal oficial de la empresa (suministrado por el usuario)"),
  region_operacion STRING OPTIONS(description="Región o zona geográfica principal de operaciones"),
  status STRING OPTIONS(description="Estatus de la empresa (ACTIVO)"),
  fecha_actualizacion TIMESTAMP OPTIONS(description="Fecha de última actualización del catálogo")
);

INSERT INTO `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` 
(source_empresa, nombre_empresa, razon_social, rif_empresa, region_operacion, status, fecha_actualizacion)
VALUES
  ('tinito', 'El Tinito', 'Distribuidora El Tinito, C.A.', NULL, 'Región Centro / Apure / Guárico / Carabobo', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('ctb', 'Comercial Tiobello', 'Comercial Tiobello, C.A.', NULL, 'Región Anzoátegui / Barcelona / Puerto La Cruz', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('daroan', 'Daroan', 'Inversiones Daroan, C.A.', NULL, 'Región Anzoátegui / Barcelona / Sucre', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('roldan', 'Distribuidora Roldan', 'Distribuidora Roldan, C.A.', NULL, 'Región Monagas / Maturín / Caicara', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('ctm', 'CTM Maturín', 'Comercial Tiobello Maturín, C.A.', NULL, 'Región Monagas / Delta Amacuro / Tucupita', 'ACTIVO', CURRENT_TIMESTAMP());
"""

sql_update_silver = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_silver.sil_empresas` AS
SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa`;
"""

def update_empresa_no_mock():
    print("==========================================================================")
    print("  ACTUALIZANDO TABLAS DE EMPRESAS CON INFORMACIÓN VERIFICADA (SINO NULL)")
    print("==========================================================================")
    client.query(sql_update_gold).result()
    client.query(sql_update_silver).result()
    print("  ✓ Tablas dim_empresa y sil_empresas actualizadas sin datos simulados.")

if __name__ == "__main__":
    update_empresa_no_mock()
