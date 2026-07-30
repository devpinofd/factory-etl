resource "google_artifact_registry_repository" "repo" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  description   = "Repositorio Docker para imagenes de factory-etl"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-recent-images"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  labels = var.labels
}
