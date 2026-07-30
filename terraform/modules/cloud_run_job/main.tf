resource "google_cloud_run_v2_job" "job" {
  name     = var.job_name
  location = var.region
  project  = var.project_id

  template {
    labels = var.labels

    template {
      service_account = var.service_account_email
      timeout         = "${var.timeout_seconds}s"
      max_retries     = var.max_retries

      containers {
        image = var.image_uri

        args = [
          "run-batch",
          "--query-id", var.query_id,
          "--source-empresa", var.source_empresa,
          "--dt", "TODAY"
        ]

        resources {
          limits = {
            cpu    = var.cpu_limit
            memory = var.memory_limit
          }
        }

        env {
          name  = "FACTORY_ETL_ENV"
          value = var.environment
        }

        env {
          name  = "FACTORY_ETL_GCP_PROJECT"
          value = var.project_id
        }

        env {
          name  = "FACTORY_ETL_BRONZE_BUCKET"
          value = var.bronze_bucket_name
        }

        env {
          name  = "FACTORY_ETL_QUARANTINE_BUCKET"
          value = var.quarantine_bucket_name
        }

        env {
          name  = "FACTORY_ETL_CONTROL_DATASET"
          value = var.control_dataset_id
        }

        env {
          name  = "FACTORY_ETL_GCP_REGION"
          value = var.region
        }
      }
    }
  }
}
