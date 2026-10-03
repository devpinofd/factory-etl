output "workflow_name" {
  value = google_workflows_workflow.workflow.name
}

output "scheduler_name" {
  value = google_cloud_scheduler_job.job.name
}
