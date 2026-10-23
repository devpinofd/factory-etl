# Inventario para despliegue de vistas y acceso aislado SORT

Fecha de inspeccion: 2026-10-22
Estado: inventario verificado por metadatos y revision del repositorio.
No se desplegaron recursos, ejecutaron consultas de datos ni modificaron permisos.

## 1. Resumen

### Resultado administrado verificado, 2026-10-22

Revision publicada: 2374d3e431be2df4e8ec89b2ab9929d627a4502a en
feat/sort-managed-dataform. Compilacion administrada:
31d2e9ea-8e11-4375-8278-b2d21a0481f1, sin errores.
Se usa pipelineConfig DATAFORM con path dataform, como en el workflow
existente; el proyecto Dataform no reside en la raiz del repositorio Git.

Terraform aplico exclusivamente un alta adicional: dataEditor de
factory-etl-runtime-prod@factory-etl-prod.iam.gserviceaccount.com en sort.
Se verifico el ACL WRITER equivalente, sin permisos del tercero.
Se retiraron el ejecutor Python y su test especifico antes de publicar.

Invocacion Dataform:
1792720154-b26de7dd-31d9-4069-a249-2f9e84a07c9c.
Identidad ejecutora: la cuenta de servicio interna anterior.
Seleccion: 14 modelos/operacion Mondelez y 37 assertions, incluidas
las dependencias de calidad de fuentes, sin reconstruir modelos ajenos.
Resultado FAILED: 46 acciones SUCCEEDED, una FAILED y cuatro SKIPPED.

La operacion pub_mondelez_existencias fallo el control aprobado
"Maestro faltante: cobertura de inventario no verificable".
Job: dataform-gcp-e5599aca0d5405e25c5db9617d23a41f017bf015cc4ed6b9f2acd96c20a25ee8-0.
Diagnostico agregado del dia 2026-10-22:
ctb tiene una fila/un articulo sin maestro; tinito dos filas/dos articulos.
Sin maestro no se puede determinar si esos articulos son del proveedor
0301; no se omiten ni se relaja la validacion para completar el despliegue.
Se omiten por dependencia las vistas interna/publica de existencias y
las dos assertions de la interna. Existencias no esta disponible.

Tres vistas publicas se crearon y verificaron mediante consultas sin cache,
limite de 1 GiB por consulta, sin NULL en ninguno de sus campos:

| Vista | Campos STRING | ctb | ctm | tinito |
|---|---:|---:|---:|---:|
| vw_mondelez_clientes | 18 | 8350 | 5333 | 15744 |
| vw_mondelez_ventas | 25 | 102158 | 58257 | 283284 |
| vw_mondelez_articulos | 6 | 95 | 122 | 189 |

No se otorgaron permisos a consumidores, no se crearon usuarios y no
se cambio la politica de organizacion. Queda bloqueada la publicacion
de existencias hasta conciliar los tres articulos con su fuente/maestro.
La recurrencia permanece pendiente: no se fusiono la rama en main ni
se habilito el flag acoplado a la API. No declarar entrega integral lista.

### Recuperacion mediante Terraform y Dataform administrado

Se retira el ejecutor Python introducido durante el primer intento. El
usuario autoriza rama, commit y push para compilar una revision Git fija.
No se incluyen cambios ajenos del worktree ni desarrollo API.
Terraform administra sort y el permiso dataEditor de la cuenta de servicio
interna existente; Dataform administra SQL, assertions y publicacion.
No se crean usuarios ni se conceden permisos del consumidor.

Estado verificado antes de recuperar: sort existe con ACL projectOwners;
pub_mondelez_existencias tiene cero filas, inventario_publication_lock una.
Dieciocho acciones del intento previo tuvieron exito, pero la publicacion
fallo al crear el dataset temporal bajo la cuenta personal. No se presume
rollback de los CREATE TABLE anteriores a la transaccion.
La cuenta factory-etl-runtime-prod@factory-etl-prod.iam.gserviceaccount.com
ya aparece en el ACL de Gold. El llamante tiene iam.serviceAccounts.actAs.
No se modifican las restricciones de dominio.

Las acciones Mondelez incluyen dependencias de assertions en los limites
de materializacion, publicacion y vistas publicas. La invocacion debe
seleccionar los modelos Mondelez y sus assertions requeridas explicitamente,
sin reconstruir modelos Gold ajenos. Se compila desde SHA con variables de
produccion y se ejecuta con la cuenta interna, no con ADC personal como
identidad BigQuery. El resultado y la revision deben verificarse en Dataform.

