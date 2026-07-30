variable "project_id" {
  type        = string
  description = "ID del proyecto GCP"
}

variable "region" {
  type        = string
  description = "Region de GCP"
}

variable "job_name" {
  type        = string
  description = "Nombre del Cloud Run Job"
}

variable "image_uri" {
  type        = string
  description = "URI de la imagen Docker en Artifact Registry"
}

variable "service_account_email" {
  type        = string
  description = "Email de la Service Account que ejecuta el job"
}

variable "environment" {
  type        = string
  description = "Ambiente logico: dev|stage|prod"
}

variable "bronze_bucket_name" {
  type        = string
  description = "Nombre del bucket Bronze"
}

variable "quarantine_bucket_name" {
  type        = string
  description = "Nombre del bucket Quarantine"
}

variable "control_dataset_id" {
  type        = string
  description = "ID del dataset de control en BigQuery"
}

variable "query_id" {
  type        = string
  description = "ID del QueryDefinition a ejecutar"
  default     = "articulos_v1"
}

variable "source_empresa" {
  type        = string
  description = "Empresa origen en FactorySoft"
  default     = "tinito"
}

variable "cpu_limit" {
  type        = string
  description = "Limite de CPU por contenedor"
  default     = "1000m"
}

variable "memory_limit" {
  type        = string
  description = "Limite de memoria RAM por contenedor"
  default     = "512Mi"
}

variable "timeout_seconds" {
  type        = number
  description = "Timeout en segundos de la ejecucion del job"
  default     = 600
}

variable "max_retries" {
  type        = number
  description = "Maximo numero de reintentos por ejecucion fallida"
  default     = 3
}

variable "labels" {
  type        = map(string)
  description = "Etiquetas a aplicar al recurso"
  default     = {}
}
