---
mode: agent
description: Completa el MVP operativo del ETL FactorySoft → Bronze (GCS) + auditoría (BigQuery) añadiendo la infraestructura de ejecución (Cloud Run Job + Workflows + Scheduler), el pipeline CI/CD con WIF, y el runbook de validación. Baseline: commit `fbb0449` con `factory-etl run-batch` operativo y 240 tests verdes.
---

<role>
Eres un ingeniero senior de plataforma en GCP (Terraform, Cloud Run Jobs,
Workflows, Scheduler, CI/CD con Workload Identity Federation) trabajando
en el repositorio `factory-etl`. Debes producir infraestructura, workflows
y automatización que cumplan las reglas del proyecto ya establecidas en
`AGENTS.md` / `copilot-instructions.md` / `PLAN_IMPLEMENTACION_FASE_1.md`.

No sugieras: **implementa**. No añadas features fuera del alcance. Prefiere
extender los módulos Terraform existentes antes de crear nuevos.
</role>

<baseline>
Estado del repositorio (commit `fbb0449`, no reescribir):

- **CLI operativa**: `factory-etl run-batch --query-id <id> --source-empresa <emp> --dt YYYY-MM-DD [--run-id <uuid>] [--parameter k=v]...` ([src/factory_etl/cli.py](src/factory_etl/cli.py)).
  - Ejecuta **un solo batch** por invocación (1 query × 1 empresa × 1 dt).
  - Exit code: `0` para `SUCCESS`, `SKIPPED_DUPLICATE`, `QUARANTINED`; `1` en excepción no controlada.
  - Emite `BATCH_FAILED` en `etl_events` en fallo, con `type(exc).__name__` + `error_id` (nunca `str(exc)`).
  - Idempotencia por `payload_hash` (no por fecha).
- **Config vía env vars** con prefijo `FACTORY_ETL_` ([src/factory_etl/config.py](src/factory_etl/config.py)):
  `FACTORY_ETL_ENV`, `FACTORY_ETL_GCP_PROJECT`, `FACTORY_ETL_GCP_REGION`,
  `FACTORY_ETL_BRONZE_BUCKET`, `FACTORY_ETL_QUARANTINE_BUCKET`,
  `FACTORY_ETL_CONTROL_DATASET`, `FACTORY_ETL_FACTORYSOFT_BASE_URL`,
  `FACTORY_ETL_FACTORYSOFT_API_KEY_SECRET`,
  `FACTORY_ETL_FACTORYSOFT_API_USER_SECRET`,
  `FACTORY_ETL_HTTP_TIMEOUT_SECONDS`, `FACTORY_ETL_HTTP_MAX_RETRIES`,
  `FACTORY_ETL_HTTP_RETRY_BACKOFF_SECONDS`.
  **Los secretos NO van como env vars**: se resuelven en runtime via
  `SecretResolver` ([src/factory_etl/secrets.py](src/factory_etl/secrets.py)), lo que permite
  rotación sin redeploy. Terraform solo debe garantizar que la SA del Job
  tenga `roles/secretmanager.secretAccessor` sobre los secretos declarados.
- **Layout Bronze en GCS** ([src/factory_etl/bronze_writer.py](src/factory_etl/bronze_writer.py)):
  `gs://<bronze>/bronze/<entity>/source_empresa=<empresa>/dt=YYYY-MM-DD/run_id=<uuid>/part-0.jsonl.gz`
  (JSONL comprimido con gzip, `mtime=0` para reproducibilidad byte-a-byte).
- **Terraform base** en `terraform/` con módulos ya provisionados:
  `bigquery`, `secrets`, `service_account`, `storage`, `wif`. Estado remoto
  en GCS (`backend.tf`). Falta: `artifact_registry`, `cloud_run_job`,
  `workflows`, `scheduler`, `monitoring`.
- **Dockerfile** existe en [docker/Dockerfile](docker/Dockerfile).
- **Estados de batch** (enum `BatchStatus`): `SUCCESS`, `WRITTEN`,
  `SKIPPED_DUPLICATE`, `QUARANTINED`, `FAILED`. Los primeros 4 son
  "no-fallo" para efectos operativos; solo `FAILED` es fallo real.
</baseline>

<objective>
Transformar el CLI operativo en un sistema **automatizado, resiliente y
auditable** en 3 fases:

1. Infraestructura de orquestación con matriz `(empresa × query)` y retry.
2. Pipeline CI/CD con WIF y escaneo de seguridad.
3. Validación operacional y runbook.