La recurrencia no se considera desplegada por crear una rama: el workflow
vigente compila main. Sigue pendiente integrar la revision aprobada y
separar el flag de modelos Mondelez del flag de API antes de activarla.

### Reanudacion sin acceso del tercero, 2026-10-22 21:00 Venezuela

Se excluyen de la ejecucion actual la creacion de usuarios y todos los
grants del consumidor. El contacto previsto es mmateu@gssve.com; no se
aprovisiona una cuenta alternativa ni se usa el antiguo piloto Outlook.
Continuan dataset y datos; la aceptacion con el tercero queda pendiente.

Consulta de politica efectiva mediante Resource Manager v1:
iam.allowedPolicyMemberDomains permite el customer C02iq6q4d.
La API BigQuery documenta que omitir access al crear agrega projectOwners,
projectReaders, projectWriters y al creador como OWNER. El caller del
intento fallido fue pinofd@gmail.com; la auditoria no expone el ACL enviado,
por lo que la entrada rechazada no queda identificada de manera directa.

Se autoriza un ACL inicial explicito solo OWNER para projectOwners:
sin incorporar al creador ni a lectores/escritores del proyecto mediante
ACL de dataset. No agrega miembros ni roles de proyecto y no elimina
permisos heredados. Terraform ignora cambios posteriores de access para
preservar autorizaciones de vistas/grants administrados por separado.
No se modifica la politica de organizacion ni se conceden permisos al tercero.
El resultado de la nueva ejecucion debe registrarse antes de declarar
disponibilidad de las vistas.

### Ejecucion autorizada y bloqueo de politica, 2026-10-22

Se autoriza ejecutar el plan integral sin API. Adaptaciones locales realizadas:
destino sort en las acciones de consumo y publicacion; vistas privadas con
sufijo _interna para conservar claves de validacion; proyecciones publicas
explicitas con source_empresa y 17/24/9/5 campos respectivamente.
El maestro canonico y las fuentes Gold permanecen en sus datasets existentes.
Las cuatro interfaces publicas mantienen nombres vw_mondelez_clientes,
vw_mondelez_ventas, vw_mondelez_existencias y vw_mondelez_articulos.
Compilacion productiva local satisfactoria y 134 pruebas focalizadas pasan.

El bloqueo GCS del plan fallido previo fue verificado y liberado mediante
su generacion numerica. Se genero un nuevo plan con bloqueo normal y se
verifico exactamente una creacion de dataset, sin cambios ajenos.
El apply fue intentado y BigQuery lo rechazo con 403 policyViolation:
"One or more users named in the policy do not belong to a permitted customer".
La auditoria confirma datasets.create autorizado y rechazo durante setPolicy;
la identidad llamante no identifica por si sola cual miembro del ACL fue rechazado.
No se pudo consultar la politica efectiva de organizacion porque su API no
esta habilitada/accesible en este contexto. No se modifico dicha politica.

Verificacion posterior: sort no existe y no tiene recurso en el estado.
No se desplegaron modelos, no se ejecutaron publicaciones productivas,
no se otorgaron grants al usuario piloto y no se tocaron recursos API.
Requiere revision administrativa de la politica efectiva y una identidad
de aprovisionamiento autorizada. El acceso posterior de pinofd@outlook.com
tambien debe validarse contra esa politica; no se presume permitido.

La CLI Dataform requiere un archivo de configuracion de credenciales aun
no preparado. No se generaron claves de servicio ni se ejecutaron acciones.
La ejecucion recurrente y la prueba del consumidor permanecen pendientes.
Este bloqueo sustituye cualquier expectativa de disponibilidad productiva.

### Plan integral ampliado, 2026-10-22 20:32 Venezuela

Negocio incluye en el plan tanto el despliegue Dataform y la disponibilidad
de datos como la habilitacion y prueba del acceso del tercero. No se limita
el resultado al dataset vacio. Esta ampliacion es del plan de entrega;
no convierte las vistas ni IAM en responsabilidades del recurso Terraform
de dataset y no constituye ejecucion de las etapas.

Destino unico vigente: factory-etl-prod.sort, us-central1.
Identidad de prueba: user:pinofd@outlook.com.
Proyecto de ejecucion/facturacion: factory-etl-prod, confirmado para el piloto.
Todo desarrollo/despliegue API queda fuera.

