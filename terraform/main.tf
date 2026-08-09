locals {
  common_labels = {
    project     = "factory-etl"
    environment = var.environment
    managed_by  = "terraform"
    owner       = "data-platform"
  }

  # Inventario operativo observado en GCP por ambiente. Se mantiene
  # declarativo para que el plan exponga diferencias entre legacy y SCD2 sin
  # migrar datos ni asumir que ambos proyectos tienen los mismos recursos.
  environment_inventory = var.environment == "prod" ? {
    project_id        = var.project_id
    bronze_bucket     = "factory-etl-prod-bronze"
    quarantine_bucket = "factory-etl-prod-quarantine"
    datasets = [
      "factory_etl_assertions",
      "factory_etl_bronze_stg",
      "factory_etl_control",
      "factory_etl_gold",
      "factory_etl_security",
      "factory_etl_shared",
      "factory_etl_silver",
    ]
    workflows = [
      "factory-etl-consolidation-prod",
      "factory-etl-daily-transaccional-prod",
      "factory-etl-data-quality-prod",
      "factory-etl-full-prod",
      "factory-etl-daily-transaccional-prod-scd2",
      "factory-etl-full-prod-scd2",
      "factory-etl-consolidation-prod-scd2",
    ]
    schedulers = [
      "factory-etl-daily-scheduler-transaccional-prod",
      "factory-etl-full-scheduler-prod",
      "factory-etl-data-quality-daily-prod",
      "factory-etl-consolidation-scheduler-prod-scd2",
    ]
    cloud_run_jobs        = ["factory-etl-extractor-prod"]
    dataform_repositories = ["factory-etl-prod"]
    artifact_repositories = ["factory-etl-repo"]
    } : {
    project_id        = var.project_id
    bronze_bucket     = "factory-etl-dev-0y1dhf-bronze"
    quarantine_bucket = "factory-etl-dev-0y1dhf-quarantine"
    datasets = [
      "factory_etl_assertions",
      "factory_etl_bronze_stg",
      "factory_etl_control",
      "factory_etl_control_dev",
      "factory_etl_gold",
      "factory_etl_security",
      "factory_etl_shared",
      "factory_etl_silver",
    ]
    workflows = [
      "factory-etl-consolidation-dev-scd2",
      "factory-etl-daily-transaccional-dev-scd2",
      "factory-etl-full-dev-scd2",
    ]
    schedulers = [
      "factory-etl-nightly-scheduler-dev",
      "factory-etl-daily-scheduler-full-dev-scd2",
      "factory-etl-consolidation-scheduler-dev-scd2",
      "factory-etl-daily-scheduler-dev-scd2",
    ]
    cloud_run_jobs        = ["factory-etl-articulos-dev"]
    dataform_repositories = ["factory-etl-dev"]
    artifact_repositories = ["factory-etl"]
  }

  cloud_run_job_name           = var.environment == "prod" ? "factory-etl-extractor-prod" : "factory-etl-articulos-${var.environment}"
  daily_workflow_name          = "factory-etl-daily-transaccional-${var.environment}-scd2"
  full_workflow_name           = "factory-etl-full-${var.environment}-scd2"
  consolidation_workflow_name  = "factory-etl-consolidation-${var.environment}-scd2"
  daily_scheduler_name         = var.environment == "prod" ? "factory-etl-daily-scheduler-transaccional-prod" : "factory-etl-daily-scheduler-dev-scd2"
  full_scheduler_name          = var.environment == "prod" ? "factory-etl-full-scheduler-prod" : "factory-etl-daily-scheduler-full-dev-scd2"
  consolidation_scheduler_name = var.environment == "prod" ? "factory-etl-consolidation-scheduler-prod-scd2" : "factory-etl-consolidation-scheduler-dev-scd2"
  workflow_control_dataset_id = var.additional_control_dataset_id != "" ? var.additional_control_dataset_id : (
    var.environment == "dev" ? "factory_etl_control_dev" : module.bigquery.dataset_id
  )

  # Tipos exactos por entidad (staging), leidos de las fuentes de verdad en
  # src/factory_etl/factory_queries/schemas/*.json en vez de autodetect.
  # El workflow deriva la entidad quitando "_v1", por lo que las claves se
  # normalizan aqui de la misma forma. Los campos de auditoria son parte del
  # contrato Bronze y deben viajar al staging nativo.
  staging_schema_dir   = "${path.root}/../src/factory_etl/factory_queries/schemas"
  staging_schema_files = fileset(local.staging_schema_dir, "*.json")
  # Columnas de auditoria que SI viajan en el JSON de Bronze (una por registro).
  # Las claves de particion Hive (source_empresa, dt, run_id) NO van aqui: no
  # existen en el JSON, las aporta el load job desde la ruta. Incluirlas en el
  # schema explicito del load rompe la carga (BigQuery las exigiria en el JSON).
  load_audit_columns = [
    { name = "_ingested_at", type = "STRING", mode = "NULLABLE" },
    { name = "_source_empresa", type = "STRING", mode = "NULLABLE" },
    { name = "_query_id", type = "STRING", mode = "NULLABLE" },
    { name = "_query_version", type = "STRING", mode = "NULLABLE" },
    { name = "_query_sql_hash", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_lote_id", type = "STRING", mode = "NULLABLE" },
    { name = "_payload_hash", type = "STRING", mode = "NULLABLE" },
    { name = "_row_hash", type = "STRING", mode = "NULLABLE" },
  ]

  # Claves de particion Hive derivadas de la ruta Bronze
  # source_empresa=.../dt=.../run_id=... El load job las agrega como columnas;
  # se incluyen en el schema de la tabla nativa para evitar drift con Terraform,
  # pero NO en el schema explicito del load.
  partition_columns = [
    { name = "source_empresa", type = "STRING", mode = "NULLABLE" },
    { name = "dt", type = "STRING", mode = "NULLABLE" },
    { name = "run_id", type = "STRING", mode = "NULLABLE" },
  ]

  # Schema del LOAD job (sin claves de particion): columnas de la entidad +
  # auditoria JSON.
  staging_schemas = {
    for f in local.staging_schema_files :
    trimsuffix(replace(f, "_v1.json", ""), ".json") => concat(
      [
        for col in jsondecode(file("${local.staging_schema_dir}/${f}")).columns : {
          name = col.name
          type = (
            lower(col.type) == "number" ? "FLOAT64" :
            lower(col.type) == "integer" ? "INT64" :
            lower(col.type) == "boolean" ? "BOOL" :
            "STRING"
          )
          mode = "NULLABLE"
        }
      ],
      local.load_audit_columns
    )
  }

  # Schema de la TABLA nativa (con claves de particion Hive que agrega el load).
  table_schemas = {
    for k, v in local.staging_schemas :
    k => concat(v, local.partition_columns)
  }
}

# -----------------------------------------------------------------------------
# APIs requeridas
# -----------------------------------------------------------------------------

resource "google_project_service" "required" {
  for_each = toset([
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "sts.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "workflows.googleapis.com",
    "cloudscheduler.googleapis.com",
    "dataform.googleapis.com",
  ])

  project = var.project_id
  service = each.key

  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Storage: buckets Bronze + Quarantine
# -----------------------------------------------------------------------------

module "storage" {
  source = "./modules/storage"

  project_id             = var.project_id
  region                 = var.region
  bronze_bucket_name     = var.bronze_bucket_name
  quarantine_bucket_name = var.quarantine_bucket_name
  enable_versioning      = var.enable_object_versioning
  bronze_retention_days  = var.bronze_retention_days
  labels                 = local.common_labels

  depends_on = [google_project_service.required]
}

# -----------------------------------------------------------------------------
# BigQuery: dataset de control
# -----------------------------------------------------------------------------

module "bigquery" {
  source = "./modules/bigquery"

  project_id               = var.project_id
  dataset_id               = var.control_dataset_id
  dataset_location         = var.control_dataset_location
  partition_control_tables = var.partition_control_tables
  labels                   = local.common_labels

  depends_on = [google_project_service.required]
}

# -----------------------------------------------------------------------------
# Secret Manager: contenedores de secretos
# -----------------------------------------------------------------------------

module "secrets" {
  source = "./modules/secrets"

  project_id   = var.project_id
  secret_names = var.secret_names
  labels       = local.common_labels

  depends_on = [google_project_service.required]
}

# -----------------------------------------------------------------------------
# Service Account del runtime + IAM
# -----------------------------------------------------------------------------

module "service_account" {
  source = "./modules/service_account"

  project_id             = var.project_id
  account_name           = var.service_account_name
  environment            = var.environment
  bronze_bucket_name     = module.storage.bronze_bucket_name
  quarantine_bucket_name = module.storage.quarantine_bucket_name
  control_dataset_id     = local.workflow_control_dataset_id
  secret_ids             = module.secrets.secret_ids
  bronze_stg_dataset_id  = var.bronze_stg_dataset_id
  silver_dataset_id      = var.silver_dataset_id
  gold_dataset_id        = var.gold_dataset_id

  depends_on = [google_project_service.required]
}

resource "google_bigquery_dataset_iam_member" "additional_control_editor" {
  count      = local.workflow_control_dataset_id == module.bigquery.dataset_id ? 0 : 1
  project    = var.project_id
  dataset_id = local.workflow_control_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${module.service_account.email}"
}

# -----------------------------------------------------------------------------
# Dataform: repositorio que construye Silver/Gold a partir del staging
# -----------------------------------------------------------------------------

module "dataform" {
  source = "./modules/dataform"

  project_id                    = var.project_id
  region                        = var.region
  repository_id                 = "factory-etl-${var.environment}"
  git_remote_url                = var.dataform_git_remote_url
  default_branch                = var.dataform_default_branch
  github_token_secret_id        = "dataform-github-token"
  runtime_service_account_email = module.service_account.email
  labels                        = local.common_labels

  depends_on = [google_project_service.required, module.secrets, module.service_account]
}

# -----------------------------------------------------------------------------
# Workload Identity Federation (GitHub Actions -> SA)
# -----------------------------------------------------------------------------

module "wif" {
  count  = var.wif_enabled ? 1 : 0
  source = "./modules/wif"

  project_id            = var.project_id
  environment           = var.environment
  service_account_email = module.service_account.email
  github_owner          = var.github_owner
  github_repo           = var.github_repo
  github_allowed_refs   = var.github_allowed_refs

  depends_on = [google_project_service.required]
}

# -----------------------------------------------------------------------------
# Artifact Registry: repositorio Docker para imagenes
# -----------------------------------------------------------------------------

module "artifact_registry" {
  source = "./modules/artifact_registry"

  project_id    = var.project_id
  region        = var.region
  repository_id = var.artifact_repo_id
  labels        = local.common_labels

  depends_on = [google_project_service.required]
}

# -----------------------------------------------------------------------------
# Cloud Run Job: ejecutor del contenedor ETL
# -----------------------------------------------------------------------------

module "cloud_run_job" {
  source = "./modules/cloud_run_job"

  project_id             = var.project_id
  region                 = var.region
  job_name               = local.cloud_run_job_name
  image_uri              = "${module.artifact_registry.repository_url}/${var.container_image_name}:${var.container_image_tag}"
  service_account_email  = module.service_account.email
  environment            = var.environment
  bronze_bucket_name     = module.storage.bronze_bucket_name
  quarantine_bucket_name = module.storage.quarantine_bucket_name
  control_dataset_id     = local.workflow_control_dataset_id
  query_id               = "articulos_v1"
  source_empresa         = "tinito"
  cpu_limit              = var.articulos_cpu_limit
  memory_limit           = var.articulos_memory_limit
  timeout_seconds        = var.articulos_timeout_seconds
  max_retries            = var.articulos_max_retries
  labels                 = local.common_labels

  depends_on = [google_project_service.required, module.artifact_registry, module.service_account]
}

# -----------------------------------------------------------------------------
# Cloud Workflows: orquestador de ejecucion
# -----------------------------------------------------------------------------
# WF1 (transaccional, 5:30 PM): sync de tablas transaccionales hasta Bronze.
# WF2 (full, 11:30 PM): sync de tablas transaccionales + maestras hasta Bronze.
# WF3 (12:30 AM): Bronze -> staging -> Dataform Silver/Gold.

module "workflows" {
  source = "./modules/workflows"

  project_id            = var.project_id
  region                = var.region
  workflow_name         = local.daily_workflow_name
  job_name              = module.cloud_run_job.job_name
  bucket_name           = module.storage.bronze_bucket_name
  control_dataset_id    = local.workflow_control_dataset_id
  service_account_email = module.service_account.email
  labels                = local.common_labels
  queries               = var.daily_queries

  depends_on = [google_project_service.required, module.cloud_run_job]
}

module "workflows_full" {
  source = "./modules/workflows"

  project_id            = var.project_id
  region                = var.region
  workflow_name         = local.full_workflow_name
  job_name              = module.cloud_run_job.job_name
  bucket_name           = module.storage.bronze_bucket_name
  control_dataset_id    = local.workflow_control_dataset_id
  service_account_email = module.service_account.email
  labels                = local.common_labels
  queries               = var.daily_queries_full

  depends_on = [google_project_service.required, module.cloud_run_job, module.dataform]
}

module "workflows_consolidation" {
  source = "./modules/workflows"

  project_id            = var.project_id
  region                = var.region
  workflow_name         = local.consolidation_workflow_name
  job_name              = module.cloud_run_job.job_name
  bucket_name           = module.storage.bronze_bucket_name
  control_dataset_id    = local.workflow_control_dataset_id
  service_account_email = module.service_account.email
  labels                = local.common_labels
  queries               = var.daily_queries_full

  enable_medallion_consolidation = true
  consolidation_only             = true
  bronze_stg_dataset_id          = var.bronze_stg_dataset_id
  dataform_repository_id         = module.dataform.repository_id
  dataform_location              = module.dataform.location
  staging_schemas_json           = jsonencode(local.staging_schemas)
  quarantine_bucket_name         = module.storage.quarantine_bucket_name
  silver_dataset_id              = var.silver_dataset_id
  gold_dataset_id                = var.gold_dataset_id
  security_dataset_id            = "factory_etl_security"

  depends_on = [google_project_service.required, module.dataform]
}

resource "google_service_account_iam_member" "dataform_service_agent_act_as" {
  service_account_id = module.service_account.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${module.dataform.service_agent_email}"
}

resource "google_service_account_iam_member" "dataform_service_agent_token_creator" {
  service_account_id = module.service_account.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${module.dataform.service_agent_email}"
}

resource "google_bigquery_dataset_iam_member" "runtime_assertions_editor" {
  project    = var.project_id
  dataset_id = "factory_etl_assertions"
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${module.service_account.email}"
}

# Staging nativo paralelo: los destinos de los load jobs no pueden ser tablas
# EXTERNAL. Se conservan las tablas legacy y Dataform consume estas tablas
# versionadas, administradas por Terraform.
resource "google_bigquery_table" "staging_native" {
  for_each            = local.staging_schemas
  project             = var.project_id
  dataset_id          = var.bronze_stg_dataset_id
  table_id            = each.key == "ventas_diarias_v2" ? "stg_ventas_diarias_v2" : "stg_${each.key}_snapshot"
  schema              = jsonencode(local.table_schemas[each.key])
  deletion_protection = true
  labels              = local.common_labels

  depends_on = [module.bigquery, google_project_service.required]
}

# -----------------------------------------------------------------------------
# Cloud Scheduler: disparadores cron (5:30 PM, 11:30 PM y 12:30 AM Caracas)
# -----------------------------------------------------------------------------
# NOTA: ambos usan el mismo string que module.workflows(_full) calcula para su
# nombre, en vez de referenciar la salida del modulo directamente. Esto evita
# que el scheduler quede bloqueado por el workflow, cuyo recurso
# (google_workflows_workflow) no soporta "terraform import": en prod ya existe
# creado fuera de Terraform, por lo que cualquier apply intentara (y fallara con
# 409) recrearlo. Desacoplar la dependencia permite seguir gestionando el
# scheduler aunque ese recurso puntual quede fuera de Terraform.

module "cloud_scheduler" {
  source = "./modules/cloud_scheduler"

  project_id            = var.project_id
  region                = var.region
  scheduler_name        = local.daily_scheduler_name
  workflow_name         = var.environment == "prod" ? "factory-etl-daily-transaccional-prod" : local.daily_workflow_name
  service_account_email = module.service_account.email
  cron_schedule         = var.cron_schedule
  time_zone             = var.time_zone

  depends_on = [google_project_service.required]
}

module "cloud_scheduler_full" {
  source = "./modules/cloud_scheduler"

  project_id            = var.project_id
  region                = var.region
  scheduler_name        = local.full_scheduler_name
  workflow_name         = var.environment == "prod" ? "factory-etl-full-prod" : local.full_workflow_name
  service_account_email = module.service_account.email
  cron_schedule         = var.cron_schedule_full
  time_zone             = var.time_zone

  depends_on = [google_project_service.required]
}

module "cloud_scheduler_consolidation" {
  source = "./modules/cloud_scheduler"

  project_id            = var.project_id
  region                = var.region
  scheduler_name        = local.consolidation_scheduler_name
  workflow_name         = local.consolidation_workflow_name
  service_account_email = module.service_account.email
  cron_schedule         = var.cron_schedule_consolidation
  time_zone             = var.time_zone

  depends_on = [google_project_service.required]
}

module "cloud_scheduler_scd2_daily" {
  count  = var.environment == "prod" ? 1 : 0
  source = "./modules/cloud_scheduler"

  project_id            = var.project_id
  region                = var.region
  scheduler_name        = "factory-etl-daily-scheduler-transaccional-prod-scd2"
  workflow_name         = local.daily_workflow_name
  service_account_email = module.service_account.email
  cron_schedule         = var.cron_schedule
  time_zone             = var.time_zone

  depends_on = [google_project_service.required]
}

module "cloud_scheduler_scd2_full" {
  count  = var.environment == "prod" ? 1 : 0
  source = "./modules/cloud_scheduler"

  project_id            = var.project_id
  region                = var.region
  scheduler_name        = "factory-etl-full-scheduler-prod-scd2"
  workflow_name         = local.full_workflow_name
  service_account_email = module.service_account.email
  cron_schedule         = var.cron_schedule_full
  time_zone             = var.time_zone

  depends_on = [google_project_service.required]
}
