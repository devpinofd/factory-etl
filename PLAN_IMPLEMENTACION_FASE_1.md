# Plan de implementacion Fase 1: entorno GCP y Bronze [ESTADO: COMPLETADO Y VERIFICADO EN GCP]

**Fecha de finalización y verificación empírica:** 2026-07-29  
**Resultado:** 95 consultas (19 queries × 5 bases de datos) extraídas, validadas y persistidas en **GCS Bronze** con auditoría en **BigQuery** (`status: SUCCESS`, duración: 9.8 minutos en la ejecución `b50eec63`).

Este plan cierra la Fase 1. Cubre la preparación del proyecto GCP, empaquetado del extractor, despliegue de IaC con Terraform, orquestación paralela en Cloud Workflows y Cloud Run Jobs, y la verificación completa de la capa Bronze.

Documentos de referencia: [PROPUESTA_DATA_LAKE_GCP.md](PROPUESTA_DATA_LAKE_GCP.md), [PROPUESTA_INTEGRACION_CONCILIAPP.md](PROPUESTA_INTEGRACION_CONCILIAPP.md) y [PLAN_OPTIMIZACION_WORKFLOWS.md](PLAN_OPTIMIZACION_WORKFLOWS.md).

---

## 1. Alcance

### Decision de ingesta (aplica a todo el proyecto)

Toda la ingesta desde FactorySoft usa **exclusivamente la API generica**
`https://login.factorysoftve.com/api/generica/efactoryApiGenerica.asmx/Seleccionar`,
que recibe consultas SQL versionadas en el catalogo `factory_queries` y
devuelve JSON. La API de servicios (`/api/servicios/<empresa>/<endpoint>`)
**no se usa** en el data lake: cualquier entidad que hoy dependa de ella
(ventas, existencias) se reescribe como consulta SQL sobre la generica
antes de aterrizar en Bronze. Consecuencias:

- Un solo transporte en `factory_queries/models.py`: `GENERIC_SQL_API`.
  La enumeracion no incluye `SERVICE_ENDPOINT`.
- Una sola URL, un solo verbo (POST) y un solo esquema de payload
  (`{"lcResultado": "json2", "lcConsulta": "<SQL>"}`). Simplifica
  auditoria y pruebas.
- Todas las entidades (maestras y transaccionales) se modelan como
  archivos `.sql` en `factory_queries/masters/` y
  `factory_queries/transactions/`.
- El renderer con marcadores tipados es el unico punto autorizado para
  materializar parametros. Concatenar cadenas SQL queda prohibido incluso
  cuando el input este validado con regex.
- Ventas y existencias, hoy servidas por la API de servicios en el ETL
  heredado, se migran a consultas SQL antes de incorporarse al lake.

### En alcance (Completado y Extendido)

- [x] Creación del proyecto GCP de desarrollo y estructura inicial de producción (`factory-etl-dev-0y1dhf`).
- [x] Infraestructura como código con Terraform (backend remoto en GCS `gs://factory-etl-dev-0y1dhf-tfstate`).
- [x] Identidades, IAM, secretos, red y hardening básico.
- [x] Empaquetado del extractor Python como contenedor Docker e imagen en Artifact Registry.
- [x] Módulo `factory_queries` con **19 consultas versionadas** (15 maestras + 4 transaccionales).
- [x] Extensión de la ingesta diaria automatizada a **5 bases de datos** (`tinito`, `ctb`, `daroan`, `roldan`, `ctm`).
- [x] Orquestación paralela en **Cloud Workflows** (`factory-etl-daily-dev`) y **Cloud Run Jobs** (`factory-etl-articulos-dev` con 2 vCPU / 1 GiB RAM).
- [x] Tablas de control (`etl_runs`, `etl_batches`, `etl_events`, `data_quality_results` en BigQuery `factory_etl_control`).
- [x] Pruebas de idempotencia, seguridad y recuperación desde Bronze (240 unit tests en verde, 92.48% de cobertura).
- [x] Runbook de optimización y documentación persistida (`PLAN_OPTIMIZACION_WORKFLOWS.md`).

