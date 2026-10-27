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

run "consumer_disabled_by_default" {
  command = plan

  assert {
    condition     = length(google_bigquery_table_iam_member.sort_consumer_viewer) == 0 && length(google_project_iam_member.sort_consumer_query_runner) == 0 && length(google_project_iam_custom_role.sort_consumer_query_runner) == 0 && length(google_bigquery_dataset_access.sort_public_views_gold_authorized) == 0
    error_message = "No debe concederse acceso sin habilitacion explicita."
  }
}

run "four_views_and_execution_only" {
  command = plan

  variables {
    enable_sort_dataset         = true
    enable_sort_consumer_access = true
  }

  assert {
    condition     = length(google_bigquery_table_iam_member.sort_consumer_viewer) == 4 && length(google_bigquery_dataset_access.sort_public_views_gold_authorized) == 4 && length(google_project_iam_member.sort_consumer_query_runner) == 1 && length(google_project_iam_custom_role.sort_consumer_query_runner) == 1
    error_message = "Solo cuatro grants de vista, cuatro autorizaciones Gold y un rol de ejecucion asignado."
  }

  assert {
    condition     = toset(google_project_iam_custom_role.sort_consumer_query_runner[0].permissions) == toset(["bigquery.config.get", "bigquery.jobs.create", "resourcemanager.projects.get"]) && google_project_iam_custom_role.sort_consumer_query_runner[0].role_id == "sortQueryRunner"
    error_message = "El rol solo permite crear jobs y leer configuracion/proyecto; nunca administrar Dataform, IAM ni datos."
  }

  assert {
    condition     = google_project_iam_member.sort_consumer_query_runner[0].member == "user:magdalena.mateu@tinitot.com" && google_project_iam_member.sort_consumer_query_runner[0].project == "factory-etl-prod"
    error_message = "El grant de ejecucion solo debe asignarse a Magdalena en el proyecto aprobado."
  }

  assert {
    condition     = alltrue([for grant in google_bigquery_table_iam_member.sort_consumer_viewer : grant.dataset_id == "sort" && grant.role == "roles/bigquery.dataViewer" && grant.member == "user:magdalena.mateu@tinitot.com"])
    error_message = "La lectura se limita a vistas SORT y a la identidad aprobada."
  }

  assert {
    condition     = alltrue([for grant in google_bigquery_dataset_access.sort_public_views_gold_authorized : grant.dataset_id == "factory_etl_gold" && one(grant.view).dataset_id == "sort"])
    error_message = "Las fuentes autorizan vistas, no al consumidor ni al dataset entero."
  }
}

run "reject_access_without_sort" {
  command = plan

  variables {
    enable_sort_consumer_access = true
  }

  expect_failures = [google_bigquery_dataset_access.sort_public_views_gold_authorized]
}

run "reject_other_project" {
  command = plan

  variables {
    project_id                  = "factory-etl-dev"
    enable_sort_dataset         = true
    enable_sort_consumer_access = true
  }

  expect_failures = [google_bigquery_dataset_access.sort_public_views_gold_authorized]
}
