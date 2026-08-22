# Plan de cierre de mejoras del QA Judge

**Proyecto:** DAX Copilot  
**Componente:** QA Judge y Golden Dataset  
**Objetivo:** convertir la suite actual de consultas DAX de referencia en una
evaluación reproducible del agente, del modelo semántico y de sus guardrails.

## 1. Estado actual

El Golden Dataset contiene 12 casos distribuidos entre seis dominios. La suite
actual:

- carga `golden_dataset.json`;
- detecta una instancia local de Power BI Desktop;
- ejecuta directamente `dax_esperado`;
- valida valores, rangos o cantidad de filas;
- calcula exactitud y latencia.

Esta implementación es útil como smoke test del modelo, pero no evalúa el DAX
generado por el agente a partir de la pregunta. También depende de una instancia
local no versionada, utiliza criterios débiles en varios casos y no distingue
entre fallos del agente, del modelo, de los datos o de infraestructura.

### Avance ejecutado

El primer incremento ya está aplicado:

- se corrigieron los períodos ambiguos de `TC-006`, `TC-008` y `TC-009`;
- se agregó desempate determinista a `TC-010`;
- el evaluador ahora aplica tolerancias, límites inferior/superior de filas,
  columnas obligatorias, tipos numéricos y criterios soportados;
- se rechazaron IDs duplicados y criterios desconocidos;
- se añadió validación semántica básica mediante fragmentos requeridos y
  prohibidos;
- se añadió `golden_negative_dataset.json` con seis rechazos esperados;
- las propuestas del QA Judge ahora se validan con un contrato independiente
  antes de generar cambios.
- los 12 casos positivos ya tienen `semantic_contract` con medidas, filtros,
  períodos o estructuras requeridas y patrones prohibidos;
- el runner expone `model-smoke` y un modo `agent-evaluation` con un archivo
  explícito de DAX generado como adaptador inicial.
- el adaptador de ejecución local ya no depende de `DataTable.Load`, evitando
  falsos fallos por nombres de columnas repetidos;
- el evaluador normaliza los alias DAX entre las formas `Columna` y
  `[Columna]`;
- `TC-006` usa el período 2026 mediante `DATESBETWEEN` sobre `fec_ini`;
- el preflight valida identidad, nivel de compatibilidad, tablas y medidas del
  modelo conectado.

El modo `agent-evaluation` ya está implementado, pero todavía requiere una
invocación autenticada del proxy desplegado; no se considera cerrada la
evaluación dinámica hasta que se capture la tool call real y se ejecute el DAX
producido por ella.

La suite negativa ya se ejecuta sin Power BI porque valida el rechazo antes de
la conexión al modelo. En la ejecución validada, los seis casos obtuvieron
`6/6`.

La ejecución `model-smoke` contra el modelo local identificado por
`0aacc740-d2dd-463b-a56b-e2b782b180dc` obtuvo `12/12`, con P95 de 1024 ms.
Este resultado valida el runner y el baseline contra ese modelo abierto; no
equivale todavía a una evaluación dinámica del agente ni a un snapshot
reproducible para CI.

### RCA y primera evaluación dinámica autenticada

La investigación del HTTP 401 se ejecutó por capas:

1. El runner envía `Authorization: Bearer <token>`; una prueba unitaria
   intercepta la solicitud y evita regresiones.
2. El JWT emitido contiene issuer, audience y versión compatibles con Easy
   Auth.
3. Easy Auth rechaza solicitudes sin token con 401.
4. La causa raíz era doble autenticación: la Function usaba
   `AuthLevel.FUNCTION`, por lo que exigía una Function Key además del token
   Entra. La ruta ahora usa `AuthLevel.ANONYMOUS`, manteniendo Easy Auth
   obligatorio y la validación defensiva de `x-ms-client-principal`.
5. El paquete se reconstruyó para Linux/Python 3.11 con dependencias bajo
   `.python_packages/lib/site-packages` y rutas ZIP POSIX.
6. La llamada autenticada mínima obtuvo HTTP 200 y una tool call
   `execute_dax_query`.

La primera suite dinámica completa obtuvo `1/12` y P95 de 12.201 ms. Este
resultado no es un fallo de infraestructura: constituye el baseline real de
calidad del agente.