### Fuera de alcance de Fase 1

- Silver, Gold, Dataform, backfill histórico.
- API analítica, sitio Vue, Superset, Power BI Desktop.
- Tablas `sec_*`, Row Access Policies, RLS y policy tags.
- Actores externos y capa de partners.
- Integración con ConciliApp.

### Criterio de exito global de la fase [CUMPLIDO AL 100%]

Bronze recibe automática y diariamente el snapshot de las 19 consultas de las 5 empresas, con idempotencia demostrada, sin secretos ni datos personales en logs, y verificado mediante la ejecución `b50eec63` en GCP.

---

## 2. Prerrequisitos organizativos (Etapa 0)

- [x] **API key rotada** con FactorySoft. La nueva clave nunca sale de Secret Manager.
- [x] **Confirmación de empresas:** `tinito`, `ctb`, `daroan`, `roldan` y `ctm`.
- [x] **Empresa y Entidades Piloto:** Ampliado a 5 empresas y 19 consultas (15 maestras + 4 transaccionales).
- [x] **Región aprobada:** `us-central1` para GCS y compute; BigQuery dataset de control en `US` multi-región.
- [x] **Ubicación del repositorio:** `c:\Repos\factory-etl/` con `pyproject.toml`, `Dockerfile`, IaC Terraform y GitHub Actions.

### 2.1 Estado del aprovisionamiento GCP (dev)

Ejecutado con `factory-etl/terraform/` sobre billing account `datalake (017B50-4057ED-227050)`:

| Recurso | ID / Nombre | Estado |
|---|---|---|
| Proyecto GCP | `factory-etl-dev-0y1dhf` | [x] Creado y vinculado a billing |
| Bucket state Terraform | `gs://factory-etl-dev-0y1dhf-tfstate` | [x] Creado con versioning |
| Bucket Bronze | `gs://factory-etl-dev-0y1dhf-bronze` | [x] uniform ACL, public_access_prevention=enforced, lifecycle→NEARLINE 90d |
| Bucket Quarantine | `gs://factory-etl-dev-0y1dhf-quarantine` | [x] uniform ACL, public_access_prevention=enforced |
| Dataset BigQuery | `factory_etl_control` (US) | [x] Creado |
| Service Account runtime | `factory-etl-runtime-dev@factory-etl-dev-0y1dhf.iam.gserviceaccount.com` | [x] Creado con least privilege |
| Secret Manager: `factory-api-key` | contenedor | [x] Creado (version 1 ENABLED) |
| Secret Manager: `factory-api-user` | contenedor | [x] Creado (version 1 ENABLED) |
| Workload Identity Federation | `github-pool-dev` | [x] Activado (Pool + provider OIDC + IAM binding para `devpinofd/factory-etl`) |
| Cloud Run Job | `factory-etl-articulos-dev` | [x] Desplegado (2 vCPU / 1 GiB RAM) |
| Cloud Workflows | `factory-etl-daily-dev` | [x] Desplegado (Paralelismo plano / limit 10) |
| Cloud Scheduler | `factory-etl-daily-scheduler-dev` | [x] Desplegado (Cron `0 19 * * *`) |
| Repositorio GitHub | `devpinofd/factory-etl` | [x] Creado y sincronizado | |

---

## 3. Etapas

Se numeran, no se datan. Cada etapa cierra con criterios de salida
verificables antes de habilitar la siguiente.

### Etapa 1. Preparacion del entorno GCP

**Objetivo:** proyecto GCP navegable, seguro y reproducible desde
Terraform.

Actividades:

- Crear `factory-analytics-dev`. Preparar los nombres y jerarquia de
  carpetas GCP para acomodar `factory-analytics-prod` en Fase 4 sin
  reorganizar.
