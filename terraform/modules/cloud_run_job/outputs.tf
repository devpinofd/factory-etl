output "job_name" {
  value       = google_cloud_run_v2_job.job.name
  description = "Nombre del Cloud Run Job"
}

output "job_id" {
  value       = google_cloud_run_v2_job.job.id
  description = "ID completo del Cloud Run Job"
}
