variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "control_dataset_id" {
  type = string
}

variable "staging_dataset_id" {
  type = string
}

variable "gold_dataset_id" {
  type = string
}

variable "bronze_bucket_name" {
  type = string
}

variable "scheduler_name" {
  type = string
}

variable "workflow_name" {
  description = "Nombre del workflow de QA."
  type        = string
}

variable "scheduler_paused" {
  description = "Mantiene el Cloud Scheduler en pausa (estado actual en prod)."
  type        = bool
  default     = true
}

variable "cron_schedule" {
  type    = string
  default = "0 3 * * *"
}

variable "time_zone" {
  type    = string
  default = "America/Caracas"
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "expected_companies" {
  description = "Lista de identificadores de empresas esperadas en fct_ventas_gold para el check de cobertura."
  type        = list(string)
  default     = ["ctb", "ctm", "daroan", "roldan", "tinito"]
}

variable "bronze_prefix" {
  description = "Prefijo en Cloud Storage para la inspección de Bronze."
  type        = string
  default     = "bronze/ventas_diarias_v3/"
}

variable "staging_table_name" {
  description = "Nombre de la tabla de staging para la reconciliación."
  type        = string
  default     = "stg_ventas_diarias_v3"
}

variable "gold_table_name" {
  description = "Nombre de la tabla Gold para los controles de calidad."
  type        = string
  default     = "fct_ventas_gold"
}

variable "max_staleness_days" {
  description = "Días máximos tolerados de antigüedad para la fecha más reciente de ventas (latest_date)."
  type        = number
  default     = 2
}