| Categoría | Casos | Acción |
|---|---|---|
| Filtros o períodos obligatorios omitidos | TC-001, TC-003, TC-006, TC-009 | Mejorar grounding semántico y comprobar filtros estructuralmente |
| Alias de salida distinto | TC-002, TC-004, TC-005, TC-007, TC-012 | Definir contrato de esquema y normalización controlada de aliases |
| Ranking no reconocido | TC-010 | Sustituir substring matching por análisis tokenizado de DAX |
| Medida incorrecta u omitida | TC-011 | Reforzar catálogo y selección de medidas |
| Caso aprobado | TC-008 | Mantener como control positivo |

El runner ahora registra fallos de generación por caso y continúa con el resto
de la suite. La siguiente iteración no debe reducir exigencias para elevar el
porcentaje: debe distinguir equivalencia semántica de incumplimiento real y
volver a ejecutar los 12 casos.

La segunda iteración incorporó análisis normalizado de fechas y `TOPN`, aliases
numéricos controlados por contrato, reportes saneados y ejecución en tres lotes
de cuatro casos con checkpoint después de cada caso. El resultado consolidado
fue `5/12` (41,7 %) y P95 de 37.190 ms:

- aprobados: `TC-007`, `TC-008`, `TC-009`, `TC-010`, `TC-012`;
- grounding/filtros: `TC-001`, `TC-004`;
- ausencia de tool call: `TC-002`, `TC-003`;
- esquema/alias no inequívoco: `TC-005`, `TC-011`;
- riesgo de memoria por DAX generado: `TC-006`.

La mejora de 8,3 % a 41,7 % proviene de reconocer equivalencias legítimas, no
de eliminar filtros ni medidas obligatorias. El siguiente incremento debe
priorizar `TC-006` porque una consulta que agota memoria es un riesgo operativo,
seguido de tool-call determinista y grounding de proveedor/período.

### Baseline con alcance empresarial uniforme

Los 12 casos positivos quedaron acotados al mismo segmento:

- `source_empresa = "ctb"`;
- `cod_pro = "0301"` (Mondelez);
- `dim_tiempo[fec_ini] = DATE(2026,7,1)`.

El alcance está presente en la pregunta, la consulta de referencia y
`semantic_contract.required_scope`. El validador comprueba la asociación entre
columna y valor mediante `TREATAS` o igualdad explícita; no basta con mencionar
los literales en otra parte de la consulta.

Las consultas de referencia obtuvieron `12/12`, los negativos `6/6` y la
evaluación dinámica acotada obtuvo `6/12` (50 %) con P95 de 42.833 ms:

- aprobados: `TC-002`, `TC-004`, `TC-005`, `TC-007`, `TC-009`, `TC-012`;
- DAX inválido: `TC-001`, `TC-010`;
- esquema/alias no inequívoco: `TC-003`, `TC-008`;
- agotamiento de memoria: `TC-006`;
- medida incorrecta u omitida: `TC-011`.

Este baseline reemplaza al resultado previo para comparaciones futuras, porque
los casos anteriores no compartían el mismo segmento de datos.

## 2. Arquitectura objetivo

La evaluación será híbrida:

1. **Contrato versionado:** pregunta, intención, medidas, filtros, período,
   esquema de salida, restricciones y política de tolerancia.
2. **Generación dinámica:** el agente recibe la pregunta y produce el DAX bajo
   prueba.
3. **Validación semántica:** se comprueba que el DAX respete el contrato y los
   guardrails antes de ejecutarlo.
4. **Modelo controlado:** el DAX generado y el DAX de referencia se ejecutan
   contra una versión identificable del modelo semántico.
5. **Oracle independiente:** el resultado se compara con un snapshot, una
   consulta de referencia, invariantes o reconciliaciones.
6. **Gobernanza:** los cambios de contrato o baseline requieren Pull Request y
   aprobación humana.

No se debe calcular el resultado esperado a partir de la misma consulta
generada por el agente. Eso produciría una validación circular.

## 3. Clasificación de validaciones

### 3.1 Elementos versionados

- ID y dominio.
- Pregunta y variantes lingüísticas aprobadas.
- Intención analítica.
- Medidas y dimensiones obligatorias.
- Filtros y período esperado.
- Columnas y tipos de salida.
- Orden, cardinalidad y unicidad.
- Patrones requeridos y prohibidos.
- Tipo de oracle y tolerancia.
- Versión del modelo y snapshot de datos usados por el baseline.

