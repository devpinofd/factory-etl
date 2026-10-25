# Despliegue de vistas SQL SORT Mondelez

Actualizado: 2026-10-25, America/Caracas.
Estado: cuatro vistas SQL y correccion acotada de inventario Gold.
Plan exclusivo de SORT verificado sin
cambios; elegida la opcion de vistas dinamicas sobre Gold, sin
automatizacion adicional. Correccion Silver-Gold y adaptacion SORT
desplegadas mediante Dataform administrado y reconciliadas en produccion.

### Alineacion SQL posterior, 2026-10-24

El despliegue de acceso descrito en el [handoff](./handoff-sort-mondelez.md)
aplico cuatro vistas publicas autonomas desde el commit
`564e622a408dfe5604ee125ad3583a4e4c31eb9a`, compilacion
`ad619e92-7af6-4627-8f29-0b34d9729a75`: cuatro vistas y 32 assertions
SUCCEEDED. Las vistas publicas leen solo tablas fisicas Gold; los grupos
y las transformaciones se integran en CTE. No necesitan leer las vistas
internas SORT ni las tablas de publicacion.

El refactor local centraliza ese SQL en
[mondelez_queries.js](../dataform/includes/mondelez_queries.js), compartido
por las vistas publicas e internas. Se conservan nodos y assertions
Dataform mediante dependencias explicitas, sin agregar persistencia,
horarios ni fuentes. El bloque SQL se publica separado de Terraform y
de las concesiones de acceso; no reaplicar infraestructura desde esta rama.
Las consultas extraidas conservan su comportamiento salvo el cambio de
FECHA_ACTUALIZACION de ventas solicitado el 2026-10-25, aun no desplegado.

## Alcance vigente

- Proyecto: `factory-etl-prod`; dataset de consumo: `sort`, `us-central1`.
- Terraform administra el dataset y el permiso del ejecutor interno.
- Dataform administrado construye modelos, controles de calidad y vistas.
- Se conservan las reglas de negocio y `source_empresa` como trazabilidad.
- No se crean servicios de consumo, usuarios ni permisos del tercero.
- No se modifican workflows, horarios, ingesta ni permisos existentes.
- Excepcion aprobada el 2026-10-23: corregir la seleccion de inventario
  Gold por empresa/dia Venezuela y generalizar la QA existente.
- No se fusionan ramas sin autorizacion de promocion a la fuente productiva.
- Se descarta por ahora incorporar otro ciclo de persistencia de cortes.
  La persistencia SORT existente no constituye aprobacion del alcance
  ni autorizacion para eliminarla.

## Decision arquitectonica vigente

Confirmado por el usuario el 2026-10-23, 01:52 America/Caracas:

- Elegir la opcion 1: vistas dinamicas sobre los datos Gold actualizados
  por la extraccion y consolidacion existentes.
- No agregar otro programador, workflow ni ciclo de publicacion SORT.
- Utilizar los atributos de los maestros actuales, como el consumo Gold
  vigente. Se posterga congelar descripciones por corte e integrar SCD2;
  una correccion del maestro puede reflejarse en fechas anteriores.
- Mantener contratos publicos, trazabilidad y representacion horaria
  Venezuela. No modificar ingesta, workflows, horarios o permisos.
- La autorizacion posterior permitio adaptar existencias: su vista interna
  ya lee Gold mediante la candidata, no la tabla persistida SORT.
- Gold selecciona una captura completa valida por empresa/dia antes del
  detalle; no equivale a seleccionar cada articulo/almacen por separado.
- No se autoriza borrar tablas existentes, ejecutar publicaciones ni
  activar otra recurrencia.

### Actualizacion Silver-Gold autorizada posteriormente

El usuario aprobo proceder con el plan el 2026-10-23, 13:56 Venezuela.
La restriccion inicial sobre Gold se sustituye exclusivamente para corregir
la seleccion diaria de inventario; no autoriza otros cambios operativos.

- Silver conserva su tabla incremental, claves, timestamps y particion UTC.
- La vista `vw_inventario_capturas_qa` se generaliza en Gold, sin depender
  de la bandera del proveedor y cubriendo las cinco empresas.
- `fct_inventario_snapshot` elige una captura COMPLETA por empresa/dia
  Venezuela antes de unir su detalle Silver. `snapshot_date` cambia de
  fecha UTC a fecha de negocio; conserva `run_id` e `_ingested_at`.
