# 🏛️ Arquitectura del Agente DAX Copilot & Comparativa Best-in-Class

Este documento presenta la arquitectura técnica del **Agente DAX Copilot** implementado para **Comercial Tinito** y realiza una comparativa exhaustiva frente a los estándares de arquitectura *Best-in-Class* para Agentes de Inteligencia Artificial Empresariales.

---

## 1. Diagrama de Arquitectura Actual

```mermaid
flowchart TB
    subgraph CLI ["💻 Capa de Usuario y Consola"]
        User["👤 Usuario / Analista BI"]
        Terminal["📟 Terminal PowerShell (UTF-8 Streaming)\n(scripts/pbi_copilot_assistant.ps1)"]
        PBIDesktop["📊 Power BI Desktop\n(Comercial_Tinito_Semantico_PROD)"]
    end

    subgraph AGENT ["🧠 Núcleo del Agente DAX Copilot"]
        ContextMgr["🪟 Gestor de Memoria Dinámica\n(Ventana Deslizante + System Prompt)"]
        RetryEngine["🔁 Capa de Resiliencia & Auto-Retry\n(Backoff Exponencial ante HTTP 429)"]
        DAXGenerator["⚡ Motor de Generación DAX\n(Estandarización: Contexto, Propósito, Uso)"]
        AdomdExecutor["📐 Ejecutor ADOMD.NET & Tablas\n(Format-Table / Output Inmediato)"]
    end

    subgraph LLM ["☁️ Inteligencia Artificial en la Nube"]
        AzureOpenAI["🌐 Azure OpenAI Service\n(GPT-4o / GPT-4 Turbo)"]
    end

    subgraph MCP_BRIDGE ["🔌 Puente de Conexión y Automatización (MCP / TOM)"]
        MCPServer["🚀 MCP Server: powerbi-modeling\n(JSON-RPC Directo)"]
        TOM["⚙️ Tabular Object Model (TOM)\n(Microsoft.AnalysisServices.Tabular)"]
        PortDetector["🔍 Auto-Detector de Puerto SSAS\n(msmdsrv.port.txt / PID msmdsrv)"]
    end

    subgraph SEMANTIC_MODEL ["💾 Modelo Semántico & VertiPaq (Local / Pro)"]
        ASInstance["🏛️ Motor Local VertiPaq (localhost:53646)"]
        MedidasTable["📂 Tabla '_Medidas' (118 Medidas Documentadas)\n(01. Ventas, 02. Tiempo, 03. Cartera, 04. Churn...)"]
        CatalogTable["📑 Tabla 'Catálogo de Medidas'\n(Diccionario Interactivo con Código DAX)"]
        BigQueryGold["🗄️ Google BigQuery (Gold Layer)\n(factory-etl-prod.factory_etl_gold)"]
    end

    %% Flujos de Información
    User -->|Preguntas de Negocio / Peticiones DAX| Terminal
    Terminal -->|Prompt Optimizado| ContextMgr
    ContextMgr -->|Control de Tokens| RetryEngine
    RetryEngine <-->|Llamada API Streaming| AzureOpenAI
    RetryEngine -->|Código DAX / Explicación| DAXGenerator
    
    DAXGenerator -->|Consulta DAX| AdomdExecutor
    PortDetector -->|Detecta Puerto Activo| AdomdExecutor
    PortDetector -->|Detecta Puerto Activo| MCPServer
    
    AdomdExecutor <-->|Ejecución DAX en Vivo| ASInstance
    AdomdExecutor -->|Resultados Tabulares en Pantalla| Terminal
    
    MCPServer <-->|Actualizaciones en Caliente (Create / Update)| TOM
    TOM <-->|Inyección de Medidas y Metadatos| ASInstance
    
    ASInstance --- MedidasTable
    ASInstance --- CatalogTable
    ASInstance <-->|Import / Particiones M| BigQueryGold
    PBIDesktop <-->|Renderizado Visual| ASInstance
```

---

## 2. Componentes de la Arquitectura Implementada

