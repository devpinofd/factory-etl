mock_provider "google" {}
mock_provider "google-beta" {}

variables {
  project_id                  = "factory-etl-prod"
  environment                 = "prod"
  region                      = "us-central1"
  bronze_bucket_name          = "factory-etl-prod-bronze"
  quarantine_bucket_name      = "factory-etl-prod-quarantine"
  adopt_existing_data_quality = false
}

run "exports_disabled_by_default" {
  command = plan

  assert {
    condition     = length(google_storage_bucket.sort_consumer_exports) == 0 && length(google_project_iam_custom_role.sort_consumer_exports) == 0 && length(google_storage_bucket_iam_member.sort_consumer_exports) == 0 && length(google_project_iam_custom_role.sort_consumer_bucket_picker) == 0 && length(google_project_iam_member.sort_consumer_bucket_picker) == 0
    error_message = "No crear almacenamiento ni permisos sin habilitacion explicita."
  }
}

run "private_exports_without_delete" {
  command = plan

  variables {
    enable_sort_dataset          = true
    enable_sort_consumer_access  = true
    enable_sort_consumer_exports = true
  }

  assert {
    condition     = google_storage_bucket.sort_consumer_exports[0].name == "factory-etl-prod-sort-magdalena-exports" && google_storage_bucket.sort_consumer_exports[0].location == "US-CENTRAL1" && google_storage_bucket.sort_consumer_exports[0].uniform_bucket_level_access && google_storage_bucket.sort_consumer_exports[0].public_access_prevention == "enforced" && !google_storage_bucket.sort_consumer_exports[0].force_destroy
    error_message = "El bucket debe ser privado, regional y no admitir borrado forzado."
  }

  assert {
    condition     = one(one(google_storage_bucket.sort_consumer_exports[0].lifecycle_rule).condition).age == 30 && one(one(google_storage_bucket.sort_consumer_exports[0].lifecycle_rule).action).type == "Delete" && !one(google_storage_bucket.sort_consumer_exports[0].versioning).enabled && one(google_storage_bucket.sort_consumer_exports[0].soft_delete_policy).retention_duration_seconds == 0
    error_message = "Eliminar automaticamente a los 30 dias sin conservar versiones o copias soft-delete."
  }

  assert {
    condition     = toset(google_project_iam_custom_role.sort_consumer_exports[0].permissions) == toset(["storage.buckets.get", "storage.objects.create", "storage.objects.get", "storage.objects.list"]) && google_storage_bucket_iam_member.sort_consumer_exports[0].member == "user:magdalena.mateu@tinitot.com"
    error_message = "Solo crear, listar y descargar; nunca borrar, sobrescribir o administrar IAM."
  }

  assert {
    condition     = toset(google_project_iam_custom_role.sort_consumer_bucket_picker[0].permissions) == toset(["storage.buckets.list"]) && google_project_iam_member.sort_consumer_bucket_picker[0].member == "user:magdalena.mateu@tinitot.com" && google_project_iam_member.sort_consumer_bucket_picker[0].project == "factory-etl-prod"
    error_message = "El selector solo puede enumerar buckets del proyecto, sin permisos sobre objetos."
  }
}

run "reject_exports_without_consumer" {
  command = plan

  variables {
    enable_sort_consumer_exports = true
  }

  expect_failures = [google_storage_bucket.sort_consumer_exports]
}

run "reject_exports_outside_prod" {
  command = plan

  variables {
    project_id                   = "factory-etl-dev"
    enable_sort_dataset          = true
    enable_sort_consumer_access  = true
    enable_sort_consumer_exports = true
  }

  expect_failures = [
    google_storage_bucket.sort_consumer_exports,
    google_bigquery_dataset_access.sort_public_views_gold_authorized,
  ]
}
