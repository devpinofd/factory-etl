variable "project_id" {
  type        = string
  description = "ID del proyecto GCP"
}

variable "region" {
  type        = string
  description = "Region de GCP"
}

variable "workflow_name" {
  type        = string
  description = "Nombre del Cloud Workflow"
}

variable "job_name" {
  type        = string
  description = "Nombre del Cloud Run Job objetivo"
}

variable "control_dataset_id" {
  type        = string
  description = "ID del dataset de control en BigQuery"
}

variable "service_account_email" {
  type        = string
  description = "Email de la Service Account que ejecuta el workflow"
}

variable "labels" {
  type        = map(string)
  description = "Etiquetas a aplicar al recurso"
  default     = {}
}
