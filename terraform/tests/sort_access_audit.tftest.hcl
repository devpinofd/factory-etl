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

run "access_audit_disabled_by_default" {
  command = plan

  assert {
    condition     = length(google_project_service.sort_access_org_policy) == 0
    error_message = "No habilitar APIs sin autorizacion explicita."
  }
}

run "access_audit_api_only" {
  command = plan

  variables {
    enable_sort_access_audit_api = true
  }

  assert {
    condition     = google_project_service.sort_access_org_policy[0].service == "orgpolicy.googleapis.com" && !google_project_service.sort_access_org_policy[0].disable_on_destroy
    error_message = "Solo gestionar Organization Policy sin deshabilitarla al retirar el recurso."
  }

  assert {
    condition     = length(google_bigquery_dataset.sort) == 0 && length(google_bigquery_table_iam_member.sort_consumer_viewer) == 0
    error_message = "La auditoria no debe crear datasets ni conceder lectura."
  }
}

run "reject_access_audit_in_dev" {
  command = plan

  variables {
    environment                 = "dev"
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
