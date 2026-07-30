"""Script para consultar eFactory stock > 0 parseando laTablas"""

import json
from google.cloud import secretmanager
from factory_etl.config import Settings
from factory_etl.query_runner import QueryRunner

PROJECT_ID = "factory-etl-dev-0y1dhf"

class GCPSecretResolver:
    def __init__(self, project_id):
        client = secretmanager.SecretManagerServiceClient()
        k_res = client.access_secret_version(request={"name": f"projects/{project_id}/secrets/factory-api-key/versions/latest"})
        u_res = client.access_secret_version(request={"name": f"projects/{project_id}/secrets/factory-api-user/versions/latest"})
        self.api_key = k_res.payload.data.decode("utf-8").strip()
        self.api_user = u_res.payload.data.decode("utf-8").strip()
        
    def get(self, key, default=None):
        if "key" in key.lower():
            return self.api_key
        if "user" in key.lower():
            return self.api_user
        return default

def test_raw():
    empresa = "tinito"
    resolver = GCPSecretResolver(PROJECT_ID)
    settings = Settings(gcp_project=PROJECT_ID, bronze_bucket="dummy", control_dataset="dummy")
    runner = QueryRunner(settings=settings, secrets=resolver)
    
    sql = "SELECT ra.cod_alm, ra.cod_art, ra.exi_act1, ra.registro FROM renglones_almacenes ra WHERE ra.exi_act1 > 0"
    print("=== CONSULTANDO INVENTARIO STOCK > 0 EN EFACTORY ===")
    res = runner.execute(sql_rendered=sql, source_empresa=empresa)
    data = json.loads(res.payload_bytes.decode('utf-8'))
    rows = data.get("d", {}).get("laTablas", [[]])[0]
    print(f"  ✓ Total renglones con stock > 0 en '{empresa}': {len(rows):,}")
    if rows:
        print("  Sample row:", rows[0])

if __name__ == "__main__":
    test_raw()
