resource "google_cloud_scheduler_job" "job" {
  name             = var.scheduler_name
  description      = "Disparador diario del ETL a las 07:00 PM horario Caracas"
  schedule         = var.cron_schedule
  time_zone        = var.time_zone
  region           = var.region
  project          = var.project_id
  attempt_deadline = "320s"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${var.workflow_name}/executions"
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
