variable "enable_sort_consumer_access" {
  description = "Habilita el acceso humano minimo de Magdalena a las cuatro vistas SORT, tras validar SQL y ACL Gold."
  type        = bool
  default     = false
}

locals {
  sort_public_views = toset([
    "vw_mondelez_clientes",
    "vw_mondelez_ventas",
    "vw_mondelez_articulos",
    "vw_mondelez_existencias",
  ])
  sort_consumer_member = "user:magdalena.mateu@tinitot.com"
}

resource "google_bigquery_dataset_access" "sort_public_views_gold_authorized" {
  for_each   = var.enable_sort_consumer_access ? local.sort_public_views : toset([])
  project    = var.project_id
  dataset_id = var.gold_dataset_id

  view {
    project_id = var.project_id
    dataset_id = "sort"
    table_id   = each.value
  }

  depends_on = [
    google_bigquery_dataset_access.powerbi_group_gold_reader,
  ]

  lifecycle {
    precondition {
      condition     = var.project_id == "factory-etl-prod" && var.environment == "prod" && var.enable_sort_dataset && var.gold_dataset_id == "factory_etl_gold"
      error_message = "El acceso del consumidor solo esta autorizado para SORT y Gold productivos."
    }
  }
}

resource "google_bigquery_table_iam_member" "sort_consumer_viewer" {
  for_each   = var.enable_sort_consumer_access ? local.sort_public_views : toset([])
  project    = var.project_id
  dataset_id = "sort"
  table_id   = each.value
  role       = "roles/bigquery.dataViewer"
  member     = local.sort_consumer_member

  depends_on = [google_bigquery_dataset_access.sort_public_views_gold_authorized]
}

resource "google_project_iam_member" "sort_consumer_job_user" {
  count   = var.enable_sort_consumer_access ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = local.sort_consumer_member

  depends_on = [google_bigquery_dataset_access.sort_public_views_gold_authorized]
}