#### Etapa A. Aprovisionar el dataset (Terraform)

1. Resolver el bloqueo remoto solo tras verificar que pertenece al plan
   fallido anterior y que no existe una operacion activa.
2. Regenerar el plan con bloqueo normal y revisar que su unico cambio sea
   crear google_bigquery_dataset.sort[0]. No aplicar el plan de inspeccion
   generado con lock=false ni el plan general con cambios ajenos.
3. Aplicar el plan revisado cuando se autorice la ejecucion.
4. Verificar existencia, region, protecciones y acceso efectivo inicial.

#### Etapa B. Crear vistas y preparar sus datos (Dataform)

1. Adaptar los destinos y referencias internas desde factory_etl_mondelez
   a sort, incluido el nombre de la tabla de bloqueo en el script de
   publicacion. No modificar los contratos ni los horarios de sincronizacion.
2. Mantener objetos auxiliares privados y cuatro interfaces de consumo con
   listas explicitas de columnas: source_empresa mas 17/24/9/5 campos de
   negocio de clientes/ventas/existencias/articulos, respectivamente.
   Separar las claves y metadatos tecnicos necesarios para assertions en
   objetos internos, sin exponerlos mediante SELECT *.
3. Compilar con proyecto prod, ubicacion regional y controlDataset correcto.
   Revisar el grafo y las acciones seleccionadas para no reconstruir ni
   desplegar modelos ajenos por inclusion automatica de dependencias.
4. Verificar permisos de la identidad ejecutora para los objetos necesarios.
   Los grants de despliegue se revisan/aplican por separado del dataset.
5. Desplegar maestros canonicos, enriquecimiento, grupos y vistas auxiliares
   aprobadas; materializar el maestro canonico y el hecho validado requerido.
6. Ejecutar controles y la publicacion transaccional de existencias antes
   de declarar lista su vista. Preservar auditabilidad e idempotencia.
7. Desplegar las cuatro interfaces finales y ejecutar sus assertions y
   conciliaciones. Clientes/ventas/articulos son vistas logicas: consultan
   Gold, no reciben una carga independiente. Existencias lee su publicacion.
8. Documentar la actualizacion recurrente: integrar la ejecucion de los
   modelos necesarios despues de la consolidacion correspondiente, mediante
   el proceso de datos y sin depender del flag de API. No basta con una
   carga manual inicial para mantener vigente la publicacion de existencias.
   Revisar cualquier ajuste de orquestacion como cambio de datos separado.

No se incluye la publicacion comun por batch_id de las cuatro entidades:
esa decision sigue pendiente. Se mantiene solo la publicacion especifica
de inventario que ya forma parte del contrato aprobado.

#### Etapa C. Habilitar lectura minima (acceso separado)

1. Revisar politicas de identidades externas, restricciones de dominio,
   perimetros y permisos heredados de pinofd@outlook.com.
2. Configurar las autorizaciones de vistas que resuelvan las dependencias
   internas sin conceder lectura Gold/Silver/Control al tercero.
   Preservar las autorizaciones existentes y probar las cadenas anidadas.
3. Conceder roles/bigquery.dataViewer solo sobre cada una de las cuatro
   vistas contractuales, no sobre sort completo ni objetos auxiliares.
4. Conceder roles/bigquery.jobUser en factory-etl-prod para el piloto.
5. Registrar exactamente los grants nuevos para revocarlos selectivamente.
   No conceder escritura, administracion, secretos ni impersonacion de cuentas.

#### Etapa D. Aceptacion con la identidad del tercero

- Iniciar sesion como pinofd@outlook.com mediante el flujo normal de Google.
  No pedir contrasenas/codigos en chat ni certificar usando la identidad admin.
- Consultar las cuatro vistas y descargar un CSV de prueba completo.
- Conciliar esquema, filas, claves, vacios y medidas contra los resultados
  contractuales para iguales filtros. Verificar source_empresa en todas.
- Comprobar rechazo de lectura directa de fuentes y auxiliares; comprobar
  denegacion de escritura con pruebas no destructivas en recursos controlados.
- Verificar valores de texto y decimales en la importacion SQL Server con
  el consumidor; no declarar validada su carga DW sin esa evidencia.
- Registrar jobs, coste de ejecucion, corte/horas y reservas de frescura.
- Probar reejecucion del publicador sin duplicados y conservacion de la
  publicacion anterior si falla una candidata.

