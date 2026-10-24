# Acceso de solo lectura a Mondelez en BigQuery para SORT

## Ejecucion autorizada, 2026-10-24: estado vigente

Este apartado prevalece sobre las etapas historicas siguientes.
El usuario autorizo retirar los dos permisos heredados incompatibles,
ejecutar la adopcion de gestion ACL Gold y habilitar el acceso minimo.

- Aplicada la retirada de domain:tinitot.com de roles/billing.creator y
  roles/resourcemanager.projectCreator en la organizacion 748544230317.
  Comparacion antes/despues: otros bindings, miembros y condiciones intactos.
  Plan posterior sin cambios.
- Aplicada la adopcion de los dos recursos Gold existentes: BI READER y
  runtime WRITER, ahora dataset_access. Snapshot fresco, serial/lineage
  comprobados, state push con bloqueo y sin force. No se recrearon grants;
  plan selectivo posterior cero cambios cloud y seis ACL Gold preservadas.
  Nunca volver a aplicar gestores dataset_iam_member antiguos sobre Gold.
- SQL autonomo desplegado desde la rama dedicada
  feat/sort-magdalena-minimum-access, SHA
  564e622a408dfe5604ee125ad3583a4e4c31eb9a, sin fusionar main.
  Crear workspace Dataform habia fallado con HTTP500; se uso compilacion
  Git inmutable ad619e92-7af6-4627-8f29-0b34d9729a75, sin workspace.
  Consultas remotas coinciden con las cuatro revisadas. Controles previos:
  invocacion 1792866182-3a8616e4-f2d9-454d-9a8d-a7fca4ce0999,
  32/32 assertions SUCCEEDED, sin reconstruir fuentes.
  Despliegue 1792866248-25ab0313-255d-4381-9b2e-5af1086c1525:
  4/4 vistas SUCCEEDED, sin transitivas, reconstruccion ni publicador.
  Metadatos productivos: consultas iguales salvo whitespace exterior
  eliminado por DDL; esquemas ordenados de 18/25/6/10 campos exactos.
- Aplicado el plan selectivo revisado: nueve altas, cero cambios/bajas.
  Cuatro autorizaciones Gold, cuatro dataViewer por vista y un jobUser
  de factory-etl-prod para user:magdalena.mateu@tinitot.com.
  Comparacion administrativa antes/despues: seis ACL Gold previas intactas
  mas cuatro vistas; SORT conserva sus dos ACL, Silver y Control intactos.
  IAM de cada vista y del proyecto solo agrega el miembro/rol previsto;
  no se observaron cambios en otros bindings o condiciones.
  Ninguna ACL de dataset agrega a Magdalena. Plan selectivo posterior,
  incluidos los dos gestores Gold adoptados: cero cambios.
  Configuracion local de prod conserva enable_sort_consumer_access=true;
  los defaults y el ejemplo siguen false, no son valores para reaplicar
  prod sin revisar. No usar configuracion antigua ni apply general.
- Prueba con login normal de magdalena.mateu@tinitot.com pendiente.
  Sin impersonacion ni solicitud de credenciales; no afirmar frescura.
  MFA no se exige por decision expresa; riesgo residual documentado.

Verificacion automatizada local: compilacion aislada correcta, cuatro
consultas identicas al manifiesto, 11 pruebas Terraform aisladas y 28
pruebas focalizadas de contratos SQL correctas. Una prueba documental
historica excluida; no se certifica todo el worktree compartido.

## Inventario actual y acceso pendiente, 2026-10-23

Esta seccion sustituye las identidades y propuestas historicas de abajo
para el trabajo de acceso. No autoriza aplicar grants del consumidor.
Identidad unica confirmada por el usuario:
**magdalena.mateu@tinitot.com**, cuenta administrada creada dentro de la
organizacion. Quedan sustituidos mmateu@gssve.com, mmateu@tinitot.com y
el piloto Outlook. No se crea otra cuenta.

### Alcance de la comprobacion

Se consultaron metadatos cloud actuales con la sesion administrativa
existente, sin impersonacion, consultas SQL ni jobs. No son pruebas del
consumidor y no certifican frescura de los datos. El inventario comprende
la organizacion y los recursos relevantes para este acceso, no una
auditoria exhaustiva de todos sus proyectos, datos y permisos.

- Proyecto factory-etl-prod, numero 864267233447, padre directo:
  organizacion 748544230317, tinitot.com; sin carpeta intermedia.
- Customer ID de la organizacion: C02iq6q4d. Politica efectiva
  iam.allowedPolicyMemberDomains: solo C02iq6q4d.
- Politica efectiva iam.managed.allowedPolicyMembers: enforce=false.
  Esto no desactiva la restriccion legacy anterior.
- Organization Policy v2: 20 politicas explicitas en la organizacion,
  cero en el proyecto y cero custom constraints listadas. Se conservan
  las restricciones de creacion/carga de claves de servicio, concesiones
  automaticas a cuentas predeterminadas y acceso publico de Storage.
- No se observaron bindings directos de Magdalena en IAM del proyecto
  ni de la organizacion. La busqueda de Cloud Asset en la organizacion
  tampoco encontro bindings directos para su correo; esto no prueba
  ausencia de permisos por grupos, dominio, condiciones u otras fuentes.
- El dominio tinitot.com tiene roles/billing.creator y
  roles/resourcemanager.projectCreator en la organizacion. Son accesos
  adicionales a la lectura de vistas; no se revocaron ni modificaron.
- bi-analistas@tinitot.com tiene lectura del dataset Gold y permisos de
  jobs/metadatos/sesiones de lectura en el proyecto. Debe comprobarse que
  Magdalena no pertenece directa, transitiva o automaticamente a ese
  grupo ni a grupos administrativos.

### Identidad y grupos: API limitada y consola verificada

Admin Directory respondio 403 insufficient_scope: el token administrativo
actual no tiene scopes de lectura del directorio. Cloud Identity esta
habilitada; usando factory-etl-prod como proyecto de cuota tambien
respondio 403 al consultar bi-analistas y los grupos administrativos.
Esas llamadas no permitieron verificar los atributos del usuario ni
sus membresias; su resultado no sustituye la comprobacion posterior.

No se habilito admin.googleapis.com: habilitarla no resolveria los scopes
ni la autorizacion del directorio. No se dieron roles, ampliaron scopes
del token CLI ni concedio delegacion a cuentas de servicio.
El usuario autorizo login normal por consola y completo personalmente
el acceso. Se inspecciono Google Admin como francisco.pino@tinitot.com,
sin cambiar la autenticacion de gcloud y sin modificar configuraciones:

