output "workflow_name" {
  value       = google_workflows_workflow.workflow.name
  description = "Nombre del Cloud Workflow"
}

output "workflow_id" {
  value       = google_workflows_workflow.workflow.id
  description = "ID completo del Cloud Workflow"
}