El sistema debe: cada día a las 07:00 UTC (03:00 hora Caracas) obtener
`dt = T-1`, ejecutar la matriz `(empresa × query)` declarada en config,
aterrizar cada batch en Bronze, y registrar auditoría. Ante fallo:
reintentar con **backoff exponencial** (5min → 10min → 20min, máx 3
intentos), y alertar via Cloud Monitoring si el último intento también
falla.
</objective>

<execution_protocol>
Trabaja iterativamente. **Detente al final de cada fase y espera
confirmación explícita ("OK, continua") antes de la siguiente.** Cada
fase termina con: (a) archivos generados, (b) plan de validación local,
(c) puntos de decisión abiertos.
</execution_protocol>

<phase_1>
# FASE 1 — Infraestructura de orquestación (Terraform)

## Objetivo

Añadir a Terraform los recursos que ejecutan y protegen la lógica del
ETL, respetando el CLI existente y el patrón de secretos actual.

## Modelo de orquestación

**Elegido**: `Scheduler → Workflows → Cloud Run Job` (single retry layer
en Workflows). Se descarta el retry nativo del Run Job para tener un
solo lugar donde razonar sobre reintentos y fan-out.

```
Cloud Scheduler (07:00 UTC diario)
   └─► Workflows (fan-out matriz + retry exponencial)
          └─► Cloud Run Job (ejecuta 1 batch: query × empresa × dt)
```

## Tareas

1. **Análisis previo** (obligatorio antes de generar `.tf`):
   - Leer `terraform/main.tf` y `terraform/modules/*/main.tf`.
   - Listar recursos existentes y su output.
   - No duplicar módulos: extender `service_account` si hace falta más
     de una SA; crear nuevos módulos solo para recursos ausentes.

2. **Módulo `artifact_registry`** (nuevo):
   - Repositorio Docker regional (`var.region`) con `cleanup_policies`
     que retenga los últimos 10 tags SHA + tags `vX.Y.Z`.
   - Output: `repository_id`, `image_base_url`.

3. **Módulo `cloud_run_job`** (nuevo):
   - Nombre: `factory-etl-<environment>`.
   - Imagen: `${artifact_registry.image_base_url}/factory-etl:${var.image_tag}`.
     `image_tag` es SIEMPRE un git-sha inmutable (nunca `latest`).
   - **Args del contenedor** (no env vars para parámetros de negocio):
     ```
     ["run-batch",
      "--query-id",       "$(QUERY_ID)",
      "--source-empresa", "$(SOURCE_EMPRESA)",
      "--dt",             "$(DT)",
      "--run-id",         "$(RUN_ID)"]
     ```
     `QUERY_ID`, `SOURCE_EMPRESA`, `DT`, `RUN_ID` son env vars
     inyectadas por Workflows en cada `task override`.
   - **Env vars fijas** (config del proceso, NO secretos):
     `FACTORY_ETL_ENV`, `FACTORY_ETL_GCP_PROJECT`, `FACTORY_ETL_GCP_REGION`,
     `FACTORY_ETL_BRONZE_BUCKET`, `FACTORY_ETL_QUARANTINE_BUCKET`,
     `FACTORY_ETL_CONTROL_DATASET`, `FACTORY_ETL_FACTORYSOFT_BASE_URL`,
     `FACTORY_ETL_FACTORYSOFT_API_KEY_SECRET`,
     `FACTORY_ETL_FACTORYSOFT_API_USER_SECRET`.
   - **Secretos**: NO se inyectan como env vars ni como `--set-secrets`
     de Run. La SA del Job tiene `roles/secretmanager.secretAccessor`
     sobre los secretos y `SecretResolver` los lee en runtime.
   - Recursos: `cpu=1`, `memory=1Gi` (baseline; variables Terraform para
     override).
   - `task_timeout=1800s` (30 min), `max_retries=0` (Workflows maneja
     retry).
   - `service_account = module.service_account.job_email`.
   - Etiquetas: `component=extractor`, `environment=<env>`.

