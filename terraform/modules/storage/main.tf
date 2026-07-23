variable "project_id" { type = string }
variable "region" { type = string }
variable "bronze_bucket_name" { type = string }
variable "quarantine_bucket_name" { type = string }
variable "enable_versioning" { type = bool }
variable "bronze_retention_days" { type = number }
variable "labels" { type = map(string) }

resource "google_storage_bucket" "bronze" {
  name                        = var.bronze_bucket_name
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = var.enable_versioning
  }

  dynamic "lifecycle_rule" {
    for_each = var.bronze_retention_days > 0 ? [1] : []
    content {
      condition {
        age = var.bronze_retention_days
      }
      action {
        type          = "SetStorageClass"
        storage_class = "NEARLINE"
      }
    }
  }

  labels = merge(var.labels, { tier = "bronze" })
}

resource "google_storage_bucket" "quarantine" {
  name                        = var.quarantine_bucket_name
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = var.enable_versioning
  }

  labels = merge(var.labels, { tier = "quarantine" })
}

output "bronze_bucket_name" {
  value = google_storage_bucket.bronze.name
}

output "quarantine_bucket_name" {
  value = google_storage_bucket.quarantine.name
}
