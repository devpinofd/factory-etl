variable "project_id" { type = string }
variable "account_name" { type = string }
variable "environment" { type = string }
variable "bronze_bucket_name" { type = string }
variable "quarantine_bucket_name" { type = string }
variable "control_dataset_id" { type = string }
variable "secret_ids" { type = map(string) }

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${var.account_name}-${var.environment}"
  display_name = "FactoryETL runtime (${var.environment})"
  description  = "Identidad del proceso ETL para acceder a GCS/BQ/Secret Manager."
}

# --- GCS: escritura en Bronze y Quarantine ------------------------------------

resource "google_storage_bucket_iam_member" "bronze_object_admin" {
  bucket = var.bronze_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "quarantine_object_admin" {
  bucket = var.quarantine_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

# --- BigQuery: dataEditor en el dataset de control ----------------------------

resource "google_bigquery_dataset_iam_member" "control_editor" {
  project    = var.project_id
  dataset_id = var.control_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

# Necesario para poder correr jobs de INSERT/QUERY sobre el dataset.
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Secret Manager: accessor sobre secretos declarados -----------------------

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = var.secret_ids

  project   = var.project_id
  secret_id = each.key
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Cloud Run & Workflows: invocador y ejecutor -----------------------------

resource "google_project_iam_member" "run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "workflows_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "sa_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

output "email" {
  value = google_service_account.runtime.email
}

output "name" {
  value = google_service_account.runtime.name
}

