output "bronze_bucket_name" {
  description = "Nombre del bucket GCS Bronze."
  value       = module.storage.bronze_bucket_name
}

output "quarantine_bucket_name" {
  description = "Nombre del bucket GCS de cuarentena."
  value       = module.storage.quarantine_bucket_name
}

output "control_dataset_id" {
  description = "ID del dataset BQ de control."
  value       = module.bigquery.dataset_id
}

output "service_account_email" {
  description = "Email de la SA runtime del ETL."
  value       = module.service_account.email
}

output "environment_inventory" {
  description = "Inventario observado de recursos operativos por ambiente."
  value       = local.environment_inventory
}

output "wif_provider_id" {
  description = "Full resource name del WIF provider para usar en GitHub Actions."
  value       = try(module.wif[0].provider_id, null)
}

output "wif_service_account_email" {
  description = "SA que GitHub Actions puede asumir via WIF."
  value       = try(module.wif[0].service_account_email, null)
}

output "artifact_registry_repository_url" {
  description = "URL del repositorio Artifact Registry."
  value       = module.artifact_registry.repository_url
}

output "cloud_run_job_name" {
  description = "Nombre del Cloud Run Job."
  value       = module.cloud_run_job.job_name
}

output "workflow_name" {
  description = "Nombre del Cloud Workflow."
  value       = module.workflows.workflow_name
}

output "workflow_full_name" {
  description = "Nombre del Cloud Workflow de ingesta completa."
  value       = module.workflows_full.workflow_name
}

output "workflow_consolidation_name" {
  description = "Nombre del Cloud Workflow de consolidacion Bronze a Silver/Gold."
  value       = module.workflows_consolidation.workflow_name
}

output "scheduler_name" {
  description = "Nombre del Cloud Scheduler Job."
  value       = module.cloud_scheduler.scheduler_name
}

output "scheduler_consolidation_name" {
  description = "Nombre del Cloud Scheduler de consolidacion."
  value       = try(module.cloud_scheduler_consolidation[0].scheduler_name, "")
}
