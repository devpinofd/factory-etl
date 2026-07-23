# Backend GCS para el remote state.
#
# El nombre del bucket se pasa con `-backend-config="bucket=<name>"` durante
# `terraform init`. El `prefix` separa environments (dev, stage, prod).
#
# Requisitos previos: el bucket debe existir y tener versioning habilitado.
# Ver README.md seccion "Bootstrap del state remoto".

terraform {
  backend "gcs" {
    # bucket = "<factory-etl-XXXXXX-tfstate>"    # via -backend-config
    # prefix = "dev"                             # via -backend-config
  }
}
