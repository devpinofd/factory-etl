# Terraform — Infraestructura FactoryETL en GCP

## Objetivo

Provisionar de manera reproducible, versionada y revisable en PR los recursos GCP que necesita el ETL de FactorySoft:

- Buckets GCS: **bronze** y **quarantine**.
- Dataset BigQuery con tablas de control (`etl_runs`, `etl_batches`, `etl_events`, `data_quality_results`).
- Secret Manager: `factory-api-key`, `factory-api-user`.
- Service Account del ETL con permisos mínimos.
- Workload Identity Federation (WIF) para que GitHub Actions asuma la SA sin claves JSON.

Este código Terraform es la **fuente autoritativa** de la infraestructura descrita en `PLAN_IMPLEMENTACION_FASE_1.md` §2 (Etapa 0) y §4.

## Regla obligatoria de despliegue

- Los **Cloud Workflows**, sus schedulers, permisos y recursos asociados se
  despliegan exclusivamente con Terraform.
- Las transformaciones **Dataform** se versionan en `dataform/` y se
  despliegan/invocan mediante la configuración administrada por Terraform.
- No se permiten despliegues manuales con `gcloud workflows deploy`, llamadas
  directas para crear revisiones de Dataform ni scripts de despliegue fuera de
  Terraform como fuente operativa.
- Antes de aplicar, se debe ejecutar `terraform plan` con el archivo de
  variables del ambiente y revisar cualquier `destroy` o reemplazo.
- La ejecución real de Dataform debe ocurrir desde el Workflow de consolidación
  administrado por Terraform; `dataform compile` y `dataform run --dry-run`
  quedan como validaciones locales.

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

## Inventario de acceso SORT

Reconciliacion Git del 2026-10-26: el codigo incluye el acceso endurecido
y las exportaciones comprobados por metadatos, sin aplicar infraestructura.
Los valores `false` del ejemplo no describen prod: preservar los valores
habilitados existentes y revisar planes selectivos antes de cualquier apply.
Los dos gestores Gold ya fueron adoptados a `dataset_access`; `removed`
con `destroy=false` no importa ACL ni autoriza recrearlas.
No se incluye la bandera local para activar modelos Mondelez recurrentes:
la consolidacion observada compila main sin esa bandera. El workflow diario
si incluye `clientes_v1`, como la configuracion productiva consultada.
Ver [procedencia y exclusiones](../docs/handoff-sort-mondelez.md).

`sort_access_audit.tf` permite habilitar exclusivamente Organization Policy
en `factory-etl-prod`, con `enable_sort_access_audit_api = true`.
El valor predeterminado es `false`. No habilita Directory, concede IAM,
crea usuarios ni modifica vistas. Retirar el recurso no deshabilita la API.

Para este cambio acotado, usar un directorio `TF_DATA_DIR` aislado, verificar
el backend prod y revisar un plan guardado con el unico target
`google_project_service.sort_access_org_policy[0]`. Nunca aplicar el plan
general del worktree compartido. La habilitacion de una API no concede
los scopes OAuth ni los privilegios administrativos del directorio.

Ver el [inventario de acceso](../docs/propuesta-acceso-bigquery-sorti-mondelez.md)
para el resultado productivo y las verificaciones pendientes del consumidor.

## Acceso minimo del consumidor SORT

`sort_consumer_access.tf` administra exclusivamente cuatro autorizaciones
de vistas en Gold, cuatro grants `dataViewer` por vista y el rol personalizado
`sortQueryRunner` en `factory-etl-prod` para `magdalena.mateu@tinitot.com`.
El rol conserva `bigquery.jobs.create`, `bigquery.config.get`,
`resourcemanager.projects.get`; excluye
creacion Dataform y permisos de IA del `jobUser` predefinido actual.
Nunca otorga lectura
al dataset completo. `enable_sort_consumer_access` sigue `false` por
defecto y en el ejemplo; la configuracion local productiva usa `true`.
No reaplicar los defaults sobre prod sin revisar el plan.

Requisitos ya ejecutados el 2026-10-24: consultas publicas autonomas
desplegadas por Dataform y dos gestores Gold adoptados a `dataset_access`
preservando ACL. No combinar gestores `dataset_iam_member` con autorizaciones
en Gold ni volver al codigo previo a la adopcion. Los bloques `removed`
usan `destroy=false`; no equivalen a una importacion automatica.

La ejecucion autorizada uso un plan guardado con solo estos targets:
`google_bigquery_dataset_access.sort_public_views_gold_authorized`,
`google_bigquery_table_iam_member.sort_consumer_viewer` y
`google_project_iam_member.sort_consumer_job_user`. Nueve altas, cero cambios
o bajas. Verificacion posterior incluye tambien
`module.service_account.google_bigquery_dataset_access.gold_editor`:
cero cambios. No usar un apply general del worktree compartido.