4. **Módulo `workflows`** (nuevo):
   - Fuente YAML del workflow generada por Terraform via `templatefile`.
   - Input: `{ "dt": "YYYY-MM-DD" | null, "run_id_prefix": string | null }`.
     Si `dt` es `null`, el workflow calcula `T-1` en UTC.
   - **Matriz**: itera sobre `var.execution_matrix` (list of objects
     `{ query_id, source_empresa }`) declarada en Terraform. Un batch
     por combinación.
   - **Paralelismo controlado**: `parallel { for }` con `concurrency_limit = 4`
     para no saturar el API de FactorySoft.
   - **Retry por batch**: `try/retry` nativo de Workflows con backoff
     exponencial:
     ```yaml
     retry:
       predicate: ${http.default_retry_predicate}
       max_retries: 3
       backoff:
         initial_delay: 300      # 5 min
         max_delay: 3600         # 1 h
         multiplier: 2
     ```
   - **Fallo terminal**: si tras 3 intentos un batch sigue fallando,
     se acumula en una lista `failed_batches` y al final del workflow
     se emite:
     - `log.error` estructurado con la lista de `{query_id, source_empresa, dt, run_id}`.
     - Un `Cloud Logging` entry con label `severity=ERROR` y
       `jsonPayload.event="factory_etl_batch_failed_terminal"` (para
       activar la alert policy — ver módulo `monitoring`).
     El workflow completo termina con `raise` para que el Scheduler
     también marque falla.
   - Output del workflow: `{ total, success, quarantined, skipped, failed: [...] }`.

5. **Módulo `scheduler`** (nuevo):
   - Cron: `0 7 * * *` en `time_zone = "Etc/UTC"` (equivalente 03:00
     America/Caracas, ajustable via variable).
   - Target: `HTTP` a `https://workflowexecutions.googleapis.com/v1/projects/<p>/locations/<r>/workflows/<w>/executions`.
   - Body: `{"argument": "{\"dt\": null}"}` (Workflows resuelve `T-1`
     internamente; el Scheduler **no** evalúa shell).
   - `oauth_token.service_account_email = google_service_account.scheduler.email`.
   - `attempt_deadline = "60s"` (Scheduler solo dispara; el work real
     es del Workflow).

6. **Módulo `monitoring`** (nuevo):
   - `google_logging_metric` de tipo COUNTER sobre
     `jsonPayload.event="factory_etl_batch_failed_terminal"`.
   - `google_monitoring_alert_policy` que dispara si la métrica > 0 en
     ventana de 10 min.
   - `google_monitoring_notification_channel` de tipo `email` (destino
     via `var.alert_email`). Placeholder para PagerDuty/Slack futuros.

7. **Service accounts** (extender `service_account` module):
   - `job-sa` (existente): `roles/storage.objectCreator` sobre bronze,
     `roles/storage.objectAdmin` sobre `_staging/` (necesita delete para
     el promote), `roles/bigquery.dataEditor` sobre control dataset,
     `roles/secretmanager.secretAccessor` sobre los secretos declarados.
   - `workflows-sa` (nuevo): `roles/run.invoker` sobre el Job.
   - `scheduler-sa` (nuevo): `roles/workflows.invoker` sobre el Workflow.

8. **Variables nuevas** (`terraform/variables.tf`):
   - `execution_matrix` (list of `{query_id, source_empresa}`).
   - `image_tag` (string, obligatorio en `terraform apply`).
   - `alert_email` (string).
   - `scheduler_cron` (default `"0 7 * * *"`).
   - `scheduler_time_zone` (default `"Etc/UTC"`).
   - `job_cpu` (default `"1"`), `job_memory` (default `"1Gi"`),
     `job_task_timeout_seconds` (default `1800`).
   - `workflow_max_concurrency` (default `4`).
   - `workflow_max_retries` (default `3`).

## Entregables Fase 1

- `terraform/modules/artifact_registry/{main.tf,variables.tf,outputs.tf}`
- `terraform/modules/cloud_run_job/{main.tf,variables.tf,outputs.tf}`
- `terraform/modules/workflows/{main.tf,variables.tf,outputs.tf,workflow.yaml.tftpl}`
- `terraform/modules/scheduler/{main.tf,variables.tf,outputs.tf}`
- `terraform/modules/monitoring/{main.tf,variables.tf,outputs.tf}`
- Extensión de `terraform/modules/service_account/main.tf` con las 2 SAs
  adicionales (o SAs separadas si es más limpio).
- Actualización de `terraform/main.tf`, `variables.tf`, `outputs.tf`,
  `envs/dev.tfvars.example`.

## Plan de validación Fase 1

```powershell
cd terraform
terraform fmt -recursive
terraform validate
terraform plan -var-file=envs/dev.tfvars.example -out=dev.tfplan
```

- `terraform validate` → sin errores.
- `plan` → recursos creados coinciden con los del módulo (sin drift
  inesperado en los módulos existentes).