- Habilitar APIs necesarias: Cloud Run, Cloud Scheduler, Workflows,
  BigQuery, Cloud Storage, Secret Manager, Artifact Registry, Cloud
  Logging, Cloud Monitoring, IAM, Dataform (aunque no se use en Fase 1,
  reduce fricciones futuras).
- Crear cuentas de servicio con minimo privilegio, sin claves JSON:
  - `sa-factory-extractor`: lectura de secretos, escritura de Bronze y
    tablas de control.
  - `sa-factory-deployer`: despliegue via CI/CD.
- Habilitar Workload Identity Federation para el runner de CI/CD (GitHub
  Actions o Cloud Build); prohibido descargar keys de service account.
- Crear bucket `gs://factory-datalake-dev-<project-id>` con:
  - Uniform Bucket-Level Access.
  - Prevencion de acceso publico.
  - Versionado activo.
  - Lifecycle inicial (Standard 0-30d, Nearline 31-90d, Coldline 91d+).
- Crear dataset `factory_control_dev` (BigQuery) y `factory_stage_dev`
  vacio para uso futuro.
- Crear repositorio Artifact Registry `factory-etl` con lifecycle policy
  para retener las N imagenes mas recientes.
- Crear los secretos en Secret Manager: `factory-api-key`,
  `factory-api-user` (segregados por ambiente).
- Backend Terraform: bucket GCS dedicado con versionado y bloqueo, state
  separado por ambiente.
- Configurar presupuesto y alertas por email al responsable financiero y
  al responsable tecnico Fase 1.

Entregables:

- Modulo Terraform base (`terraform/environments/dev` + modulos
  reusables).
- Diagrama de identidades e IAM con la matriz de permisos aprobada.
- Runbook corto de rotacion de secretos (quien, cuando, comando).
- CI/CD del propio Terraform ejecutando `plan` en cada pull request y
  `apply` solo tras aprobacion.

Criterios de salida:

- `terraform plan` en la rama principal reporta cero cambios.
- `sa-factory-extractor` puede leer el secreto y escribir en Bronze en una
  prueba manual; ninguna otra identidad puede.
- Un intento de acceso publico al bucket falla con 403.
- Presupuesto activo con alerta al 50%, 80% y 100%.

### Etapa 2. Empaquetado del extractor

**Objetivo:** convertir el ETL Python actual en un contenedor productivo
sin destino SQL Server.

Actividades:

- Extraer del script actual la parte de extraccion correspondiente al
  transporte generico y desacoplarla del destino heredado. El destino
  de esta fase es Bronze en GCS mas tablas de control en BigQuery.
- **Retirar del extractor** todo el codigo asociado a la API de
  servicios: `API_BASE_URL`, `build_payload`, la rama de
  `fetch_endpoint` que arma URL por empresa/endpoint, y el uso de
  `Desde`/`Hasta` como argumentos de servicio. Esos parametros pasan a
  ser parametros SQL tipados del renderer.
- **Retirar el destino SQL Server**: `pyodbc`, `create_db_connection`,
  `insert_staging`, `write_log`, `run_transforms`, `STAGING_INSERT_SQL`
  y toda referencia a `stg_*`, `etl_lotes`, `log_ejecuciones` y
  procedimientos `sp_transform_*`. El flag `--transformar` no se porta.
- Estructurar el codigo en `src/factory_etl/` siguiendo la propuesta:
  `extractor.py`, `query_runner.py`, `factory_queries/` (aun vacio, se
  puebla en Etapa 3).
- Fijar versiones de dependencias en `requirements.txt` o `pyproject.toml`
  y publicar un lockfile.
- Dockerfile multi-stage: imagen final con usuario no privilegiado,
  distroless o `python:*-slim`, sin herramientas de compilacion.
- Pipeline CI que corre:
  - Tests unitarios y de integracion con fixtures grabados de respuestas
    reales sanitizadas de FactorySoft (patron VCR).
  - Bandit y auditoria de dependencias (pip-audit o similar).
  - Build de imagen etiquetada con SHA de commit.
  - Publicacion condicional a Artifact Registry solo desde ramas
    aprobadas.