- Magdalena aparece activa, creada el 2026-10-23, en Comercial Tinito.
- El panel indica que no tiene privilegios ni roles de administrador.
- La pestana Grupos indica expresamente que no pertenece a ningun grupo.
  Es evidencia de la lista de membresias de la consola en ese momento;
  no una evaluacion independiente de membresias dinamicas o transitivas.
- Verificacion en dos pasos desactivada. Su unidad permite activarla,
  pero la implementacion obligatoria esta desactivada.
- Cambio de contrasena obligatorio en el proximo inicio de sesion.

Decision posterior del usuario, 2026-10-23 21:15 America/Caracas:
no se aplicara MFA ni se exigira como puerta de este acceso. La cuenta
permanece sin segundo factor; se documenta el riesgo residual de acceso
con un unico factor. No se deshabilita ninguna proteccion existente ni
se modifica una politica organizacional. Se mantiene el primer cambio
de contrasena requerido por el directorio. No se solicitaron credenciales.
Los roles por dominio siguen pendientes aunque la lista de grupos este vacia.

Recomprobacion cloud posterior a esa decision: domain:tinitot.com conserva
billing.creator y resourcemanager.projectCreator, ambos sin condiciones.
Los grants explicitos de los grupos administrativos permanecen separados;
no existe binding directo de Magdalena en la organizacion o el proyecto.
Retirar el miembro de dominio afectaria a todos sus usuarios, no solo a
Magdalena. Este alcance requiere aprobacion especifica antes de modificarlo;
no esta administrado actualmente por este Terraform.

### Vistas y ACL observados en produccion

Las cuatro interfaces existen como VIEW en sort, us-central1. Sus
politicas individuales no devolvieron bindings. El ACL del dataset sort
conserva projectOwners OWNER y el runtime interno WRITER; no contiene
autorizaciones de vistas. Hay 11 objetos, incluidos auxiliares y las
tablas de publicacion preexistentes: nunca dar dataViewer al dataset.

| Vista publica | Dependencia directa actual |
|---|---|
| sort.vw_mondelez_clientes | sort.vw_mondelez_clientes_interna |
| sort.vw_mondelez_ventas | sort.vw_mondelez_ventas_interna |
| sort.vw_mondelez_articulos | factory_etl_gold.dim_mondelez_articulo_enriquecido |
| sort.vw_mondelez_existencias | sort.vw_mondelez_existencias_interna |

Clientes y ventas internas leen Gold y sort.vw_mondelez_grupos.
Existencias interna lee sort.vw_mondelez_existencias_candidata; esta lee
Gold y grupos. Articulos enriquecidos lee dos tablas Gold.
El grafo observado no requiere lectura directa de Silver ni Control.
No se presupone que ese grafo permanezca igual despues de otro despliegue.

Gold conserva projectWriters/runtime WRITER, projectOwners/runtime OWNER
y bi-analistas/projectReaders READER, sin entradas de vistas autorizadas.
Silver conserva sus cuatro autorizaciones de vistas BI de Gold.
Control conserva sus ACL existentes. No se modifico ninguno.

Hay dos puertas tecnicas antes de preparar un plan IAM aplicable:

1. La documentacion de BigQuery exige que una vista autorizada este en
   un dataset distinto al usado por su consulta fuente. Tres wrappers
   publicos referencian auxiliares dentro de sort. No proponer autorizacion
   del dataset completo ni lectura directa de auxiliares para resolverlo.
   Revisar una solucion Dataform acotada que mantenga las cuatro interfaces,
   contratos y comportamiento, sin nueva persistencia ni recurrencia.
   La preparacion local posterior se describe abajo; no se desplego SQL.
2. El proveedor Terraform advierte que dataset_iam_member elimina
   autorizaciones de vistas y no debe combinarse con dataset_access en
   el mismo dataset. Gold tiene un dataset_iam_member para el grupo BI;
   sort tiene otro para el runtime. Cualquier migracion necesaria de su gestion
   debe preservar exactamente los grants existentes, planificar el
   estado de forma separada y recibir aprobacion. No quitar y recrear
   permisos para forzar esa migracion.

### Unico cambio cloud autorizado y verificado

El usuario autorizo habilitar solo las APIs de directorio/politicas
necesarias, sin nuevos roles ni cambios de autenticacion.
Se habilito exclusivamente orgpolicy.googleapis.com mediante
[Terraform de auditoria](../terraform/sort_access_audit.tf), con
enable_sort_access_audit_api=true en la configuracion local de prod.
El default sigue false; existe guardia de proyecto y entorno y
disable_on_destroy=false. No concede permisos para usar la API.

Se reviso el plan guardado: una creacion, cero cambios y cero destrucciones,
solo google_project_service.sort_access_org_policy[0].
Aplicacion: un recurso agregado, cero modificados y cero destruidos.
Estado ENABLED verificado por Service Usage y plan selectivo posterior
sin cambios. Terraform validate correcto y nueve pruebas focalizadas
aprobadas con proveedores mock. Backend prod y directorio de datos
Terraform aislado; sin apply general ni cambios productivos a ACL,
modelos o workflows.
Las evidencias JSON y planes permanecen fuera de Git en la sesion.

### Adaptacion Dataform preparada, no desplegada

El usuario autorizo preparar cambios revisables sin desplegar.
Las consultas de negocio se extraen a
[mondelez_queries.js](../dataform/includes/mondelez_queries.js) y se
reutilizan tanto en los seis modelos existentes como en las cuatro
interfaces publicas. Los wrappers incorporan grupos y transformaciones
como CTE, no como tablas o vistas adicionales.

Las consultas publicas compiladas solo leen tablas fisicas Gold:

| Interfaz preparada | Fuentes Gold |
|---|---|
| Clientes | dim_cliente, dim_pais, dim_estado, dim_ciudad, dim_vendedor |
| Ventas | fct_ventas_gold, dim_cliente, dim_pais, dim_estado, dim_ciudad, dim_articulo, dim_proveedor |
| Articulos | dim_articulo, dim_mondelez_producto_canonico |
| Existencias | fct_inventario_snapshot, dim_articulo, dim_almacen |

No hay referencias SQL a sort, Silver, Control ni vistas Gold intermedias.
Se conservan como dependencias Dataform los modelos internos y sus
assertions: el consumidor no consulta sus datos y el ejecutor interno
sigue sujeto a sus controles. No se eliminan los auxiliares existentes.
Gold, Silver, seleccion diaria, contratos, horarios y persistencia
no cambian. El grafo conserva 106 tablas/vistas y 124 assertions.

