"""Script para actualizar dim_empresa y sil_empresas con las razones sociales y RIFs oficiales suministrados por el usuario:
- tinito: Comercial Tinito El Tigre, C.A. (J310904553)
- ctb: Comercial Tinito Barcelona C.A. (J409990001)
- daroan: Drinks and Food C.A. (J501104921)
- ctm: Comercial Tinito C.A. (J298069104)
- roldan: Inversiones Roldan, C.A. (J303949827)
"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

sql_update_gold = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa`
(
  source_empresa STRING OPTIONS(description="Código único de la base de datos de origen"),
  nombre_empresa STRING OPTIONS(description="Nombre comercial de la empresa"),
  razon_social STRING OPTIONS(description="Razón social fiscal oficial de la empresa"),
  rif_empresa STRING OPTIONS(description="RIF fiscal oficial de la empresa"),
  status STRING OPTIONS(description="Estatus de la empresa (ACTIVO)"),
  fecha_actualizacion TIMESTAMP OPTIONS(description="Fecha de última actualización del catálogo")
);

INSERT INTO `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` 
(source_empresa, nombre_empresa, razon_social, rif_empresa, status, fecha_actualizacion)
VALUES
  ('tinito', 'Comercial Tinito El Tigre', 'Comercial Tinito El Tigre, C.A.', 'J310904553', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('ctb', 'Comercial Tinito Barcelona', 'Comercial Tinito Barcelona C.A.', 'J409990001', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('daroan', 'Drinks and Food', 'Drinks and Food C.A.', 'J501104921', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('ctm', 'Comercial Tinito', 'Comercial Tinito C.A.', 'J298069104', 'ACTIVO', CURRENT_TIMESTAMP()),
  ('roldan', 'Inversiones Roldan', 'Inversiones Roldan, C.A.', 'J303949827', 'ACTIVO', CURRENT_TIMESTAMP());
"""

sql_update_silver = """
CREATE OR REPLACE TABLE `factory-etl-dev-0y1dhf.factory_etl_silver.sil_empresas` AS
SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa`;
"""

def populate_official_empresas():
    print("==========================================================================")
    print("  ACTUALIZANDO DIM_EMPRESA Y SIL_EMPRESAS CON DATOS OFICIALES DE LA EMPRESA")
    print("==========================================================================")
    client.query(sql_update_gold).result()
    client.query(sql_update_silver).result()
    print("  ✓ Tablas dim_empresa y sil_empresas actualizadas exitosamente.")

    # Consulta de verificación
    print("\n  📊 CATÁLOGO MAESTRO DE EMPRESAS REGISTRADO EN BIGQUERY:")
    for r in client.query("SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_gold.dim_empresa` ORDER BY source_empresa").result():
        print("  ", dict(r))

if __name__ == "__main__":
    populate_official_empresas()
