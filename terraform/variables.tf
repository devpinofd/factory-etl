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

variable "additional_control_dataset_id" {
  description = "Dataset de control adicional usado por workflows históricos del entorno."
  type        = string
  default     = ""
}

variable "control_dataset_location" {
  description = "Ubicacion del dataset BQ. US multi-region para queries cross-region baratas."
  type        = string
  default     = "us-central1"
}

variable "partition_control_tables" {
  description = "Si true, particiona por dia (inserted_at) y clusteriza las tablas etl_batches/etl_events. Debe coincidir con el estado real del dataset (la particion es inmutable)."
  type        = bool
  default     = false
}

variable "artifact_repo_id" {
  description = "ID del repositorio Artifact Registry Docker. Prod usa un nombre distinto al de dev (creado fuera de Terraform)."
  type        = string
  default     = "factory-etl-repo"
}

variable "service_account_name" {
  description = "Nombre corto de la Service Account del runtime del ETL."
  type        = string
  default     = "factory-etl-runtime"
}

variable "secret_names" {
  description = "Secretos placeholder que crea Terraform (las versiones se cargan manual)."
  type        = list(string)
  default     = ["factory-api-key", "factory-api-user", "dataform-github-token"]
}

# --- Medallion (Staging/Silver/Gold) automatizado -----------------------------

variable "bronze_stg_dataset_id" {
  description = "Dataset BigQuery donde el workflow full carga (load jobs) las tablas nativas de staging desde Bronze."
  type        = string
  default     = "factory_etl_bronze_stg"
}

variable "silver_dataset_id" {
  description = "Dataset BigQuery donde Dataform construye las tablas Silver."
  type        = string
  default     = "factory_etl_silver"
}

variable "gold_dataset_id" {
  description = "Dataset BigQuery donde Dataform construye las tablas Gold."
  type        = string
  default     = "factory_etl_gold"
}

variable "dataform_git_remote_url" {
  description = "URL del repo Git que respalda el Dataform repository (debe existir el secreto dataform-github-token con un PAT valido)."
  type        = string
  default     = "https://github.com/devpinofd/factory-etl.git"
}

variable "dataform_default_branch" {
  description = "Branch por defecto que Dataform compila."
  type        = string
  default     = "main"
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

variable "powerbi_reader_emails" {
  description = "Cuentas de Power BI con lectura sobre el dataset Gold."
  type        = set(string)
  default     = []
}

variable "powerbi_group_email" {
  description = "Grupo de Google Workspace que centraliza el acceso Power BI."
  type        = string
  default     = "bi-analistas@tinitot.com"
}

variable "enable_object_versioning" {
  description = "Si true, activa versioning en ambos buckets. Recomendado en prod."
  type        = bool
  default     = true
}

# --- Cloud Scheduler & Compute ------------------------------------------------

variable "cron_schedule" {
  description = "Expresion cron del WF transaccional nocturno (11:30 PM)."
  type        = string
  default     = "30 23 * * *" # 11:30 PM diario
}

variable "cron_schedule_full" {
  description = "Expresion cron del WF full (4:30 PM)."
  type        = string
  default     = "30 16 * * *" # 04:30 PM diario
}

variable "cron_schedule_consolidation" {
  description = "Expresion cron del WF de consolidacion Bronze a Silver/Gold."
  type        = string
  default     = "30 0 * * *" # 12:30 AM diario, despues de la ingesta full
}

variable "time_zone" {
  description = "Zona horaria de ambos schedulers."
  type        = string
  default     = "America/Caracas"
}

variable "container_image_tag" {
  description = "Tag de la imagen Docker en Artifact Registry."
  type        = string
  default     = "latest"
}

variable "container_image_name" {
  description = "Nombre de la imagen Docker en Artifact Registry. Prod usa un nombre distinto (creado fuera de Terraform)."
  type        = string
  default     = "factory-etl"
}

variable "articulos_cpu_limit" {
  description = "Limite de CPU del Cloud Run Job de articulos. Debe coincidir con el valor real desplegado (cambiarlo fuerza una nueva revision)."
  type        = string
  default     = "2000m"
}

variable "articulos_memory_limit" {
  description = "Limite de memoria del Cloud Run Job de articulos. Debe coincidir con el valor real desplegado."
  type        = string
  default     = "1024Mi"
}

variable "articulos_timeout_seconds" {
  description = "Timeout del Cloud Run Job de articulos, en segundos."
  type        = number
  default     = 600
}

variable "articulos_max_retries" {
  description = "Reintentos maximos del Cloud Run Job de articulos."
  type        = number
  default     = 3
}

variable "daily_queries" {
  description = "Lista de query_ids ejecutados por el Cloud Workflow diario, con has_param indicando si se le inyectan --parameter fec_des/fec_has."
  type = list(object({
    id        = string
    has_param = bool
  }))
  default = [
    { id = "renglones_almacenes_v1", has_param = false },
    { id = "ventas_diarias_v2", has_param = true },
    { id = "renglones_monedas_v1", has_param = true },
    { id = "renglones_aprecios_v1", has_param = true },
  ]
}

variable "daily_queries_full" {
  description = "Lista de query_ids del WF full (transaccionales + maestras), corre a las 11:30 PM."
  type = list(object({
    id        = string
    has_param = bool
  }))
  default = [
    { id = "renglones_almacenes_v1", has_param = false },
    { id = "ventas_diarias_v2", has_param = true },
    { id = "renglones_monedas_v1", has_param = true },
    { id = "renglones_aprecios_v1", has_param = true },
    { id = "articulos_v1", has_param = false },
    { id = "impuestos_v1", has_param = false },
    { id = "departamentos_v1", has_param = false },
    { id = "marcas_v1", has_param = false },
    { id = "secciones_v1", has_param = false },
    { id = "proveedores_v1", has_param = false },
    { id = "paises_v1", has_param = false },
    { id = "estados_v1", has_param = false },
    { id = "ciudades_v1", has_param = false },
    { id = "vendedores_v1", has_param = false },
    { id = "sucursales_v1", has_param = false },
    { id = "almacenes_v1", has_param = false },
    { id = "clientes_v1", has_param = false },
    { id = "clases_clientes_v1", has_param = false },
    { id = "conceptos_v1", has_param = false },
  ]
}
