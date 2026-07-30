# factory-etl

ETL en Python empaquetado como imagen de Cloud Run Job. Ingesta datos
desde la **API generica** de FactorySoft
(`efactoryApiGenerica.asmx/Seleccionar`) y los aterriza en **Bronze**
(GCS) con auditoria en **BigQuery**.

Este paquete forma parte del proyecto de data lake definido en la raiz
del repositorio; ver:

- `PROPUESTA_DATA_LAKE_GCP.md` — arquitectura completa.
- `PLAN_IMPLEMENTACION_FASE_1.md` — plan de esta fase.
- `PLAN_OPTIMIZACION_WORKFLOWS.md` — plan de optimización de tiempo de ejecución (< 5 min).

## Estado de Completitud (Capa Bronze - Listo para Producción/Dev en GCP)

El extractor e ingesta hacia la **Capa Bronze en GCS** se encuentra **100% implementado, desplegado mediante IaC (Terraform) y verificado empíricamente en GCP**:

- **Catálogo de Consultas Completo (19 Consultas Versionadas):**
  - **15 Tablas Maestras:** `articulos_v1`, `impuestos_v1`, `departamentos_v1`, `marcas_v1`, `secciones_v1`, `proveedores_v1`, `paises_v1`, `estados_v1`, `ciudades_v1`, `vendedores_v1`, `sucursales_v1`, `almacenes_v1`, `clientes_v1`, `clases_clientes_v1`, `conceptos_v1`.
  - **4 Tablas Transaccionales:** `renglones_almacenes_v1`, `ventas_diarias_v1` (soporta parámetro `registro`), `renglones_monedas_v1`, `renglones_aprecios_v1` (soporta parámetro `registro`).
- **Soporte Multi-Empresa:** Integración completa para 5 bases de datos (`tinito`, `ctb`, `daroan`, `roldan`, `ctm`).
- **Orquestación en Nube (Cloud Workflows & Cloud Run Jobs):**
  - Flujo paralelo con concurrencia optimizada y aceleración de cómputo (2 vCPU / 1 GiB RAM).
  - Ejecución verificada exitosa de **95 lotes procesados en 9.8 minutos con 100% de éxito (`status: SUCCESS`)** en GCP (`Execution b50eec63`).
- **Persistencia en GCS Bronze:**
  - Archivos Parquet / JSONL.GZ particionados por `source_empresa` y fecha `dt`.
- **Control y Auditoría en BigQuery:**
  - Tablas de control en `factory_etl_control` y registro de validación de calidad en `data_quality_results`.

## Estructura

```text
factory-etl/
├── pyproject.toml               # Dependencias y config de herramientas
├── uv.lock                      # Lockfile (generar con `uv lock`)
├── .python-version              # Version fija: 3.12
├── docker/
│   └── Dockerfile               # Multi-stage, usuario no privilegiado
├── src/
│   └── factory_etl/
│       ├── __init__.py
│       ├── __main__.py          # `python -m factory_etl`
│       ├── cli.py               # comandos typer (run, list-queries, version)
│       ├── config.py            # pydantic-settings
│       ├── logging_config.py    # structlog + redaccion de secretos
│       ├── errors.py            # jerarquia de excepciones tipadas
│       ├── ids.py               # run_id, batch_id, sql_hash, row_hash
│       ├── protocols.py         # Protocols estructurales (contratos de DI)
│       ├── bootstrap.py         # Composition Root (cablea concretas)
│       ├── secrets.py           # wrapper Secret Manager
│       ├── query_runner.py      # httpx a FactorySoft
│       ├── bronze_writer.py     # Parquet a GCS con escritura atomica
│       ├── control_tables.py    # inserts a BigQuery
│       ├── quarantine.py        # zona separada para respuestas invalidas
│       ├── extractor.py         # orquestacion del batch
│       └── factory_queries/     # catalogo de consultas versionadas
│           ├── models.py        # QueryDefinition, Transport, ParamSpec
│           ├── catalog.py       # registro de consultas disponibles
│           ├── renderer.py      # sustitucion SEGURA de parametros SQL
│           ├── masters/
│           │   └── articulos.sql
│           ├── transactions/    # vacio en Fase 1
│           └── schemas/
│               └── articulos.json
└── tests/
    ├── unit/                    # renderer, ids, catalogo, fixture, config, errors, bootstrap
    ├── security/                # inyeccion SQL, hardening del renderer, redaccion de logs
    └── fixtures/factorysoft/    # payloads reales sanitizados

terraform/                       # IaC de GCP (buckets, BQ, secrets, SA, WIF)
├── main.tf                      # composicion de modulos
├── variables.tf
├── outputs.tf
├── envs/                        # dev.tfvars.example, prod.tfvars.example
└── modules/                     # storage, bigquery, secrets, service_account, wif
```

