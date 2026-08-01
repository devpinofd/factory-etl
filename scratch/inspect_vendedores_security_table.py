"""Script para Inspeccionar el Resumen del Scope de Vendedores y Usuarios en BigQuery Security"""

from google.cloud import bigquery

PROJECT_ID = "factory-etl-dev-0y1dhf"
client = bigquery.Client(project=PROJECT_ID, location="us-central1")

def inspect_sec():
    print("==========================================================================")
    print("  RESUMEN DE GOVERNANZA EN BIGQUERY (factory_etl_security.sec_vendedores_auth)")
    print("==========================================================================")

    # 1. Conteo por Rol y Dominio
    q_roles = """
    SELECT 
      domain,
      role_type,
      status,
      COUNT(*) as total_registros,
      COUNT(DISTINCT correo) as total_usuarios_unicos
    FROM `factory-etl-dev-0y1dhf.factory_etl_security.sec_vendedores_auth`
    GROUP BY 1, 2, 3
    ORDER BY total_registros DESC;
    """
    print("\n--- DISTRIBUCIÓN POR DOMINIO Y ROL ---")
    for r in client.query(q_roles).result():
        print(" ", dict(r))

    # 2. Conteo de Vendedores por Empresa (source_empresa)
    q_emp = """
    SELECT 
      COALESCE(source_empresa, 'GLOBAL (ALL)') as empresa,
      COUNT(*) as asignaciones_scope,
      COUNT(DISTINCT correo) as vendedores_unicos
    FROM `factory-etl-dev-0y1dhf.factory_etl_security.sec_vendedores_auth`
    GROUP BY 1
    ORDER BY asignaciones_scope DESC;
    """
    print("\n--- DISTRIBUCIÓN DE ASIGNACIONES POR EMPRESA (TENANT) ---")
    for r in client.query(q_emp).result():
        print(" ", dict(r))

    # 3. Muestra de Usuarios Multi-Empresa / Multi-Ruta
    q_multi = """
    SELECT 
      correo,
      COUNT(DISTINCT source_empresa) as empresas_distintas,
      COUNT(DISTINCT cod_ven) as codigos_vendedor_distintos,
      ARRAY_AGG(DISTINCT source_empresa IGNORE NULLS) as lista_empresas,
      ARRAY_AGG(DISTINCT cod_ven IGNORE NULLS) as lista_codigos
    FROM `factory-etl-dev-0y1dhf.factory_etl_security.sec_vendedores_auth`
    GROUP BY 1
    HAVING empresas_distintas > 1 OR codigos_vendedor_distintos > 1
    LIMIT 10;
    """
    print("\n--- EJEMPLOS DE VENDEDORES MULTI-EMPRESA / MULTI-CÓDIGO (TOP 10) ---")
    for r in client.query(q_multi).result():
        print(" ", dict(r))

if __name__ == "__main__":
    inspect_sec()