- Diagrama de flujo Scheduler → Workflows → Job en la explicación,
  detallando cómo viaja `dt` y los args por-tarea.

## Puntos de decisión

- ¿`workflow_max_concurrency=4` es apropiado para el rate limit de
  FactorySoft? (default conservador; ajustable).
- ¿Alerta solo por email es suficiente para el MVP o se conecta ya a
  Slack/PagerDuty?
- ¿`workflow_max_retries=3` con backoff 5min→10min→20min cubre el SLA?
</phase_1>

<phase_2>
# FASE 2 — Pipeline CI/CD con WIF

## Objetivo

Automatizar `build → scan → push → deploy` con credenciales efímeras
(WIF), imágenes trazables por git-sha, y verificación post-deploy.

## Tareas

1. **Workflow `.github/workflows/deploy.yml`**:
   - Triggers: `push` a `main` + `workflow_dispatch` con inputs
     `environment` (`dev`|`stage`|`prod`) y `image_tag_override`.
   - Permissions mínimos: `contents: read`, `id-token: write`.
   - **Job `test`**: `uv sync`, `uv run ruff check`, `uv run pyright`,
     `uv run bandit -r src -c pyproject.toml`, `uv run pytest -q`.
     Falla el pipeline si cobertura < 70%.
   - **Job `build_and_deploy`** (needs `test`):
     - `actions/checkout@v4` con `fetch-depth: 0` (para versionado).
     - `google-github-actions/auth@v2` con
       `workload_identity_provider = ${vars.WIF_PROVIDER}` y
       `service_account = ${vars.DEPLOYER_SA}`. **No** usar keys.
     - `google-github-actions/setup-gcloud@v2`.
     - **Build**: `docker build` con `--tag <region>-docker.pkg.dev/<proj>/factory-etl/factory-etl:${{ github.sha }}`.
       Un solo tag: `git-sha` (nunca `latest`).
     - **Scan Trivy**:
       ```yaml
       - uses: aquasecurity/trivy-action@master
         with:
           image-ref: ${{ steps.build.outputs.image }}
           format: 'table'
           exit-code: '1'
           severity: 'HIGH,CRITICAL'
           ignore-unfixed: true
           vuln-type: 'os,library'
       ```
     - **Push**: `docker push` solo si Trivy pasa.
     - **Deploy**: `gcloud run jobs deploy factory-etl-<env> \
       --image=<sha-image> --region=<r> --project=<p>`
       (usa `deploy`, no `update` — es idempotente y aplica delta
       completo de env vars, SA, secretos, timeout).
     - **Smoke test**: `gcloud run jobs execute factory-etl-<env> \
       --update-env-vars QUERY_ID=articulos_smoke,SOURCE_EMPRESA=tinito,DT=1970-01-01,RUN_ID=$(uuidgen) \
       --wait --region=<r>`.
       Requiere: un fixture `articulos_smoke` en el catálogo que devuelva
       payload vacío conocido → resultado esperado `QUARANTINED` (exit 0)
       o `SKIPPED_DUPLICATE` en corridas subsecuentes. Sin crear datos
       reales en Bronze.
     - **Validación**: `gcloud run jobs describe factory-etl-<env> \
       --format='value(status.conditions[?type=Ready].status)'` == `True`.
   - **Job `notify`** (needs `build_and_deploy`, `if: failure()`):
     - `POST` a webhook Slack/Teams con `github.sha`, `github.actor`,
       `github.run_id`.

2. **WIF configuración** (documentar, no crear en el workflow — ya
   existe módulo `wif`):
   - `wif_enabled = true` en `dev.tfvars`.
   - `github_owner = "devpinofd"`, `github_repo = "factory-etl"`.
   - `github_allowed_refs = ["refs/heads/main"]` (más restrictivo para
     `prod`).
   - **Attribute condition** en el provider WIF debe validar
     `assertion.repository == 'devpinofd/factory-etl' && assertion.ref in ['refs/heads/main']`
     para prevenir que otros repos usen el pool.

3. **IAM del `deployer-sa`** (crear como cuarta SA en `service_account`
   module o dedicada):
   - `roles/artifactregistry.writer` sobre el repo.
   - `roles/run.developer` sobre el Job (para `jobs deploy` y `execute`).
   - `roles/iam.serviceAccountUser` sobre `job-sa` (necesario para
     asignar SA al Job).
   - `roles/logging.viewer` (para leer logs post-deploy si el smoke falla).
   - **Sin** roles de `owner`, `editor`, ni `iam.securityAdmin`.

## Entregables Fase 2