## Requisitos locales

- **Python 3.12** (fijado via `.python-version`).
- **uv** 0.4+ — https://docs.astral.sh/uv/
- Docker Desktop (para construir la imagen).

Instalar `uv` en Windows:

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Setup

```powershell
cd factory-etl
uv sync --all-extras
```

`uv sync` crea `.venv/`, instala dependencias de runtime + dev y genera
`uv.lock` si no existe.

## Comandos frecuentes

Todos desde `factory-etl/`.

```powershell
# Formato + lint (autofix)
uv run ruff format .
uv run ruff check --fix .

# Type checking estricto
uv run pyright

# Tests con cobertura
uv run pytest

# Tests solo de seguridad
---

## 🛠️ Guía de Ejecución Operativa del Data Lake

### 1. Ingesta Diaria Incremental (Capa Bronze en GCP)
Para ejecutar la ingesta diaria de las 95 consultas (19 queries × 5 empresas):

- **Automatizado en la Nube (GCP Cloud Workflows):**
  ```bash
  gcloud workflows run factory-etl-daily-orchestrator --location=us-central1
  ```
- **CLI Local (Una consulta/empresa puntual):**
  ```bash
  uv run python -m factory_etl.cli run-batch --query-id ventas_diarias_v1 --company tinito --dt 2026-07-29 --params '{"fec_des":"2026-07-29","fec_has":"2026-07-29"}'
  ```

---

### 2. Backfill Histórico de Ventas y Monedas (2022 - 2026)
Para ejecutar o reanudar el seed masivo de datos históricos por rangos quincenales:

- **Todas las empresas (2022 a 2026):**
  ```bash
  uv run python scratch/backfill_sales_biweekly.py ALL
  ```
- **Una empresa específica y año (ej. `tinito` 2025):**
  ```bash
  uv run python scratch/backfill_sales_biweekly.py tinito 2025
  ```

---

### 3. Consolidación de Medallion Architecture (Bronze → Silver → Gold)
Para procesar las tablas de Staging externas, la consolidación limpia/deduplicada en **Silver** y la tabla de hechos en **Gold**:

- **Ejecución Completa en BigQuery:**
  ```bash
  uv run python scratch/build_staging_and_silver.py
  ```
- **Reconstrucción de la Dimensión Tiempo (`dim_tiempo`):**
  ```bash
  uv run python scratch/build_dim_tiempo.py
  ```

---

### 4. Orquestación y Compilación con Dataform (SQLX)
Para compilar o ejecutar las transformaciones a través del CLI de Dataform:

- **Compilar grafo de dependencias Dataform:**
  ```bash
  cd dataform
  npx @dataform/cli compile
  ```
- **Ejecutar Dataform en GCP BigQuery:**
  ```bash
  cd dataform
  npx @dataform/cli run --project factory-etl-dev-0y1dhf
  ```
uv run pytest tests/security -v

# Bandit
uv run bandit -r src -c pyproject.toml

# Auditoria de dependencias
uv run pip-audit --strict

# Ejecutar el CLI
uv run factory-etl --help
uv run factory-etl list-queries
uv run factory-etl run --query-id articulos_v1 --source-empresa tinito
```

