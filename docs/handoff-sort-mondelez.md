# SORT Mondelez: highlights y continuidad

Actualizado: 2026-10-26, America/Caracas.
Repositorio: factory-etl, proyecto productivo factory-etl-prod.

### Sincronizacion del codigo productivo, 2026-10-26

Esta revision reconcilia el codigo probado sin desplegar ni cambiar cloud.
La base es origin/main 2dc0635; clientes 8b2b24f contiene managed 99ceb5a,
incluidos SQL compartido, hora de consulta de ventas y limpieza Silver.
No se reaplican las correcciones Gold de inventario: sus cuatro archivos
coinciden con main. De acceso 564e622a/1eeb8a5 se conserva el alcance,
pero se incorpora el Terraform local posterior endurecido, no su jobUser.

Lecturas actuales confirmaron sortQueryRunner con solo config.get,
jobs.create y projects.get; cuatro grants individuales y autorizaciones
Gold; bucket privado, roles de exportacion separados y caducidad 30 dias.
No hay jobUser directo de Magdalena ni sus seis dataform.admin directos.
Esto no certifica membresias de grupos, descarga local ni acceso efectivo
universal. No se reprodujeron consultas comerciales ni despliegues.

El workflow diario vigente incluye clientes_v1, coherente con la seleccion
versionada. Consolidacion sigue en revision 000006-44c, compila main y no
incluye enableMondelez. Se conserva esa pausa: no se publica la bandera
local de activacion recurrente ni se alteran horarios. La limpieza Silver
si debe estar en main para evitar su reversion en consolidaciones futuras.
fec_ini no existe en el esquema productivo de fct_ventas_bi y queda fuera,
igual que servicios HTTP, Power BI, dependencias opcionales y temporales ajenos.
La publicacion Git no reconstruye tablas ni cambia las vistas actuales.

El usuario reporto haber cambiado su preferencia de consola a 1 GiB
(1073741824 bytes). No se verifico esa preferencia; los 2 GiB de las
pruebas siguientes son historicos. Ninguno es un guardrail IAM obligatorio.
Las notas siguientes conservan la cronologia previa a esta integracion.

### Texto de clientes, 2026-10-25: desplegado y reconstruido

CSV de ventas revisado: 36153 registros con 24 columnas correctas; 213
direcciones contienen LF embebido, no corrupcion de FECHA_ACTUALIZACION.
Captura vigente en el catalogo local: clientes_v1@1.0.0,
masters/clientes.sql, via GENERIC_SQL_API, full_snapshot. Contrato con
nom_cli, dir_fis y dir_exa; no contiene dir_ent. No afirmar que dir_exa
equivale a direccion de entrega ni que la tabla eFactory carece de otros
campos no seleccionados. No se consulto el esquema remoto eFactory.

El usuario aprobo preservar Bronze y limpiar en Silver los tres campos
nom_cli/dir_fis/dir_exa. sil_clientes usa helpers.singleLineStr:
REGEXP_REPLACE de secuencias CR/LF por un espacio, seguido del trim habitual.
Conserva NULL, acentos, comas, comillas y espacios internos que no sean
saltos; no cambia columnas, claves, filtros ni deduplicacion. dim_cliente
hereda los campos y las vistas Mondelez de clientes/ventas leen esa
dimension. No cambia captura ni version 1.0.0.

Se desplegaron y reconstruyeron exclusivamente sil_clientes y dim_cliente.
Los datos ya exportados no cambian. La ruta historica dim_cliente_scd2 lee record_json
de sil_maestros_scd2, no sil_clientes: queda fuera de esta correccion para
no reescribir historicos/hashes ni alterar versionado SCD2.
Validacion: 20 pruebas unitarias focalizadas aprobadas, lint y formato del
nuevo test correctos. Compilacion Dataform con Mondelez activo: 255 targets,
cero errores; tres expresiones de limpieza en sil_clientes y dependencias
dim_cliente -> sil_clientes, vistas Mondelez -> dim_cliente confirmadas.
Prueba administrativa BigQuery solo con literales sinteticos: 12/12 casos
correctos, cero bytes procesados, job
job_nwzohhXD9Xfo3CR4yVxMr0ytGIbV. Incluye NULL, vacios, CR, LF, CRLF,
secuencias repetidas, extremos, acentos, comillas, comas, espacios internos
y tabulador interno. No prueba datos de negocio ni despliega modelos.

