# ==============================================================================
# Tablas de Gobernanza RLS: Matriz de Acceso de Proveedores Externos
# ==============================================================================

variable "security_dataset_id" {
  type        = string
  description = "ID del dataset BigQuery para tablas de seguridad y gobernanza RLS."
  default     = "factory_etl_security"
}

# --- Dataset factory_etl_security ---------------------------------------------

resource "google_bigquery_dataset" "security" {
  project       = var.project_id
  dataset_id    = var.security_dataset_id
  location      = var.dataset_location
  friendly_name = "FactoryETL Security & Governance"
  description   = "Dataset para tablas de seguridad, matriz de acceso de proveedores externos (RLS) y logs de auditoria."
  labels        = var.labels
}

# --- Tabla sec_acceso_proveedores (SCD Type 2) --------------------------------

resource "google_bigquery_table" "sec_acceso_proveedores" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.security.dataset_id
  table_id            = "sec_acceso_proveedores"
  description         = "Matriz centralizada de acceso de proveedores externos al ecosistema de datos. Patron SCD Type 2 con audit trail."
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "effective_from"
  }

  clustering = ["user_email", "provider_id", "is_current"]

  schema = <<EOF
[
  {"name": "access_id",       "type": "STRING",    "mode": "REQUIRED", "description": "UUID v4 universal"},
  {"name": "access_hash",     "type": "INT64",     "mode": "NULLABLE", "description": "FARM_FINGERPRINT para lookups SQL"},
  {"name": "user_email",      "type": "STRING",    "mode": "REQUIRED", "description": "Email normalizado a lowercase"},
  {"name": "provider_id",     "type": "STRING",    "mode": "REQUIRED", "description": "cod_pro autorizado"},
  {"name": "source_empresa",  "type": "STRING",    "mode": "REQUIRED", "description": "Empresa: tinito, ctb, o *"},
  {"name": "cod_suc",         "type": "STRING",    "mode": "REQUIRED", "description": "Sucursal: 01, 03, o *"},
  {"name": "role_type",       "type": "STRING",    "mode": "REQUIRED", "description": "EDC, KAM, DIRECTOR_CANAL"},
  {"name": "access_level",    "type": "STRING",    "mode": "REQUIRED", "description": "VENTAS_VOLUMEN, FINANCIERO, FULL"},
  {"name": "platform_scope",  "type": "STRING",    "mode": "REQUIRED", "description": "ALL, PBI, LOOKER, SUPERSET"},
  {"name": "access_status",   "type": "STRING",    "mode": "REQUIRED", "description": "ACTIVE, REVOKED, SUSPENDED"},
  {"name": "effective_from",  "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Inicio de vigencia"},
  {"name": "effective_to",    "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Fin de vigencia"},
  {"name": "is_current",      "type": "BOOL",      "mode": "REQUIRED", "description": "Flag registro vigente"},
  {"name": "granted_by",      "type": "STRING",    "mode": "NULLABLE", "description": "Admin que otorgo el acceso"},
  {"name": "revoked_by",      "type": "STRING",    "mode": "NULLABLE", "description": "Admin que revoco"},
  {"name": "change_reason",   "type": "STRING",    "mode": "NULLABLE", "description": "Motivo del cambio"},
  {"name": "created_at",      "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "updated_at",      "type": "TIMESTAMP", "mode": "REQUIRED"}
]
EOF

  labels = merge(var.labels, {
    data_classification = "confidential"
    domain              = "security"
  })
}

# --- Tabla sec_audit_log (Log Inmutable) --------------------------------------

resource "google_bigquery_table" "sec_audit_log" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.security.dataset_id
  table_id            = "sec_audit_log"
  description         = "Log inmutable de auditoria de accesos."
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "performed_at"
  }

  clustering = ["access_id", "action"]

  schema = <<EOF