**Criterio de cierre:** dataset creado, cuatro vistas consultables con datos
conformes, existencias publicada, actualizacion recurrente definida/verificada
y acceso/CSV probado por el tercero con aislamiento comprobado.
Si falta autenticacion del tercero o prueba de SQL Server, reportar ese
pendiente explicitamente y no dar por certificado el extremo consumidor.

**Estado actual:** solo el recurso Terraform de dataset y sus pruebas estan
preparados. Las adaptaciones Dataform, configuracion de acceso y pruebas
productivas descritas aqui todavia no se ejecutaron.

### Plan preparado para sort, 2026-10-22 20:25 Venezuela

Configuracion local: [sort_dataset.tf](../terraform/sort_dataset.tf),
habilitada mediante enable_sort_dataset en prod.tfvars. Independiente de
enable_mondelez_api: crea solo sort en us-central1, con prevent_destroy y
delete_contents_on_destroy=false, sin expiracion predeterminada y sin ACL
explicitos ni grants externos. No altera los modelos o workflows existentes.
No se agregaron vistas ni IAM del piloto en esta etapa.

Validaciones: fmt y validate satisfactorios; cuatro pruebas Terraform pasan,
incluidas independencia de API, deshabilitacion por defecto y rechazo fuera
de produccion. El plan dirigido verificado propone exactamente una creacion,
google_bigquery_dataset.sort[0], sin cambios ni destrucciones adicionales.
Se usa plan dirigido porque el worktree contiene cambios ajenos pendientes.

El backend conserva un bloqueo del intento anterior fallido de plan.
No se retiro ni modifico ese bloqueo. El plan de inspeccion se genero
sin bloqueo, exclusivamente para revision, y **no debe aplicarse**:
antes del despliegue se debe resolver el bloqueo con verificacion de
propiedad y regenerar/revisar un plan con bloqueo normal.
No se ejecuto apply ni se aprovisionaron recursos.

El recurso dataset sin grants externos explicitos no implica ausencia de
permisos heredados/default del proyecto; la revision de acceso efectivo
y la autorizacion por vista pertenecen a la etapa de habilitacion del piloto.

### Nombre definitivo y ejecucion del piloto, 2026-10-22 20:23 Venezuela

El unico dataset objetivo se llama literalmente **sort**:
factory-etl-prod.sort, region us-central1. Sustituye factory_etl_mondelez
como nombre objetivo de este despliegue; tampoco crear factory_etl_sort_mondelez.
Las referencias a los nombres anteriores en este inventario describen
definiciones existentes o propuestas historicas, no datasets adicionales a crear.
Las definiciones Dataform y Terraform aun requieren adaptarse al nombre final.

Se confirma jobUser para user:pinofd@outlook.com en factory-etl-prod
durante el piloto, ademas de dataViewer por cada una de las cuatro vistas.
No se han aplicado estos grants. Se mantiene la exclusion total de API.

### Alcance vigente, 2026-10-22 20:16 Venezuela

El trabajo activo es publicar las cuatro vistas aprobadas en produccion
para consulta SQL y descarga CSV del tercero Mondelez. Todo desarrollo
de API queda fuera: sin Cloud Run, imagen, secretos HTTP, identidad API,
GCS de entrega ni publicacion comun por lotes no aprobada.

Se usara **un solo dataset factory_etl_mondelez**. No crear
factory_etl_sort_mondelez ni duplicar las cuatro vistas contractuales.
source_empresa se conserva como trazabilidad SQL; CODIGO_GRUPO mantiene
su semantica aprobada y articulos no se replica por grupo.

Identidad de prueba del tercero: user:pinofd@outlook.com.
Conceder dataViewer por cada una de las cuatro vistas de consumo, no al
dataset entero; no conceder lectura directa de Gold, Silver, Control ni
objetos auxiliares. Configurar las autorizaciones necesarias de la cadena
de vistas sin ampliar el acceso del usuario a sus fuentes.

Terraform aprovisionara solo el dataset, independiente de cualquier flag API.
Los modelos, las vistas y la publicacion especifica de existencias pertenecen
al proceso de datos. IAM y autorizaciones se gestionaran por separado.
El proyecto de ejecucion/facturacion para jobUser esta pendiente de confirmar.
La validacion funcional de acceso requiere iniciar sesion con la identidad
de prueba; no asumir ni reutilizar credenciales administrativas para certificarla.

