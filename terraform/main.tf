locals {
  common_labels = {
    project     = "factory-etl"
    environment = var.environment
    managed_by  = "terraform"
    owner       = "data-platform"
  }

  # Tipos exactos por entidad (staging), leidos de las 19 fuentes de verdad en
  # src/factory_etl/factory_queries/schemas/*.json en vez de autodetect. El
  # nombre del archivo (sin .json) coincide siempre con el entity_name que el
  # workflow deriva de query_id (quitando el sufijo "_v1").
  staging_schema_dir   = "${path.root}/../src/factory_etl/factory_queries/schemas"
  staging_schema_files = fileset(local.staging_schema_dir, "*.json")

  staging_schemas = {
    for f in local.staging_schema_files :
    trimsuffix(f, ".json") => [
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
    ]
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
  control_dataset_id     = module.bigquery.dataset_id
  secret_ids             = module.secrets.secret_ids
  bronze_stg_dataset_id  = var.bronze_stg_dataset_id
  silver_dataset_id      = var.silver_dataset_id
  gold_dataset_id        = var.gold_dataset_id

  depends_on = [google_project_service.required]
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
  job_name               = "factory-etl-articulos-${var.environment}"
  image_uri              = "${module.artifact_registry.repository_url}/${var.container_image_name}:${var.container_image_tag}"
  service_account_email  = module.service_account.email
  environment            = var.environment
  bronze_bucket_name     = module.storage.bronze_bucket_name
  quarantine_bucket_name = module.storage.quarantine_bucket_name
  control_dataset_id     = module.bigquery.dataset_id
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
# WF1 (transaccional, 5:30 PM): sync de tablas transaccionales.
# WF2 (full, 11:30 PM): sync de tablas transaccionales + maestras.

module "workflows" {
  source = "./modules/workflows"

  project_id            = var.project_id
  region                = var.region
  workflow_name         = "factory-etl-daily-${var.environment}"
  job_name              = module.cloud_run_job.job_name
  bucket_name           = module.storage.bronze_bucket_name
  control_dataset_id    = module.bigquery.dataset_id
  service_account_email = module.service_account.email
  labels                = local.common_labels
  queries               = var.daily_queries

  depends_on = [google_project_service.required, module.cloud_run_job]
}

module "workflows_full" {
  source = "./modules/workflows"

  project_id            = var.project_id
  region                = var.region
  workflow_name         = "factory-etl-daily-full-${var.environment}"
  job_name              = module.cloud_run_job.job_name
  bucket_name           = module.storage.bronze_bucket_name
  control_dataset_id    = module.bigquery.dataset_id
  service_account_email = module.service_account.email
  labels                = local.common_labels
  queries               = var.daily_queries_full

  # Solo el WF full (11:30 PM) consolida Silver/Gold: ya trae el universo
  # completo de 19 consultas (transaccionales + maestras) que Dataform necesita.
  enable_medallion_consolidation = true
  bronze_stg_dataset_id          = var.bronze_stg_dataset_id
  dataform_repository_id         = module.dataform.repository_id
  dataform_location              = module.dataform.location
  staging_schemas_json           = jsonencode(local.staging_schemas)
  quarantine_bucket_name         = module.storage.quarantine_bucket_name

  depends_on = [google_project_service.required, module.cloud_run_job, module.dataform]
}

# -----------------------------------------------------------------------------
# Cloud Scheduler: disparadores cron (5:30 PM y 11:30 PM Caracas)
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
  scheduler_name        = "factory-etl-daily-scheduler-${var.environment}"
  workflow_name         = "factory-etl-daily-${var.environment}"
  service_account_email = module.service_account.email
  cron_schedule         = var.cron_schedule
  time_zone             = var.time_zone

  depends_on = [google_project_service.required]
}

module "cloud_scheduler_full" {
  source = "./modules/cloud_scheduler"

  project_id            = var.project_id
  region                = var.region
  scheduler_name        = "factory-etl-daily-scheduler-full-${var.environment}"
  workflow_name         = "factory-etl-daily-full-${var.environment}"
  service_account_email = module.service_account.email
  cron_schedule         = var.cron_schedule_full
  time_zone             = var.time_zone

  depends_on = [google_project_service.required]
}

