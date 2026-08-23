# Suite de pruebas nativas de Terraform para validación de contratos de infraestructura

run "validate_production_contracts" {
  command = plan

  variables {
    project_id   = "factory-etl-prod"
    region       = "us-central1"
    environment  = "prod"
    
    bronze_bucket_name     = "factory-etl-prod-bronze"
    quarantine_bucket_name = "factory-etl-prod-quarantine"
    control_dataset_id     = "factory_etl_control"
    control_dataset_location = "us-central1"
    service_account_name   = "factory-etl-runtime"
    artifact_repo_id       = "factory-etl-repo"
    container_image_tag    = "v1.1.0"
    container_image_name   = "factory-etl-extractor"
    
    daily_queries = [
      { id = "ventas_diarias_v3", has_param = true },
      { id = "renglones_monedas_v1", has_param = true },
      { id = "renglones_aprecios_v1", has_param = true },
      { id = "renglones_almacenes_v1", has_param = false },
    ]
  }

  # Aserción: El workflow diario en producción DEBE usar ventas_diarias_v3
  assert {
    condition     = contains([for q in local.effective_daily_queries : q.id], "ventas_diarias_v3")
    error_message = "ERROR DE CONTRATO: En producción, effective_daily_queries debe incluir ventas_diarias_v3."
  }

  # Aserción: El workflow diario en producción NO DEBE usar versiones obsoletas v1 o v2
  assert {
    condition     = !contains([for q in local.effective_daily_queries : q.id], "ventas_diarias_v1") && !contains([for q in local.effective_daily_queries : q.id], "ventas_diarias_v2")
    error_message = "ERROR DE CONTRATO: Se detectaron versiones obsoletas de ventas_diarias en daily_queries."
  }

  # Aserción: La imagen del extractor en producción debe ser v1.1.0 (que soporta v3)
  assert {
    condition     = var.container_image_tag == "v1.1.0"
    error_message = "ERROR DE CONTRATO: container_image_tag en producción debe ser v1.1.0 para incluir los queries v3."
  }
}