Correccion aplicada y verificada tras auditoria del 2026-10-24:
el bloque `moved` conserva la direccion del grant existente y
`create_before_destroy` concede el rol personalizado antes de retirar
exclusivamente el miembro Magdalena de `roles/bigquery.jobUser`.
Los demas miembros de ese rol se preservan. El plan selectivo de esta
migracion debe incluir `google_project_iam_custom_role.sort_consumer_query_runner`,
`google_project_iam_member.sort_consumer_query_runner` y su direccion
anterior `google_project_iam_member.sort_consumer_job_user`.
Las cuatro vistas y sus autorizaciones Gold deben permanecer sin cambios.

La auditoria tambien confirmo seis grants directos `dataform.admin` en
repositorios UUID. Su retirada se ejecuto con un estado LOCAL aislado y el
proveedor `google-beta`, importando solo cada
`google_dataform_repository_iam_member`, con un plan destroy de exactamente
seis miembros, sin importar repositorios completos.
No escribir ese estado en GCS ni borrar repositorios, usar bindings
autoritativos o retirar permisos de terceros. Ambos planes requieren
aprobacion especifica antes de apply y verificacion cloud posterior.
Ambas se realizaron: dos altas/una baja para el rol, seis bajas de miembros
Dataform y comparacion cloud sin cambios ajenos. El rol final tiene tres
permisos: `projects.list` fue rechazado por Google y retirado antes del
segundo plan aprobado. La configuracion LOCAL temporal ahora usa `removed`
para evitar recrear grants. No reutilizar el plan destroy ya aplicado.

## Convenciones

### Resultados descargables SORT

`sort_consumer_exports.tf` administra un bucket dedicado
`factory-etl-prod-sort-magdalena-exports` en `US-CENTRAL1`, compatible con
la ubicacion del dataset SORT. Se habilita de forma independiente con
`enable_sort_consumer_exports=true`, solo en prod y con acceso SORT activo.
Plan selectivo: bucket, rol personalizado `sortExportFiles` y su miembro
IAM de bucket; exactamente tres altas, sin modificar IAM de proyecto.
No usar apply general.

El rol, asignado SOLO al bucket a Magdalena, incluye `storage.buckets.get`
y `storage.objects.create/get/list`. No incluye borrar, sobrescribir,
modificar metadatos o gestionar IAM. IAM es aditivo; otros permisos heredados
podrian ampliar el acceso y no quedan certificados por este grant.
UBLA y prevencion de acceso publico activados; `force_destroy=false` y
`prevent_destroy=true`. No se habilitan versiones ni soft delete. La regla
de ciclo de vida elimina archivos de edad >=30 dias de forma asincrona;
no es una retencion bloqueada ni una garantia de borrado exacto al minuto.
La eliminacion automatica del servicio no concede borrado al usuario.
Se facturan almacenamiento, operaciones y posibles descargas.

La documentacion de exportacion BigQuery solicita create y delete; el
usuario eligio mantener SIN delete y validar `EXPORT DATA` con nombres
nuevos y `overwrite=false` desde su login normal. Desplegado el 2026-10-25:
tres altas y plan posterior sin cambios; prod.tfvars local conserva true.
La prueba SELECT 1 de Magdalena exporto una fila/un archivo sin error,
con maximo 2 GiB, sin conceder delete. No generalizar a otros flujos.
Listado consumidor confirmado; descarga final al equipo no certificada
por limitacion del navegador integrado.
No ampliar permisos automaticamente si falla. No se necesita conexion
BigQuery ni cuenta de servicio nueva para exportar a Cloud Storage.

Para Guardar resultados > Cloud Storage > Explorar se agrego, bajo
aprobacion expresa, el rol `sortExportBucketPicker` a nivel de proyecto:
SOLO `storage.buckets.list`. Los permisos objects.* siguen asignados
unicamente en el bucket dedicado mediante sortExportFiles; nunca asignar
ese rol de archivos al proyecto. Enumerar revela los buckets del proyecto,
no autoriza leer o escribir sus objetos. Esta correccion uso exactamente
dos altas y plan posterior cero cambios. Ocho pruebas aprobadas.
Prueba normal del consumidor: selector y exportacion por boton correctos,
job bquxjob_3cd79bd_1a173e40f41 DONE sin error, CSV confirmado en su bucket.
Para despliegues selectivos de este ajuste usar solo los targets
`google_project_iam_custom_role.sort_consumer_bucket_picker` y
`google_project_iam_member.sort_consumer_bucket_picker`, comprobando backend
GCS bucket factory-etl-prod-tfstate, prefix prod antes del plan.

- **Ningún secreto en Terraform**: `google_secret_manager_secret_version` NO se crea desde IaC. Terraform provisiona el `secret` (contenedor); las versiones se cargan manualmente con `gcloud secrets versions add` y quedan fuera del repo.
- **Buckets**: `uniform_bucket_level_access = true`, `public_access_prevention = enforced`, versioning habilitado, retention lock en `prod`.
- **BigQuery**: dataset con `default_table_expiration_ms = null` para las tablas de control (no expiran).
- **WIF**: el pool solo confía en el repo `<org>/<repo>` y la rama `main` (más `pull_request` para dry-runs). Configurable en `variables.tf`.

## Ver también

- `PLAN_IMPLEMENTACION_FASE_1.md` §2 Etapa 0 (matriz de recursos GCP)
- `SEGURIDAD.md` (política de secretos)