- Una assertion general reconcilia captura, conteos y cobertura diaria.
- SORT lee el hecho Gold y agrega almacenes solo dentro del mismo corte.
  Conserva maestros actuales, contrato publico y hora Venezuela.
- Los errores de maestros o contrato se exponen, sin mezclar capturas
  ni sustituir silenciosamente por un corte anterior.
- Las tablas de publicacion existentes no se borran ni se ejecutan.
- La fuente de consolidacion es `main`: la promocion limitada ya fue
  autorizada y fusionada para que el ciclo no revierta la correccion.

Verificacion previa al despliegue (historico):

- Compilacion Dataform sin errores con la bandera del proveedor tanto
  deshabilitada como habilitada; Gold y sus controles activos en ambos.
- 34 pruebas focalizadas aprobadas.
- SQL compilado ejecutado en BigQuery con 13 capturas sinteticas:
  tres cortes diarios, desaparicion de SKU, cruce UTC/Venezuela, empate,
  empresas independientes, fallo y carga parcial. Cero diferencias.
- Preview real sin escritura: 80 dias validos por cada una de las cinco
  empresas; Gold 1842691 filas. El rango comienza el 2026-08-03:
  los dias anteriores sin captura completa no se convierten en cortes.
- SORT conserva 49737 filas: CTB 6911, CTM 7566 y Tinito 35260.
  Cero fechas invalidas y cero capturas mezcladas.
- Jobs: fixtures `job_VThtB-E32OUS4X8baGdT5AmPcjr9`;
  preview `job_ZUgHcSuR0vzLiWCnBLJlkhvOsNDU`, 346811357 bytes.
- Estos resultados corresponden a consultas previas, no a un despliegue.
- Comparacion posterior de los 49737 registros publicos: cero diferencias
  de claves y campos entre propuesta y produccion. Esquemas publico
  (10 campos) e interno (13 campos) coinciden en nombre, tipo y orden.
- Reconciliacion independiente de captura/conteos Gold: cero diferencias.
  Jobs `inventory_validation_e68bcbf05d084c46a74a0c3981b3406c` y
  `inventory_validation_e65473f7653743eebf565cb31d167947`.
- `main` no contiene los modelos SORT. La promocion fue selectiva:
  cuatro SQL Gold y sus pruebas independientes, sin fusionar los modelos
  SORT adicionales de la rama ni incluir cambios Terraform locales.

### Promocion y despliegue completados