Validaciones locales y administrativas:

- Compilacion con Mondelez habilitado y deshabilitado, sin errores;
  deshabilitado conserva las cuatro interfaces inactivas.
- Compilacion con proyecto/default database factory-etl-prod y variables
  productivas; las cuatro interfaces solo referencian tablas Gold de prod.
- Comparacion de queries compiladas antes/despues: todos los modelos
  excepto los cuatro publicos son identicos tras trim inicial/final.
  Se conservan todas las dependencias de assertions previas.
- Dry-run administrativo BigQuery de las cuatro consultas compiladas,
  sin ejecutar datos, crear jobs persistidos ni desplegar vistas:
  contratos 18/25/6/10 campos correctos; solo DISPONIBLE y
  UNIDAD_SIMPLE_X_EMPAQUE son NUMERIC, todos los demas STRING.
  Limite configurado: 2 GiB; estimaciones: clientes 9680279,
  ventas 362765814, articulos 1251267 y existencias 165293533 bytes.
- El CLI bq local fallo antes de conectar por permisos de lectura en su
  instalacion. No se modifico ni reparo; se valido con requests dryRun
  explicitos del SQL compilado por Dataform, sin ejecutor Python.
- Ruff y formato correctos. Pruebas focalizadas y de encoding:
  515 aprobadas y dos excluidas por fallos de linea base reproducidos:
  test_current_deployment_documentation_has_no_http_scope prohibe enlaces
  documentales; test_fact_sql_preserves_history_signs_and_inventory_barcode_scope
  aun exige el hecho de inventario anterior. No se corrigieron expectativas
  historicas ajenas a este acceso.

Esto verifica preparacion, sintaxis, referencias y esquema, no igualdad
de resultados de datos ni acceso real del consumidor. No se ejecutaron
consultas de datos ni se certifico frescura.

Si se aprueba y despliega esta adaptacion, la autorizacion propuesta se
simplifica a cuatro entradas de vistas en el ACL de Gold, una por interfaz.
No se necesita autorizar vistas en sort ni migrar su permiso runtime.
La gestion del lector BI y del WRITER del runtime en Gold debe
reconciliarse con dataset_access antes de combinarla con vistas
autorizadas, preservando ambos permisos existentes.
No se implemento ni aplico esa migracion ni permisos del consumidor.

### Planes solicitados para revision, sin autorizacion de ejecucion

El usuario solicito preparar la retirada de las dos entradas de dominio
para toda la organizacion, preservando los grants explicitos de
administradores, y presentar los planes de SQL/ACL antes de ejecutarlos.
No se aplicaron esos cambios. La decision de no exigir MFA sigue vigente.

**A. Retirada de roles por dominio: plan Terraform generado.**

| Organizacion | Rol | Unico miembro que se retiraria |
|---|---|---|
| 748544230317 | roles/billing.creator | domain:tinitot.com |
| 748544230317 | roles/resourcemanager.projectCreator | domain:tinitot.com |

El plan contiene exactamente dos delete de
google_organization_iam_member, no destruccion de la organizacion ni
reemplazo de bindings/politica completos. Conserva en billing.creator
group:gcp-billing-admins@tinitot.com y user:PINOFD@gmail.com; en
projectCreator conserva group:gcp-organization-admins@tinitot.com y
user:PINOFD@gmail.com. Los demas bindings no se modifican.

Impacto intencional: todos los usuarios que dependan exclusivamente del
grant de dominio perderian esas dos capacidades, no solo Magdalena.
Esto no elimina proyectos o cuentas de facturacion existentes ni revoca
accesos a datos por si mismo. Se genero un diff esperado de IAM para
comparar despues de una eventual aplicacion; la politica actual mantiene
ambos miembros de dominio y etag BwZYeHt4pKw= al revisar el plan.

La simulacion usa backend LOCAL privado y dos imports de lectura, sin
importar ni modificar el estado remoto productivo. El plan binario y
los estados no se versionan. Releer IAM y regenerar el plan si cambia
la politica, el estado local o el alcance antes de solicitar su aplicacion.

**B. Despliegue SQL: manifiesto de revision generado, no invocacion lista.**

Se recompilo localmente para prod y se compararon los cuatro esquemas
con metadatos cloud actuales y las respuestas dryRun previas: nombres,
tipos y orden coinciden exactamente (18/25/6/10 campos). Las queries
coinciden con las que ya pasaron dryRun y solo referencian tablas Gold.
El manifiesto privado incluye hashes SHA256 de las once fuentes
implicadas, las cuatro consultas propuestas y las cuatro consultas
actuales para recuperacion.

Seleccion prevista: exactamente las cuatro interfaces publicas de sort,
runtime interno, sin dependencias/dependientes transitivos ni full refresh.
Antes de invocarlas se deben verificar explicitamente sus assertions
existentes sin reconstruir fuentes. No ejecutar el publicador.
No se modifican tablas, modelos fuente, workflows ni horarios.

Falta promocion selectiva de las fuentes revisadas a un SHA inmutable:
no se creo commit/push ni compilationResult remoto. El manifiesto tiene
sourcePublishedCommit=null y no es una invocacion ejecutable ni una
autorizacion para publicar cambios ajenos del worktree.

**C. Gestion ACL Gold: adopcion offline ensayada, pendiente de aprobacion.**

Ademas del lector BI de la raiz, existe
module.service_account.google_bigquery_dataset_iam_member.gold_editor:
WRITER del runtime. Ambos gestores IAM deben retirarse o migrarse antes
de administrar autorizaciones de vistas en Gold; no basta migrar el BI.
Se deben preservar todas las entradas, incluido el OWNER del runtime
que no es objeto de esta migracion.

El proveedor fijado google 6.50.0 no admite import de dataset_access.
Su creacion falla si encuentra la misma entrada ACL existente:
resourceBigQueryDatasetAccessPatchCreateEncoder devuelve
"Unable to create DatasetAccess, existing object already found".
Por ello se descarto y elimino el plan preliminar de dos create y dos
forget, aunque tuviera cero delete. No es un plan ejecutable valido.
La propuesta de codigo de migracion se retiro, conservando los gestores
IAM actuales y sus permisos hasta decidir el metodo de adopcion.

No se quito/recreo un grant para sortear el bloqueo ni se modifico el
estado remoto. El usuario eligio investigar una adopcion de estado
revisable que conserve ambos grants gestionados por Terraform, sin
autorizar escritura remota ni apply.

