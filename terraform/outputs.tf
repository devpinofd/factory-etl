output "bronze_bucket_name" {
  description = "Nombre del bucket GCS Bronze."
  value       = module.storage.bronze_bucket_name
}

output "quarantine_bucket_name" {
  description = "Nombre del bucket GCS de cuarentena."
  value       = module.storage.quarantine_bucket_name
}

output "control_dataset_id" {
  description = "ID del dataset BQ de control."
  value       = module.bigquery.dataset_id
}

output "service_account_email" {
  description = "Email de la SA runtime del ETL."
  value       = module.service_account.email
}

output "wif_provider_id" {
  description = "Full resource name del WIF provider para usar en GitHub Actions."
  value       = try(module.wif[0].provider_id, null)
}

output "wif_service_account_email" {
  description = "SA que GitHub Actions puede asumir via WIF."
  value       = try(module.wif[0].service_account_email, null)
}
