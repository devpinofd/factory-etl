# Terraform — Infraestructura FactoryETL en GCP

## Objetivo

Provisionar de manera reproducible, versionada y revisable en PR los recursos GCP que necesita el ETL de FactorySoft:

- Buckets GCS: **bronze** y **quarantine**.
- Dataset BigQuery con tablas de control (`etl_runs`, `etl_batches`, `etl_events`, `data_quality_results`).
- Secret Manager: `factory-api-key`, `factory-api-user`.
- Service Account del ETL con permisos mínimos.
- Workload Identity Federation (WIF) para que GitHub Actions asuma la SA sin claves JSON.

Este código Terraform es la **fuente autoritativa** de la infraestructura descrita en `PLAN_IMPLEMENTACION_FASE_1.md` §2 (Etapa 0) y §4.

## Estructura

```
terraform/
├── README.md                        # este archivo
├── versions.tf                      # versiones de terraform + providers
├── backend.tf                       # backend GCS remote state
├── variables.tf                     # variables raiz
├── main.tf                          # composicion de modulos
├── outputs.tf                       # salidas utiles (bucket, dataset, sa email)
├── envs/
│   ├── dev.tfvars.example           # copiar a dev.tfvars antes de plan/apply
│   └── prod.tfvars.example
└── modules/
    ├── storage/                     # buckets bronze + quarantine
    ├── bigquery/                    # dataset + tablas de control
    ├── secrets/                     # secretos placeholder (versiones se cargan manual)
    ├── service_account/             # SA del runtime del ETL
    └── wif/                         # Workload Identity Federation para GH Actions
```

## Requisitos locales

- Terraform ≥ 1.9
- `gcloud` autenticado con una identidad que tenga `roles/owner` o combinación equivalente (`roles/resourcemanager.projectIamAdmin`, `roles/iam.serviceAccountAdmin`, `roles/storage.admin`, `roles/bigquery.admin`, `roles/secretmanager.admin`).
- Proyecto GCP ya creado (Terraform no crea el proyecto en esta iteración — se hace con `gcloud projects create` una sola vez).

## Bootstrap del state remoto (primera vez)

Antes del primer `terraform init`, crear el bucket que aloja el state:

```powershell
$PROJECT_ID = "factory-etl-dev-XXXXXX"
$STATE_BUCKET = "$PROJECT_ID-tfstate"
gcloud storage buckets create gs://$STATE_BUCKET `
    --project=$PROJECT_ID `
    --location=southamerica-east1 `
    --uniform-bucket-level-access
gcloud storage buckets update gs://$STATE_BUCKET --versioning
```

Luego editar `backend.tf` con el nombre exacto del bucket, o pasarlo con `-backend-config`:

```powershell
terraform init -backend-config="bucket=$STATE_BUCKET"
```

## Flujo por ambiente

```powershell
# dev
Copy-Item envs/dev.tfvars.example envs/dev.tfvars
# editar envs/dev.tfvars con el project_id real

terraform init -backend-config="bucket=<state-bucket>" -backend-config="prefix=dev"
terraform plan -var-file=envs/dev.tfvars -out=dev.tfplan
terraform apply dev.tfplan
```

Para producción se repite con `envs/prod.tfvars` y `-backend-config="prefix=prod"`.

## Convenciones

- **Ningún secreto en Terraform**: `google_secret_manager_secret_version` NO se crea desde IaC. Terraform provisiona el `secret` (contenedor); las versiones se cargan manualmente con `gcloud secrets versions add` y quedan fuera del repo.
- **Buckets**: `uniform_bucket_level_access = true`, `public_access_prevention = enforced`, versioning habilitado, retention lock en `prod`.
- **BigQuery**: dataset con `default_table_expiration_ms = null` para las tablas de control (no expiran).
- **WIF**: el pool solo confía en el repo `<org>/<repo>` y la rama `main` (más `pull_request` para dry-runs). Configurable en `variables.tf`.

## Ver también

- `PLAN_IMPLEMENTACION_FASE_1.md` §2 Etapa 0 (matriz de recursos GCP)
- `SEGURIDAD.md` (política de secretos)
