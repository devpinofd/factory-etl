variable "project_id" { type = string }
variable "region" { type = string }
variable "repository_id" { type = string }
variable "git_remote_url" { type = string }
variable "default_branch" { type = string }
variable "github_token_secret_id" {
  type        = string
  description = "Nombre del secreto (Secret Manager) con el PAT de GitHub usado para clonar el repo. La version se carga fuera de Terraform."
}
variable "runtime_service_account_email" {
  type        = string
  description = "SA que ejecuta el Cloud Workflow y necesita invocar Dataform (compilationResults/workflowInvocations)."
}
variable "labels" {
  type    = map(string)
  default = {}
}
