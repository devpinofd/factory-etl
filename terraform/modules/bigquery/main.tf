variable "project_id" { type = string }
variable "dataset_id" { type = string }
variable "dataset_location" { type = string }
variable "labels" { type = map(string) }

resource "google_bigquery_dataset" "control" {
  project       = var.project_id
  dataset_id    = var.dataset_id
  location      = var.dataset_location
  friendly_name = "FactoryETL control"
  description   = "Tablas de control: etl_runs, etl_batches, etl_events, data_quality_results."
  labels        = var.labels

  # Sin default_table_expiration: las tablas de control no expiran.
}

# --- Tablas de control --------------------------------------------------------
# Las definiciones formales de schema viven en factory_etl (esta module solo
# crea el contenedor; en Fase 1 Etapa 4 se agregan google_bigquery_table).

output "dataset_id" {
  value = google_bigquery_dataset.control.dataset_id
}

output "dataset_project" {
  value = google_bigquery_dataset.control.project
}