### 3.2 Elementos dinámicos

- DAX generado por el agente.
- Existencia de tablas, columnas y medidas.
- Versión y fecha máxima disponible del modelo.
- Resultado, esquema, orden y latencia.
- Cumplimiento de guardrails.
- Diferencias respecto al DAX de referencia.
- Drift de modelo y de datos.

### 3.3 Tipos de oracle

- `SnapshotExact`: valor fijo para un período cerrado.
- `ReferenceQuery`: compara el resultado del DAX generado con una consulta
  canónica independiente.
- `NumericRange`: valida límites empresariales razonables.
- `InvariantSet`: valida porcentajes, nulabilidad, tipos, orden y unicidad.
- `Reconciliation`: compara totales contra desgloses o conteos alternativos.
- `ExpectedRejection`: exige que una solicitud insegura o fuera de alcance sea
  rechazada.

## 4. Plan de ejecución por fases

## Fase 0 - Congelar contratos y baseline

**Objetivo:** obtener una referencia reproducible antes de modificar el runner.

### Actividades

1. Registrar la versión del modelo semántico de QA.
2. Definir el snapshot o fecha de corte de datos.
3. Corregir ambigüedades conocidas:
   - `TC-006`: aplicar explícitamente el filtro de 2026.
   - `TC-008`: sustituir "último mes" por un período reproducible.
   - `TC-009`: filtrar todo 2026 y no solamente enero.
   - `TC-010`: agregar desempate determinista al `TOPN`.
4. Ejecutar y guardar los resultados de referencia aprobados.
5. Asignar un propietario funcional a cada dominio.

### Entregables

- Identificador de versión del modelo.
- Fecha de corte del baseline.
- 12 casos corregidos y aprobados.
- Evidencia de ejecución contra el modelo controlado.

### Criterio de salida

Los 12 casos tienen período, filtros, resultado y responsable inequívocos.

---

## Fase 1 - Endurecer contratos y evaluador

**Objetivo:** eliminar falsos positivos y hacer explícito el contrato de cada
criterio.

### Actividades

1. Crear un esquema versionado para `golden_dataset.json`.
2. Validar IDs únicos y campos obligatorios.
3. Rechazar criterios desconocidos; nunca usar éxito por defecto.
4. Implementar tolerancia absoluta y relativa para valores numéricos.
5. Distinguir columna ausente, valor nulo, tipo inválido y resultado vacío.
6. Aplicar `min_filas` y `max_filas`.
7. Añadir validación de columnas, tipos, orden y unicidad.
8. Crear pruebas unitarias para cada criterio y caso de error.

### Entregables

- Esquema JSON o validador tipado.
- Evaluadores desacoplados por criterio.
- Pruebas unitarias del evaluador.
- Mensajes de fallo estructurados.

### Criterio de salida

Cada criterio tiene pruebas positivas y negativas, y un criterio inválido
produce fallo explícito.

---

## Fase 2 - Separar smoke test y evaluación del agente

**Objetivo:** conservar la validación del modelo y añadir la evaluación real del
agente.

### Actividades

1. Renombrar conceptualmente `dax_esperado` a `dax_referencia`.
2. Mantener un modo `model-smoke` que ejecute solo la consulta de referencia.
3. Crear un modo `agent-evaluation` que:
   - envíe `pregunta` al agente;
   - capture la llamada de tool y el DAX generado;
   - valide el contrato;
   - ejecute el DAX generado;
   - ejecute el DAX de referencia;
   - compare resultados.
4. Persistir únicamente hashes, métricas y diagnósticos saneados.
5. Clasificar fallos como:
   - `AGENT_GENERATION`;
   - `SEMANTIC_CONTRACT`;
   - `GUARDRAIL`;
   - `MODEL_DRIFT`;
   - `DATA_BASELINE`;
   - `INFRASTRUCTURE`.

### Entregables

- Adaptador para invocar el agente.
- Captura tipada del DAX generado.
- Modos `model-smoke` y `agent-evaluation`.
- Reporte por categoría de fallo.

### Criterio de salida