- Fixtures que cubran los casos rarizos ya conocidos: BOM UTF-8, raiz
  `d.laTablas[0]` vs `datos.laTablas[0]`, nulos inesperados, respuestas
  vacias.

Entregables:

- Repositorio de codigo con la estructura anterior y CI verde.
- Imagen `factory-etl:<sha>` publicada en Artifact Registry.
- Documento breve de convenciones (branching, versionado, semver del
  contrato de datos).

Criterios de salida:

- CI publica una imagen por cada merge a la rama principal.
- Ningun secreto aparece en logs de CI ni en la imagen construida.
- Bandit y pip-audit sin hallazgos de severidad alta.
- Los tests con fixtures pasan en menos de N minutos (definir umbral
  aceptable).

### Etapa 3. Modulo `factory_queries` con la primera consulta

**Objetivo:** dejar el extractor operando por catalogo, no por SQL
embebido en codigo.

Actividades:

- Implementar `factory_queries/` con `catalog.py`, `models.py`,
  `renderer.py`. El enum `Transport` en `models.py` incluye unicamente
  `GENERIC_SQL_API`; `SERVICE_ENDPOINT` no se implementa en Fase 1 ni
  en fases posteriores (decision de ingesta, seccion 1).
- Migrar `ARTICLES_QUERY` actual a `masters/articulos.sql` y definir
  `QueryDefinition` `articulos_v1` con:
  - `category=MASTER`, `transport=GENERIC_SQL_API`,
    `load_strategy=FULL_SNAPSHOT`.
  - `natural_key=("_source_empresa", "cod_art")`.
  - `required_columns` alineadas con la consulta: `cod_art`, `nom_art`,
    `cod_uni1`, `status`. Resto opcionales.
  - `reject_empty=True`.
  - `allowed_companies` limitado a la empresa piloto.
  - **El SQL no aplica `RTRIM` ni `CAST`**. Solo proyecta columnas con
    alias. La normalizacion (trim de padding CHAR, coercion de tipos,
    parseo de `fec_ini`) es responsabilidad de Silver, no de la
    consulta. Bronze debe ser un espejo del payload devuelto por
    FactorySoft.
- Renderer que rechaza rutas absolutas, `..`, marcadores no declarados y
  tipos incorrectos.
- Esquema JSON explicito de la entidad `articulos` en
  `factory_queries/schemas/articulos.json`.
- Pruebas unitarias del renderer y del catalogo (rechazo de SQL
  injection, parametros invalidos, empresas no autorizadas).

Entregables:

- Modulo `factory_queries` con `articulos_v1` funcional.
- Suite de pruebas de seguridad sobre el renderer.

Criterios de salida:

- Un intento de renderizar SQL con `;`, `--`, `UNION`, o una empresa
  fuera de `allowed_companies` falla con excepcion.
- El SQL renderizado tiene el mismo hash entre dos ejecuciones con los
  mismos parametros.
- La ejecucion del modulo contra FactorySoft en un ambiente controlado
  devuelve una respuesta valida para la empresa piloto.

### Etapa 4. Bronze end-to-end en desarrollo

**Objetivo:** una ejecucion diaria automatizada aterrizando articulos de
la empresa piloto en Bronze, con auditoria completa.

#### Reglas de aterrizaje en Bronze

Estas reglas fijan como se comporta el ETL al escribir en Bronze. Su
proposito es garantizar (a) que Bronze sea fiel a la base de datos
operativa de FactorySoft, y (b) que la reejecucion nunca genere
duplicados ni sobreescriba historia. Aplican a Fase 1 y a todas las
fases posteriores.

**Layout fisico.** Ruta canonica en GCS:

```text
gs://factory-datalake-<ambiente>/bronze/<entidad>/
    source_empresa=<empresa>/
    dt=YYYY-MM-DD/
    run_id=<uuid>/
    part-*.parquet
```