El PR [#11](https://github.com/devpinofd/factory-etl/pull/11) se fusiono
el 2026-10-23 a las 16:27 Caracas, con CI aprobado. Main:
`2dc06352de721f99a8e6b66a069df43ac46261bc`.
La autorizacion original de cuatro archivos se amplio expresamente a
cinco: era necesaria la declaracion de `etl_batches`, tabla de control
existente, para compilar Gold sin depender de archivos SORT. Se movio a
`definitions/gold/etl_batches.sqlx`; una declaracion no crea ni carga tablas.
La rama SORT completa no se fusiono. Sus cambios SQL dirigidos proceden
del commit `81415d6ff86d546495e46a6c98658825deee2413`.

- 402 pruebas locales aprobadas, incluidos contratos de inventario y
  referencias/encoding; Ruff correcto y ambas compilaciones sin errores.
- CI del PR `40018839931` y CI de main `40019312430`: SUCCESS.
- Preflight: cero workflows o invocaciones Dataform activos; la carga
  existente de las 16:00 ya habia concluido.
- Recuperacion preparada: lectura time travel Gold verificada y
  compilaciones anteriores Gold/SORT conservadas, sin crear otra tabla
  de negocio ni ejecutar una restauracion.
- Gold: compilacion `11199b56-5c4c-4a01-9034-4992cc0e1a88` desde main,
  con `enableMondelez=false`, `enableScd2=false`, `enableLegacyFacts=false`.
  Invocacion `1792787432-b687bcdf-2baf-4bf5-b8ca-52f86b0bedcc`:
  SUCCEEDED, cinco acciones (QA, hecho y tres assertions).
- SORT: compilacion `59d4fb62-140a-4e15-9484-07e69605d4cc` desde el SHA
  dirigido de la rama, `enableMondelez=true` solo en esa compilacion.
  Invocacion `1792787603-388d3fe9-8f13-457b-907f-771b1d41015d`:
  SUCCEEDED, cuatro acciones (candidata, interna y dos assertions).
- Ambas invocaciones usan la cuenta runtime existente, targets explicitos,
  sin dependencias/dependientes transitivos y sin full refresh Silver.
  No se ejecutaron el publicador, modelos legacy ni el wrapper publico.

Resultado real posterior, no solo preview:

| Empresa | Filas Gold | Dias Gold | Filas SORT | Dias SORT |
|---|---:|---:|---:|---:|
| CTB | 573576 | 81 | 7025 | 81 |
| CTM | 205618 | 81 | 7665 | 81 |
| Daroan | 139518 | 81 | No aplica | No aplica |
| Roldan | 53764 | 81 | No aplica | No aplica |
| Tinito | 893865 | 81 | 35704 | 81 |
| Total | 1866341 | | 50394 | |

Rango: 2026-08-03 a 2026-10-23. Ultimas capturas Venezuela SORT:
CTB `20261023160106`, CTM `20261023160109`, Tinito `20261023160057`.
Gold coincide con el detalle completo de sus ganadoras; SORT coincide
con el SQL esperado sobre ese Gold. EXCEPT bidireccional: cero faltantes
y sobrantes; cero dias mezclados o fechas invalidas. Se verificaron el
SQL real del job Gold y las definiciones reales de las tres vistas.
Se conservan nombre, tipo y orden de los diez campos publicos y trece
internos; `FECHA_DATA` mantiene 14 digitos y fecha/hora Caracas.

El Gold anterior tenia 1922443 filas: el menor total nuevo responde a la
seleccion completa por dia de negocio, no al arrastre por clave/fecha UTC.
La igualdad con el detalle Silver esperado se probo; Silver permanece
sin modificaciones. Tambien permanecen iguales los maestros, ventas,
definicion BI, tabla y lock de publicacion, ACL, revisiones de workflows
y horarios (16:00 y 22:00 America/Caracas; calidad pausada).
Las compilaciones anteriores de recuperacion son
`c43ea7f0-cbf9-424c-b9d7-40f3c616cd65` (Gold) y
`382fa8f5-f639-4063-b881-2cbd178c807c` (SORT).

Seguimiento: observar la siguiente ejecucion existente de las 22:00
Caracas; aun no se afirma verificada. No se disparo otra ejecucion ni
se activo programacion adicional. Una captura nocturna completa del
mismo dia sustituira la de las 16:00, sin sumar ni mezclar ambas.

## Requisito de snapshots diarios

Confirmado por el usuario el 2026-10-23:

- Conservar la ultima captura valida de cada empresa y dia de negocio;
  no reducir la vista al ultimo estado global ni mezclar capturas.
- Conservar los dias anteriores para consultar sus registros mediante
  `source_empresa` y `FECHA_DATA`.
- Elegir la captura por `captura DESC, run_id DESC` entre las capturas
  completas verificadas por la QA de origen.
- Una carga posterior incompleta no desplaza a una completa del mismo dia.
  SORT verifica su contrato sobre la ganadora y expone errores sin
  combinar filas ni seleccionar otro corte para ocultarlos.
- El dia de negocio se interpreta en `America/Caracas`; `FECHA_DATA`
  representa la fecha y hora Venezuela de la captura seleccionada,
  no la hora de consulta.
- Durante el dia puede avanzar la captura seleccionada. No se requiere
  exponer todas las capturas intradiarias descartadas por esa seleccion.

La vista interna actual conserva una captura por empresa/dia desde Gold,
sin depender de lo publicado ni agregar persistencia o disparadores.
La adaptacion esta desplegada y verificada. Si un dia no tiene ninguna captura valida, no generar
corte para ese dia y conservar los dias anteriores con sus fechas reales.
No inventar una captura ni cambiar la fecha de otra.

## Contrato de fecha y hora Venezuela

Acuerdo del 2026-10-23, con cambio de origen para ventas solicitado
el 2026-10-25. Este ultimo cambio esta preparado localmente, sin desplegar:

| Vista | Campo | Tipo y formato | Origen |
|---|---|---|---|
| Ventas | `FECHA_ACTUALIZACION` | STRING de 14 digitos, `AAAAMMDDHHMMSS` | `CURRENT_TIMESTAMP()` al ejecutar la consulta, representado en `America/Caracas` |
| Existencias | `FECHA_DATA` | STRING de 14 digitos, `AAAAMMDDHHMMSS` | Timestamp de la captura, representado en `America/Caracas` |

Clientes y articulos no exponen esos campos. La zona se aplica una sola
vez al TIMESTAMP de origen, no mediante resta de horas a cadenas.
Los instantes tecnicos `_captured_at` y `_published_at` no se alteran.
La seleccion de captura valida por empresa/dia y el calendario `FECHA`
de ventas no cambian: `registro` sigue siendo el origen de `FECHA` y del
filtro historico. Solo `FECHA_ACTUALIZACION` pasa a indicar el inicio de
la consulta, igual para todas sus filas; no representa la ultima carga
ETL ni una modificacion ERP. Se utiliza `CURRENT_TIMESTAMP()`, equivalente
BigQuery de `GETDATE()`, en el SQL compartido por las vistas publica e
interna. Existencias mantiene la fecha de su captura, no la de consulta.

Para corregir tambien los cortes ya publicados, la vista interna de
existencias calcula `FECHA_DATA` desde `_captured_at`. No se reescriben
las filas historicas ni se vuelven a publicar las capturas. La candidata
utiliza la misma zona para el consumo dinamico desde Gold. Por ejemplo,
`2026-10-23 01:59:17 UTC` se presenta como `20261022215917`.

Las descripciones UTC de contratos historicos no definen la semantica
vigente de estos campos; se mantienen el tipo STRING y los 14 digitos.
Este cambio SQL fue desplegado mediante Dataform administrado el
2026-10-23. No modifica Gold, workflows, permisos ni activa el mecanismo
de actualizacion de cortes.

### Despliegue horario productivo verificado

- Revision publicada: `cf319221613754025e0cace8d475ac533a75b9a2`,
  solo tres archivos SQL; sin fusionar la rama.
- Compilacion: `e8dd5eb1-e514-4d66-802d-1dedc6ba1173`, sin errores,
  proyecto prod y variable `enableMondelez=true` para esa compilacion.
- Invocacion: `1792731748-4385d4bc-37b8-4422-abd5-3b18c0e93740`,
  SUCCEEDED, 3/3 acciones; 2026-10-23 01:02:28 a 01:02:34 Venezuela.
- Seleccion exclusiva: `sort.vw_mondelez_ventas_interna`,
  `sort.vw_mondelez_existencias_interna` y
  `sort.vw_mondelez_existencias_candidata`; dependencias y dependientes
  transitivos desactivados, con la cuenta runtime interna.
- Las vistas publicas existentes reflejan el cambio sin reconstruccion.
  SQL y esquemas desplegados verificados contra la compilacion.
- Conteos publicos sin cache: clientes 29428, ventas 443725,
  articulos 406 y existencias 49737.
- Existencias conserva 80 dias por empresa, formato de 14 digitos,
  cero discrepancias con fecha/hora Venezuela y el dia de negocio,
  y cero claves publicas duplicadas.
- Ventas conserva todas las filas y campos no temporales; todas las
  fechas de actualizacion coinciden con la conversion esperada.
- Revision y fecha de modificacion de los tres workflows operativos
  sin cambios. Las cuatro tablas Gold verificadas, la tabla de cortes
  y el ACL directo de `sort` tampoco cambiaron.
- No se ejecuto `pub_mondelez_existencias` ni se activaron horarios.
- Jobs posteriores: conteos `job_4g9LjiYUjn8yxGgLXcc30_4VEf__`;
  fechas existencias `job_kTQDy0DkH4X1fCKUhDEFaubd8Jll`;
  fechas ventas `job_mviZCQ4tBwy8j3eW3NfV50VfTJfH`;
  campos y claves existencias `job_LmHvLEN5Y-iiPPw_lr8OD8plf1-a`.

### Evidencia de la correccion horaria

- Grafo Dataform local compilado sin errores con variables de produccion.
- Dry-run BigQuery de las tres consultas modificadas correcto; cada una
  por debajo del limite de 2 GiB.
- Ventas: 443725 filas antes y despues; cero diferencias en campos distintos
  de `FECHA_ACTUALIZACION` y cero discrepancias en la conversion a Venezuela.
- Existencias interna y candidata: 49737 filas cada una, antes y despues;
  cero diferencias en campos distintos de `FECHA_DATA`.
- Todos los nuevos `FECHA_DATA` coinciden con la captura en Venezuela y
  con el dia `FECHA_SNAPSHOT`. Longitud minima y maxima: 14.
- Seis casos BigQuery de conversion aprobados: cambio de dia, medianoche,
  cambio de ano, dia bisiesto y la zona historica venezolana de 2015.
- Jobs: ventas `job_ip5F2orb5MSsyMvauNmlDuzBGkTg`;
  existencias interna `job_2io92mE5XWJWZzBf9Dm335pdCAzH`;
  candidata `job_7m_EPP5NXCzL8qpC6rkaomN0vloc`;
  casos horarios `job_hB9ZXXp1V8_fSP4HiwuvQW1i7daO`.
- 30 pruebas de contratos y publicacion aprobadas; Ruff correcto.

Estas comprobaciones previas ejecutaron solo SELECT y dry-run sobre las
consultas compiladas nuevas. El despliegue posterior se describe arriba
y se limito a las tres vistas, sin reconstruir fuentes ni ejecutar la
operacion de cortes.

## Inventario inicial verificado (historico)

Consultas sin cache realizadas el 22 de octubre, aproximadamente a las
23:25 Venezuela. Estos valores son una fotografia, no un monitor de frescura.

| Vista en sort | Filas | Esquema publico |
|---|---:|---|
| `vw_mondelez_clientes` | 29428 | 18 STRING |
| `vw_mondelez_ventas` | 443725 | 25 STRING |
| `vw_mondelez_articulos` | 406 | 6 STRING |
| `vw_mondelez_existencias` | 49737 | 8 STRING y 2 NUMERIC |

En existencias, `DISPONIBLE` y `UNIDAD_SIMPLE_X_EMPAQUE` son NUMERIC.
Hay 80 cortes por empresa, del 2026-08-03 al 2026-10-22. El ultimo corte
local contiene 657 filas: ctb 114, ctm 99 y tinito 444. Las fechas
`FECHA_DATA` observados en esa verificacion eran del 23 de octubre en UTC;
el cambio contractual a fecha/hora Venezuela se especifica arriba.
No se observaron claves publicas duplicadas.

### Recursos y dependencias iniciales (historico)

- Clientes y ventas: wrappers publicos sobre vistas internas.
- Articulos: vista sobre los modelos de producto y maestros.
- Existencias: fuentes Gold, vista candidata, operacion SQL transaccional
  `pub_mondelez_existencias`, tabla persistida, tabla
  `inventario_publication_lock`, vista interna y wrapper publico.
- La tabla de existencias conserva capturas; la vista interna selecciona
  la ultima captura por empresa y dia. No es solo una vista logica.
- El ACL directo de `sort` contiene `projectOwners` como OWNER y
  `factory-etl-runtime-prod@factory-etl-prod.iam.gserviceaccount.com`
  como WRITER. Esto no certifica permisos heredados ni acceso del tercero.

## Plan corregido: exclusivamente SORT

La intencion es comprobar la alineacion de produccion con su definicion,
no cambiar el proceso que alimenta los datos. El plan anterior dirigido al
workflow de consolidacion queda descartado y no debe aplicarse.

| Superficie | Propietario | Accion del plan corregido |
|---|---|---|
| Dataset `factory-etl-prod.sort` | Terraform | Plan dirigido solo a `google_bigquery_dataset.sort[0]` |
| Cuatro vistas publicas de SORT | Dataform administrado | Comparar SQL desplegado con la compilacion y fuentes locales |
| Permiso runtime existente | Terraform | Conservar; sin cambios IAM |
| Tablas y operacion de cortes existentes | Dataform administrado | Conservar; sin ejecuciones ni cambios |
| Workflows, horarios, ingesta y Gold | Proceso operativo existente | Fuera del plan; no modificar |

`enable_sort_dataset=true` ya figura en la configuracion productiva.
Los controles locales de habilitacion de modelos en orquestacion no se
usan en este plan ni autorizan modificar la consolidacion. Las vistas
consumen sus fuentes actuales; esa dependencia de lectura no obliga a
compartir su ciclo de despliegue con Gold.

### Verificacion del 2026-10-23

- Backend confirmado: bucket `factory-etl-prod-tfstate`, prefijo `prod`.
- Plan con variables de produccion, refresco normal y target exclusivo
  `google_bigquery_dataset.sort[0]`: exit code 0, sin cambios.
- Resultado: 0 altas, 0 modificaciones y 0 eliminaciones; ningun workflow,
  permiso, carga ni recurso Gold incluido como cambio.
- El refresco registra el ACL WRITER del ejecutor existente. Esta entrada
  se administra por separado; no se propone modificar el ACL del dataset.
- Las cuatro vistas son VIEW en `sort`, `us-central1`, y conservan los
  esquemas contractuales indicados en el inventario.
- El SQL de cada vista en produccion coincide con `relation.selectQuery`
  de la compilacion `31d2e9ea-8e11-4375-8278-b2d21a0481f1`, normalizando
  solo finales de linea, espacios exteriores y el punto y coma final.
- Antes del cambio horario, los cuatro archivos SQL publicos locales
  coincidieron con la revision de esa compilacion. La correccion posterior
  modifica vistas internas y la candidata de existencias, no sus fuentes.
- El plan de infraestructura sigue sin requerir apply. La correccion
  horaria posterior se completo como despliegue SQL distinto, sin Terraform.

Terraform conserva la propiedad de la infraestructura; no se importan las
vistas como recursos Terraform porque su SQL sigue administrado por Dataform.
No introducir doble gestion de los mismos objetos.

## Evidencia del despliegue inicial

- Revision SQL: `2374d3e431be2df4e8ec89b2ab9929d627a4502a`.
- Compilacion: `31d2e9ea-8e11-4375-8278-b2d21a0481f1`;
  proyecto prod, `enableMondelez=true`, sin errores.
- Invocacion: `1792724476-9d02d8ab-95d1-40bb-93f2-22ae224c7e96`,
  SUCCEEDED, 51/51 acciones, cuenta ejecutora interna verificada.
- Reejecucion de solo existencias:
  `1792724702-0a97ae5e-5288-45db-b48c-e14eecf2ac23`, SUCCEEDED.
- Conteos de las vistas: job `job_ntAH6bBiIoLUX6oLvUs22jAjdT16`.
- Historico y ultima publicacion: job `job_ZDZmHys1QxG7Kciav5ryE3D-7sJs`.
- Duplicados: job `job_ladZCXp3-3F2cZP76kRf3NrTGYs4`, resultado cero.

## Validacion inicial y decisiones de esa etapa (historico)

Validacion local del refactor: configuracion Terraform valida, formato
correcto, 5 escenarios Terraform aprobados con proveedores simulados y
36 pruebas de plantillas/contratos SQL aprobadas antes de la correccion
horaria. La validacion posterior de fechas se detalla arriba.
El refactor de infraestructura no se aplico en produccion. El unico cambio
posterior desplegado es la representacion horaria de las tres vistas
indicadas arriba.

1. Mantener los controles de alcance mediante las pruebas de
   infraestructura, plantillas y contratos SQL.
2. Acordar el mecanismo de actualizacion de existencias, preservando el
   requisito de ultima captura valida por empresa/dia y su consulta historica.
3. Revisar la revision SQL a compilar antes de cualquier activacion.
4. Si cambia la definicion de infraestructura de SORT, regenerar su plan
   exclusivo. Detenerse ante cambios de workflow, Gold, ingesta o permisos.
5. Si cambia el SQL contractual, revisar el despliegue Dataform de las vistas
   afectadas sin reconstruir sus fuentes ni ejecutar la operacion de cortes.
   La frescura de datos es una comprobacion distinta de alinear definiciones.

El worktree es compartido. No aplicar Terraform general ni publicar cambios
ajenos. La documentacion anterior conserva evidencia historica y no define
el alcance de este despliegue.

## Fuentes de verdad

- [Infraestructura SORT](../terraform/sort_dataset.tf).
- [Modelos SQL](../dataform/definitions/mondelez).
- [Pruebas Terraform](../terraform/tests/sort_dataset.tftest.hcl).
- [Contratos SQL y alcance del despliegue](../tests/unit/test_sort_sql_contracts.py).