- `.github/workflows/deploy.yml` completo.
- Actualización de `terraform/modules/wif/main.tf` con la attribute
  condition estricta (si falta).
- Nueva SA `deployer-sa` en el módulo `service_account` con los roles
  mínimos.
- Sección en `terraform/README.md` con la matriz IAM (quién tiene qué).

## Plan de validación Fase 2

- `act -j test` o push a rama de PR → job `test` verde.
- Push a `main` en ambiente `dev` → deploy completo, imagen visible en
  Artifact Registry, `jobs describe` muestra `Ready=True`.
- Introducir vulnerabilidad conocida en `pyproject.toml` (temporalmente,
  ej. `requests<2.20`) → Trivy debe fallar el pipeline con severity HIGH.
  Revertir tras verificar.

## Puntos de decisión

- ¿Se requiere aprobación manual (`environment: prod` con reviewers)
  para deploy a prod?
- ¿Trivy contra el image final o también scan de dependencias con
  `pip-audit` en el job `test`?
- ¿Push de imagen firmada con `cosign`? (fuera de MVP salvo requisito).
</phase_2>

<phase_3>
# FASE 3 — Validación operacional y runbook

## Objetivo

Verificar E2E con datos reales, definir criterios verificables de MVP,
y entregar runbook operativo.

## Tareas

### 3.1 Pruebas E2E asistidas

- **Ejecución manual con fecha histórica** (probar reprocesamiento):
  ```powershell
  gcloud run jobs execute factory-etl-dev `
    --region=us-central1 --project=<proj> --wait `
    --update-env-vars QUERY_ID=articulos_v1,SOURCE_EMPRESA=tinito,DT=2026-06-01,RUN_ID=$(New-Guid)
  ```
  Resultado esperado: exit 0, un objeto en
  `gs://<bronze>/bronze/articulos_v1/source_empresa=tinito/dt=2026-06-01/run_id=<uuid>/part-0.jsonl.gz`.

- **Idempotencia por payload_hash** (spec real, no por fecha):
  Ejecutar el comando anterior dos veces consecutivas con `RUN_ID`
  distintos pero mismo `(QUERY_ID, SOURCE_EMPRESA, DT)`.
  - Si el payload de FactorySoft es idéntico bit-a-bit → 2ª corrida
    devuelve `SKIPPED_DUPLICATE`, no crea objeto nuevo, registra
    evento `DUPLICATE_SKIPPED` en `etl_events`.
  - Si el payload cambió entre corridas → 2ª corrida crea un nuevo
    `batch_id` distinto y un nuevo objeto (comportamiento correcto,
    no bug).

- **Simulación de fallo de API para validar retry de Workflows**:
  1. Redesplegar temporalmente Cloud Run Job con env var
     `FACTORY_ETL_FACTORYSOFT_BASE_URL=https://httpbin.org/status/503`.
  2. Ejecutar el workflow manualmente:
     ```powershell
     gcloud workflows execute factory-etl-dev-workflow `
       --data='{"dt":"2026-06-01"}' --location=us-central1
     ```
  3. Verificar en Cloud Logging que el Workflow reintentó 3 veces con
     backoff 5min → 10min → 20min.
  4. Verificar que la alert policy disparó (email recibido).
  5. Revertir la URL a producción.

### 3.2 Queries de validación

**Objeto en GCS** (PowerShell):
```powershell
gcloud storage ls "gs://<bronze>/bronze/articulos_v1/source_empresa=tinito/dt=2026-06-01/**"
# Debe devolver exactamente 1 objeto part-0.jsonl.gz por run exitoso.
```

**Auditoría en BigQuery**:
```sql
-- Runs de la fecha objetivo
SELECT run_id, status, started_at, ended_at,
       TIMESTAMP_DIFF(ended_at, started_at, SECOND) AS duration_seconds
FROM `<proj>.<dataset>.etl_runs`
WHERE DATE(started_at) = CURRENT_DATE("Etc/UTC")
ORDER BY started_at DESC;

-- Batches exitosos vs. cuarentena vs. fallo del día
SELECT status, COUNT(*) AS n, SUM(record_count) AS rows_total
FROM `<proj>.<dataset>.etl_batches`
WHERE dt = DATE_SUB(CURRENT_DATE("Etc/UTC"), INTERVAL 1 DAY)
GROUP BY status;