[
  {"name": "audit_id",      "type": "STRING",    "mode": "REQUIRED"},
  {"name": "access_id",     "type": "STRING",    "mode": "REQUIRED"},
  {"name": "action",        "type": "STRING",    "mode": "REQUIRED"},
  {"name": "field_changed", "type": "STRING",    "mode": "NULLABLE"},
  {"name": "old_value",     "type": "STRING",    "mode": "NULLABLE"},
  {"name": "new_value",     "type": "STRING",    "mode": "NULLABLE"},
  {"name": "performed_by",  "type": "STRING",    "mode": "REQUIRED"},
  {"name": "performed_at",  "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "source_system", "type": "STRING",    "mode": "NULLABLE"}
]
EOF

  labels = merge(var.labels, {
    data_classification = "audit"
    domain              = "security"
  })
}

# --- Tabla sec_vendedores_auth (SCD Type 2 / Fuerza de Ventas) -----------------

resource "google_bigquery_table" "sec_vendedores_auth" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.security.dataset_id
  table_id            = "sec_vendedores_auth"
  description         = "Matriz de acceso y asignaciones RLS de la fuerza de ventas y supervisores. Sincronizada desde Firebase Auth y Firestore."
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "effective_from"
  }

  clustering = ["user_email", "source_empresa", "cod_suc"]

  schema = <<EOF
[
  {"name": "access_id",       "type": "STRING",    "mode": "REQUIRED", "description": "UUID v4 universal"},
  {"name": "access_hash",     "type": "INT64",     "mode": "NULLABLE", "description": "FARM_FINGERPRINT para lookups SQL"},
  {"name": "user_email",      "type": "STRING",    "mode": "REQUIRED", "description": "Email del vendedor normalizado a lowercase"},
  {"name": "source_empresa",  "type": "STRING",    "mode": "REQUIRED", "description": "Empresa: tinito, ctb, daroan, ctm, roldan, o *"},
  {"name": "cod_suc",         "type": "STRING",    "mode": "REQUIRED", "description": "Sucursal: 01, 02, 03, 04, 05, 06, 07, o *"},
  {"name": "cod_ven",         "type": "STRING",    "mode": "REQUIRED", "description": "Codigo del vendedor en esa empresa (ej: E004, B002, o *)"},
  {"name": "nom_ven",         "type": "STRING",    "mode": "NULLABLE", "description": "Nombre completo del vendedor en ERP"},
  {"name": "role_type",       "type": "STRING",    "mode": "REQUIRED", "description": "VENDEDOR, SUPERVISOR, GERENTE_VENTAS, ADMIN"},
  {"name": "access_level",    "type": "STRING",    "mode": "REQUIRED", "description": "VENTAS_OPERATIVAS, FULL"},
  {"name": "platform_scope",  "type": "STRING",    "mode": "REQUIRED", "description": "ALL, PBI, FIREBASE, LOOKER"},
  {"name": "access_status",   "type": "STRING",    "mode": "REQUIRED", "description": "ACTIVE, REVOKED, SUSPENDED"},
  {"name": "effective_from",  "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Inicio de vigencia"},
  {"name": "effective_to",    "type": "TIMESTAMP", "mode": "REQUIRED", "description": "Fin de vigencia"},
  {"name": "is_current",      "type": "BOOL",      "mode": "REQUIRED", "description": "Flag registro vigente"},
  {"name": "firestore_email", "type": "STRING",    "mode": "NULLABLE", "description": "Email canonico en Firestore"},
  {"name": "granted_by",      "type": "STRING",    "mode": "NULLABLE", "description": "Origen o Admin que otorgo el acceso"},
  {"name": "revoked_by",      "type": "STRING",    "mode": "NULLABLE", "description": "Admin que revoco"},
  {"name": "change_reason",   "type": "STRING",    "mode": "NULLABLE", "description": "Motivo del cambio o sync"},
  {"name": "created_at",      "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "updated_at",      "type": "TIMESTAMP", "mode": "REQUIRED"}
]
EOF

  labels = merge(var.labels, {
    data_classification = "confidential"
    domain              = "security"
  })
}