Se preparo una transformacion offline estrictamente acotada:

| Direccion original | Direccion propuesta | ACL preservada |
|---|---|---|
| google_bigquery_dataset_iam_member.powerbi_group_gold_reader[0] | google_bigquery_dataset_access.powerbi_group_gold_reader[0] | READER bi-analistas@tinitot.com |
| module.service_account.google_bigquery_dataset_iam_member.gold_editor | module.service_account.google_bigquery_dataset_access.gold_editor | WRITER factory-etl-runtime-prod@factory-etl-prod.iam.gserviceaccount.com |

La copia original tiene 57 recursos y serial112. El candidato local
conserva lineage y numero de recursos, propone serial113 y cambia solo
los dos recursos indicados y las referencias de dependencia que apuntan
a sus direcciones anteriores. Outputs, checks y demas atributos y
metadatos se preservan. El OWNER del runtime y todas las otras ACL
siguen intactos, fuera del alcance de esta adopcion.

El preparador exige formato/version de estado y esquema del proveedor
exactos, comprueba proyecto, dataset, roles, identidades, indices,
ausencia de condiciones y de destino existente. No sobrescribe evidencia
previa y no contiene comandos cloud ni state push. Se descarta metadata
privada del proveedor solo para las dos instancias cuyo tipo cambia,
no para otros recursos. Es una conversion manual de estado, no un import
oficial ni un moved soportado por el proveedor.

Ensayos realizados exclusivamente con backend LOCAL:

- Ensayo minimo: dos grants leidos por el proveedor como dataset_access,
  plan con cero altas, cambios o bajas. Normalizacion inicial de strings
  opcionales vacios corregida en el candidato posterior.
- Ensayo con copia de configuracion completa, estado candidato y variables
  prod: dos targets y sus dependencias, 16 recursos no-op, cero acciones
  create/update/delete/forget y cero entradas resource_drift.
  Esto no es un plan general ni prueba que el worktree completo no tenga
  cambios ajenos.
- Cinco pruebas del preparador aprobadas: conservacion de estado y
  dependencias, rechazo de identidad equivocada, grant condicionado,
  destino ocupado y version de esquema inesperada.
- Relectura del estado remoto: mismo serial112, lineage y contenido
  semantico. El orden de la lista check_results varia al serializarse;
  normalizar su orden antes de comparar evita falsos positivos.

Los estados original, candidato y ensayo son privados y permanecen
fuera de Git. No son artefactos publicables ni planes para aplicar
directamente contra el backend GCS.

Puertas antes de cualquier adopcion productiva:

1. Aprobar explicitamente el cambio de estado remoto como operacion
   separada de aplicar IAM o SQL. La autorizacion de investigar no lo permite.
2. Revisar el preparador y el diff de configuracion de los dos gestores.
   La configuracion propuesta usa dataset_access, prevent_destroy y
   removed con destroy=false para las direcciones anteriores. Actualmente
   esa propuesta solo existe en la copia privada del ensayo; la raiz del
   repositorio conserva sus gestores IAM originales.
3. Acordar ventana exclusiva de Terraform/CI, confirmar que nadie escribe
   estado ni IAM y coordinar la configuracion nueva con la adopcion.
   Nunca ejecutar la configuracion antigua contra el estado convertido.
4. Obtener backup nuevo del estado remoto/version GCS y ACL; comprobar
   lineage, serial y hashes antes de regenerar el candidato. No reutilizar
   serial112/113 si cambia el estado. Repetir el ensayo local con esa copia.
5. Solo con aprobacion especifica, usar el mecanismo nativo de escritura
   de estado con sus protecciones de lineage/serial, sin force ni saltos
   de bloqueo. No escribir el backend mediante uploads ad hoc.
6. Leer inmediatamente el estado y ACL reales, y verificar el plan
   selectivo contra el backend prod: cero cambios cloud y grants exactos.
   Si no coincide, detenerse antes de autorizar vistas o dar grants.
   El respaldo permitiria una recuperacion solo de estado, con nueva
   revision de concurrencia; nunca reponer una version antigua a ciegas.

Resultado: la adopcion es tecnicamente viable en el ensayo, pero sigue
requiriendo revision y aprobacion por tratarse de manipulacion excepcional
de estado. No se ejecuto state push ni apply, ni se modifico IAM productivo.