Publicacion selectiva autorizada: rama feat/clientes-single-line-text,
SHA 8b2b24ffef2fc97b81c6639c815c94bd342cd11d, solo helper, Silver y pruebas,
sin fusionar main ni incluir cambios ajenos. Compilacion administrada
7be1aa92-d60e-49a7-b123-655037ba42e0: al comparar con el grafo anterior,
solo cambia el SELECT de sil_clientes por las tres limpiezas.
Invocacion 1792949313-c049e487-63cf-4ed2-bf2c-2a097dfb9d8c:
2/2 tablas SUCCEEDED; invocacion de QA
1792949326-d33a909a-ca8c-4c27-9460-8a3e8cf129d3:
4/4 assertions SUCCEEDED. Sin transitivas ni full refresh incremental.

Ambas tablas conservan 54005 filas, mismas claves y esquema; huellas
agregadas de filas normalizadas antes/despues coinciden por empresa.
Direcciones con saltos antes: ctb40, ctm96, daroan41, roldan13, tinito94,
total284; despues cero en nom_cli, dir_fis y dir_exa. Fuentes staging y
clases no cambiaron. ACL Gold/Silver/SORT, SQL e IAM de las cuatro vistas
publicas preservados. Validacion administrativa de ventas Tinito de
septiembre2026, sin cache: mismas36153 filas, cero saltos en DIRECCION
y SOCIO_NEGOCIO, job_cXepCzZUFicsdn9JqYqHcANmLDME. No regenera CSV existentes.

Continuidad pendiente: el workflow efectivo factory-etl-consolidation-prod,
revision 000006-44c, sigue compilando gitCommitish main. Esta correccion se
publico en rama dedicada sin fusion autorizada; un ciclo futuro que compile
SQL anterior puede revertirla. No se cambio workflow, scheduler ni main.
La promocion a la fuente programada requiere aprobacion separada.

### Resultados descargables, 2026-10-25