-- Eventos de fallo terminal (deben ser 0 en día normal)
SELECT run_id, batch_id, entity, phase, event_type, extras, inserted_at
FROM `<proj>.<dataset>.etl_events`
WHERE event_type IN ('BATCH_FAILED', 'QUARANTINED_SCHEMA', 'QUARANTINED_EMPTY')
  AND DATE(inserted_at) = CURRENT_DATE("Etc/UTC")
ORDER BY inserted_at DESC;

-- Idempotencia: batches duplicados por (source_empresa, entity, dt, payload_hash)
-- Debe ser 0. Si > 0, hay bug en find_batch_by_hash.
SELECT source_empresa, entity, dt, payload_hash, COUNT(*) AS n
FROM `<proj>.<dataset>.etl_batches`
WHERE status IN ('SUCCESS', 'WRITTEN')
GROUP BY source_empresa, entity, dt, payload_hash
HAVING n > 1;
```

### 3.3 Verificación de no-leakage de secretos

- Test unitario ya existente ([tests/security/test_log_redaction.py](tests/security/test_log_redaction.py))
  debe pasar en CI. Extender con casos adicionales:
  - Payload FactorySoft con `token=`, `password=`, cadenas base64
    largas → nunca deben aparecer en logs estructurados.
- Query de Cloud Logging (post-deploy):
  ```
  resource.type="cloud_run_job"
  resource.labels.job_name="factory-etl-dev"
  jsonPayload=~"(password|token|api[_-]?key|secret)="
  ```
  Debe devolver **0 entradas** en la última semana.

## Criterios de aceptación del MVP (verificables)

| # | Criterio | Método de verificación |
|---|---|---|
| 1 | 5 ejecuciones automáticas consecutivas del Scheduler diario sin intervención | Query BQ: `SELECT COUNT(DISTINCT DATE(started_at)) FROM etl_runs WHERE status='SUCCESS' AND started_at > CURRENT_TIMESTAMP() - INTERVAL 7 DAY` >= 5 |
| 2 | 0 secretos filtrados en Cloud Logging (últimos 7 días) | Query Cloud Logging (ver 3.3) devuelve 0 |
| 3 | Latencia p95 por batch < 10 min | `PERCENTILE_CONT(duration_seconds, 0.95) OVER ()` sobre etl_runs < 600 |
| 4 | Idempotencia funcional | Query "batches duplicados" (ver 3.2) devuelve 0 |
| 5 | Alertas funcionan | Prueba simulación de fallo (ver 3.1) → email recibido en `alert_email` |
| 6 | Rollback funciona | `gcloud run jobs update factory-etl-dev --image=<sha-anterior>` completa en < 2 min sin errores |
| 7 | Cobertura tests ≥ 70% en CI | Salida de `pytest --cov-fail-under=70` |

## Entregables Fase 3

- Sección "Runbook" en [README.md](README.md) o nuevo
  `docs/RUNBOOK.md` (solo si el usuario lo pide explícitamente) con:
  - Comandos de troubleshooting (ver logs, re-ejecutar, revisar
    alertas).
  - Queries SQL de validación (las de 3.2).
  - Procedimiento de rollback.
  - Checklist de on-call diario.
- Reporte final de aceptación del MVP con las 7 métricas marcadas.
</phase_3>

<constraints>
- No introducir `latest` como tag Docker.
- No inyectar secretos como env vars del contenedor (usar SecretResolver
  en runtime).
- No usar shell substitution en payloads de Cloud Scheduler.
- No duplicar retries (Workflows es la única capa de reintento).
- No crear archivos `.md` de documentación si no se piden explícitamente.
- Cada módulo Terraform con `main.tf` + `variables.tf` + `outputs.tf`
  separados (patrón existente).
- Cada Service Account con el mínimo conjunto de roles (nunca `owner`
  o `editor`).
</constraints>

<open_questions>
Antes de arrancar Fase 1, confirmar:

1. **Matriz de ejecución MVP**: ¿solo `(articulos_v1, tinito)` o hay
   más `(query, empresa)` que orquestar desde el día 1?
2. **Zona horaria del Scheduler**: `07:00 UTC` (03:00 Caracas) o algún
   otro slot para evitar picos de carga en FactorySoft?
3. **Canal de alertas MVP**: email a una casilla concreta, Slack
   webhook, o ambos?
4. **Ambiente objetivo**: ¿arrancamos solo con `dev` y luego promovemos
   a `stage`/`prod`, o creamos los 3 desde ya?
5. **Nombre de este prompt**: renombrar `prompt.prompt.md` →
   `mvp_operacional.prompt.md` para no colisionar con futuros prompts.
</open_questions>