Esta seccion sustituye la propuesta de dos datasets y cuatro envolturas
externas de las secciones historicas siguientes. La topologia vigente es:

```text
Gold y fuentes privadas
          |
factory_etl_mondelez
  cuatro vistas de consumo autorizadas
  objetos auxiliares privados sin grant al tercero
          |
pinofd@outlook.com: lectura por vista
```

Antes de conceder acceso, separar las columnas tecnicas de las proyecciones
de consumo. Una recomendacion de SELECT no restringe las columnas accesibles.
No se aplicaron cambios cloud al registrar esta decision.

Decision de negocio, 2026-10-22 15:40 Venezuela: el desarrollo y despliegue
de la API deben estar desacoplados de las vistas. Es un requisito obligatorio,
no una opcion de implementacion. Este inventario documenta la separacion
requerida; el acoplamiento actual del codigo aun debe corregirse.

Produccion tiene las fuentes Gold necesarias, pero **no tiene desplegada la
integracion Mondelez ni el dataset externo SORT**. Dev dispone del entorno
QA transaccional previo, pero le faltan cuatro fuentes para probar las cuatro
interfaces completas con datos propios de ese entorno.

Objetivo propuesto:

```text
Fuentes privadas Gold / Silver / Control
             |
Integracion interna factory_etl_mondelez
             |
Cuatro vistas externas con columnas explicitas
factory_etl_sort_mondelez
             |
Usuarios SORT: lectura + ejecucion en proyecto acordado
```

Inventario logico a crear por entorno objetivo: **2 datasets, 12 objetos
internos y 4 vistas externas**, mas assertions y autorizaciones.
No incluye recrear las fuentes existentes ni contar cada assertion generada
como una tabla de negocio. Los nombres externos son propuestos.

## 2. Recursos existentes: verificacion real

Proyectos exactos: `factory-etl-prod` y `factory-etl-dev-0y1dhf`.
Una primera sonda complementaria uso identificadores abreviados incorrectos;
sus errores se descartaron. Los resultados siguientes corresponden a las
sondas con nombres completos e interprete del repositorio.

| Dataset | Produccion | Dev | Ubicacion |
|---|---|---|---|
| factory_etl_gold | Existe, 34 objetos | Existe, 32 objetos | us-central1 |
| factory_etl_silver | Existe, 41 objetos | Existe, 42 objetos | us-central1 |
| factory_etl_control | Existe, 5 objetos | Existe, 4 objetos | Prod us-central1; dev US |
| factory_etl_control_dev | No existe | Existe, 3 objetos | us-central1 |
| factory_etl_mondelez | No existe | No existe | Crear en us-central1 |
| factory_etl_sort_mondelez | No existe | No existe | Crear en us-central1 |
| factory_etl_mondelez_qa | No existe | Existe, 11 objetos | us-central1; expiracion por defecto 7 dias |

Los conteos son una fotografia del momento de inspeccion. QA contiene los
recursos sinteticos de la prueba anterior: no sustituye un despliegue integral
ni es un dataset para consumidores. No compartirlo con SORT.

### Fuentes requeridas

| Fuente | Prod | Dev |
|---|---|---|
| Gold fct_ventas_gold | Existe | Falta |
| Gold dim_articulo | Existe | Existe |
| Gold dim_cliente | Existe | Existe |
| Gold dim_almacen | Existe | Existe |
| Gold dim_proveedor | Existe | Existe |
| Gold dim_vendedor | Existe | Existe |
| Gold dim_pais | Existe | Falta |
| Gold dim_estado | Existe | Falta |
| Gold dim_ciudad | Existe | Falta |
| Silver sil_renglones_almacenes_historico | Existe | Existe |
| Control etl_batches | Existe en factory_etl_control | Existe en ambos datasets de control |

Columnas verificadas de etl_batches:
`batch_id, run_id, entity, source_empresa, dt, status, record_count,
object_uri, payload_hash, inserted_at`.
Existencia y esquema no certifican que los recibos esten completos o que haya
capturas publicables: eso requiere ejecutar los controles sobre los datos.

En dev debe seleccionarse explicitamente
`controlDataset=factory_etl_control_dev` para el procesamiento regional.
No unir accidentalmente las fuentes us-central1 con factory_etl_control en US.

Los cuatro objetos Gold nuevos de la seccion siguiente se verificaron ausentes
en ambos proyectos, no solo las cuatro interfaces internas.

