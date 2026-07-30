variable "project_id" {
  type        = string
  description = "ID del proyecto GCP"
}

variable "region" {
  type        = string
  description = "Region de GCP"
}

variable "scheduler_name" {
  type        = string
  description = "Nombre del Cloud Scheduler Job"
}

variable "workflow_name" {
  type        = string
  description = "Nombre del Cloud Workflow a disparar"
}

variable "service_account_email" {
  type        = string
  description = "Email de la Service Account para la ficha OIDC"
}

variable "cron_schedule" {
  type        = string
  description = "Expresion cron para el disparo"
  default     = "0 19 * * *" # 07:00 PM diario
}

variable "time_zone" {
  type        = string
  description = "Zona horaria del scheduler"
  default     = "America/Caracas"
}
