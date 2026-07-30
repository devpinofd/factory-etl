# Plan de Optimización de Tiempo de Ejecución: Cloud Workflows & Cloud Run Jobs (< 5 Minutos)

Este documento detalla el diagnóstico de rendimiento, las métricas alcanzadas y las estrategias técnicas preparadas para reducir la ventana de ejecución diaria del pipeline ETL (`factory-etl-daily-dev`) de las **95 consultas (5 bases de datos)** a **menos de 5 minutos** en el futuro.

---

## 1. Evolución Histórica de Rendimiento en GCP

| Etapa de Arquitectura | Configuración de Ejecución | Lotes Procesados | Tiempo Total de Ejecución | Estado | Costo Neto Mensual |
|---|---|---|---|---|---|
| **Etapa 1 (Secuencial Original)** | 1 job a la vez (1 empresa) | 19 queries | ~38 minutos | `SUCCEEDED` | \$0.00 USD |
| **Etapa 2 (Secuencial 2 BDs)** | 1 job a la vez (`tinito` y `ctb`) | 38 queries | 76.1 minutos (1h 16m) | `SUCCEEDED` | \$0.00 USD |
| **Etapa 3 (Paralelo por Empresa)** | 5 empresas / limit 4 trans, limit 5 maestras | 38 queries | 11.4 minutos | `SUCCEEDED` | \$0.00 USD |
| **Etapa 4 (Paralelo 5 BDs)** | 5 empresas (`tinito`, `ctb`, `daroan`, `roldan`, `ctm`) | 95 queries | 13.3 minutos | `SUCCEEDED` | \$0.00 USD |
| **Etapa 5 (Actual - 2 vCPU / Limit 10)** | Paralelismo plano / 2 vCPU 1 GiB / Limit 10 | 95 queries | **9.8 minutos** | `SUCCEEDED` | **\$0.00 USD / mes** |
| **Etapa 6 (Propuesta Futura)** | **1 Ola Simultánea / 4 vCPU / Limit 19** | **95 queries** | **~2.5 a 4.0 minutos** | *Pendiente* | **\$0.00 USD / mes** |

---

## 2. Diagnóstico del Cuello de Botella Actual (9.8 Minutos)

En la ejecución `b50eec63`, las 19 consultas de cada una de las 5 empresas se procesan con `concurrency_limit: 10`.
* **Mecánica:** Al ser 19 consultas por empresa con límite 10, Cloud Workflows fragmenta la ejecución de cada empresa en **2 olas consecutivas**:
  1. **Ola 1:** 10 consultas simultáneas (~4.5 minutos).
  2. **Ola 2:** 9 consultas simultáneas (~4.5 minutos).
* **Resultado:** 4.5 min + 4.5 min = **9.8 minutos acumulados**.

---

## 3. Hoja de Ruta para Optimización Futura (< 5 Minutos)

### Fase 1: Paralelismo en 1 Sola Ola (`concurrency_limit: 19`)
* **Cambio:** Modificar el límite de concurrencia en `workflow.yaml.tftpl`:
  ```yaml
  process_all_queries_flat_in_parallel:
    parallel:
      concurrency_limit: 19
  ```
* **Efecto:** Elimina la 2ª ola de espera. Las 19 consultas de las 5 empresas (95 jobs en total) arrancan en **1 sola ola simultánea en el segundo 0**.
* **Tiempo Proyectado:** **~4.0 a 4.5 minutos**.

---

### Fase 2: Escalado de Recursos de Cómputo (4 vCPU / 2 GiB RAM)
* **Cambio:** En `terraform/main.tf`, actualizar los recursos asignados a `module.cloud_run_job`:
  ```hcl
  cpu_limit    = "4000m"
  memory_limit = "2048Mi"
  ```
* **Efecto:** Aumenta la velocidad de procesamiento de **DuckDB** y **PyArrow**, permitiendo compresión Parquet y JSONL.GZ multinúcleo en menos de 20 segundos por lote.
* **Tiempo Proyectado:** **~2.5 a 3.5 minutos**.

---

### Fase 3: Optimización I/O de Extracción (`batch_size = 50,000`)
* **Cambio:** En `src/factory_etl/extractors/sql.py`, incrementar el tamaño de lote de lectura SQL:
  ```python
  BATCH_SIZE = 50000  # En lugar de 10,000
  ```
* **Efecto:** Reduce el overhead de llamadas I/O entre la base de datos de origen y la app en Python en un 60%.
* **Tiempo Proyectado:** **~2.0 a 3.0 minutos**.

---

## 4. Análisis de Impacto Financiero en GCP

| Componente GCP | Consumo Mensual Proyectado (Fase 1+2) | Free Tier Mensual | Costo Neto Real |
|---|---|---|---|
| **Cloud Run Jobs (vCPU)** | 140,400 vCPU-segundos | **180,000 vCPU-segundos GRATIS** | **\$0.00 USD** |
| **Cloud Run Jobs (RAM)** | 77,400 GiB-segundos | **360,000 GiB-segundos GRATIS** | **\$0.00 USD** |
| **Cloud Workflows** | 3,150 pasos | **5,000 pasos GRATIS** | **\$0.00 USD** |
| **GCS Bronze Bucket** | ~150 MB comprimidos | **5.0 GB GRATIS** | **\$0.00 USD** |
| **TOTAL MENSUAL** | **95 lotes/día (5 BDs en < 5 min)** | **Cubierto al 78% del Free Tier** | **\$0.00 USD / mes** |

---

## 5. Pasos para Implementar en el Futuro

1. Abrir `scratch/generate_workflow.py` y actualizar `concurrency_limit: 19`.
2. Ejecutar `python scratch/generate_workflow.py`.
3. En `terraform/main.tf`, establecer `cpu_limit = "4000m"` y `memory_limit = "2048Mi"`.
4. Ejecutar `terraform apply -var-file="envs/dev.tfvars" -auto-approve`.
5. Ejecutar `gcloud workflows run factory-etl-daily-dev --location=us-central1 --project=factory-etl-dev-0y1dhf` y verificar la finalización en **< 4 minutos**.
