"""Script para Sincronizar Vendedores y Usuarios desde Firestore (conciliapp-prod) hacia BigQuery (factory_etl_security.sec_vendedores_auth)
"""

import os
import sys
import google.auth
from google.cloud import firestore, bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
FIRESTORE_PROJECT_ID = "conciliapp-prod"

def sync_firestore_to_bigquery():
    print("==========================================================================")
    print("  SINCRONIZANDO VENDEDORES DESDE FIRESTORE HACIA BIGQUERY SECURITY")
    print("==========================================================================")

    # 1. Clientes Firestore y BigQuery
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    bq_client = bigquery.Client(project=PROJECT_ID, location="us-central1")

    # 2. Asegurar existencia del Dataset factory_etl_security y Tabla sec_vendedores_auth
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.factory_etl_security")
    dataset_ref.location = "us-central1"
    bq_client.create_dataset(dataset_ref, exists_ok=True)

    create_table_sql = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.factory_etl_security.sec_vendedores_auth` (
      uid STRING,
      correo STRING NOT NULL,
      domain STRING NOT NULL,
      source_empresa STRING,
      cod_suc STRING,
      cod_pro STRING,
      cod_ven STRING,
      role_type STRING NOT NULL,
      status STRING NOT NULL
    );
    """
    bq_client.query(create_table_sql).result()
    print("  ✓ Tabla factory_etl_security.sec_vendedores_auth creada/verificada.")

    # 3. Extraer Vendedores de /vendedores
    vendedores_ref = db.collection("vendedores")
    vendedores_docs = list(vendedores_ref.stream())
    print(f"  ✓ Extraídos {len(vendedores_docs)} documentos de la colección /vendedores en Firestore.")

    rows_to_insert = []
    
    # Agregar SuperAdmin por defecto
    rows_to_insert.append({
        "uid": "superadmin-pinofd",
        "correo": "pinofd@gmail.com",
        "domain": "gmail.com",
        "source_empresa": None,
        "cod_suc": None,
        "cod_pro": None,
        "cod_ven": None,
        "role_type": "SUPERADMIN",
        "status": "A"
    })

    # Procesar Vendedores
    for doc in vendedores_docs:
        data = doc.to_dict()
        email = (data.get("email") or doc.id).strip().lower()
        if not email:
            continue

        domain = email.split("@")[-1] if "@" in email else "gmail.com"
        is_active = data.get("isActive", True)
        status_val = "A" if is_active else "I"
        vendedores_arr = data.get("vendedores") or []

        if not vendedores_arr:
            tenant_id = (data.get("tenantId") or "").strip().lower() or None
            rows_to_insert.append({
                "uid": doc.id,
                "correo": email,
                "domain": domain,
                "source_empresa": tenant_id,
                "cod_suc": None,
                "cod_pro": None,
                "cod_ven": None,
                "role_type": "VENDEDOR",
                "status": status_val
            })
        else:
            for item in vendedores_arr:
                empresa_raw = (item.get("empresa") or item.get("tenantId") or "").strip().lower()
                cod_ven = item.get("codVendedor") or item.get("cod_ven")
                cod_suc = item.get("codSucursal") or item.get("cod_suc")
                item_status = item.get("status", "A")
                final_status = "A" if (status_val == "A" and item_status == "A") else "I"

                rows_to_insert.append({
                    "uid": doc.id,
                    "correo": email,
                    "domain": domain,
                    "source_empresa": empresa_raw if empresa_raw else None,
                    "cod_suc": cod_suc if cod_suc else None,
                    "cod_pro": None,
                    "cod_ven": cod_ven if cod_ven else None,
                    "role_type": "VENDEDOR",
                    "status": final_status
                })

    # 4. Extraer Usuarios Analistas / Admins de /users
    users_ref = db.collection("users")
    users_docs = list(users_ref.stream())
    print(f"  ✓ Extraídos {len(users_docs)} documentos de la colección /users en Firestore.")

    for doc in users_docs:
        data = doc.to_dict()
        email = (data.get("email") or "").strip().lower()
        if not email:
            continue
        domain = email.split("@")[-1] if "@" in email else "gmail.com"
        role_raw = (data.get("role") or "").strip()
        is_active = data.get("isActive", True)
        status_val = "A" if is_active else "I"

        if "Analista" in role_raw or "Admin" in role_raw or domain == "tinitot.com":
            role_type = "ANALISTA_VENTAS" if "Analista" in role_raw else ("SUPERADMIN" if "Admin" in role_raw else "ANALISTA_VENTAS")
            rows_to_insert.append({
                "uid": doc.id,
                "correo": email,
                "domain": domain,
                "source_empresa": None,  # Acceso global
                "cod_suc": None,
                "cod_pro": None,
                "cod_ven": None,
                "role_type": role_type,
                "status": status_val
            })

    print(f"\n  • Total de mapeos RLS preparados para BigQuery: {len(rows_to_insert):,} filas.")

    # 5. Insertar en BigQuery
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    load_job = bq_client.load_table_from_json(
        rows_to_insert,
        f"{PROJECT_ID}.factory_etl_security.sec_vendedores_auth",
        job_config=job_config
    )
    load_job.result()

    total_count = list(bq_client.query(f"SELECT COUNT(*) as total FROM `{PROJECT_ID}.factory_etl_security.sec_vendedores_auth`").result())[0].total
    print(f"  🎉 Sincronización exitosa. Total registros en BigQuery sec_vendedores_auth: {total_count:,} filas.")

if __name__ == "__main__":
    sync_firestore_to_bigquery()
