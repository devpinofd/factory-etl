locals {
  common_labels = {
    project     = "factory-etl"
    environment = var.environment
    managed_by  = "terraform"
    owner       = "data-platform"
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

  project_id               = var.project_id
  region                   = var.region
  bronze_bucket_name       = var.bronze_bucket_name
  quarantine_bucket_name   = var.quarantine_bucket_name
  enable_versioning        = var.enable_object_versioning
  bronze_retention_days    = var.bronze_retention_days
  labels                   = local.common_labels

  depends_on = [google_project_service.required]
}

# -----------------------------------------------------------------------------
# BigQuery: dataset de control
# -----------------------------------------------------------------------------

module "bigquery" {
  source = "./modules/bigquery"

  project_id         = var.project_id
  dataset_id         = var.control_dataset_id
  dataset_location   = var.control_dataset_location
  labels             = local.common_labels

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

  depends_on = [google_project_service.required]
}

# -----------------------------------------------------------------------------
# Workload Identity Federation (GitHub Actions -> SA)
# -----------------------------------------------------------------------------

module "wif" {
  count  = var.wif_enabled ? 1 : 0
  source = "./modules/wif"

  project_id             = var.project_id
  environment            = var.environment
  service_account_email  = module.service_account.email
  github_owner           = var.github_owner
  github_repo            = var.github_repo
  github_allowed_refs    = var.github_allowed_refs

  depends_on = [google_project_service.required]
}
