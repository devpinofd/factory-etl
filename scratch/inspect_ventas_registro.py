from google.cloud import bigquery

client = bigquery.Client(project="factory-etl-dev-0y1dhf")

print("=== 1. SAMPLE STG_VENTAS_DIARIAS ===")
q_stg = "SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_ventas_diarias` LIMIT 3"
for row in client.query(q_stg).result():
    d = dict(row)
    print({k: v for k, v in d.items() if "fec" in k.lower() or "reg" in k.lower() or k == "dt"})

print("\n=== 2. NULL COUNT REGISTRO vs FEC_REG EN STG_VENTAS_DIARIAS ===")
q_counts = """
SELECT
  COUNT(*) as total,
  COUNTIF(registro IS NULL) as registro_nulls,
  COUNTIF(Fec_Reg IS NULL) as fec_reg_nulls,
  COUNTIF(Fec_Ini IS NULL) as fec_ini_nulls,
  COUNTIF(SAFE_CAST(registro AS TIMESTAMP) IS NULL) as registro_cast_nulls,
  COUNTIF(SAFE_CAST(Fec_Reg AS TIMESTAMP) IS NULL) as fec_reg_cast_nulls,
  COUNTIF(SAFE_CAST(Fec_Ini AS TIMESTAMP) IS NULL) as fec_ini_cast_nulls
FROM `factory-etl-dev-0y1dhf.factory_etl_bronze_stg.stg_ventas_diarias`
"""
for r in client.query(q_counts).result():
    print(dict(r))

print("\n=== 3. SAMPLE SIL_VENTAS_DIARIAS ===")
q_sil = "SELECT * FROM `factory-etl-dev-0y1dhf.factory_etl_silver.sil_ventas_diarias` LIMIT 3"
for row in client.query(q_sil).result():
    d = dict(row)
    print({k: v for k, v in d.items() if "fec" in k.lower() or "reg" in k.lower() or k == "dt"})
