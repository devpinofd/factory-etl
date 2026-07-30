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
}

# --- Tabla etl_runs -----------------------------------------------------------

resource "google_bigquery_table" "etl_runs" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.control.dataset_id
  table_id            = "etl_runs"
  description         = "Registro de corridas completas del ETL."
  deletion_protection = false

  schema = <<EOF
[
  {"name": "run_id",     "type": "STRING",    "mode": "REQUIRED"},
  {"name": "status",     "type": "STRING",    "mode": "REQUIRED"},
  {"name": "started_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "ended_at",   "type": "TIMESTAMP", "mode": "NULLABLE"},
  {"name": "error",      "type": "STRING",    "mode": "NULLABLE"},
  {"name": "extras",     "type": "STRING",    "mode": "NULLABLE"}
]
EOF

  labels = var.labels
}

# --- Tabla etl_batches --------------------------------------------------------

resource "google_bigquery_table" "etl_batches" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.control.dataset_id
  table_id            = "etl_batches"
  description         = "Registro de lotes procesados por entidad y empresa."
  deletion_protection = false

  schema = <<EOF
[
  {"name": "batch_id",       "type": "STRING",    "mode": "REQUIRED"},
  {"name": "run_id",         "type": "STRING",    "mode": "REQUIRED"},
  {"name": "entity",         "type": "STRING",    "mode": "REQUIRED"},
  {"name": "source_empresa", "type": "STRING",    "mode": "REQUIRED"},
  {"name": "dt",             "type": "STRING",    "mode": "REQUIRED"},
  {"name": "status",         "type": "STRING",    "mode": "REQUIRED"},
  {"name": "record_count",   "type": "INTEGER",   "mode": "NULLABLE"},
  {"name": "object_uri",     "type": "STRING",    "mode": "NULLABLE"},
  {"name": "payload_hash",   "type": "STRING",    "mode": "NULLABLE"},
  {"name": "inserted_at",   "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF

  labels = var.labels
}

# --- Tabla etl_events ---------------------------------------------------------

resource "google_bigquery_table" "etl_events" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.control.dataset_id
  table_id            = "etl_events"
  description         = "Eventos de auditoria y monitoreo de fases."
  deletion_protection = false

  schema = <<EOF
[
  {"name": "event_id",    "type": "STRING",    "mode": "REQUIRED"},
  {"name": "run_id",      "type": "STRING",    "mode": "REQUIRED"},
  {"name": "batch_id",    "type": "STRING",    "mode": "NULLABLE"},
  {"name": "entity",      "type": "STRING",    "mode": "NULLABLE"},
  {"name": "phase",       "type": "STRING",    "mode": "NULLABLE"},
  {"name": "event_type",  "type": "STRING",    "mode": "REQUIRED"},
  {"name": "duration_ms", "type": "INTEGER",   "mode": "NULLABLE"},
  {"name": "extras",      "type": "STRING",    "mode": "NULLABLE"},
  {"name": "inserted_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF

  labels = var.labels
}

# --- Tabla data_quality_results -----------------------------------------------

resource "google_bigquery_table" "data_quality_results" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.control.dataset_id
  table_id            = "data_quality_results"
  description         = "Resultados de pruebas de calidad de datos."
  deletion_protection = false

  schema = <<EOF
[
  {"name": "check_id",    "type": "STRING",    "mode": "REQUIRED"},
  {"name": "run_id",      "type": "STRING",    "mode": "REQUIRED"},
  {"name": "batch_id",    "type": "STRING",    "mode": "NULLABLE"},
  {"name": "entity",      "type": "STRING",    "mode": "NULLABLE"},
  {"name": "check_name",  "type": "STRING",    "mode": "REQUIRED"},
  {"name": "status",      "type": "STRING",    "mode": "REQUIRED"},
  {"name": "details",     "type": "STRING",    "mode": "NULLABLE"},
  {"name": "inserted_at", "type": "TIMESTAMP", "mode": "NULLABLE"}
]
EOF

  labels = var.labels
}

output "dataset_id" {
  value = google_bigquery_dataset.control.dataset_id
}

output "dataset_project" {
  value = google_bigquery_dataset.control.project
}
