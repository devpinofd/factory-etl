variable "project_id" { type = string }
variable "secret_names" { type = list(string) }
variable "labels" { type = map(string) }

# IMPORTANTE: Terraform crea el contenedor del secreto, NO la version con el
# valor. Cargar el valor manualmente con:
#
#   gcloud secrets versions add factory-api-key --data-file=-  --project=<PROJECT>
#
# Esto mantiene los secretos fuera del state de Terraform.

resource "google_secret_manager_secret" "secrets" {
  for_each = toset(var.secret_names)

  project   = var.project_id
  secret_id = each.key

  replication {
    auto {}
  }

  labels = var.labels
}

output "secret_ids" {
  description = "Map de secret_name -> secret full ID."
  value       = { for k, s in google_secret_manager_secret.secrets : k => s.id }
}