## Docker

```powershell
# Build local
docker build -f docker/Dockerfile -t factory-etl:local .

# Ejecutar con env vars minimas (dev)
docker run --rm `
    -e FACTORY_ETL_ENV=dev `
    -e FACTORY_ETL_GCP_PROJECT=mi-proyecto-dev `
    -e FACTORY_ETL_BRONZE_BUCKET=factory-datalake-dev-mi-proyecto `
    -e FACTORY_ETL_CONTROL_DATASET=factory_control_dev `
    factory-etl:local `
    list-queries
```

## Arquitectura de una corrida

```text
Cloud Scheduler (cron)
    -> Cloud Workflow "factory-etl-daily"
        -> genera run_id
        -> INSERT etl_runs (RUNNING)
        -> Cloud Run Job "factory-etl:<sha>"
            1. resuelve QueryDefinition desde el catalogo
            2. renderiza SQL (renderer con placeholders tipados)
            3. POST a FactorySoft (httpx + retries con tenacity)
            4. calcula payload_hash y batch_id
            5. si batch_id ya existe con mismo hash: SKIPPED_DUPLICATE
            6. escribe Parquet a gs://.../bronze/_staging/run_id=<uuid>/
            7. valida contra schemas/articulos.json
            8. INSERT etl_batches (WRITTEN)
            9. mueve _staging/ a bronze/articulos/source_empresa=tinito/dt=.../run_id=.../
            10. UPDATE etl_batches (SUCCESS)
        -> UPDATE etl_runs (SUCCESS)
```

## Reglas invariantes

1. **Nunca** concatenar strings para armar SQL. Todo pasa por
   `factory_queries.renderer.render`.
2. **Nunca** loguear API key, SQL renderizado, payload crudo, headers de
   autenticacion, ni PII de clientes. La redaccion esta en
   `logging_config.py`.
3. **Nunca** sobreescribir una particion `dt` cerrada de Bronze. Ver
   "Reglas de aterrizaje en Bronze" en `PLAN_IMPLEMENTACION_FASE_1.md`.
4. **Nunca** commitear secretos, `.env`, credenciales, ni service account
   JSON. `.gitignore` los bloquea; `detect-secrets` en CI da alerta.
5. **Nunca** ampliar `Transport` mas alla de `GENERIC_SQL_API` sin
   revisar la seccion 1 del plan Fase 1.

## Extension: como agregar una consulta nueva

1. Crear `factory_queries/masters/<entidad>.sql` o
   `factory_queries/transactions/<entidad>.sql`.
2. Crear `factory_queries/schemas/<entidad>.json` con columnas, tipos y
   dominios.
3. Declarar el `QueryDefinition` en `factory_queries/catalog.py`.
4. Agregar tests en `tests/unit/test_catalog.py` que verifiquen los
   campos declarados.
5. Si la consulta usa parametros, agregar tests de seguridad en
   `tests/security/`.

Cambios incompatibles = nueva version (`articulos_v2`), la vieja convive
hasta migracion.

## Estado de implementacion

Los modulos marcados con `NotImplementedError` son stubs con interfaz
definida pero implementacion pendiente. Se completan en Fase 1 Etapa 4:

- `secrets.py`
- `query_runner.py`
- `bronze_writer.py`
- `control_tables.py`
- `quarantine.py`
- `extractor.py`

Ya implementados y con tests:

- `config.py`, `logging_config.py`, `errors.py`, `ids.py`, `protocols.py`, `bootstrap.py`
- `factory_queries/models.py`
- `factory_queries/catalog.py`
- `factory_queries/renderer.py` (con registry `_FORMATTERS` extensible)
- `masters/articulos.sql`, `schemas/articulos.json`
