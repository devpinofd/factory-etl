variable "project_id" {
  description = "ID del proyecto GCP donde se provisiona el ETL."
  type        = string
}

variable "region" {
  description = "Region primaria para recursos regionales. Alineada con ConciliApp (us-central1)."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Ambiente logico (dev, stage, prod). Usado como sufijo y label."
  type        = string
  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "environment debe ser dev, stage o prod."
  }
}

variable "bronze_bucket_name" {
  description = "Nombre completo del bucket GCS para Bronze."
  type        = string
}

variable "quarantine_bucket_name" {
  description = "Nombre completo del bucket GCS para quarantine."
  type        = string
}

variable "control_dataset_id" {
  description = "ID del dataset BigQuery para tablas de control."
  type        = string
  default     = "factory_etl_control"
}

variable "control_dataset_location" {
  description = "Ubicacion del dataset BQ. US multi-region para queries cross-region baratas."
  type        = string
  default     = "US"
}

variable "service_account_name" {
  description = "Nombre corto de la Service Account del runtime del ETL."
  type        = string
  default     = "factory-etl-runtime"
}

variable "secret_names" {
  description = "Secretos placeholder que crea Terraform (las versiones se cargan manual)."
  type        = list(string)
  default     = ["factory-api-key", "factory-api-user"]
}

# --- Workload Identity Federation ---------------------------------------------

variable "wif_enabled" {
  description = "Si true, crea el pool WIF y binding para GitHub Actions."
  type        = bool
  default     = true
}

variable "github_owner" {
  description = "Org/usuario duenio del repo (ej. 'mi-org')."
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "Nombre del repositorio (ej. 'bd-sort')."
  type        = string
  default     = ""
}

variable "github_allowed_refs" {
  description = "Refs permitidas para asumir la SA (ej. ['refs/heads/main'])."
  type        = list(string)
  default     = ["refs/heads/main"]
}

# --- Retention ----------------------------------------------------------------

variable "bronze_retention_days" {
  description = "Dias antes de que Bronze pase a Nearline/Coldline. 0 = sin lifecycle."
  type        = number
  default     = 90
}

variable "enable_object_versioning" {
  description = "Si true, activa versioning en ambos buckets. Recomendado en prod."
  type        = bool
  default     = true
}
