mock_provider "google" {}
mock_provider "google-beta" {}

variables {
  project_id                  = "factory-etl-prod"
  region                      = "us-central1"
  environment                 = "prod"
  bronze_bucket_name          = "factory-etl-prod-bronze"
  quarantine_bucket_name      = "factory-etl-prod-quarantine"
  adopt_existing_data_quality = false
}

run "dataset_independent_of_api" {
  command = plan

  variables {
    enable_sort_dataset = true
    enable_mondelez_api = false
  }

  assert {
    condition     = length(google_bigquery_dataset_iam_member.sort_runtime_editor) == 1 && google_bigquery_dataset_iam_member.sort_runtime_editor[0].role == "roles/bigquery.dataEditor" && google_bigquery_dataset_iam_member.sort_runtime_editor[0].dataset_id == "sort"
    error_message = "Solo el ejecutor interno recibe escritura en sort, no el consumidor."
  }

  assert {
    condition     = length(google_bigquery_dataset.sort) == 1 && google_bigquery_dataset.sort[0].dataset_id == "sort"
    error_message = "Debe crearse un unico dataset llamado sort."
  }

  assert {
    condition     = google_bigquery_dataset.sort[0].project == "factory-etl-prod" && google_bigquery_dataset.sort[0].location == "us-central1"
    error_message = "sort debe residir en prod, us-central1."
  }

  assert {
    condition     = google_bigquery_dataset.sort[0].delete_contents_on_destroy == false
    error_message = "No se permite borrar el contenido del dataset automaticamente."
  }

  assert {
    condition     = length(google_bigquery_dataset.sort[0].access) == 1 && one(google_bigquery_dataset.sort[0].access).role == "OWNER" && one(google_bigquery_dataset.sort[0].access).special_group == "projectOwners"
    error_message = "El ACL inicial solo debe incluir projectOwners; no debe anadir al creador ni al tercero."
  }

  assert {
    condition     = length(google_bigquery_dataset.mondelez) == 0 && length(google_service_account.mondelez) == 0 && length(google_secret_manager_secret.mondelez) == 0 && length(google_cloud_run_v2_service.mondelez) == 0
    error_message = "El dataset sort no debe activar recursos de API ni el dataset anterior."
  }
}

run "dataset_disabled_by_default" {
  command = plan

  assert {
    condition     = length(google_bigquery_dataset.sort) == 0
    error_message = "Sin habilitacion explicita no debe crearse sort."
  }
}

run "reject_non_production" {
  command = plan

  variables {
    environment         = "dev"
    enable_sort_dataset = true
  }

  expect_failures = [google_bigquery_dataset.sort]
}