Una consulta de referencia correcta no puede ocultar un DAX incorrecto
generado por el agente.

---

## Fase 3 - Validación semántica y guardrails

**Objetivo:** evaluar intención y seguridad, no solamente equivalencia textual.

### Actividades

1. Añadir a cada caso un `semantic_contract`.
2. Verificar medidas, dimensiones, filtros y períodos obligatorios.
3. Detectar patrones prohibidos como eliminación global de filtros o acceso a
   objetos no autorizados.
4. Aplicar los mismos guardrails usados por el cliente antes de ejecutar DAX.
5. Añadir casos `ExpectedRejection` para:
   - escrituras no autorizadas;
   - consultas sin límite;
   - múltiples statements;
   - tablas o columnas sensibles;
   - solicitudes fuera de alcance.
6. Comparar estructura semántica en lugar de exigir igualdad literal de DAX.

### Entregables

- Contrato semántico por caso.
- Validador semántico.
- Suite negativa de seguridad.
- Evidencia de reutilización de guardrails.

### Criterio de salida

Consultas DAX textualmente diferentes pueden aprobar si son semánticamente
equivalentes, y consultas válidas pero inseguras siempre son rechazadas.

---

## Fase 4 - Modelo de QA reproducible

**Objetivo:** eliminar la dependencia exclusiva de cualquier Power BI Desktop
que esté abierto.

### Actividades

1. Seleccionar un destino estable:
   - workspace de QA con endpoint XMLA, preferido para CI;
   - modelo PBIP/PBIX versionado para pruebas locales;
   - Power BI Desktop local solo como modo de desarrollo.
2. Implementar un proveedor de conexión configurable.
3. Ejecutar una comprobación previa de:
   - identidad del modelo;
   - medidas y columnas requeridas;
   - fecha máxima cargada;
   - versión del baseline.
4. Detener la suite si el modelo no coincide con el baseline.
5. Separar errores de autenticación y conectividad de los fallos funcionales.

### Entregables

- Adaptador de conexión.
- Preflight del modelo semántico.
- Configuración segura de QA.
- Ejecución reproducible fuera de Power BI Desktop.

### Criterio de salida

Dos ejecuciones contra la misma versión de modelo y snapshot producen el mismo
resultado funcional.

---

## Fase 5 - Ampliar cobertura a 50 casos

**Objetivo:** ampliar cobertura después de fortalecer el motor de evaluación.

### Matriz mínima

| Área | Mínimo |
|---|---:|
| Valores exactos sobre períodos cerrados | 6 |
| Consultas de referencia | 10 |
| Rangos e invariantes | 8 |
| Rankings, orden y unicidad | 6 |
| Reconciliaciones | 6 |
| Filtros combinados | 6 |
| Rechazos y guardrails | 6 |
| Ambigüedad y abstención | 2 |

Un caso puede cubrir más de un área, pero la matriz debe registrar esa
cobertura explícitamente.

### Variantes requeridas

- empresa, sucursal, proveedor, vendedor, producto y cliente;
- mes, año, rango y último período cerrado;
- cero, nulo, negativo y ausencia de datos;
- sinónimos y errores ortográficos;
- solicitudes ambiguas;
- filtros simples y combinados;
- rankings con empates;
- consultas fuera de alcance.

### Entregables

- 50 casos aprobados.
- Matriz de trazabilidad dominio-riesgo-criterio.
- Revisión funcional por propietarios de dominio.

### Criterio de salida

No se acepta completar la fase solo por cantidad. Todos los riesgos críticos
deben tener al menos un caso positivo y uno negativo.

---

## Fase 6 - CI/CD y política de promoción

**Objetivo:** convertir la evaluación en una puerta real de release.

### Actividades

1. Ejecutar en cada Pull Request:
   - esquema del dataset;
   - pruebas unitarias;
   - contratos estáticos;
   - guardrails;
   - evaluación con fixtures.
2. Ejecutar contra el modelo controlado antes de promover a producción.
3. Ejecutar contra producción en solo lectura para detectar drift.
4. Definir umbrales:
   - 100% en seguridad y criterios deterministas;
   - 100% de consultas ejecutables;
   - cero regresiones frente al baseline;
   - límite de latencia p95;
   - cobertura mínima por dominio.
