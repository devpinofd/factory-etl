# Flujo periódico de QA de datos

## Objetivo

`factory-etl-data-quality-prod` revisa las capas Bronze/staging y Gold sin
recargar archivos, ejecutar Cloud Run ni invocar Dataform. Su única escritura
es el registro idempotente de resultados en
`factory_etl_control.data_quality_results`.

## Ejecución

- Workflow: `factory-etl-data-quality-prod`
- Scheduler: `factory-etl-data-quality-daily-prod`
- Frecuencia: diariamente a las 03:00, zona `America/Caracas`
- Gestión: Terraform
- Dataset de resultados: `factory_etl_control`

El scheduler se ejecuta después del ciclo diario de ingesta y consolidación.
Una ejecución repetida para el mismo día actualiza los mismos cinco `check_id`;
no vuelve a procesar Bronze, Silver ni Gold.

## Controles

1. Existen objetos transaccionales en Bronze.
2. Existe una fecha reciente en `factory_etl_gold.fct_ventas`.
3. No existen filas Gold con `source_empresa` nulo o vacío.
4. No existen duplicados de la clave natural de ventas.
5. Gold no contiene más filas que staging en la última fecha; la diferencia
   esperada corresponde a deduplicación y queda registrada.
6. La última fecha contiene las cinco empresas esperadas.

Cada control queda registrado como `PASS` o `FAIL`, con sus métricas en
`details`. Un `FAIL` no modifica datos: debe investigarse y, si corresponde,
corregirse mediante un backfill controlado desde Bronze.

## Revisión operativa

```sql
SELECT
  run_id,
  check_name,
  status,
  details,
  inserted_at
FROM `factory-etl-prod.factory_etl_control.data_quality_results`
ORDER BY inserted_at DESC;
```

Para revisar una fecha específica, filtrar el JSON de `details` y contrastar
los conteos por empresa en staging y Gold. No se deben ejecutar `DELETE`,
`UPDATE` o cargas manuales como parte de QA.

## Política de reproceso

- QA es de solo lectura sobre los datos de negocio.
- Los resultados son idempotentes por `check_id` y fecha de ejecución.
- Un fallo genera evidencia, no un reproceso automático.
- Los reprocesos se ejecutan solo después de identificar la fecha y entidad
  afectadas, preservando Bronze como fuente de verdad.