- Particionado por `source_empresa` y `dt` (fecha logica de la corrida).
- Formato Parquet con compresion Snappy o Zstd.
- Nombre de archivo determinista basado en `run_id` y numero de parte.

**Fidelidad al origen.** El ETL **no transforma semantica** al aterrizar:

- Se conservan **todas las columnas** que devuelve FactorySoft para la
  consulta, con el mismo nombre y el mismo tipo declarado por el schema
  JSON de la entidad.
- **No se filtran filas**, ni siquiera si tienen la clave natural
  duplicada dentro del mismo payload. Si FactorySoft devuelve dos filas
  con el mismo `codigo_articulo`, Bronze guarda las dos y Silver decide
  como resolverlo con un test de calidad.
- **No se dedupean** filas entre corridas: Bronze es un **historico de
  snapshots**, no una tabla acumulada. Cada `dt` es una foto completa e
  independiente. El mismo SKU aparece en la particion del 21 y en la del
  22 con su descripcion de cada dia.
- **No se aplica logica de negocio**: nada de `TRIM`, `UPPER`, coerciones
  de tipo mas alla del schema declarado, imputacion de nulos, ni
  descarte de columnas "vacias".
- Los tipos y nombres se documentan en `factory_queries/schemas/<entidad>.json`
  y ese archivo es la unica autoridad sobre el contrato.

**Columnas de sistema anadidas por el ETL.** Se agregan **sin modificar**
las columnas del origen, con prefijo `_` para evitar colision:

| Columna | Contenido |
|---|---|
| `_source_empresa` | Empresa FactorySoft origen (tinito, ctb, ctm). |
| `_query_id` | Identificador de la consulta en `factory_queries` (ej. `articulos_v1`). |
| `_query_version` | Version semantica de la definicion (`v1`, `v2`, ...). |
| `_query_sql_hash` | Hash SHA-256 del SQL renderizado que produjo la fila. |
| `_run_id` | UUID de la corrida. |
| `_lote_id` | Identificador deterministico del lote (ver §7 propuesta). |
| `_payload_hash` | SHA-256 del payload crudo de FactorySoft. |
| `_ingested_at` | Timestamp UTC de escritura en Bronze. |
| `_row_hash` | Hash de las columnas de negocio de la fila, usado en Silver para detectar cambios. |

Silver y Gold pueden proyectar solo las columnas de negocio y descartar
las de sistema para consumo analitico.

**Idempotencia y reproceso.** Reglas de escritura:

- **Nunca se sobreescribe una particion `dt` cerrada.** Una particion se
  considera cerrada cuando el `run_id` termino con estado `SUCCESS` en
  la tabla `etl_runs`.
- **Escritura atomica**: los objetos se escriben a un prefijo temporal
  (`gs://.../bronze/_staging/run_id=<uuid>/`) y se mueven al prefijo
  definitivo solo si la corrida completa termina en `SUCCESS`. Si falla
  a la mitad, el `_staging` se limpia y la particion final nunca se
  toca.
- **Reejecucion del mismo `lote_id` con el mismo `_payload_hash`**: se
  detecta antes de escribir consultando `etl_batches`. El ETL registra
  el evento como `SKIPPED_DUPLICATE` en `etl_events` y no crea objetos
  Bronze nuevos.
- **Reejecucion del mismo `lote_id` con `_payload_hash` distinto**: solo
  esta permitida si la particion `dt` no esta cerrada; genera un lote
  nuevo con `run_id` distinto y ambos quedan en `etl_batches` (el
  anterior marcado `SUPERSEDED`, el nuevo `SUCCESS`). Si la particion ya
  estaba cerrada, se rechaza y requiere un `run_id` de **reproceso
  explicito** con flag operativo.