## 3. Objetos internos definidos localmente y pendientes

Definiciones en [mondelez](../dataform/definitions/mondelez/).
Todos son privados para SORT.

| Dataset | Objeto | Tipo | Proposito |
|---|---|---|---|
| factory_etl_gold | dim_mondelez_producto_canonico | TABLE | 121 modelos del Excel y atributos canonicos |
| factory_etl_gold | dim_mondelez_articulo_enriquecido | VIEW | Cruce local sin perdida ni fallback canonico |
| factory_etl_gold | vw_inventario_capturas_qa | VIEW | Conciliar recibos y filas Silver |
| factory_etl_gold | fct_inventario_diario_validado | TABLE | Captura completa por empresa/dia Venezuela |
| factory_etl_mondelez | vw_mondelez_grupos | VIEW | Mapeo sucursal/grupo |
| factory_etl_mondelez | vw_mondelez_clientes | VIEW | Contrato aprobado de 17 campos y tecnicas internas |
| factory_etl_mondelez | vw_mondelez_ventas | VIEW | Contrato aprobado de 24 campos y tecnicas internas |
| factory_etl_mondelez | vw_mondelez_articulos | VIEW | Contrato aprobado de 5 campos y empresa |
| factory_etl_mondelez | vw_mondelez_existencias_candidata | VIEW | Consolidacion previa a publicacion |
| factory_etl_mondelez | pub_mondelez_existencias | TABLE | Publicacion transaccional append-only |
| factory_etl_mondelez | inventario_publication_lock | TABLE | Serializacion/reintentos de publicacion |
| factory_etl_mondelez | vw_mondelez_existencias | VIEW | Captura publicada ganadora por dia |

Ademas:

- Declaration `mondelez_etl_batches`: referencia una tabla existente; no la crea.
- Assertion explicita `assert_mondelez_clientes_maestro` y assertions generadas
  por los modelos. Verificar dataset factory_etl_assertions y permisos del ejecutor.
- La tabla de bloqueo la crea el script de publicacion; no es un modelo
  independiente registrado con ref en Dataform.
- Validar que ninguna seleccion de despliegue omita dependencias por usar
  solo tags sin inclusion de dependencias.

Los 12 objetos anteriores no son 12 endpoints ni deben concederse al consumidor.

## 4. Dataset y vistas externas a definir

Dataset propuesto: `factory_etl_sort_mondelez`, us-central1, privado.
Todavia no hay definiciones de estas cuatro vistas ni recursos Terraform para
este dataset aislado.

| Vista externa propuesta | Fuente interna | Campos de negocio |
|---|---|---:|
| vw_clientes | vw_mondelez_clientes | 17 |
| vw_ventas | vw_mondelez_ventas | 24 |
| vw_existencias | vw_mondelez_existencias | 9 |
| vw_articulos | vw_mondelez_articulos | 5 |

Usar proyeccion explicita, sin SELECT *. Excluir columnas tecnicas y fuentes
de auditoria. Proponer source_empresa como columna adicional de trazabilidad
SQL/CSV requiere acuerdo; no cambia el contrato HTTP aprobado.

Definir restricciones por empresa/grupo en la interfaz si no se autoriza todo
el alcance CTB/CTM/Tinito. Un WHERE escrito voluntariamente por SORT no es
una barrera de acceso.

Para existencias, definir como descubrir y seleccionar FECHA_DATA exacta sin
dar acceso a tablas de control. Una quinta vista minima de capturas seria
opcional y requeriria contrato adicional; no esta incluida en las cuatro.

## 5. Dependencias y autorizaciones de lectura

| Interfaz | Dependencias internas principales |
|---|---|
| Clientes | Grupos; Gold cliente, vendedor, pais, estado y ciudad |
| Ventas | Grupos; Gold ventas, cliente, articulo, proveedor, pais, estado y ciudad |
| Articulos | Gold articulo enriquecido -> articulo + canonico |
| Existencias | Publicacion interna; su consulta no necesita recalcular Silver/Control |
| Preparacion de existencias, no consulta externa | QA de capturas -> Silver historico + Control recibos; hecho validado + articulo + almacen + grupos |

Configurar autorizaciones **por vista** en cada frontera de datasets requerida
por el grafo real, incluidas las dependencias de vistas anidadas.
No asumir que autorizar la envoltura externa resuelve toda la cadena.
Los usuarios no deben recibir dataViewer sobre Gold/Silver/Control para
corregir un error de autorizacion.

