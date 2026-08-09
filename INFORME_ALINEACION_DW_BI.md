# Evaluación de alineación con referentes de Data Warehousing y BI

## Resumen ejecutivo

El proyecto encaja **parcialmente** con las teorías de los principales referentes de Data Warehousing, Business Intelligence y arquitectura de datos. La implementación no contradice esos enfoques, pero requiere alineación adicional para considerarse un Data Warehouse dimensional empresarial completo.

La descripción más precisa del estado actual es:

> **Plataforma moderna Data Lake/Medallion con un datamart empresarial Gold parcialmente dimensionalizado.**

La plataforma tiene una base sólida: ingesta por capas Bronze, Silver y Gold, procesamiento con BigQuery y Dataform, datos atómicos de ventas, dimensiones de negocio, dimensión de tiempo, controles de calidad y seguridad. Sin embargo, la capa Gold todavía se comporta principalmente como un datamart analítico de ventas e inventario.

## Referentes más relevantes

### Ralph Kimball y Margy Ross

**Nivel de alineación: medio.**

El proyecto sigue varios principios de modelado dimensional:

- Existe una tabla de hechos de ventas a nivel de transacción/renglón.
- Se conserva el detalle atómico para permitir diferentes análisis.
- Existe una dimensión de tiempo con calendario, semanas, trimestres y quincenas.
- Existen dimensiones de cliente, artículo, sucursal, vendedor, proveedor y empresa.
- Las métricas de ventas están separadas de los atributos descriptivos.

La alineación todavía es incompleta porque:

- Las dimensiones utilizan principalmente claves naturales compuestas.
- La tabla de hechos no utiliza claves sustitutas como claves foráneas dimensionales.
- Las dimensiones Gold son principalmente proyecciones directas de Silver.
- No se evidencia una estrategia formal de Slowly Changing Dimensions, especialmente Tipo 2.
- No se documenta un Bus Matrix empresarial.
- No todos los procesos de negocio están representados mediante tablas de hechos.

### Bill Inmon

**Nivel de alineación: parcial.**

La arquitectura por capas, la integración de varias empresas y la conservación de datos históricos en Bronze son compatibles con una visión de Data Warehouse corporativo.

No obstante, el proyecto todavía no alcanza plenamente un Enterprise Data Warehouse porque:

- La integración dimensional de todos los procesos aún no está madura.
- La capa Gold está enfocada en casos de uso analíticos concretos.
- No se observa un modelo corporativo integral que incluya formalmente ventas, inventario, precios, monedas y otros procesos relacionados.
- La gobernanza y el catálogo empresarial requieren mayor formalización.

### Christopher Adamson

**Nivel de alineación: incompleto.**

Ventas está bien encaminada como hecho transaccional. Su grano puede expresarse como:

> Una línea de factura por empresa, tipo de documento, sucursal, documento y renglón.

Sin embargo, inventario debería modelarse explícitamente como un hecho de snapshot periódico, con una estructura semejante a:

```text
fecha_key
empresa_sk
almacen_sk
articulo_sk
unidades_disponibles
cajas_disponibles
peso_total_kg
```

Actualmente el inventario se expone principalmente mediante vistas analíticas sobre estructuras Silver, en lugar de representar de forma explícita el proceso de snapshot y su grano.

### DAMA-DMBOK

**Nivel de alineación: inicial/intermedio.**

El proyecto ya contempla elementos importantes:

- Controles de calidad y aserciones.
- Tablas de rechazados o cuarentena.
- Auditoría de cargas y lotes.
- Seguridad y Row-Level Security.
- Gestión de secretos.
- Infraestructura y transformaciones como código.

Para una alineación más completa se requiere formalizar:

- Responsables de datos y data owners.
- Data stewards por dominio.
- Catálogo empresarial de datos.
- Linaje técnico y funcional.
- Acuerdos de calidad y niveles de servicio.
- Glosario de términos de negocio.
- Políticas de retención y clasificación de información.

### James Serra y arquitectura Lakehouse moderna

**Nivel de alineación: buena.**

La arquitectura actual es coherente con prácticas modernas de plataformas de datos:

- Bronze para conservar datos originales.
- Silver para tipificación, limpieza y deduplicación.
- Gold para consumo analítico.
- Cloud Storage como almacenamiento desacoplado.
- BigQuery como motor analítico.
- Dataform para transformaciones versionadas.
- Terraform para infraestructura.
- Orquestación serverless mediante Cloud Run, Workflows y Scheduler.

Es importante distinguir que una arquitectura Lakehouse o Medallion describe principalmente la organización y el flujo de datos. No garantiza por sí sola que la capa Gold cumpla todas las reglas del modelado dimensional de Kimball.

## Evidencia técnica del modelo actual

El proyecto contiene:

- Una tabla de hechos de ventas (`fct_ventas`).
- Dimensiones Gold de artículo, cliente, empresa, sucursal, vendedor, proveedor y tiempo.
- Una clave operacional compuesta para ventas:
  `source_empresa + tipo_documento + cod_suc + documento + renglon`.
- Particionamiento de ventas por fecha y clustering por empresa, sucursal, proveedor y vendedor.
- Aserciones de unicidad y no nulidad principalmente en Silver y dimensiones.
- Vistas analíticas para inventario, activación de clientes, evolución de ventas y facturación.
- Capas Bronze, Staging, Silver y Gold implementadas sobre GCP.

