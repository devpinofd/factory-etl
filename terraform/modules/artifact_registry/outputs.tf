output "repository_id" {
  value       = google_artifact_registry_repository.repo.repository_id
  description = "ID del repositorio Artifact Registry"
}

output "repository_url" {
  value       = "${google_artifact_registry_repository.repo.location}-docker.pkg.dev/${google_artifact_registry_repository.repo.project}/${google_artifact_registry_repository.repo.repository_id}"
  description = "URL base del repositorio Docker en Artifact Registry"
}