La ruta externa de inventario debe terminar en la publicacion aceptada, no
en la candidata o en las fuentes de completitud. Reducir asi tanto exposicion
como permisos necesarios para entrega.

### Autorizaciones ya existentes que hay que preservar

Metadatos inspeccionados, solo entradas de vistas/datasets autorizados:

- Prod Gold y Control: sin entradas autorizadas observadas.
- Prod Silver: cuatro vistas Gold autorizadas:
  vw_clientes_bi_matriz, vw_inventario_bi_matriz, vw_ventas_bi_matriz y
  vw_facturas_renglones_consolidado.
- Dev Gold y Silver: dos vistas shared autorizadas en cada dataset:
  vw_conciliapp_ventas_kpi y vw_conciliapp_inventario.
- Dev Control, Control_dev y QA: sin entradas autorizadas observadas.

Esto **no es una auditoria de IAM efectivo** ni significa que los datasets
carezcan de usuarios/roles. No se inventariaron grants humanos.
Al agregar autorizaciones preservar las entradas anteriores.
No mezclar recursos Terraform que administren de forma conflictiva el ACL
completo y entradas individuales; revisar estado/importacion antes de aplicar.

## 6. Identidades y grants pendientes

| Identidad | Acceso requerido | Estado |
|---|---|---|
| Ejecutor ETL/Dataform existente | Leer fuentes; crear/actualizar modelos y assertions; ejecutar publicacion | Reutilizar tras verificar IAM efectivo |
| Administrador de aprovisionamiento | Crear datasets/vistas y configurar autorizaciones/grants | Confirmar responsable; no entregar sus credenciales a SORT |
| Grupo SORT nominativo | dataViewer solo en dataset externo | Grupo e integrantes pendientes |
| Grupo SORT nominativo | jobUser en proyecto de ejecucion acordado | Proyecto/facturacion pendientes |

No se necesita cuenta de servicio externa para el uso manual inicial.
No se necesitan claves JSON, secretos HTTP, permisos de Cloud Run ni lectura
GCS para consultar y descargar CSV local desde consola.

El proyecto de ejecucion puede pertenecer a SORT o ser uno dedicado bajo
nuestro control. No otorgar jobUser en prod automaticamente.
Revisar restricciones de dominios externos, perimetros VPC-SC y acceso heredado.

## 7. Orquestacion existente y brecha de configuracion

Verificacion REST Dataform en us-central1:

- Prod: repositorio factory-etl-prod.
- Dev: repositorios factory-etl-dev, factory-etl-dataform y dos IDs UUID.
  Elegir el repositorio operativo declarado en Terraform; no asumir que
  todos los repositorios dev son equivalentes ni modificar los otros.

Workflows observados:

- Prod: factory-etl-full-prod, factory-etl-consolidation-prod,
  factory-etl-daily-transaccional-prod y factory-etl-data-quality-prod,
  reportados ACTIVE.
- Dev: factory-etl-full-dev-scd2, factory-etl-consolidation-dev-scd2 y
  factory-etl-daily-transaccional-dev-scd2.

La existencia de workflows no demuestra que ejecuten las definiciones locales
Mondelez, sus flags, el commit correcto o las assertions.
Verificar compilacion/release, cuenta ejecutora, seleccion de acciones y
dependencias antes de programar la publicacion.

### Acoplamiento actual a la API

[mondelez.tf](../terraform/mondelez.tf) usa enable_mondelez_api para crear
dataset interno, identidad API y secretos. Aunque imagen vacia evita Cloud Run,
no evita esos otros recursos HTTP.

Para un despliegue SQL de minimo privilegio se necesita separar:

1. Aprovisionamiento de datos internos.
2. Dataset/vistas autorizadas para consumidores.
3. Servicio HTTP opcional.

No activar el flag actual como atajo. El flag Dataform enableMondelez controla
los modelos; no equivale al flag Terraform ni crea por si solo datasets/grants.
Mantener una fuente de verdad de las vistas: evitar que Terraform y Dataform
administren simultaneamente la misma definicion.

### Criterios obligatorios de desacoplamiento

- Datos: datasets internos, modelos Dataform, assertions y publicacion de
  existencias tienen configuracion y ciclo de despliegue independientes de HTTP.
- Acceso SQL: dataset externo, proyecciones y autorizaciones SORT pueden
  habilitarse con la API desactivada y sin imagen, secretos ni identidad HTTP.
