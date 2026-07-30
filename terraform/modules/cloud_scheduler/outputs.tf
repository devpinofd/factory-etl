output "scheduler_name" {
  value       = google_cloud_scheduler_job.job.name
  description = "Nombre del Cloud Scheduler Job"
}

output "scheduler_id" {
  value       = google_cloud_scheduler_job.job.id
  description = "ID completo del Cloud Scheduler Job"
}
