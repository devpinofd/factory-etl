mock_provider "google" {}
mock_provider "google-beta" {}

override_module {
  target = module.service_account
  outputs = {
    email = "factory-etl-runtime-prod@factory-etl-prod.iam.gserviceaccount.com"
    name  = "projects/factory-etl-prod/serviceAccounts/factory-etl-runtime-prod@factory-etl-prod.iam.gserviceaccount.com"
  }
}

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

run "access_audit_disabled_by_default" {
  command = plan

  assert {
    condition     = length(google_project_service.sort_access_org_policy) == 0
    error_message = "La auditoria de acceso no debe habilitar APIs sin autorizacion explicita."
  }
}

run "access_audit_api_only" {
  command = plan

  variables {
    enable_sort_access_audit_api = true
  }

  assert {
    condition     = google_project_service.sort_access_org_policy[0].project == "factory-etl-prod" && google_project_service.sort_access_org_policy[0].service == "orgpolicy.googleapis.com" && google_project_service.sort_access_org_policy[0].disable_on_destroy == false
    error_message = "Solo se autoriza Organization Policy en prod, sin deshabilitarla al retirar el recurso."
  }

  assert {
    condition     = length(google_bigquery_dataset.sort) == 0 && length(google_bigquery_dataset_iam_member.sort_runtime_editor) == 0
    error_message = "La auditoria no debe crear datasets, conceder IAM ni habilitar modelos."
  }
}

run "reject_access_audit_in_dev" {
  command = plan

  variables {
    environment                  = "dev"
    enable_sort_access_audit_api = true
  }

  expect_failures = [google_project_service.sort_access_org_policy]
}

run "reject_access_audit_in_other_project" {
  command = plan

  variables {
    project_id                   = "factory-etl-dev"
    enable_sort_access_audit_api = true
  }

  expect_failures = [google_project_service.sort_access_org_policy]
}