## Principales brechas de alineación

### 1. Claves sustitutas

Las dimensiones deberían contar con claves técnicas propias, por ejemplo:

```text
articulo_sk
cliente_sk
sucursal_sk
vendedor_sk
proveedor_sk
empresa_sk
```

Las claves naturales de FactorySoft, como `cod_art` o `cod_cli`, deben conservarse como claves de negocio para trazabilidad, pero no deberían ser la única forma de relacionar hechos y dimensiones.

### 2. Historial de dimensiones

Cuando cambien atributos relevantes de un artículo, cliente, vendedor o proveedor, se debe decidir si el cambio:

- Sobrescribe el valor actual, como SCD Tipo 1.
- Conserva versiones históricas, como SCD Tipo 2.

Para SCD Tipo 2 normalmente se requieren atributos como:

```text
version_desde
version_hasta
es_version_actual
```

### 3. Relaciones entre hechos y dimensiones

La tabla de hechos debería referenciar dimensiones mediante claves sustitutas en lugar de repetir descripciones:

```text
fecha_key
empresa_sk
sucursal_sk
cliente_sk
articulo_sk
vendedor_sk
proveedor_sk
```

### 4. Eliminación de columnas descriptivas del hecho

Las siguientes columnas deberían trasladarse progresivamente a sus dimensiones:

| Columna | Destino recomendado |
|---|---|
| `nom_cli` | `dim_cliente` |
| `nom_art` | `dim_articulo` |
| `modelo` | `dim_articulo` |
| `nom_ven` | `dim_vendedor` |
| `nom_pro` | `dim_proveedor` |
| `nom_mar` | `dim_articulo` o `dim_marca` |
| `nom_dep` | Dimensión o jerarquía de producto |
| `cod_sec` | Dimensión o jerarquía de producto |
| `nom_est` | Dimensión geográfica o cliente |
| `nom_ciu` | Dimensión geográfica o cliente |

Se recomienda conservar temporalmente las claves naturales y las columnas descriptivas durante una etapa de transición, hasta migrar los consumidores analíticos.

### 5. Hechos adicionales

Para avanzar hacia un DW dimensional más completo deberían evaluarse hechos separados para:

- Inventario como snapshot periódico.
- Movimientos de almacén.
- Listas de precios.
- Tasas de moneda.
- Compras o abastecimiento, si existe información suficiente.

Cada hecho debe tener un grano explícito y no mezclar niveles de detalle.

### 6. Bus Matrix empresarial

Debe documentarse una matriz que relacione procesos de negocio, grano y dimensiones conformadas. Un ejemplo inicial sería:

| Proceso | Grano | Tiempo | Empresa | Producto | Cliente | Sucursal | Vendedor | Almacén |
|---|---|---|---|---|---|---|---|---|
| Ventas | Línea de factura | Sí | Sí | Sí | Sí | Sí | Sí | No |
| Inventario | Artículo-almacén-fecha | Sí | Sí | Sí | No | No | No | Sí |
| Precios | Documento/renglón o artículo-vigencia | Sí | Sí | Sí | No | No | No | No |
| Monedas | Moneda-vigencia | Sí | Sí | No | No | No | No | No |

#### Contratos para promoción

Antes de promover a Producción se deben cerrar cuatro hechos versionados: `fct_ventas_v2`
por línea de factura, `fct_inventario_snapshot` por artículo-almacén-fecha,
`fct_precios_snapshot` por artículo-vigencia y `fct_monedas_snapshot` por
moneda-vigencia. Todos deben relacionarse con dimensiones conformadas mediante
claves sustitutas; las claves naturales se conservan sólo para búsqueda y
conciliación.

Las dimensiones de cliente, artículo, vendedor, sucursal, almacén y proveedor
seguirán SCD2 cuando el cambio afecte la interpretación histórica, y SCD1 para
correcciones administrativas. `documento` y `renglon` serán dimensiones
degeneradas del hecho de ventas. La conformidad entre empresas queda limitada a
atributos comunes hasta que exista un mapeo MDM aprobado.

## Conclusión

El modelo no necesita una reconstrucción total. La arquitectura de plataforma está bien encaminada y es compatible con prácticas modernas de datos. La principal necesidad es fortalecer el diseño dimensional de la capa Gold.

El proyecto se encuentra en una etapa intermedia:

> **Más avanzado que un conjunto de reportes aislados, pero aún por debajo de un Data Warehouse dimensional empresarial plenamente conformado.**

Las prioridades recomendadas son:

1. Formalizar el grano de cada proceso.
2. Introducir claves sustitutas en las dimensiones.
3. Relacionar la tabla de hechos mediante claves dimensionales.
4. Definir las estrategias SCD.
5. Modelar inventario como snapshot periódico.
6. Crear dimensiones conformadas.
7. Documentar el Bus Matrix.
8. Completar catálogo, linaje, ownership y gobierno de datos.

## Referencia doctrinal

La evaluación dimensional se basa principalmente en las reglas de modelado de:

- [Kimball Group: The 10 Essential Rules of Dimensional Modeling](https://www.kimballgroup.com/2009/05/the-10-essential-rules-of-dimensional-modeling/)

Este documento es una evaluación conceptual basada en la inspección estática del repositorio. No modifica código ni valida cardinalidades o resultados de ejecución directamente en BigQuery.
