resource "google_workflows_workflow" "workflow" {
  name            = var.workflow_name
  region          = var.region
  project         = var.project_id
  description     = "Orquestador diario que registra etl_runs en BigQuery y ejecuta el Cloud Run Job"
  service_account = var.service_account_email
  labels          = var.labels

  user_env_vars = {
    PROJECT_ID         = var.project_id
    REGION             = var.region
    JOB_NAME           = var.job_name
    CONTROL_DATASET_ID = var.control_dataset_id
  }

  source_contents = templatefile("${path.module}/templates/workflow.yaml.tftpl", {
    project_id         = var.project_id
    region             = var.region
    job_name           = var.job_name
    control_dataset_id = var.control_dataset_id
  })
}
