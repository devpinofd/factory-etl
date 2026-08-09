data "google_project" "this" {
  project_id = var.project_id
}

# El Service Agent de Dataform se aprovisiona de forma perezosa; lo forzamos
# explicitamente para poder concederle acceso al secreto antes de crear el repo.
resource "google_project_service_identity" "dataform_agent" {
  provider = google-beta

  project = var.project_id
  service = "dataform.googleapis.com"
}

resource "google_dataform_repository" "repo" {
  provider = google-beta

  project      = var.project_id
  region       = var.region
  name         = var.repository_id
  display_name = var.repository_id
  labels       = var.labels

  git_remote_settings {
    url                                 = var.git_remote_url
    default_branch                      = var.default_branch
    authentication_token_secret_version = "projects/${var.project_id}/secrets/${var.github_token_secret_id}/versions/latest"
  }

  depends_on = [google_secret_manager_secret_iam_member.dataform_agent_token_accessor]
}

# El Service Agent de Dataform necesita leer el token de GitHub para clonar el repo.
resource "google_secret_manager_secret_iam_member" "dataform_agent_token_accessor" {
  project   = var.project_id
  secret_id = var.github_token_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_project_service_identity.dataform_agent.email}"
}

# La SA del runtime (usada por el Cloud Workflow) necesita compilar y correr
# workflow invocations sobre este repositorio especifico.
resource "google_dataform_repository_iam_member" "runtime_editor" {
  provider = google-beta

  project    = var.project_id
  region     = var.region
  repository = google_dataform_repository.repo.name
  role       = "roles/dataform.editor"
  member     = "serviceAccount:${var.runtime_service_account_email}"
}

output "repository_id" {
  value = google_dataform_repository.repo.name
}

output "location" {
  value = var.region
}

output "service_agent_email" {
  value = google_project_service_identity.dataform_agent.email
}
