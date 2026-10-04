resource "google_workflows_workflow" "workflow" {
  name            = var.workflow_name
  project         = var.project_id
  region          = var.region
  service_account = var.service_account_email
  description     = "QA periódico idempotente de Bronze, staging, Silver y Gold; no reprocesa datos."
  labels          = var.labels

  source_contents = templatefile("${path.module}/templates/workflow.yaml.tftpl", {
    project_id               = var.project_id
    region                   = var.region
    control_dataset_id       = var.control_dataset_id
    staging_dataset_id       = var.staging_dataset_id
    gold_dataset_id          = var.gold_dataset_id
    bronze_bucket_name       = var.bronze_bucket_name
    bronze_prefix            = var.bronze_prefix
    staging_table_name       = var.staging_table_name
    gold_table_name          = var.gold_table_name
    expected_companies_count = length(var.expected_companies)
    expected_companies_array = "[${join(", ", [for c in var.expected_companies : "'${c}'"])}]"
  })
}

resource "google_cloud_scheduler_job" "job" {
  name             = var.scheduler_name
  project          = var.project_id
  region           = var.region
  description      = "Ejecuta el QA periódico del ETL sin reprocesar datos."
  schedule         = var.cron_schedule
  time_zone        = var.time_zone
  paused           = var.scheduler_paused
  attempt_deadline = "320s"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${google_workflows_workflow.workflow.name}/executions"
    body        = base64encode(jsonencode({}))

    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = var.service_account_email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}