Fuentes del proveedor fijado:
[import no soportado](https://github.com/hashicorp/terraform-provider-google/blob/v6.50.0/website/docs/r/bigquery_dataset_access.html.markdown),
[comportamiento ante entrada existente](https://github.com/hashicorp/terraform-provider-google/blob/v6.50.0/google/services/bigquery/resource_bigquery_dataset_access.go).
Referencia operativa:
[protecciones y advertencia de state push](https://developer.hashicorp.com/terraform/cli/commands/state/push).

**D. Permisos del consumidor: etapa posterior, no aplicada.**

Tras resolver C y desplegar B con aprobacion: revisar un plan separado
con cuatro dataViewer individuales, un jobUser en factory-etl-prod y
cuatro autorizaciones de vistas en Gold. Nunca dataViewer del dataset
sort completo, ni grant directo de fuentes o auxiliares al consumidor.

### Matriz objetivo y puertas de aprobacion

| Recurso | Grant nuevo al consumidor |
|---|---|
| Cada una de las cuatro vistas publicas | roles/bigquery.dataViewer por vista |
| factory-etl-prod, ejecucion de consultas | roles/bigquery.jobUser |
| Dataset sort completo y objetos auxiliares | Ninguno |
| Gold, Silver y Control | Ninguno |
| Organizacion, carpetas y cuentas de servicio | Ninguno |

Las autorizaciones de fuentes se conceden a las vistas, no al usuario.
Antes de aplicar IAM: revalidar grupos y mantener el cambio de contrasena
del primer login conforme a la configuracion del directorio; MFA no exigida
por decision del usuario;
aprobar y resolver la retirada organizacional de los accesos por dominio,
con su impacto en otros usuarios explicitamente aceptado;
aprobar/desplegar la adaptacion preparada y la gestion Terraform de ACL;
revisar un plan selectivo de habilitacion aditivo, sin reemplazos ni bajas
de grants preexistentes en datasets.
Los roles de dominio detectados requieren una decision organizacional
separada; no se elimina un grant global para resolver solo este piloto.

La aceptacion posterior requiere login normal de Magdalena: SELECT y
descarga sobre las cuatro vistas, denegacion de acceso directo a fuentes
y auxiliares, y comprobacion de ausencia de permisos de escritura sin
intentar mutaciones de datos productivos. Las pruebas administrativas
no sustituyen esas evidencias. No se declara listo el acceso.

Referencias:
[vistas autorizadas](https://cloud.google.com/bigquery/docs/authorized-views),
[incompatibilidad IAM/ACL del proveedor](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/bigquery_dataset_iam).

## Propuestas y decisiones historicas

> Propuesta historica; sus identidades, alternativas y referencias no
> autorizan cambios. El acceso del tercero sigue fuera del
> [despliegue vigente de vistas](./despliegue-vistas-sort-mondelez.md).

Fecha: 2026-10-22
Estado: propuesta para revision; no se aplicaron permisos ni se desplegaron recursos.

## Despliegue pausado y acceso organizacional propuesto, 2026-10-22

El usuario pausa el despliegue tras el rechazo de creacion de sort por
policyViolation. Se requiere una via que respete la politica vigente,
sin excepciones de dominio ni permisos amplios. Esta seccion prevalece
sobre la propuesta de acceso directo de pinofd@outlook.com que sigue abajo.
No se cambia todavia el principal de despliegue ni se aplican grants.

### Via recomendada: identidad nominativa administrada para el tercero

El administrador del directorio debe confirmar primero el customer ID,
los dominios y los conjuntos de principales permitidos por la politica
efectiva del proyecto. Si la politica admite usuarios de nuestro directorio,
aprovisionar en ese directorio Cloud Identity o Google Workspace una cuenta
individual para el representante externo, por ejemplo
ext.sort.<persona>@<dominio-corporativo-permitido>.
El ejemplo no identifica un dominio real ni garantiza su admision.
No basta con registrar una cuenta Google personal con un correo parecido.

La persona sigue siendo un tercero: la cuenta es administrada por nuestra
organizacion, con patrocinador interno, MFA, alta aprobada, fecha de revision
y baja/suspension al terminar la relacion. Usar una unidad organizativa
para externos si existe; esa ubicacion no concede permisos BigQuery.
Revisar grupos automaticos, accesos predeterminados e IAM heredado para
evitar que el alta otorgue acceso interno adicional.
Cloud Identity puede evitar una licencia completa de Workspace si el
administrador confirma disponibilidad y requisitos.

Para el piloto, usar grants directos a esa identidad en los cuatro recursos:

| Alcance | Permiso | Limite |
|---|---|---|
| Cada una de las cuatro vistas publicas de sort | roles/bigquery.dataViewer | Sin grant general al dataset |
| Proyecto de ejecucion confirmado | roles/bigquery.jobUser | Permite jobs, no lectura general de datos |
| Gold, Silver, Control y objetos auxiliares | Ninguno para el consumidor | Lectura mediante cadena de vistas autorizadas |
| Organizacion, carpeta, buckets, secretos y cuentas de servicio | Ninguno adicional | Sin roles basicos ni impersonacion |

Se conserva factory-etl-prod como proyecto de ejecucion aprobado para el
piloto; sus consultas generan costes alli. Un proyecto de ejecucion separado
es una opcion futura, no una creacion autorizada por este documento.
No conceder Viewer de proyecto para facilitar la navegacion de consola.
La lectura y descarga CSV estan permitidas; revocar IAM no recupera copias.

La alternativa de grupo administrado solo procede con miembros aprobados
del directorio y control de altas/bajas. No usar un grupo interno con la
cuenta Outlook externa como mecanismo para eludir restricciones de dominio.
Tampoco usar claves de servicio, cuentas compartidas o impersonacion como
sustitutos del alta nominativa.

### Verificacion administrativa y criterio de reanudacion

1. Consultar la politica efectiva y heredada, incluidas
   iam.allowedPolicyMemberDomains, iam.managed.allowedPolicyMembers y
   posibles restricciones personalizadas. No solicitar policyAdmin al tercero.
2. Confirmar que la identidad propuesta pertenece al conjunto permitido.
   Si no lo permite la politica actual, no ejecutar grants ni prometer acceso:
   elevar la incompatibilidad al administrador, manteniendo el despliegue pausado.
3. Separar la identidad interna de aprovisionamiento de la del consumidor.
   Investigar tambien los ACL iniciales del dataset: el rechazo anterior
   no demuestra que Outlook fuera su causa, pues ese grant aun no se intento.
4. Aprobar la cuenta nominativa y auditar sus accesos efectivos antes de usarla.
5. Con autorizacion para reanudar, crear sort y desplegar/validar los datos;
   autorizar cada dependencia de vistas sin ampliar lectura a las fuentes.
6. Con la sesion real del consumidor, probar SELECT y CSV sobre las cuatro
   vistas; comprobar denegacion de lectura Gold/auxiliares y de escritura
   sobre nuestros datos. Validar sin permisos administrativos heredados.
7. Registrar responsable, revision de acceso, procedimiento de revocacion
   y evidencia de las pruebas. No dar el acceso por listo antes de verificarlas.

Si se exige conservar exclusivamente pinofd@outlook.com y la politica no
admite esa identidad, no existe una concesion IAM directa compatible sin
cambiar esa condicion. No se propone relajar la politica para resolverlo.
La cuenta corporativa administrada es una propuesta pendiente de aprobacion.
La automatizacion futura del consumidor requiere un diseno de identidad
de carga separado; este piloto es acceso humano SQL/CSV, sin API.

Referencias oficiales:
[restriccion de identidades](https://cloud.google.com/resource-manager/docs/organization-policy/restricting-domains),
[Cloud Identity y Workspace](https://cloud.google.com/architecture/identity/best-practices-for-planning),
[vistas autorizadas BigQuery](https://cloud.google.com/bigquery/docs/authorized-views).

## Nombre definitivo del dataset, 2026-10-22 20:23 Venezuela

Nombre confirmado: **factory-etl-prod.sort**, region us-central1.
Es el unico dataset a aprovisionar; reemplaza los nombres propuestos
factory_etl_mondelez y factory_etl_sort_mondelez para este despliegue.
Se autoriza jobUser a user:pinofd@outlook.com en factory-etl-prod para
el piloto; lectura dataViewer solo por las cuatro vistas, no por dataset.
No se aplicaron permisos al documentar esta confirmacion.

## Decision vigente, 2026-10-22 20:16 Venezuela

Se sustituye la recomendacion inicial de dos datasets por un unico dataset
factory_etl_mondelez. La identidad de prueba del tercero sera
user:pinofd@outlook.com, con dataViewer por cada una de las cuatro vistas,
no sobre el dataset completo. source_empresa permanece como trazabilidad
SQL y no se modifica la asignacion aprobada de CODIGO_GRUPO.
Los objetos auxiliares y las fuentes Gold/Silver/Control no se comparten.
El proyecto de ejecucion para jobUser requiere confirmacion.

El alcance activo es publicacion productiva SQL/CSV, sin desarrollo ni
despliegue API. Tampoco se aprueba por esta decision un publicador comun
versionado. Ver el [inventario actualizado](./inventario-despliegue-sort-mondelez.md).
Los ejemplos siguientes con factory_etl_sort_mondelez son historicos y no
deben usarse como instrucciones de aprovisionamiento vigentes.

## 1. Objetivo y recomendacion

Permitir que usuarios identificados de SORT consulten los datos aprobados de
Mondelez, descarguen resultados CSV manualmente y los incorporen a SQL Server
y a su DW, sin acceso general a Gold ni permisos de escritura sobre nuestros datos.

**Recomendacion inicial: un dataset exclusivo de consumo externo con cuatro
vistas autorizadas, acceso mediante grupo y permiso de ejecutar consultas en
un proyecto de ejecucion definido.**

No entregar acceso directo a `factory_etl_gold` ni reutilizar la cuenta de
servicio de la API. El acceso SQL es un canal adicional: no exige terminar
la API ni obliga a retirar el POST compatible con SORT.

Esto requiere configuracion y validacion futuras. Este documento no ejecuta
ninguna de ellas y no modifica codigo, Terraform ni las vistas aprobadas.

## 2. Estado real del repositorio

- Las cuatro vistas tienen aprobacion funcional, pero siguen sin despliegue
  productivo autorizado en esta fase.
- El dataset interno previsto es `factory_etl_mondelez`.
- Contiene o puede contener objetos de implementacion, no solo las cuatro
  interfaces publicas: candidata de inventario, publicacion e informacion de control.
- Las vistas internas incluyen columnas tecnicas no expuestas por la API.
  Por tanto, compartir todo ese dataset o indicar `SELECT *` no equivale
  a compartir unicamente el contrato aprobado.
- El Terraform actual da a la identidad interna de la API lectura sobre
  determinadas fuentes Gold. **Ese modelo no se debe copiar para SORT**:
  otorgaria acceso directo a tablas con informacion fuera de la interfaz externa.
- No se consulto IAM efectivo ni se verifico disponibilidad productiva en
  la elaboracion de este documento; se revisaron definiciones del repositorio.

Referencias locales:
[especificacion](./mondelez-api-0301.md),
[arquitectura API](./propuesta-arquitectura-api-mondelez.md) y
[permisos historicos de la API](../archive/mondelez/mondelez.tf).

## 3. Separacion de acceso

```text
Gold y publicaciones internas
          |
    autorizacion de vistas
          |
factory_etl_sort_mondelez  [nombre propuesto; us-central1]
  vw_clientes
  vw_ventas
  vw_existencias
  vw_articulos
          |
grupo de usuarios SORT: lectura
          |
BigQuery SQL Studio -> resultado -> CSV -> staging SQL Server -> DW
```

El dataset externo solo debe contener interfaces que SORT tenga autorizadas.
La region propuesta debe coincidir con las fuentes: `us-central1`, no la
multirregion `US`. Validar las ubicaciones efectivas antes de crear recursos.

### Por que vistas autorizadas y no vistas comunes

Una vista comun por si sola no elimina la necesidad de permisos sobre las
fuentes. Una vista autorizada permite consultar el subconjunto definido por
el propietario **sin conceder al consumidor lectura directa del dataset fuente**.

La autorizacion se concede a la vista en el dataset fuente; no se concede
`dataViewer` al usuario externo sobre Gold para resolver un error de acceso.

Como las definiciones actuales encadenan vistas y tablas de varios datasets,
un administrador debe inventariar y configurar cada dependencia necesaria.
No asumir que autorizar una envoltura en el primer dataset autoriza
automaticamente toda la cadena. Probarla con una identidad sin permisos heredados
sobre las fuentes.

Preferir autorizaciones a vistas individuales en este alcance de cuatro recursos.
Un dataset autorizado completo es otra opcion, pero exige controlar estrictamente
quien puede crear/modificar vistas en el: una nueva vista podria ampliar la exposicion.
SORT no debe tener esos permisos.

## 4. Matriz de permisos minimos del consumidor

Identidad recomendada: un grupo administrado con cuentas individuales nominativas,
por ejemplo `<grupo-sort-autorizado>`. El nombre y sus integrantes deben confirmarse.
No usar `allUsers`, `allAuthenticatedUsers`, cuentas compartidas ni claves JSON
de la cuenta de servicio del ETL.

| Recurso | Principal | Rol propuesto | Finalidad |
|---|---|---|---|
| Dataset externo exclusivo | Grupo SORT | `roles/bigquery.dataViewer` | Ver metadatos y leer las cuatro interfaces |
| Proyecto de ejecucion/facturacion | Grupo SORT | `roles/bigquery.jobUser` | Crear sus propios jobs de consulta |
| Dataset Gold y demas fuentes internas | Grupo SORT | Ninguno | Sin lectura directa |
| Dataset fuente correspondiente | Vista autorizada especifica | Entrada de autorizacion de vista | Resolver la lectura interna de esa interfaz |
| Buckets, secretos, Cloud Run y cuentas de servicio | Grupo SORT | Ninguno en el acceso inicial | No necesarios para descargar un resultado local |

Si el dataset externo no puede ser exclusivo, conceder lectura **por vista**
en lugar de sobre todo el dataset. Puede hacer menos comoda la navegacion
en consola; usar nombres completos y agregar el recurso al explorador.
No ampliar a nivel proyecto solo para que aparezcan todos los datasets.

No conceder `Owner`, `Editor`, `Viewer` basico a nivel proyecto,
`roles/bigquery.admin`, `roles/bigquery.dataEditor`,
`roles/bigquery.dataOwner` ni `roles/bigquery.user` como atajo.
`jobUser` basta para crear consultas sin dar creacion de datasets.

### Lectura no significa cero ejecucion ni impedir copias

BigQuery necesita crear jobs y resultados temporales para ejecutar un `SELECT`.
Eso no requiere permiso de modificar tablas de negocio. El usuario puede
formular consultas arbitrarias sobre lo expuesto, no unicamente las consultas
de ejemplo; limitar datos mediante la definicion de la vista, no mediante instrucciones.

`dataViewer` es un rol predefinido de lectura que tambien permite capacidades
de exportacion/copia de datos. No es un control que impida descargar.
Una vez autorizado a leer y descargar, no podemos revocar los CSV ya obtenidos.
Aplicar acuerdos de uso, tratamiento de datos personales y retencion.

Los permisos IAM son acumulativos: un grant reducido no elimina accesos
heredados por organizacion, carpeta, proyecto u otros grupos. Revisar acceso
efectivo antes de afirmar que una identidad es exclusivamente lectora.

## 5. Proyecto de ejecucion, costes e identidad externa

Dos alternativas:

1. **Proyecto de SORT:** SORT habilita BigQuery y facturacion y otorga
   `jobUser` a sus usuarios en ese proyecto. Nosotros damos solo lectura al
   dataset externo. Las consultas se ejecutan/facturan en su proyecto;
   el almacenamiento de nuestras fuentes sigue en el nuestro.
2. **Proyecto de ejecucion controlado por nosotros:** habilitar un proyecto
   dedicado para consultas externas y dar alli `jobUser`. Nosotros asumimos
   el coste de ejecucion y configuramos controles operativos.

Evitar dar `jobUser` en el proyecto productivo por comodidad si se puede
separar el proyecto de ejecucion. Usar `factory-etl-prod` en un nombre de tabla
no obliga a ejecutar/facturar el job en ese mismo proyecto.

Antes de habilitar:

- Confirmar cuentas Google/Cloud Identity o un mecanismo federado compatible.
- Comprobar politicas de organizacion que restrinjan dominios externos.
- Comprobar VPC Service Controls si existe perimetro: una vista autorizada
  no evita sus restricciones ni garantiza descarga fuera del perimetro.
- Definir responsable de altas, bajas, revision periodica y fecha de expiracion.
- Preferir acceso temporal para el piloto cuando el mecanismo elegido lo permita.

## 6. Que datos exponer

| Interfaz propuesta | Campos de negocio | Alcance |
|---|---:|---|
| `vw_clientes` | 17 | Seleccion aprobada de clientes con sucursal mapeada |
| `vw_ventas` | 24 | Proveedor 0301, grano renglon, reglas SORT aprobadas |
| `vw_existencias` | 9 | Publicacion validada, captura ganadora por empresa/dia Venezuela |
| `vw_articulos` | 5 | Articulos locales, clase canonica cuando corresponde |

Proyectar listas explicitas de columnas; no exponer automaticamente futuras
columnas mediante `SELECT *`. Conservar los tipos y reglas de las vistas
aprobadas, incluido el tratamiento de faltantes sin NULL en articulos.

Para consultas consolidadas se propone agregar `source_empresa` como columna
de trazabilidad, fuera del conteo anterior de campos de negocio. **Esto requiere
acuerdo del contrato SQL/CSV**; no cambia automaticamente el contrato JSON.
Es necesaria para distinguir codigos locales repetidos entre empresas.

Si SORT solo esta autorizado para ciertas empresas o grupos, ese filtro debe
quedar impuesto por las vistas autorizadas o una politica de acceso validada,
no depender de que el usuario escriba el `WHERE`.

No exponer `_cod_cli`, `_renglon`, `_capture_id`, hashes de origen, tablas de
control o candidatos salvo acuerdo explicito. Si su carga DW necesita una
clave de renglon estable o un manifiesto de corte, definir una interfaz adicional
minima: la lectura directa de los 24 campos de ventas no resuelve esa identidad.

El maestro de clientes mantiene el alcance aprobado por sucursal; no agregar
un filtro por proveedor basado en compras/ventas que cambie silenciosamente su seleccion.

## 7. Consulta y descarga manual CSV

Una vez desplegadas y autorizadas las interfaces:

1. Iniciar sesion individual en Google Cloud Console y abrir BigQuery.
2. Seleccionar el proyecto de ejecucion/facturacion acordado.
3. Agregar el proyecto/dataset compartido al explorador si es necesario.
4. Usar GoogleSQL y ubicacion `us-central1`.
5. Revisar bytes estimados y el maximo de bytes facturados antes de ejecutar.
6. Ejecutar la consulta.
7. En resultados, elegir **Save results / Guardar resultados -> CSV local**.
8. Registrar job ID, consulta/filtros, hora de extraccion y cantidad total
   de filas; conciliar las filas descargadas con el resultado completo.

Ejemplo ilustrativo para la interfaz externa propuesta, aun inexistente:

```sql
SELECT
  source_empresa,
  CODIGO_GRUPO, NOMBRE_GRUPO, RUTA, RIF, SOCIO_NEGOCIO,
  PAIS, ESTADO, MUNICIPIO, CIUDAD, DIRECCION,
  CODIGO_SKU, CODIGO_BARRA, UNIDAD_MEDIDA, FECHA,
  NUMERO_DOCUMENTO, TIPO_DOCUMENTO, NOMBRE_SKU, PROVEEDOR,
  CANAL_VENTA, CANTIDAD, PRECIO, MONEDA, NETO_MONEDA,
  FECHA_ACTUALIZACION
FROM `factory-etl-prod.factory_etl_sort_mondelez.vw_ventas`
WHERE source_empresa = 'tinito'
  AND FECHA BETWEEN '20261001' AND '20261001';
```

`FECHA` es STRING AAAAMMDD en el contrato aprobado; el rango anterior consulta
un dia. Para un mes seria `20261001` a `20261031`, sujeto al volumen.
La poda de particiones y el coste real deben verificarse con el plan/estimacion;
no asumir que un filtro sobre la fecha formateada reduce todo el escaneo.
`LIMIT` limita filas de salida, no garantiza reducir bytes leidos.

Existencias debe consultarse por empresa y `FECHA_DATA` exacta de la captura
publicada, respetando el dia de negocio Venezuela. La consulta SQL no ejecuta
las validaciones de parametros del adaptador HTTP; se necesitan consultas
guiadas y, si procede, una vista minima de capturas disponibles aprobada.
No habilitar lectura de toda la auditoria solo para descubrir una captura.

### Limites y volumen

- La descarga local de consola tiene limites de tamano; no tratarla como
  exportacion ilimitada ni garantizar que un mes Tinito quepa en un archivo.
  Confirmar limites vigentes en la consola/documentacion al habilitar el acceso.
- Si se exceden, dividir por dias o usar una exportacion controlada a GCS.
  Verificar completitud; nunca incorporar solo la pagina visible del resultado.
- CSV requiere columnas planas; nuestras proyecciones deben evitar ARRAY/STRUCT.
- Descargar no hace gratuita la consulta ni elimina el tiempo de calculo de vistas.
- Las vistas logicas son lecturas de fuentes vigentes. Consultas sucesivas
  pueden observar estados distintos. Para un corte reproducible del DW,
  publicar tablas/lotes inmutables en vez de afirmar que la consulta manual
  ya proporciona consistencia entre las cuatro entidades.

## 8. CSV hacia SQL Server

- Definir UTF-8, encabezados, delimitador, comillas y manejo de saltos de linea.
- Cargar primero en staging con tipos explicitos; no inferir tipos desde Excel.
- Conservar SKU, RIF, barcode, grupos y documentos como texto, incluidos ceros iniciales.
- Conservar cadenas vacias de articulos; el importador no debe convertirlas
  automaticamente en NULL si el contrato exige cadena vacia.
- Ventas mantiene valores absolutos y FACTURA/N/CR en compatibilidad. No
  aplicar dos veces el signo de notas de credito ni sumar monedas distintas.
- Usar DECIMAL adecuado al convertir cantidades/importes; no FLOAT.
- No deduplicar ventas por factura + SKU: pueden existir renglones repetidos.
- No sumar instantaneas de inventario entre fechas/capturas.
- Registrar origen, filtros, job ID y, cuando exista, version del lote en la carga.

Los CSV contienen informacion de clientes. No publicarlos en buckets abiertos,
correos masivos ni repositorios; controlar ubicacion y retencion en SORT.

## 9. Si requieren CSV masivo

No dar permisos amplios de GCS al grupo como parte del acceso inicial.
Preferir un exportador administrado por nosotros que genere archivos en un
bucket privado y entregue descarga autorizada de los objetos correspondientes.

Si se acuerda exportacion directa por SORT, disenar por separado permisos
BigQuery de exportacion y permisos de creacion/lectura en un bucket dedicado,
con alcance, ubicacion y retencion definidos. No conceder Storage Admin.
Crear nuevos nombres de objeto evita necesitar sobrescritura, pero se debe
verificar el conjunto exacto de permisos requerido por el mecanismo elegido.

La alternativa para mayor estabilidad es compartir **tablas de publicacion
congeladas y exclusivas de Mondelez** en lugar de vistas logicas sobre fuentes
cambiantes. Mantiene dataViewer + jobUser para el consumidor, agrega
almacenamiento/publicacion y evita trasladar joins Gold a cada consulta.
Su seleccion requiere acordar frescura, retencion y lote, no cambiar las reglas
funcionales aprobadas.

## 10. Costes, auditoria y revocacion

- Definir cuotas de consulta en el proyecto de ejecucion y alertas de presupuesto.
  Una alerta de presupuesto no es un corte automatico de gasto.
- `maximum bytes billed` sirve para consultas concretas, pero si el usuario
  puede configurar jobs no es una restriccion obligatoria que no pueda cambiar.
  Complementar con cuotas administrativas compatibles con el modelo de capacidad.
- Promover consultas guardadas y filtros acotados, sin tratarlos como barrera IAM.
- Revisar auditoria BigQuery por identidad y job; evitar copiar resultados con
  datos personales a registros de operacion.
- Revocar acceso retirando integrantes del grupo y grants especificos, y
  verificar otros permisos heredados. La revocacion no recupera CSV descargados.
- No prometer que el usuario no pueda conocer nombres o definiciones internas:
  los permisos de metadatos de vistas pueden exponer SQL/referencias. El objetivo
  principal es impedir lectura de filas y escritura sobre fuentes no autorizadas.

## 11. Plan de habilitacion y criterios de aceptacion

Ejecucion futura por administradores autorizados:

1. Confirmar usuarios, empresas/grupos permitidos, proyecto de ejecucion y responsable de costes.
2. Desplegar las vistas aprobadas y verificar fuentes/publicaciones.
3. Crear el dataset externo y las proyecciones explicitas acordadas.
4. Configurar la cadena de vistas autorizadas sin grants de lectura Gold al grupo.
5. Conceder dataViewer al dataset externo y jobUser al proyecto de ejecucion.
6. Probar con una identidad SORT real, no con una cuenta administrativa:
   - SELECT de las cuatro interfaces funciona.
   - Descarga CSV local permitida y completa para un corte de prueba.
   - Esquema, faltantes, empresas y totales concilian con los contratos.
   - Lectura directa de Gold, Silver, control y publicacion interna denegada.
   - INSERT/UPDATE/DELETE/CREATE/ALTER/DROP en nuestros datasets denegados.
   - No hay acceso a secretos, impersonacion de cuentas ni administracion IAM.
   - Empresas/grupos fuera de su alcance no aparecen ni pueden recuperarse.
   - Consulta con el proyecto de ejecucion acordado y coste verificable.
7. Verificar una carga CSV de staging a SQL Server sin perdida de ceros ni precision.
8. Documentar alta, guia de consultas, soporte, baja y aceptacion del consumidor.

No basta el IAM Policy Troubleshooter o una inspeccion estatica: comprobar
la cadena real de consultas y descargas bajo esa identidad. Hasta entonces
no declarar habilitado ni certificado el canal.

## 12. Decisiones pendientes

- Identidades nominativas y grupo administrado.
- Empresas/grupos que SORT puede consultar.
- Proyecto de ejecucion y facturacion.
- Aprobacion de `source_empresa` y, si hace falta, metadatos de lote/identidad de renglon.
- Vistas vigentes o tablas publicadas con corte fijo.
- Volumen/frecuencia de descarga y tratamiento de correcciones.
- Retencion de CSV y condiciones de tratamiento de datos de clientes.

## 13. Documentacion oficial consultada

- [Vistas autorizadas: aislamiento, permisos, dependencias y ubicacion](https://cloud.google.com/bigquery/docs/authorized-views).
- [Roles IAM de BigQuery](https://cloud.google.com/bigquery/docs/access-control).
- [Descarga y exportacion de resultados, incluida consola a CSV](https://cloud.google.com/bigquery/docs/export-file).
- [Cuotas y limites vigentes](https://cloud.google.com/bigquery/quotas).
- [Control de costes de consultas](https://cloud.google.com/bigquery/docs/best-practices-costs).

**Conclusion:** es viable dar acceso SQL de lectura para consulta y CSV
sin abrir Gold. La combinacion recomendada es dataset externo aislado,
vistas autorizadas, dataViewer en ese dataset y jobUser en el proyecto de
ejecucion acordado, con validacion real de aislamiento y descarga.
