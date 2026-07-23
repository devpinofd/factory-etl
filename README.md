# factory-etl

ETL en Python empaquetado como imagen de Cloud Run Job. Ingesta datos
desde la **API generica** de FactorySoft
(`efactoryApiGenerica.asmx/Seleccionar`) y los aterriza en **Bronze**
(GCS) con auditoria en **BigQuery**.

Este paquete forma parte del proyecto de data lake definido en la raiz
del repositorio; ver:

- `../PROPUESTA_DATA_LAKE_GCP.md` — arquitectura completa.
- `../PLAN_IMPLEMENTACION_FASE_1.md` — plan de esta fase.

## Alcance de Fase 1

- Una sola consulta: `articulos_v1` (tabla maestra `articulos`).
- Una sola empresa: `tinito`.
- Un solo destino: Bronze en GCS + control en BigQuery.
- Sin Silver ni Gold.
- Sin ingesta desde la API de servicios de FactorySoft (decision de
  ingesta: solo API generica).

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
