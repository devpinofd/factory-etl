variable "project_id" {
  type        = string
  description = "ID del proyecto GCP"
}

variable "region" {
  type        = string
  description = "Region de GCP"
}

variable "repository_id" {
  type        = string
  description = "Nombre/ID del repositorio en Artifact Registry"
  default     = "factory-etl"
}

variable "labels" {
  type        = map(string)
  description = "Etiquetas a aplicar al recurso"
  default     = {}
}
