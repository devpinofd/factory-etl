variable "enable_sort_dataset" {
  description = "Aprovisiona sort y el acceso de su ejecutor interno en produccion, sin recursos API ni permisos del consumidor."
  type        = bool
  default     = false
}

resource "google_bigquery_dataset_iam_member" "sort_runtime_editor" {
  count      = var.enable_sort_dataset ? 1 : 0
  project    = var.project_id
  dataset_id = google_bigquery_dataset.sort[0].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${module.service_account.email}"
}

resource "google_bigquery_dataset" "sort" {
  count                      = var.enable_sort_dataset ? 1 : 0
  project                    = var.project_id
  dataset_id                 = "sort"
  location                   = "us-central1"
  description                = "Vistas contractuales Mondelez para consulta SQL de terceros; acceso por vista."
  delete_contents_on_destroy = false
  labels                     = local.common_labels

  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }

  lifecycle {
    prevent_destroy = true
    # Subsequent view authorizations and grants are managed separately.
    ignore_changes = [access]

    precondition {
      condition     = var.environment == "prod"
      error_message = "El dataset sort de esta etapa solo se aprovisiona en produccion."
    }
  }
}
