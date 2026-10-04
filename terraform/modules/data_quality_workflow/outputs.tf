output "workflow_name" {
  value = google_workflows_workflow.workflow.name
}

output "scheduler_name" {
  value = google_cloud_scheduler_job.job.name
}

output "workflow_source_contents" {
  description = "Contenido fuente YAML renderizado del workflow de Data Quality."
  value       = google_workflows_workflow.workflow.source_contents
}