- **Corridas del mismo dia**: si el operador ejecuta el ETL dos veces el
  mismo `dt` (mismo `source_empresa`, misma entidad), la segunda corrida
  se registra pero **no** genera un objeto Bronze nuevo salvo que el
  `_payload_hash` haya cambiado. El proposito es tolerar reintentos, no
  sobrecargar Bronze con snapshots identicos del mismo dia.

**Detecccion de cambios sin duplicar registros.** Bronze no dedupea, pero
las tablas de control permiten a Silver detectar exactamente que
cambio:

- El `_row_hash` de cada fila se calcula sobre las columnas de negocio
  del schema (excluye columnas de sistema).
- Silver hace `MERGE` contra la tabla historizada comparando
  `_row_hash`; si cambio, cierra la version vigente (`valid_to`,
  `is_current=false`) e inserta la nueva. Si no cambio, no hace nada.
- El detalle de la estrategia SCD por entidad es responsabilidad de
  Fase 2. Fase 1 solo garantiza que el `_row_hash` este presente y sea
  estable.

**Deteccion de borrados en el origen.** FactorySoft no envia flag de baja
logica. Si un SKU deja de aparecer en el snapshot diario, la ausencia se
detecta comparando la particion `dt` de hoy contra la de ayer. Esta
comparacion se hace en Silver (Fase 2). Bronze solo garantiza que la
particion sea una **foto completa** del payload devuelto por
FactorySoft, sin filas eliminadas silenciosamente.

**Retencion y borrado.**

- Las particiones `dt` **nunca** se eliminan desde el ETL.
- Lifecycle GCS gestiona el traslado a Nearline/Coldline segun edad, sin
  cambiar rutas ni afectar la trazabilidad desde `etl_batches`.
- El borrado fisico definitivo requiere una operacion manual autorizada
  fuera del ETL, con registro en un runbook.

**Cuarentena.** Si `reject_empty=True` y la respuesta viene vacia, o si
el schema JSON rechaza el payload, el objeto no aterriza en la ruta
canonica de Bronze; aterriza en:

```text
gs://factory-datalake-<ambiente>/quarantine/<entidad>/
    source_empresa=<empresa>/dt=YYYY-MM-DD/run_id=<uuid>/...
```

con el registro correspondiente en `etl_events` marcado
`QUARANTINED_<motivo>`. Ninguna consulta downstream lee de `quarantine/`.

Actividades:

- Cloud Run Job desplegado con la imagen versionada de Etapa 2.
- Cloud Scheduler creando la corrida diaria en la ventana pactada.
- Workflow minimo: Scheduler → Workflow → Cloud Run Job (con reintentos
  controlados y estado final registrado).
- Crear tablas de control en `factory_control_dev`:
  - `etl_runs`
  - `etl_batches`
  - `etl_events`
  - `data_quality_results`
- Escribir el manifiesto de cada objeto Bronze con `source_empresa`,
  `entidad`, `run_id`, `lote_id`, `payload_hash`, `record_count`,
  `schema_version`, `object_uri`, tiempos y estado.
- Zona `quarantine/` con dataset `factory_quarantine_dev` para respuestas
  vacias o parciales cuando `reject_empty=True`.
- Alertas basicas (Cloud Monitoring + notificacion por email/chat):
  - Job fallido o no ejecutado en la ventana.
  - Autenticacion rechazada por FactorySoft.
  - Respuesta vacia inesperada para snapshot critico.
  - Volumen anomalo respecto al historico corto observado durante el
    piloto.

Entregables:

- Cloud Run Job `factory-etl-articulos-dev`.
- Workflow `factory-etl-daily-dev`.
- Scheduler `factory-etl-daily-scheduler-dev`.
- Tablas de control pobladas y consultables.
- Dashboard operativo minimo en Cloud Monitoring.

Criterios de salida:

- Ejecucion diaria automatica durante al menos **5 dias corridos** sin
  intervencion.