- API: administra solo sus recursos de servicio y permisos propios; consume
  contratos de datos disponibles, sin crear o modificar sus definiciones.
- Deshabilitar o retirar la API no elimina datasets, vistas, publicaciones
  ni permisos de consumidores SQL.
- Cambiar o desplegar la API no exige recompilar ni desplegar Dataform.
- Publicar datos no exige construir imagenes ni desplegar Cloud Run.
- Los contratos de datos se versionan y validan de forma independiente;
  cambios incompatibles requieren migracion coordinada de consumidores.
- La futura implementacion IaC debe probar el plan de datos con API apagada
  y el retiro de API sin destruccion ni revocacion de recursos SQL.

La dependencia es unidireccional: API -> contrato de datos. Si se adopta
entrega desde GCS, el publicador tambien pertenece al ciclo de datos y la
API consume sus publicaciones; no traslada la transformacion al servicio HTTP.
No se exige separar repositorios ni crear microservicios para lograrlo.

## 8. Recursos no necesarios para esta primera entrega SQL

- Cloud Run API, imagen y credenciales HTTP.
- API Gateway, balanceador, Redis o nuevas bases de datos.
- Bucket de exportacion o permisos GCS al consumidor para CSV local.
- Recursos separados por cada empresa.
- Proyecto nuevo de datos si se mantiene el dataset aislado dentro de prod;
  el proyecto separado de ejecucion es una decision de coste/aislamiento.

Las tablas de publicacion inmutables para todas las entidades y exportaciones
masivas siguen siendo alternativas para mayor consistencia/rendimiento;
no estan implementadas ni incluidas como requisitos de estas cuatro vistas.

## 9. Secuencia propuesta y puertas de salida

1. Confirmar identidades, empresas/grupos, proyecto de ejecucion y contrato CSV.
2. Definir los recursos IaC separados de la API, sin aplicar aun.
3. Completar las cuatro fuentes faltantes de dev mediante su pipeline autorizado,
   o aprobar fixtures aislados. No copiar datos prod a dev sin autorizacion.
4. Crear datasets internos/externos y permisos del ejecutor en dev.
5. Compilar/desplegar modelos, assertions y primera publicacion controlada.
6. Crear las cuatro proyecciones externas y autorizar su cadena de lectura.
7. Probar con identidad externa sin grants heredados:
   - SELECT y CSV completos sobre las cuatro interfaces.
   - Ausencia de filas/columnas fuera del contrato.
   - Denegacion de lectura directa Gold, Silver, Control y objetos internos.
   - Denegacion de DML/DDL sobre nuestros datasets.
   - Reintento/rollback de publicacion e integridad sin duplicados.
   - Coste/job de consulta atribuible al proyecto elegido.
8. Revisar plan de produccion preservando ACL y recursos existentes.
9. Aplicar solo con autorizacion explicita y verificar nuevamente con consumidor.

Rollback de acceso: retirar grants y autorizaciones nuevas de forma selectiva;
no borrar datasets compartidos, fuentes Gold ni publicaciones historicas.
Versionar definiciones para restaurar las vistas anteriores si se modifican.
Los CSV ya descargados no se recuperan al revocar IAM.

## 10. Pendientes concretos antes de aprovisionar

| Pendiente | Responsable esperado |
|---|---|
| Grupo/cuentas SORT y alcance de empresas/grupos | Negocio + SORT |
| Proyecto de ejecucion, presupuesto y cuotas | Plataforma + SORT |
| source_empresa y necesidades de clave/lote en CSV | Datos + consumidor DW |
| Definicion de las cuatro vistas externas | Ingenieria de datos |
| Separacion IaC de datos/consumidores/API | Plataforma |
| Completar fuentes o fixtures dev | Ingenieria de datos |
| Grafo exacto de autorizaciones e IAM efectivo | Plataforma |
| Plan revisado y autorizacion dev/prod | Propietario del entorno |

**Resultado:** las fuentes productivas son reutilizables; faltan los dos
datasets, los 12 objetos internos y las cuatro interfaces externas, junto con
su configuracion de ejecucion y acceso. El inventario no constituye autorizacion
de despliegue ni demuestra conformidad de los datos actuales.

Documento de acceso relacionado:
[Propuesta de acceso BigQuery SORT](./propuesta-acceso-bigquery-sorti-mondelez.md).
