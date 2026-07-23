variable "project_id" { type = string }
variable "environment" { type = string }
variable "service_account_email" { type = string }
variable "github_owner" { type = string }
variable "github_repo" { type = string }
variable "github_allowed_refs" { type = list(string) }

# Workload Identity Federation: GitHub Actions asume la SA sin claves JSON.
#
# Referencia:
# - https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines
# - https://github.com/google-github-actions/auth

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-pool-${var.environment}"
  display_name              = "GitHub Actions (${var.environment})"
  description               = "Pool WIF para autenticar GitHub Actions sin claves JSON."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
    "attribute.actor"      = "assertion.actor"
  }

  # Solo permite tokens del repo declarado. Sin este condition, cualquier repo
  # de GitHub podria intentar canjear tokens contra este pool.
  attribute_condition = "assertion.repository == '${var.github_owner}/${var.github_repo}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Solo los refs permitidos pueden impersonar la SA.
resource "google_service_account_iam_binding" "wif_binding" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.service_account_email}"
  role               = "roles/iam.workloadIdentityUser"

  members = [
    for ref in var.github_allowed_refs :
    "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.ref/${ref}"
  ]
}

output "provider_id" {
  description = "Full resource name para google-github-actions/auth."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "service_account_email" {
  value = var.service_account_email
}