- Reintentar el mismo `lote_id` no genera objetos Bronze nuevos.
- Un cambio de `payload_hash` genera un lote nuevo y queda auditado.
- El objeto Bronze puede localizarse en menos de 1 minuto a partir del
  `lote_id` en las tablas de control.

### Etapa 5. Pruebas de la fase

**Objetivo:** demostrar que Bronze es idempotente, seguro y
reproducible antes de declararlo estable.

Actividades y casos de prueba:

- **Idempotencia:** reejecutar un lote con la misma respuesta no crea
  objetos nuevos; con `payload_hash` distinto crea un lote nuevo y
  audita ambos.
- **Reproceso desde Bronze:** reconstruir un dia sin volver a llamar a
  FactorySoft, unicamente leyendo Bronze.
- **Reintentos y errores transitorios:** mock de 5xx, timeouts,
  respuestas truncadas; el job debe reintentar con backoff y no
  registrar exito falso.
- **Contrato de esquema:** columna nueva en la respuesta genera alerta
  pero no rompe el lote; columna requerida ausente envia el lote a
  cuarentena.
- **Seguridad SQL:** intentos de inyectar `;`, `UNION SELECT`, `--`, ruta
  `../` a los parametros son rechazados antes de emitir el request.
- **Higiene de logs:** los logs de la corrida completa no contienen
  API key, headers, SQL renderizado, payload ni datos personales.
- **Rotacion de secreto:** rotar la API key en Secret Manager y ejecutar
  el job; el proximo run debe tomar la nueva version sin redeploy.
- **Recuperacion GCS:** mover manualmente un objeto Bronze a Coldline y
  medir el costo/tiempo de recuperarlo; validar que la tabla de control
  lo localiza aunque la clase de storage haya cambiado.

Entregables:

- Reporte de pruebas con evidencia (capturas, hashes, logs sanitizados).
- Backlog priorizado de defectos y trabajo diferido.
- Runbook operativo Fase 1: como diagnosticar los tres incidentes mas
  probables (autenticacion, red, cuarentena) y como reejecutar
  manualmente.

Criterios de salida:

- Todos los casos de idempotencia, seguridad y reproceso pasan.
- Ningun secreto ni dato personal detectado en revision de logs.
- Backlog aceptado por el Data Owner y el responsable de seguridad.

### Etapa 6. Puesta en marcha piloto

**Objetivo:** operar Bronze bajo condiciones reales durante un periodo
de estabilizacion antes de habilitar Fase 2.

Actividades:

- Congelar la version de la imagen desplegada (tag inmutable).
- Correr el job diariamente durante **14 dias corridos** sin cambios de
  configuracion, salvo hotfix aprobado.
- Monitoreo activo: revisar alertas, tiempos, volumen de registros y
  errores; ajustar umbrales si el observado en piloto difiere de lo
  supuesto.
- Sesion de handoff con el equipo que va a operar (soporte L1/L2):
  runbook, alertas, contactos, expectativa de SLO.
- Documento de decisiones abiertas para Fase 2: si la region resulto
  adecuada, si la ventana horaria es sostenible, si el bucket muestra
  crecimiento esperado, si el modelo de control necesita ajustes antes
  de escalar a mas entidades.

Entregables:

- Bronze piloto estabilizado en `factory-analytics-dev` (no se sube a
  produccion en esta fase; se promueve en Fase 4 tras Silver y Gold).
- Runbook operativo firmado por el responsable de operaciones.
- Aprobacion escrita del Data Owner y del responsable de seguridad para
  abrir Fase 2.

Criterios de salida:

- 14 ejecuciones diarias consecutivas exitosas.
- Cero incidentes P1 abiertos al cierre.
- Presupuesto mensual real dentro del 120% de lo estimado.
- Data Owner firma el paso a Fase 2.

---

## 4. Roles y responsabilidades en Fase 1

