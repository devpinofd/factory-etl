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

variable "bucket_name" {
  type        = string
  description = "Nombre del bucket Bronze inyectado como FACTORY_ETL_BRONZE_BUCKET en el Cloud Run Job"
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

variable "queries" {
  description = "Lista de query_ids a ejecutar por el workflow, con has_param indicando si se inyectan --parameter fec_des/fec_has."
  type = list(object({
    id        = string
    has_param = bool
  }))
}

variable "consolidation_workflow_name" {
  description = "Workflow SCD2 de consolidación invocado al finalizar una ingesta."
  type        = string
  default     = ""
}

variable "enable_scd2" {
  description = "Activa acciones Dataform SCD2 durante la consolidación."
  type        = bool
  default     = true
}

# --- Consolidacion Medallion automatizada (opcional por instancia del modulo) --

variable "enable_medallion_consolidation" {
  description = "Si true, luego de la extraccion a Bronze el workflow ademas corre BigQuery load jobs (staging nativo) y una invocacion de Dataform (Silver/Gold)."
  type        = bool
  default     = false
}

variable "consolidation_only" {
  description = "Si true, omite la ingesta y ejecuta solamente Bronze -> staging -> Dataform Silver/Gold."
  type        = bool
  default     = false
}

variable "bronze_stg_dataset_id" {
  description = "Dataset de staging donde se cargan (load jobs) las tablas nativas desde Bronze. Solo se usa si enable_medallion_consolidation=true."
  type        = string
  default     = ""
}

variable "dataform_repository_id" {
  description = "ID del repositorio Dataform a compilar/invocar. Solo se usa si enable_medallion_consolidation=true."
  type        = string
  default     = ""
}

variable "dataform_location" {
  description = "Region del repositorio Dataform. Solo se usa si enable_medallion_consolidation=true."
  type        = string
  default     = ""
}

variable "staging_schemas_json" {
  description = "JSON con el mapa entity_name -> [{name,type,mode}] (tipos exactos, sin autodetect) usado por los load jobs de staging. Solo se usa si enable_medallion_consolidation=true."
  type        = string
  default     = "{}"
}

variable "quarantine_bucket_name" {
  description = "Bucket de cuarentena. Si un load job de staging detecta columnas fuera del esquema, los objetos Bronze de esa entidad se copian aqui y se registra un evento. Solo se usa si enable_medallion_consolidation=true."
  type        = string
  default     = ""
}

variable "silver_dataset_id" {
  description = "Dataset Silver que recibe la consolidacion de Dataform."
  type        = string
  default     = ""
}

variable "gold_dataset_id" {
  description = "Dataset Gold que recibe la consolidacion de Dataform."
  type        = string
  default     = ""
}

variable "security_dataset_id" {
  description = "Dataset de seguridad usado por Dataform."
  type        = string
  default     = ""
}
