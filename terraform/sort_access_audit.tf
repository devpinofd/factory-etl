variable "enable_sort_access_audit_api" {
  description = "Habilita Organization Policy para inventariar el acceso SORT; no concede IAM ni acceso al directorio."
  type        = bool
  default     = false
}

resource "google_project_service" "sort_access_org_policy" {
  count              = var.enable_sort_access_audit_api ? 1 : 0
  project            = var.project_id
  service            = "orgpolicy.googleapis.com"
  disable_on_destroy = false

  lifecycle {
    precondition {
      condition     = var.environment == "prod" && var.project_id == "factory-etl-prod"
      error_message = "La API de auditoria SORT solo esta autorizada en factory-etl-prod."
    }
  }
}