| Rol | Persona | Responsabilidad principal |
| --- | --- | --- |
| Sponsor / Data Owner | **Francisco Pino** | Aprueba alcance, empresa piloto, presupuesto y paso a Fase 2. |
| Data Steward | pendiente de nombrar | Valida contrato de datos y catalogo de consultas. |
| Responsable tecnico Fase 1 | pendiente de nombrar | Ejecuta el plan y coordina las etapas. |
| Seguridad | pendiente de nombrar | Revisa IAM, secretos, logs y pruebas de seguridad. |
| Operaciones | pendiente de nombrar | Recibe el handoff y opera desde Etapa 6. |
| CI/CD | pendiente de nombrar | Configura runners con Workload Identity Federation. |

Tooling operativo GCP: **`gcloud` CLI** (herramienta principal para
interaccion manual con GCP) + **Terraform** (fuente unica de verdad para
la infraestructura). Ningun recurso critico se crea desde la consola web
sin dejar la definicion Terraform equivalente.

---

## 5. Riesgos de la fase y mitigacion

| Riesgo | Impacto | Mitigacion |
| --- | --- | --- |
| FactorySoft aplica rate limit o degradacion durante extraccion | Falla diaria del piloto | Horario pactado, backoff exponencial, alerta de autenticacion, reintentos limitados. |
| Cambio de esquema no anunciado en la fuente | Bronze aterriza payload valido pero contrato falla | Contrato de esquema, alerta de drift, cuarentena antes de escalar a Silver. |
| API key mal rotada o mal comunicada | Bloqueo total | Runbook de rotacion, dos personas involucradas (segregacion), verificacion en dev antes de prod. |
| Empresa piloto con volumen mucho mayor al supuesto | Riesgo de costo y de saturacion del job | Medir en dev, presupuesto con alertas al 50/80/100%, techos de tamano de respuesta. |
| Retrasos en nominar roles o aprobar region | Bloqueo administrativo | Escalar semanalmente al comite de gobierno; cada etapa exige responsables antes de iniciar. |
| Fatiga de fixtures VCR (respuestas viejas que ya no representan la fuente) | Falsa confianza en tests | Refresco periodico de fixtures sanitizados en cada etapa. |
| Crecimiento silencioso de logs con secretos por error | Fuga de credenciales | Revision de logs en Etapa 5 y filtros en Cloud Logging. |

---

## 6. Metricas de la fase

Se miden y publican al cierre para dimensionar Fase 2:

- Volumen medio y maximo de la respuesta por corrida (bytes, registros).
- Duracion del job (p50, p95).
- Tasa de exito de las 14 corridas piloto.
- Bytes escritos en Bronze en el periodo.
- Numero de alertas disparadas y su clasificacion (verdadero positivo,
  falso positivo).
- Costo real GCP del periodo piloto vs estimacion.

---

## 7. Al terminar Fase 1

- Se abre Fase 2: aterrizaje tipado en `factory_stage_<ambiente>`,
  Silver y modelo Gold minimo. Todavia sin capa de consumo.
- El equipo de seguridad puede iniciar en paralelo el diseno del modelo
  RLS y `sec_*`, para tenerlo listo cuando Gold exista.
- Este plan no se modifica; se archiva como registro. Fase 2 tendra su
  propio documento (`PLAN_IMPLEMENTACION_FASE_2.md`).

---

## 8. Decisiones abiertas

Bloqueantes para iniciar Etapa 1:

- Region GCP definitiva.
- Empresa y entidad piloto.
- Ubicacion del repositorio de codigo (nuevo repo dedicado o
  monorepo existente).
- Nominacion de Data Owner, Data Steward y responsable tecnico Fase 1.
- Presupuesto mensual aprobado y umbral de alerta.
- Herramienta de CI/CD (GitHub Actions vs Cloud Build).
- Canal de alertas (email, Slack, Google Chat, PagerDuty).

Recomendables antes de Etapa 4:

- Politica de retencion de Bronze en dev (piloto sugerido: 90 dias).
- Formato final del `run_id` y `lote_id` en logs (documentado como
  invariante para que los futuros consumidores lo asuman).
