resource "google_workflows_workflow" "workflow" {
  name            = var.workflow_name
  region          = var.region
  project         = var.project_id
  description     = "Orquestador diario que registra etl_runs en BigQuery y ejecuta el Cloud Run Job"
  service_account = var.service_account_email
  labels          = var.labels
  deletion_protection = false

  user_env_vars = {
    PROJECT_ID         = var.project_id
    REGION             = var.region
    JOB_NAME           = var.job_name
    CONTROL_DATASET_ID = var.control_dataset_id
  }

  source_contents = templatefile("${path.module}/templates/workflow.yaml.tftpl", {
    project_id                     = var.project_id
    region                         = var.region
    job_name                       = var.job_name
    consolidation_workflow_name    = var.consolidation_workflow_name
    enable_scd2                    = var.enable_scd2
    service_account_email          = var.service_account_email
    bucket_name                    = var.bucket_name
    control_dataset_id             = var.control_dataset_id
    queries_json                   = jsonencode(var.queries)
    enable_medallion_consolidation = var.enable_medallion_consolidation
    consolidation_only             = var.consolidation_only
    bronze_stg_dataset_id          = var.bronze_stg_dataset_id
    dataform_repository_id         = var.dataform_repository_id
    dataform_location              = var.dataform_location
    staging_schemas_json           = var.staging_schemas_json
    quarantine_bucket_name         = var.quarantine_bucket_name
    silver_dataset_id              = var.silver_dataset_id
    gold_dataset_id                = var.gold_dataset_id
    security_dataset_id            = var.security_dataset_id
  })
}