5. Publicar reportes y artefactos sin prompts, DAX o PII en claro.
6. Impedir que el QA Judge modifique automáticamente baseline o tolerancias.

### Entregables

- Jobs de validación estática, integración y drift.
- Reporte de regresión descargable.
- Reglas de protección de rama.
- Política de actualización de baseline.

### Criterio de salida

Ningún cambio del prompt, tools, guardrails o evaluador puede desplegarse si
falla un caso determinista o de seguridad.

---

## Fase 7 - Cerrar el ciclo del QA Judge

**Objetivo:** permitir mejora continua sin autoaprobación.

### Actividades

1. Convertir incidentes de telemetría en propuestas de caso de regresión.
2. Exigir que cada propuesta incluya:
   - diagnóstico;
   - caso reproducible;
   - contrato semántico;
   - oracle independiente;
   - evidencia antes y después.
3. Crear Pull Request, nunca modificar producción directamente.
4. Ejecutar la suite completa sobre la propuesta.
5. Requerir aprobación del propietario funcional y del arquitecto.
6. Registrar por qué se actualizó un baseline.

### Entregables

- Plantilla de propuesta del QA Judge.
- Automatización de PR.
- Evidencia de regresión adjunta.
- Registro de aprobaciones.

### Criterio de salida

El QA Judge puede proponer mejoras, pero no puede aprobar su propio cambio ni
alterar silenciosamente la definición de éxito.

## 5. Orden y dependencias

```text
Fase 0
  └── Fase 1
        └── Fase 2
              ├── Fase 3
              └── Fase 4
                    └── Fase 5
                          └── Fase 6
                                └── Fase 7
```

Las fases 3 y 4 pueden avanzar en paralelo después de completar la separación
entre smoke test y evaluación del agente.

## 6. Priorización

### P0

- Corregir casos temporales ambiguos.
- Rechazar criterios desconocidos.
- Probar el DAX generado por el agente.
- Establecer un modelo y snapshot controlados.
- Añadir casos de seguridad.

### P1

- Contratos semánticos.
- Oracles independientes.
- Validación de esquema, orden y tipos.
- Clasificación de fallos.
- Integración con CI.

### P2

- Ampliación a 50 casos.
- Variantes lingüísticas.
- Drift de producción.
- Reconciliaciones y pruebas metamórficas.

## 7. Riesgos y controles

| Riesgo | Control |
|---|---|
| Baseline cambia con datos productivos | Snapshot cerrado y versionado |
| El agente se evalúa contra sí mismo | Oracle independiente |
| Falsos positivos por criterios débiles | Tipos, rangos, consultas de referencia y reconciliación |
| Drift del modelo | Preflight y versión de modelo |
| Suite no reproducible | Endpoint QA o modelo versionado |
| QA Judge relaja tolerancias | PR y aprobación humana |
| Datos sensibles en reportes | Hashes y diagnósticos saneados |
| Aumento de costo y latencia | Separar PR rápido, integración y ejecución nocturna |

## 8. Definición global de terminado

Las mejoras del QA Judge se consideran cerradas cuando:

1. Los 50 casos cumplen la matriz de cobertura.
2. El runner evalúa el DAX generado por el agente.
3. Existe un modelo semántico de QA reproducible.
4. Cada caso usa un oracle independiente y una política de tolerancia explícita.
5. Los guardrails tienen casos positivos y negativos.
6. Los fallos se clasifican por agente, modelo, datos, seguridad o
   infraestructura.
7. La suite bloquea releases con regresiones deterministas o de seguridad.
8. Producción se valida en solo lectura mediante drift e invariantes.
9. Los cambios de baseline requieren aprobación humana.
10. El QA Judge propone cambios mediante Pull Request y no puede autoaprobarlos.

## 9. Primer incremento ejecutable

El primer incremento debe limitarse a:

1. Corregir `TC-006`, `TC-008`, `TC-009` y `TC-010`.
2. Implementar esquema y evaluadores estrictos.
3. Separar `model-smoke` de `agent-evaluation`.
4. Migrar los 12 casos al contrato híbrido.
5. Añadir seis casos `ExpectedRejection`.
6. Ejecutar la suite contra un modelo de QA identificado.

Este incremento debe completarse antes de ampliar mecánicamente el dataset a
50 casos.
