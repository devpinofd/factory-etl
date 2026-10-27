variable "enable_sort_consumer_exports" {
  description = "Habilita el bucket privado de resultados SORT para Magdalena, sin permiso de borrado."
  type        = bool
  default     = false
}

resource "google_storage_bucket" "sort_consumer_exports" {
  count                       = var.enable_sort_consumer_exports ? 1 : 0
  project                     = var.project_id
  name                        = "${var.project_id}-sort-magdalena-exports"
  location                    = "US-CENTRAL1"
  storage_class               = "STANDARD"
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = merge(local.common_labels, { purpose = "sort-consumer-exports" })

  versioning {
    enabled = false
  }

  soft_delete_policy {
    retention_duration_seconds = 0
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  lifecycle {
    prevent_destroy = true

    precondition {
      condition     = var.project_id == "factory-etl-prod" && var.environment == "prod" && var.enable_sort_consumer_access && var.enable_sort_dataset
      error_message = "El bucket de resultados solo se autoriza en produccion con el acceso SORT habilitado."
    }
  }
}

resource "google_project_iam_custom_role" "sort_consumer_exports" {
  count       = var.enable_sort_consumer_exports ? 1 : 0
  project     = var.project_id
  role_id     = "sortExportFiles"
  title       = "SORT export files"
  description = "Crea, lista y descarga archivos del bucket autorizado, sin borrar ni sobrescribir."
  permissions = [
    "storage.buckets.get",
    "storage.objects.create",
    "storage.objects.get",
    "storage.objects.list",
  ]

  depends_on = [google_storage_bucket.sort_consumer_exports]
}

resource "google_storage_bucket_iam_member" "sort_consumer_exports" {
  count  = var.enable_sort_consumer_exports ? 1 : 0
  bucket = google_storage_bucket.sort_consumer_exports[0].name
  role   = google_project_iam_custom_role.sort_consumer_exports[0].name
  member = local.sort_consumer_member
}

resource "google_project_iam_custom_role" "sort_consumer_bucket_picker" {
  count       = var.enable_sort_consumer_exports ? 1 : 0
  project     = var.project_id
  role_id     = "sortExportBucketPicker"
  title       = "SORT export bucket picker"
  description = "Enumera buckets para el selector Guardar resultados de BigQuery, sin acceso a sus archivos."
  permissions = ["storage.buckets.list"]

  depends_on = [google_storage_bucket.sort_consumer_exports]
}

resource "google_project_iam_member" "sort_consumer_bucket_picker" {
  count   = var.enable_sort_consumer_exports ? 1 : 0
  project = var.project_id
  role    = google_project_iam_custom_role.sort_consumer_bucket_picker[0].name
  member  = local.sort_consumer_member
}

output "sort_consumer_exports_bucket" {
  description = "Bucket privado de resultados SORT; usar nombres nuevos, sin sobrescritura."
  value       = var.enable_sort_consumer_exports ? "gs://${google_storage_bucket.sort_consumer_exports[0].name}" : null
}