Bucket privado factory-etl-prod-sort-magdalena-exports desplegado via
Terraform con aprobacion: tres altas, plan posterior sin cambios.
Rol sortExportFiles solo en el bucket: buckets.get y objects.create/get/list;
sin borrado, sobrescritura o IAM. UBLA/PAP activos, US-CENTRAL1, ciclo Delete
a partir de 30 dias, sin versiones ni soft delete. No cambio BigQuery.
Flag local prod enable_sort_consumer_exports=true; default false.
Ocho pruebas aprobadas. EXPORT DATA SELECT 1 con login normal Magdalena
funciono con overwrite=false y limite 2 GiB, un archivo/una fila; listado
Storage confirmado. Descarga final al equipo pendiente de confirmar fuera
del navegador integrado (timeout/ERR_FAILED), no ampliar IAM por ello.
Ver [bucket y uso](./propuesta-acceso-bigquery-sorti-mondelez.md#bucket-de-resultados-2026-10-25-desplegado-y-exportacion-verificada).

Correccion posterior del mismo dia: aplicado sortExportBucketPicker con
SOLO storage.buckets.list al proyecto para el selector Explorar de
Guardar resultados. Dos altas, otros bindings preservados y postplan cero.
Prueba consumidor del boton completa: extract bquxjob_3cd79bd_1a173e40f41
DONE sin error, archivo ventas-guardar-resultados-20261025-1628.csv de
31105 bytes confirmado. No se agrego permiso de borrado ni acceso a objetos
de otros buckets. La descarga al equipo sigue sin certificacion.

### Correccion de privilegios, 2026-10-24: aplicada y verificada

El usuario eligio corregir ambos hallazgos de la auditoria: sustituir su
jobUser por el rol personalizado sortQueryRunner y retirar dataform.admin
directo en seis repositorios UUID. Aplicados ambos planes tras aprobacion:
dos altas/una baja en prod y seis bajas de miembros IAM en estado LOCAL.
El rol final contiene solo jobs.create, config.get y projects.get con sus
prefijos BigQuery/Resource Manager. Google rechazo projects.list en el
primer intento; la correccion se aprobo y aplico despues.
Verificacion administrativa: otros bindings, ACL Gold/SORT/Silver/Control
y politicas de las cuatro vistas intactos; no se borraron repositorios.
Cuatro pruebas focalizadas aprobadas. Las membresias de grupos siguen sin
certificacion y falta prueba posterior del consumidor. Ver la
[correccion aplicada](./propuesta-acceso-bigquery-sorti-mondelez.md#correccion-de-privilegios-2026-10-24-aplicada-y-verificada).
Planes posteriores productivo selectivo y LOCAL normal: cero cambios.

### Ejecucion de acceso, 2026-10-24: estado vigente

El usuario aprobo ejecutar en produccion y publicar selectivamente una rama
dedicada, sin fusionar main ni incluir cambios ajenos. Ya se retiraron
domain:tinitot.com de billing.creator y resourcemanager.projectCreator en
la organizacion; los otros miembros, bindings y condiciones se preservaron.
La adopcion de estado Gold ya se realizo con bloqueo nativo, backup fresco
y sin force: BI READER y runtime WRITER ahora usan dataset_access.
Plan selectivo posterior sin cambios y ACL Gold intactas.
No volver a aplicar configuraciones antiguas con dataset_iam_member en Gold.

SQL autonomo y nueve grants ya aplicados. Dataform uso Git inmutable
564e622a408dfe5604ee125ad3583a4e4c31eb9a en la rama dedicada
feat/sort-magdalena-minimum-access tras fallar el workspace con HTTP500.
Compilacion ad619e92-7af6-4627-8f29-0b34d9729a75:
32/32 assertions y 4/4 vistas SUCCEEDED, sin reconstruir fuentes.
Consultas y contratos 18/25/6/10 verificados en metadatos reales.
Terraform agrego exactamente cuatro autorizaciones Gold, cuatro
dataViewer por vista y un jobUser del proyecto. ACL previas preservadas:
Gold seis originales mas cuatro vistas; SORT dos, Silver/Control intactos.
Plan selectivo posterior cero cambios. Configuracion local prod conserva
enable_sort_consumer_access=true; no reaplicar defaults false ni codigo
antiguo. No se fusiono main. Falta prueba con login normal de Magdalena:
verificacion administrativa no equivale a prueba del consumidor.
Sin MFA por decision expresa; nunca lectura al dataset completo.
Las notas del 23 siguientes son historicas y no describen el estado actual.

### Acceso del tercero: actualizacion 2026-10-23

Identidad vigente confirmada por el usuario: magdalena.mateu@tinitot.com,
cuenta administrada ya creada. Sustituye todas las propuestas anteriores,
incluidos mmateu@gssve.com, mmateu@tinitot.com y el piloto Outlook.
El trabajo de acceso es separado del despliegue SQL descrito abajo.
Ver el [inventario de acceso actual](./propuesta-acceso-bigquery-sorti-mondelez.md).

Se habilito solo orgpolicy.googleapis.com con Terraform bajo autorizacion
expresa del usuario para APIs necesarias; plan de un recurso y posterior
sin cambios. No se aplicaron grants ni se cambiaron ACL, SQL o workflows.
Politica efectiva legacy: C02iq6q4d, igual al customer de la organizacion.
Las llamadas de directorio siguen bloqueadas por scopes/permisos, pero el
usuario completo login normal por consola Admin. Evidencia visual:
Magdalena activa, en Comercial Tinito, sin roles administrativos; la lista
de grupos esta vacia. MFA desactivado y primer cambio de contrasena requerido.
No se cambio autenticacion gcloud ni configuracion del directorio.
El dominio hereda billing.creator y projectCreator; el grupo BI lee Gold.
Decision del usuario 2026-10-23 21:15 America/Caracas: no aplicar ni exigir
MFA para este acceso; documentado el riesgo residual de un unico factor.
No cambiar politicas MFA existentes. No certificar minimo privilegio sin
resolver los accesos por dominio. Su retirada afecta a todos los usuarios
del dominio y requiere aprobacion especifica; no se aplico.

Antes de un plan IAM aplicable, revisar tambien la cadena de wrappers que
leen auxiliares del mismo dataset sort y la incompatibilidad documentada
de dataset_iam_member con autorizaciones dataset_access.
No conceder lectura al dataset completo ni a auxiliares como atajo.
El usuario autorizo despues preparar una adaptacion Dataform SIN desplegar.
Los cuatro SQL publicos locales incorporan CTE de consultas compartidas:
solo leen tablas fisicas Gold; no leen auxiliares SORT. Los internos
conservan queries y assertions. Sin nuevos nodos, persistencia ni horarios.
Compilacion en ambos estados del flag y prod correcta; cuatro dry-runs
administrativos validan esquemas 18/25/6/10, sin ejecucion de datos.
515 pruebas aprobadas, dos fallos historicos excluidos y documentados.
No se desplego SQL ni se modifico IAM. Si se aprueba la adaptacion, solo
requiere cuatro autorizaciones en Gold y reconciliar alli la gestion del
lector BI Y del WRITER del runtime (module.service_account.gold_editor);
no requiere autorizaciones ni migracion runtime en sort.
Antes de cualquier grant: acceso heredado resuelto y plan selectivo aprobado.
MFA no es una puerta por decision expresa del usuario.

El usuario solicito despues SOLO preparar planes antes de aprobar su
ejecucion, incluida retirada global de las dos entradas de dominio.
Plan organizacional listo: dos delete de IAM member, conservando grupos y
usuarios explicitos; estado local aislado, no aplicado.
Manifiesto SQL de revision con cuatro targets y recuperacion listo;
sin SHA publicado ni compilationResult remoto, no ejecutado.
ACL Gold bloqueado: google6.50.0 no importa dataset_access y rechaza crear
una entrada ya existente. El plan preliminar2create2forget se descarto,
elimino y retiro su propuesta de codigo. No ejecutar esa migracion.
El usuario eligio investigar adopcion de estado sin escribir remoto.
Ensayo posterior: candidato local convierte exactamente BI READER y
runtime WRITER a dataset_access, conserva57recursos y lineage; reescribe
solo dependencias afectadas. Cinco pruebas correctas. Copia de configuracion
completa y backend LOCAL:16recursos no-op,cero altas/cambios/bajas/forget
y cero drift. Estado remoto reconsultado:serial112 y contenido semantico
identico (normalizar orden de check_results al comparar).
Propuesta solo en copia privada: fuente raiz mantiene gestores originales.
Adopcion requiere aprobacion expresa de escritura de estado, backup
actualizado, ventana exclusiva y configuracion coordinada; nunca force
ni plan/apply general. No ejecutar el candidato local como si fuera plan
GCS ni reutilizarlo si cambia el estado. Ver protocolo en la propuesta
de acceso. Ningun grant, state push ni despliegue de esta etapa aplicado.

El alcance vigente comprende vistas SQL y la correccion acotada de
seleccion diaria de inventario Gold aprobada el 2026-10-23, 13:56 Venezuela.
Ver [despliegue vigente](./despliegue-vistas-sort-mondelez.md).
Implementacion desplegada: QA general para cinco empresas sin bandera
del proveedor; Gold elige la captura completa por dia Venezuela antes del
detalle; SORT lee Gold sin publicacion adicional. Silver no se modifica.
PR #11 fusionado con autorizacion expresa, ampliada a cinco archivos para
incluir la declaracion de la tabla existente etl_batches en Gold:
main 2dc06352de721f99a8e6b66a069df43ac46261bc. No se fusiono la rama SORT
completa. CI del PR y de main aprobados; 402 pruebas locales aprobadas.
Despliegue Dataform dirigido: Gold 5/5 y SORT 4/4 SUCCEEDED.
Verificacion real: Gold 1866341 filas, SORT 50394 filas; 81 dias por
empresa, 2026-08-03 a 2026-10-23. Comparacion bidireccional de claves,
cantidades y campos: cero faltantes/sobrantes, fechas invalidas o mezclas.
Contratos publico de 10 campos e interno de 13 conservados.
La consolidacion ya compila el Gold corregido desde main; las vistas
SORT leen ese hecho sin otro ciclo. Siguiente ejecucion automatica de
22:00 Caracas aun no observada: no se disparo ni cambio su programacion.
Compilacion Gold 11199b56-5c4c-4a01-9034-4992cc0e1a88, invocacion
1792787432-b687bcdf-2baf-4bf5-b8ca-52f86b0bedcc.
Compilacion SORT 59d4fb62-140a-4e15-9484-07e69605d4cc, SHA
81415d6ff86d546495e46a6c98658825deee2413, invocacion
1792787603-388d3fe9-8f13-457b-907f-771b1d41015d.
Time travel Gold verificado antes de escribir; compilaciones anteriores
preparadas para recuperacion. Silver, maestros, ventas, BI, tabla y lock
de publicacion, ACL, revisiones de workflows y horarios sin cambios.
No modificar workflows, horarios, ingesta, permisos, ni borrar recursos.
Decision vigente del usuario, 2026-10-23 01:52 America/Caracas: opcion 1,
vistas dinamicas sobre Gold aprovechando la extraccion y consolidacion
existentes. Sin otro programador, workflow o ciclo de persistencia SORT.
Se posterga congelar atributos por corte e integrar SCD2; las descripciones
se consultan con los maestros actuales y pueden cambiar para dias previos.
La vista SORT de existencias ya no depende de la tabla persistida:
la adaptacion posterior se autorizo y desplego; no se eliminaron recursos.
La declaracion etl_batches se movio a Gold para independizar la QA de SORT.
El plan Terraform del dataset SORT no propone cambios. La correccion Gold
posterior es SQL Dataform, no una modificacion de infraestructura.
El plan anterior del workflow queda descartado: no aplicar ni modificar
workflows, orden de cargas, esquemas de ingesta o permisos. La excepcion
posterior para inventario Gold se limita a lo indicado al inicio.
Requisito confirmado: existencias conserva la ultima captura valida de
cada empresa/dia y permite consultar sus registros por FECHA_DATA.
No limitar a un unico estado global. Reutilizar el ciclo Gold existente;
no agregar procesos ni persistencia. La seleccion por captura completa
valida se ha desplegado y verificado en produccion; falta observar la
siguiente ejecucion automatica. Sin captura valida en un dia: no generar corte de
ese dia; conservar los anteriores con sus fechas reales.
Acuerdo posterior: FECHA_DATA y FECHA_ACTUALIZACION se representan en
America/Caracas, STRING de 14 digitos AAAAMMDDHHMMSS. Se corrigieron
las vistas de ventas y existencias; el despliegue SQL se completo:
SHA cf319221613754025e0cace8d475ac533a75b9a2,
compilacion e8dd5eb1-e514-4d66-802d-1dedc6ba1173 e invocacion
1792731748-4385d4bc-37b8-4422-abd5-3b18c0e93740 SUCCEEDED 3/3.
Solo tres vistas SORT, sin transitivas ni operacion de cortes. Produccion
verificada con las mismas filas/campos no temporales, fechas Venezuela de
14 digitos y 80 dias por empresa. Workflows, Gold, tabla de cortes y ACL
sin cambios. El commit/push incluyo solo tres SQL; documentos y pruebas
locales no se publicaron. No cambiar timestamps tecnicos ni reescribir
capturas historicas para esta representacion.

Cambio solicitado y desplegado el 2026-10-25: FECHA_ACTUALIZACION de ventas
pasa de registro a CURRENT_TIMESTAMP() al consultar, formateado en
America/Caracas con los mismos 14 digitos. SQL compartido por ventas
publica e interna; FECHA y el filtro de ventas siguen usando registro.
FECHA_DATA de existencias conserva su captura.
Commits selectivos publicados: ea9f0b41ad541b36c3e2026e8e8d7f693195e0c2
y 99ceb5a37a26dcec433b19d17948772983b9b217; no se fusiono main.
Compilacion 97c67eec-001d-49ac-876b-faeb5bad9936, invocacion
1792943360-202998f8-d6c9-4c69-ba20-85bca7b3728c: SUCCEEDED 2/2,
solo las dos vistas de ventas, sin transitivas ni reconstruir fuentes.
446308 filas por vista, cero diferencias no temporales, esquemas 25/29
conservados. Dos consultas reales por vista verificaron que la marca
Caracas coincide con el inicio de consulta y avanza entre consultas.
IAM por vista, ACL Gold/SORT y recursos no objetivo permanecen intactos.
34 pruebas SQL/inventario aprobadas. Pruebas de infraestructura separadas
y locales sin publicar con este bloque. Notas de postdespliegue locales;
los dos commits publicados conservan el estado previo a su ejecucion.

## 1. Instruccion de continuidad

Antes de implementar mas cambios, reconciliar el alcance arquitectonico
acordado con el mecanismo de cortes de existencias ya desplegado.
El usuario recuerda que se acordo una arquitectura sencilla, orientada
a datos, y cuestiona que el plan incluyera un publicador.
No tratar la implementacion existente como prueba de aprobacion.
No activar recurrencia, ampliar arquitectura ni eliminar recursos
durante esta revision. Inicialmente, solo lectura.

Este documento distingue hechos verificados de decisiones pendientes.
El inventario detallado es un registro historico: sus secciones antiguas
pueden contener decisiones sustituidas.

## 2. Objetivo y limites

- Exponer cuatro vistas contractuales del proveedor 0301 Mondelez desde Gold.
- Un unico dataset de consumo: factory-etl-prod.sort, us-central1.
- Terraform para infraestructura; Dataform administrado para modelos,
  assertions, tablas y vistas. No usar un ejecutor SQL Python alternativo.
- Contratos de clientes, ventas, existencias y articulos aprobados
  funcionalmente; conservar reglas de negocio.
- Mantener source_empresa como trazabilidad SQL; no sustituirla por
  CODIGO_GRUPO ni replicar articulos por grupo.
- Servicios adicionales y publicador comun de cuatro entidades fuera
  del alcance vigente.
- Creacion de usuarios y permisos del tercero excluidos del despliegue SQL.
  La cuenta administrada magdalena.mateu@tinitot.com ya fue creada por la
  organizacion; no crear otras identidades. Su acceso se revisa por separado
  conforme a la actualizacion de acceso al inicio de este documento.

## 3. Estado inicial verificado (historico)

Los conteos y la publicacion de esta seccion corresponden al despliegue
inicial, anterior a la correccion Gold indicada en los highlights.

Dataset sort creado con Terraform, protegido contra destruccion.
ACL directo verificado: projectOwners OWNER y la cuenta interna de
ejecucion WRITER, equivalente a roles/bigquery.dataEditor:
factory-etl-runtime-prod@factory-etl-prod.iam.gserviceaccount.com.
No se concedieron permisos al consumidor ni se cambio la politica de dominio.
Los permisos heredados no quedan anulados por este ACL.

| Vista en sort | Campos publicos, incluida source_empresa | Filas |
|---|---|---:|
| vw_mondelez_clientes | 18 STRING | 29428 |
| vw_mondelez_ventas | 25 STRING | 443725 |
| vw_mondelez_articulos | 6 STRING | 406 |
| vw_mondelez_existencias | 8 STRING y 2 NUMERIC | 49737 |

Consultas de aceptacion sin cache, maximo 2 GiB por consulta:
ningun NULL publico, sin claves tecnicas expuestas.
DISPONIBLE y UNIDAD_SIMPLE_X_EMPAQUE son NUMERIC, no STRING.

Existencias: 80 cortes por empresa, 2026-08-03 a 2026-10-22;
una captura por empresa/dia y cero claves publicas duplicadas por corte.
Se verifico idempotencia: reejecutar solo la operacion Dataform no cambio
filas, capturas ni timestamps de publicacion.

## 4. Distincion arquitectonica inicial (historico)

Clientes, ventas y articulos son vistas logicas sobre Gold y auxiliares.
Existencias usaba antes de la adaptacion:

- Gold: vw_inventario_capturas_qa y fct_inventario_diario_validado.
- sort: vw_mondelez_existencias_candidata.
- Una operacion SQL Dataform llamada pub_mondelez_existencias.
- Tabla append-only del mismo nombre y tabla inventario_publication_lock.
- Vista interna del ultimo corte validado y wrapper publico contractual.

No hay servicio externo publicador desplegado.
No hay publicacion comun/versionada de las cuatro entidades.
Pero conservar cortes y ejecutar una transaccion SI agrega persistencia
y mantenimiento; no minimizar esa complejidad llamandola simplemente SQL.

El resumen historico de la sesion describe la publicacion de inventario
como previamente aprobada; el usuario acaba de cuestionar ese alcance.
Se debe buscar evidencia de los acuerdos originales y exponer la diferencia.
La decision posterior fue la opcion 1 indicada al inicio; la persistencia
existente se conserva, pero ya no alimenta la vista de consumo.

## 5. Evidencia del despliegue inicial y Git (historico)

Rama publicada: feat/sort-managed-dataform.
Revision funcional compilada:
2374d3e431be2df4e8ec89b2ab9929d627a4502a.
Ultimo commit publicado antes de este handoff:
79b0fa986b9c5006b2cf0950c7d1c850b0a194b4, documentacion de aceptacion.
Este handoff aun no tiene commit al crearlo.

Dataform:
- Repositorio: projects/factory-etl-prod/locations/us-central1/repositories/factory-etl-prod.
- Compilacion: 31d2e9ea-8e11-4375-8278-b2d21a0481f1, SHA funcional anterior.
- Invocacion final: 1792724476-9d02d8ab-95d1-40bb-93f2-22ae224c7e96.
  SUCCEEDED: 51/51 acciones; 14 modelos/operacion y 37 assertions,
  incluidas assertions de fuentes, sin reconstruir modelos fuente ajenos.
- Reejecucion de existencias:
  1792724702-0a97ae5e-5288-45db-b48c-e14eecf2ac23, SUCCEEDED.
  El identificador abreviado que se registro antes era incorrecto.
- Proyecto Dataform en subdirectorio dataform:
  codeCompilationConfig.pipelineConfig = {pipelineType: DATAFORM, path: dataform}.
  Omitirlo produce 404 Can't find package.json; no es ausencia del repo.
- defaultDatabase y variables deben apuntar a prod; los defaults locales
  de workflow_settings.yaml apuntan a dev.
- Ejecucion con invocationConfig.serviceAccount de la cuenta interna.
  Seleccion explicita includedTargets, dependencias/dependientes transitivos
  desactivados para no reconstruir todo Gold.

## 6. Incidentes resueltos y lecciones

1. Crear sort sin ACL explicito fallo por restriccion de dominio:
   BigQuery agrega al creador personal como OWNER por defecto.
   Politica efectiva legacy allowedPolicyMemberDomains: C02iq6q4d.
   El ACL inicial projectOwners explicito permitio crearlo.
   Terraform ignora modificaciones posteriores de access y administra
   el permiso runtime por recurso IAM member independiente.
2. Se introdujo equivocadamente scripts/deploy_sort.py como ejecutor.
   Fue retirado con su test. No recrearlo. Terraform + Dataform es el
   camino exigido por el usuario y revisado con Claude Opus 5.5.
3. Primera ejecucion administrada fallo por tres articulos sin maestro:
   ctb uno, tinito dos. Se preservo el control de cobertura.
4. Usuario lanzo full 0086cc75-bee9-40a1-85c6-a20d6e1b9ddc,
   SUCCEEDED, 21:57-22:03 Venezuela. No se lanzo duplicado.
   dim_articulo/dim_almacen actualizados 22:02:29 Venezuela.
   Mismo hecho de inventario previo: faltantes pasaron de tres a cero.
   Luego la reejecucion administrada completo las 51 acciones.
5. No equiparar workflow full SUCCEEDED con consolidacion completa:
   revisar child/ejecucion Dataform y frescura real cuando corresponda.

## 7. Pendientes reales

- Primero: revisar alcance de persistencia/publicacion de existencias
  frente al acuerdo de arquitectura sencilla.
- Recurrencia NO habilitada. El control local `enable_mondelez_views`
  permanece false por defecto y requiere `enable_sort_dataset`.
  El workflow de consolidacion desplegado compila main sin habilitar
  Mondelez. No fusionar ramas ni activar modelos durante esta pausa.
- Las vistas logicas consultan fuentes actuales; nuevos cortes de
  existencias necesitan ejecutar el mecanismo actual hasta decidir otra cosa.
- Acceso del tercero, identidad admitida, vistas autorizadas y pruebas
  positivas/negativas quedan pendientes y fuera del despliegue actual.
- No fusionar ni aplicar Terraform general sin autorizacion.

## 8. Archivos y seguridad operativa

- [Inventario vigente y evidencia](./despliegue-vistas-sort-mondelez.md).
- [Dataset y permiso runtime](../terraform/sort_dataset.tf).
- [Pruebas Terraform](../terraform/tests/sort_dataset.tftest.hcl).
- [Modelos Mondelez](../dataform/definitions/mondelez).
- [Pruebas de contratos SQL](../tests/unit/test_sort_sql_contracts.py).

El worktree es compartido y contiene numerosos cambios ajenos sin commit:
no git add -A, no reset/checkout destructivo y no publicar cambios ajenos.
El plan Terraform general incluye cambios ajenos y reemplazo de staging:
no aplicarlo. Revisar planes selectivos con exactitud antes de aplicar.
No incluir estado, planes, credenciales ni evidencias privadas en Git.

Evidencias adicionales de la sesion anterior estan en:
C:\Users\francisco.pino\.copilot\session-state\37d60d8b-1279-4470-bdaa-a2f5245d049d\files.
Usar solo si hace falta, con lecturas acotadas. No confundir validaciones
historicas de dev/sinteticas con la evidencia final sort-managed-retry y
sort-final de produccion.