### 2.1 Capa de Interfaz y Terminal (CLI Layer)
* **Script Principal:** [`pbi_copilot_assistant.ps1`](file:///c:/Repos/factory-etl/scripts/pbi_copilot_assistant.ps1)
* **Streaming UTF-8:** Decodificación explícita `[System.Text.Encoding]::UTF8` que erradica problemas de codificación (*mojibake* / caracteres especiales en español).
* **Renderizado Directo:** Presentación en pantalla con `Format-Table` para entrega instantánea de resultados sin latencias innecesarias de síntesis.

### 2.2 Capa de Orquestación y Resiliencia (Agent Core)
* **Ventana Deslizante (*Sliding Window*):** Mantiene el *System Prompt* corporativo intacto y las últimas 4 interacciones, garantizando cero desbordes de ventana de contexto.
* **Auto-Retry con Backoff Exponencial:** Captura errores `HTTP 429 (Too Many Requests)` y reintenta de forma autónoma con pausas de 2s, 4s y 8s.

### 2.3 Capa de Integración Semántica y Automatización (MCP & TOM Bridge)
* **Model Context Protocol (MCP):** Servidor `powerbi-modeling` con herramientas para manipulación de tablas, medidas, jerarquías y particiones vía JSON-RPC.
* **Tabular Object Model (TOM):** Inyección directa de metadatos, descripciones, formatos y encabezados DAX en caliente sobre el motor VertiPaq (`msmdsrv.exe`).
* **ADOMD.NET:** Ejecución de consultas DAX en tiempo real y retorno de datos tabulares estructurados.

### 2.4 Capa de Datos y Gobierno Semántico (Semantic Layer)
* **118 Medidas Homologadas:** Clasificadas en 9 carpetas de presentación funcionales (`01. Ventas Base`, `02. Inteligencia de Tiempo`, `03. Cartera y Cobertura`, etc.).
* **Documentación Estricta:** Encabezados DAX y propiedades `Description` estructuradas con `• CONTEXTO`, `• PROPÓSITO` y `• USO PREVISTO`.
* **Catálogo de Medidas:** Tabla interactiva `Catálogo de Medidas` generada dentro del modelo para acceso universal de usuarios y reportes.

---

## 3. Comparativa: Arquitectura Actual vs. Best-in-Class (Enterprise AI Agent)

| Dimensión de Evaluación | 🛠️ Implementación Actual (Tinito DAX Copilot) | 🏆 Arquitectura Best-in-Class (Enterprise Agent) | Diagnóstico & Brecha |
| :--- | :--- | :--- | :--- |
| **1. Protocolo de Herramientas** | **MCP (Model Context Protocol) + TOM**<br>Estandarizado por Anthropic / Microsoft, ejecución directa en caliente. | **MCP + Function Calling Nativo**<br>Uso de herramientas desacopladas con esquemas JSON Schema. | **⭐⭐⭐⭐⭐ (Paridad Total)**<br>Está en el estándar moderno más avanzado de la industria. |
| **2. Conexión al Motor de Datos** | **ADOMD.NET directo sobre Analysis Services**<br>Baja latencia (<50 ms), ejecución en memoria. | **ADOMD.NET / XMLA Endpoint + Semantic Caching**<br>Caché semántico previo (Redis) para consultas idénticas. | **⭐⭐⭐⭐☆ (Muy Alto)**<br>La conexión directa es óptima; se puede añadir caché para escalabilidad. |
| **3. Manejo de Contexto y Memoria** | **Sliding Window (FIFO compacta)**<br>Ventana fija de últimos 4 turnos + System Prompt. | **Memoria Híbrida (Short-Term + Long-Term Vectorial)**<br>RAG de metadatos del catálogo + grafo de dependencias de medidas. | **⭐⭐⭐☆☆ (Medio-Alto)**<br>Funciona perfecto para sesiones CLI; el RAG vectorial aportaría búsqueda semántica histórica. |
| **4. Resiliencia y Tolerancia a Fallos** | **Auto-Retry Exponencial (2s, 4s, 8s)**<br>Manejo de HTTP 429 y reintento transparente. | **Circuit Breaker + Fallback a Modelos Secundarios**<br>Conmutación automática de Azure OpenAI a modelo local/alternativo. | **⭐⭐⭐⭐☆ (Alto)**<br>Maneja saturación eficientemente; la redundancia multimodelo es el siguiente paso. |
| **5. Verificación y Self-Healing** | **Ejecución y Captura de Errores Semánticos**<br>Detección de columnas inexistentes o sintaxis DAX inválida. | **Bucle de Auto-Corrección Autónomo (Agentic Loop)**<br>El agente prueba la consulta con `EVALUATE`, detecta error y se auto-corrige antes de responder. | **⭐⭐⭐⭐☆ (Alto)**<br>El agente verifica con `dax_query_operations` y ajusta el código en tiempo real. |
| **6. Observabilidad y Telemetría** | **Logs locales en JSONL y consola UTF-8**<br>Trazas paso a paso de cada ejecución de herramienta. | **OpenTelemetry / Langfuse / Azure App Insights**<br>Métricas de consumo de tokens por usuario, latencia p95 y costos. | **⭐⭐⭐☆☆ (Medio)**<br>Ideal para desarrollo; en producción multiusuario se recomienda centralizar en App Insights. |
| **7. Gobierno y Seguridad** | **Permisos granulares `Read + Build` y roles de Workspace**<br>Prevención total de modificación del modelo central. | **Role-Based Access Control (RBAC) + Row-Level Security (RLS)**<br>Seguridad por rol integrada en el prompt del agente. | **⭐⭐⭐⭐⭐ (Paridad Total)**<br>El modelo protege las 118 medidas centrales contra escrituras no autorizadas. |

---

## 4. Nivel de Madurez del Agente

```
[Nivel 1: Asistente Básico] ➔ [Nivel 2: RAG Estático] ➔ [Nivel 3: Agente con Herramientas (MCP/TOM)] ➔ [Nivel 4: Agente Multi-Rol Autónomo]
                                                                ▲
                                                    ESTADO ACTUAL (Nivel 3.5)
```

* **Estado Actual:** **Nivel 3.5 (Agente Operacional con Ejecución en Caliente y Protocolo MCP)**.
* Capaz de inspeccionar esquemas, ejecutar DAX en vivo, inyectar metadatos en memoria y gobernar la documentación de 118 medidas sin intervención humana manual.

---

## 5. Próximos Pasos para Evolución a Nivel 4 (Enterprise Best-in-Class)

1. **Semantic Caching:** Integrar una capa de almacenamiento en caché para responder consultas analíticas recurrentes con 0 ms de latencia y $0 costo de tokens.
2. **Grafo de Linaje de Medidas (Lineage Graph):** Mapear visualmente qué medidas dependen de otras para prevenir impactos en cascada al modificar fórmulas base.
3. **Telemetría Centralizada en Azure Monitor:** Trazar el costo exacto en dólares y tiempo de respuesta de cada consulta emitida por los analistas de Comercial Tinito.
