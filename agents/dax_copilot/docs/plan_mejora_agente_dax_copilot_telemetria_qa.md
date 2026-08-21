# 🚀 Plan Maestro: Despliegue, Gobernanza y Ciclo de Vida en Azure AI Foundry

**Proyecto:** Agente DAX Copilot para Power BI  
**Empresa:** Comercial Tinito  
**Fecha:** Agosto 2026  
**Documento:** Plan Integral de Arquitectura, Despliegue Zero-Touch, Seguridad (P0-P3) y Gestión de Ciclo de Vida (ALM) en Azure AI Foundry

---

## 1. Visión y Objetivos Estratégicos

Este documento consolida la arquitectura objetivo para transformar el prototipo local del **Agente DAX Copilot** en una plataforma empresarial robusta, segura y escalable gestionada integralmente en **Azure AI Foundry (Azure AI Agent Service)**.

### Pilares Clave del Plan:
1. **Seguridad y Custodia de Secretos (Resolución P0):** Eliminación total de API keys en scripts locales mediante Proxy Backend con Managed Identity y autenticación Microsoft Entra ID.
2. **Despliegue Confiable Zero-Touch con Fallback:** Ejecución verificada con checksum SHA256 y resiliencia offline.
3. **Gobernanza del Agente de QA (Human-in-the-Loop + Golden Dataset):** El agente evaluador propone mejoras vía Pull Requests y validación sobre un dataset de regresión antes de promover cambios a producción.
4. **Tool-Calling Determinista Nativo & Guardrails:** Adopción de Function Calling nativo de OpenAI/Foundry con límites de ejecución DAX (máx. 5.000 filas, timeout 60 s).
5. **Telemetría Robusta & Cumplimiento PII:** Ingesta por lotes con cola local *outbox*, pseudonimización de usuarios y retención controlada en Azure Log Analytics.

---

## 2. Diagrama de Arquitectura Objetivo en Azure AI Foundry

```mermaid
flowchart TB
    subgraph CLIENT_ZONE ["💻 Puestos de Trabajo de Analistas (Clientes Locales)"]
        User["👤 Analista BI (Luis Malavé / Equipo)"]
        Launcher["⚡ Launcher Seguro (launch_copilot.bat)\n(Verifica Checksum SHA256 + Cache Offline)"]
        LocalPBIDesktop["📊 Power BI Desktop (VertiPaq Engine: Port)"]
    end

    subgraph AZURE_SECURITY ["🛡️ Capa de Seguridad y Gateway en Azure"]
        EntraID["🔑 Microsoft Entra ID (Auth Corporativa)"]
        APIProxy["🚪 Azure Function Proxy / Agent Gateway\n(Managed Identity - Cero Claves Expuestas)"]
        KeyVault["🔐 Azure Key Vault (Custodia Centralizada)"]
    end

    subgraph FOUNDRY_CORE ["🏛️ Azure AI Foundry (Agent Service Core)"]
        AgentRuntime["🧠 Agente DAX Copilot (GPT-4o)\n(Managed Thread State & Function Calling)"]
        PromptRegistry["📚 Agent Registry & Versioned System Prompts\n(v1.0.0, v1.1.0-stable)"]
        DaxGuardrails["🛡️ DAX Guardrails Engine\n(Allow-List, Max 5K Rows, Timeout 60s)"]
    end

    subgraph DETERMINISTIC_BRIDGE ["⚙️ Ejecución Determinista Local"]
        ADOMD["📐 ADOMD.NET (Lectura en Memoria VertiPaq)"]
        TOM_Engine["⚙️ TOM (Inyección Segura de Medidas)"]
        ExcelExporter["📊 Motor Nativo OpenXML (.XLSX)"]
    end

    subgraph TELEMETRY_OBSERVABILITY ["📊 Telemetría y Observabilidad en Azure"]
        OutboxQueue["📦 Cola Local Outbox (copilot_qa_history.jsonl)"]
        DCR_Ingestion["📥 Log Analytics Data Collection Rule (DCR)\n(Ingesta Asíncrona con Pseudonimización PII)"]
        LogAnalytics["🗄️ Azure Log Analytics / App Insights"]
    end

    subgraph QA_LIFECYCLE_LOOP ["🎓 Bucle de Calidad y Ciclo de Vida (ALM)"]
        QAAgent["🧑‍⚖️ Agente de QA (OpenAI o1 / GPT-4o Reasoning)"]
        GoldenDataset["🧪 Golden Dataset de Regresión\n(50 Preguntas y Resultados DAX Esperados)"]
        PullRequest["📝 Pull Request / Aprobación Humana (Francisco Pino)"]
    end

    %% Flujos de Operación
    User --> Launcher
    Launcher -->|1. Autenticación con Token| EntraID
    Launcher -->|2. Petición Segura| APIProxy
    APIProxy -->|3. Valida y Redirige con Managed Identity| AgentRuntime
    KeyVault -.->|Custodia Credenciales| APIProxy
    
    AgentRuntime -->|4. Emite Function Calling Nativo| DaxGuardrails
    DaxGuardrails -->|5. Ejecuta Consulta Validada| ADOMD
    ADOMD <--> LocalPBIDesktop
    ADOMD --> ExcelExporter
    
    %% Flujo de Telemetría
    Launcher -.->|Eventos en Lotes| OutboxQueue
    OutboxQueue -.->|Batching Asíncrono| DCR_Ingestion
    DCR_Ingestion --> LogAnalytics
    
    %% Bucle de QA y Gobernanza
    LogAnalytics -->|Auditoría Diaria de Incidentes| QAAgent
    QAAgent -->|Valida Mejoras vs Dataset| GoldenDataset
    GoldenDataset -->|Si pasa 100%| PullRequest
    PullRequest -->|Aprobado por Arquitecto| PromptRegistry
    PromptRegistry -->|Actualiza Reglas en Producción| AgentRuntime
```

---

## 3. Matriz de Tratamiento de Brechas y Mejoras (P0 a P3)

| Prioridad | Oportunidad Identificada | Solución Arquitectural en Azure AI Foundry | Componente / Estado real |
| :---: | :--- | :--- | :--- |
| **🔴 P0** | **Secreto API Key expuesto en `.ps1`** | Implementar **Azure Function Proxy con Managed Identity**. El cliente solo envía su token de Entra ID; la clave nunca sale de Azure. | **Implementado y desplegado:** Managed Identity, `FUNCTION` auth, sin fallback de API key y `AuthLevel.FUNCTION` en `func-dax-copilot-proxy`. |
| **🔴 P0** | **`iex (irm ...)` sin verificación** | Launcher verifica **hash SHA256 publicado en Azure App Config** antes de ejecutar. Fallback a copia local firmada. | **Implementado parcialmente:** el launcher valida `manifest.json` + SHA-256 antes de ejecutar y soporta LAN/offline. Falta reemplazar hash por firma criptográfica real. |
| **🔴 P0** | **QA Agent auto-modificando reglas** | **Human-in-the-Loop + Golden Dataset:** El agente evaluador genera propuestas como Pull Requests en GitHub y requiere pasar 50 tests de regresión antes de despliegue. | **Implementado:** QA Judge sin `shell=True`, propuestas por PR y dataset dorado versionado; falta ampliar cobertura de regresión. |
| **🟠 P1** | **Telemetría frágil (`Start-Job`)** | Cola local *outbox* (`jsonl`) con reintentos y envío por lotes (*batching*) mediante **Log Analytics Ingestion API (DCR)**. | **Implementado:** outbox local saneado sin PII + DCE `dce-dax-copilot`, DCR `dcr-dax-copilot` y tabla `DaxCopilotEvent_CL` (retención 90 días) provisionados; la Function ingiere eventos vía DCR con Managed Identity y muestreo configurable. |
| **🟠 P1** | **Tool-calling por regex `[EXECUTE_DAX]`** | Migrar a **Function Calling nativo de OpenAI / Foundry Tools** con esquemas JSON estructurados y límite de 5 iteraciones ReAct. | **Implementado:** tools fijas en proxy, resultados `role="tool"`, contratos de request y whitelist de tools. |
| **🟠 P1** | **Sin Guardrails sobre DAX** | Interceptor que valida sintaxis (`EVALUATE`/`ROW`), aplica `TOPN 5000` de seguridad y `CommandTimeout = 60s`. | **Implementado:** guardrails centralizados en `dax_guardrails.ps1`, límite de longitud, rechazo de múltiples statements y bloqueo de consultas directas sin `TOPN`/`SAMPLE`. |
| **🟠 P1** | **Privacidad / PII en trazas** | Pseudonimización del usuario con SHA-256 (`hash(email)`), exclusión de valores literales sensibles y retención de 90 días en Log Analytics. | **Implementado parcialmente:** hash SHA-256 de usuario y eventos sin prompts/DAX en claro; falta retención formal de 90 días en Log Analytics. |
| **🟠 P1** | **Autenticación corporativa en el proxy** | Habilitar **Easy Auth / Entra ID** en la Function con tenant, audiencia y validación de principal. | **Implementado y verificado en Azure:** Easy Auth activo, `Return401`, issuer del tenant, audiencia `api://e9545efd-83a8-4b56-a297-1c05c7d1f51b/func-dax-copilot-proxy-auth`, scope `access_as_user`. |
| **🟠 P1** | **Mutaciones TOM sin respaldo persistente** | Snapshot previo a `inject_measure` y rollback verificable. | **Implementado:** snapshot JSON persistente y rollback explícito mediante `rollback <snapshot>`; rollback en memoria ante fallos de `SaveChanges()`. |
| **🟡 P2** | **System Prompt en Base64** | Desacoplar a `system_prompt.md` en **Azure AI Foundry Prompt Registry** con versionado semántico (`v1.2.0`). | **Implementado parcialmente:** prompt desacoplado y versionado en repositorio; falta migrar a registro Foundry formal. |
| **🟡 P2** | **Resiliencia offline del Launcher** | Si no hay conexión a Azure/LAN, el launcher carga la **última copia local verificada** (`OFFLINE_CACHE`). | **Implementado:** fallback local cacheado y fallback a copia del repositorio. |
| **🟡 P2** | **Costos de Telemetría y QA** | Muestreo de eventos de éxito (10% en éxitos, 100% en errores). El QA Agent con modelo o1 solo analiza anomalías agregadas. | **Pendiente:** no implementado. |
| **🟡 P2** | **Distribución controlada del agente** | Empaquetar launcher + instalador + manifiesto para Intune/GPO/SCCM con variables de entorno corporativas. | **Implementado:** `install_copilot.ps1`, publicación de artefactos en Storage privado y pipeline de release actualizado. |
| **🟡 P2** | **CI/CD sin despliegue real** | OIDC + `azure/login@v2` + publicación automática en Function y Storage tras validaciones. | **Implementado:** workflow actualizado con OIDC, validaciones, empaquetado, zip deploy, subida de artefactos y verificación del deployment. |
| **🟢 P3** | **Exportación nativa a Excel** | **Completado:** Motor OpenXML nativo que genera archivos `.xlsx` formateados con tablas, colores corporativos y autofiltros. | **`Export-NativeExcelXlsx` (Listo)** |
| **🟢 P3** | **Batería de Pruebas Pester** | 50 pruebas automatizadas sobre el modelo `Comercial_Tinito_Semantico_PROD` ejecutables vía CI/CD. | **Pendiente:** aún no se alcanzó cobertura completa; se validan contratos y pruebas críticas. |

---

## 4. Diseño del Proxy Backend en Azure (Cero Secretos en Clientes)

### 4.1 Arquitectura del Proxy (Azure Function Consumption)
* **Costo mensual estimado:** **~$0.00 / mes** (dentro del *free tier* de 1M de ejecuciones y 400.000 GB-s).
* **Autenticación:** El analista inicia sesión en PowerShell con su cuenta corporativa Microsoft 365 (`Connect-AzAccount` o token MSAL interactivo).
* **Seguridad:** La Azure Function valida el token JWT del analista y utiliza **Managed Identity** para consultar Azure OpenAI sin que ningún usuario conozca la API Key.

```mermaid
sequenceDiagram
    autonumber
    actor User as Analista BI (PowerShell)
    participant Entra as Microsoft Entra ID
    participant Proxy as Azure Function Proxy (East US)
    participant OpenAI as Azure OpenAI (GPT-4o)
    participant AS as VertiPaq (Power BI Local)

    User->>Entra: Autenticación Interactiva (M365)
    Entra-->>User: Bearer JWT Token (Corta duración)
    User->>Proxy: POST /api/chat-stream (JWT + Pregunta)
    Proxy->>Proxy: Valida JWT + Rate Limit por Usuario
    Proxy->>OpenAI: Request con Managed Identity (Streaming)
    OpenAI-->>Proxy: Tokens de Respuesta + Tool Call JSON
    Proxy-->>User: Stream SSE Seguro
    User->>AS: Ejecuta DAX localmente vía ADOMD.NET
    AS-->>User: Resultado Tabular / Exporta .xlsx
```

---

## 5. Implementación del Ciclo de Vida del Agente en Azure AI Foundry (ALM)

### 5.1 Registro y Versionado del Agente (`azure-ai-projects` SDK)
```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Conectar al Proyecto Foundry de Comercial Tinito
client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str="eastus.api.azureml.ms;sub_id;rg_tinito_bi;foundry_tinito_copilot"
)

# Definir herramientas estructuradas (Function Calling)
dax_tool = {
    "type": "function",
    "function": {
        "name": "ExecuteDaxQuery",
        "description": "Ejecuta una consulta DAX de solo lectura en el motor VertiPaq de Power BI.",
        "parameters": {
            "type": "object",
            "properties": {
                "daxQuery": {"type": "string", "description": "Sentencia DAX que inicia con EVALUATE."}
            },
            "required": ["daxQuery"]
        }
    }
}

# Registrar Agente con Versionado
agent = client.agents.create_agent(
    model="gpt-4o",
    name="Tinito-DAX-Copilot",
    instructions=open("prompts/system_prompt_v1.2.md", encoding="utf-8").read(),
    tools=[dax_tool],
    headers={"x-ms-enable-preview": "true"}
)
print(f"✔ Agente registrado en Foundry: {agent.name} (ID: {agent.id})")
```

---

### 5.2 Golden Dataset de Regresión para el Agente de QA
Antes de que cualquier actualización de reglas o prompts entre en producción, el pipeline de Foundry ejecuta automáticamente el **Golden Dataset**:

```json
[
  {
    "id": "TEST-001",
    "categoria": "03. Cartera y Cobertura",
    "pregunta": "Calcula la cartera activable de Mondelez en julio 2026 para CTB",
    "dax_esperado": "EVALUATE SUMMARIZECOLUMNS(vw_ventas_bi_consumo[nom_pro], TREATAS({\"ctb\"}, vw_ventas_bi_consumo[source_empresa]), TREATAS({\"0301\"}, vw_ventas_bi_consumo[cod_pro]), TREATAS({DATE(2026,7,1)}, dim_tiempo[fec_ini]), \"Cartera\", [Cartera_Activable_90D])",
    "resultado_esperado": {"Cartera": 2115},
    "criterio_tolerancia": "ExactMatch"
  },
  {
    "id": "TEST-002",
    "categoria": "05. Eficiencia y Ticket",
    "pregunta": "Dame el ticket promedio de venta por factura en mayo",
    "dax_esperado": "EVALUATE ROW(\"Ticket\", [Ticket_Promedio_Venta])",
    "criterio_tolerancia": "NonZeroNumeric"
  }
]
```

---

## 6. Hoja de Ruta Actualizada de Implementación de la Nueva Arquitectura

```
COMPLETADO (Seguridad P0 & Proxy):
  ├── 1. Rotación inmediata de API Keys expuestas.
  ├── 2. Despliegue de Azure Function Proxy con Managed Identity.
  ├── 3. Endurecimiento del proxy con validación de request, límites y errores seguros.
  ├── 4. Easy Auth / Entra ID habilitado en producción con autenticación obligatoria.
  └── 5. Despliegue cloud real validado con HTTP 401 sin token.

COMPLETADO (Foundry, Guardrails & Telemetría P1):
  ├── 6. Function Calling nativo y tools fijadas en el servidor.
  ├── 7. Guardrails centralizados en `dax_guardrails.ps1`.
  ├── 8. Telemetría estructurada en proxy con correlation ID y subject hash.
  ├── 9. Outbox local saneado: ya no persiste preguntas, DAX ni respuestas en claro.
  ├── 10. Snapshot persistente TOM y rollback explícito.
  └── 11. MCP validado contra modelo real Power BI en modo de solo lectura.

COMPLETADO (QA Agent & Release P2):
  ├── 12. QA Judge sin `shell=True` y propuestas vía Pull Request.
  ├── 13. CI/CD con Python 3.12, Ruff, pruebas de contrato, hash SHA-256 y OIDC.
  ├── 14. Publicación automática real en Function y Storage tras validaciones.
  └── 15. Empaquetado de distribución para analistas (`install_copilot.ps1`).

COMPLETADO (Observabilidad DCR):
  ├── 16. DCE `dce-dax-copilot` creado en `rg-powerbi-ai-prod` (eastus2).
  ├── 17. Tabla `DaxCopilotEvent_CL` creada con retención de 90 días.
  ├── 18. DCR `dcr-dax-copilot` creado con stream `Custom-DaxCopilotEvent_CL`.
  ├── 19. Managed Identity de la Function con `Monitoring Metrics Publisher` en DCE/DCR.
  └── 20. Proxy actualizado: ingesta DCR con Managed Identity + fallback a App Insights.

PENDIENTE (Bloqueado por acciones administrativas externas):
  ├── 21. Configurar certificado / cadena de confianza para firma de release.
  ├── 22. Completar el consentimiento interactivo del scope `access_as_user`
  │      (ventana de navegador: `az login --scope .../access_as_user`).
  ├── 23. Ejecución real de GitHub Actions para validar OIDC/RBAC en producción.
  └── 24. Ampliar cobertura de QA hacia la suite completa de 50 casos.
```

---

## 7. Hallazgos operativos relevantes

* **Recursos Azure confirmados:** `func-dax-copilot-proxy`, Application Insights homónimo, Storage `stpbicopilotprod` y Azure OpenAI `aoai-pbi-tinito-prod` en `rg-powerbi-ai-prod`.
* **Workspace actual:** `DefaultWorkspace-42bf5029-cccc-4331-a1b6-ce286a4f88ee-EUS2`; la tabla `DaxCopilotEvent_CL` tiene retención de 90 días (el resto del workspace conserva 30).
* **DCR/DCE provisionados:** `dce-dax-copilot` + `dcr-dax-copilot` (stream `Custom-DaxCopilotEvent_CL`) en `rg-powerbi-ai-prod`.
* **Storage privado:** `stpbicopilotprod` no permite acceso anónimo; la distribución del cliente debe hacerse por mecanismo interno controlado o con autenticación adecuada.
* **Easy Auth real:** habilitado y validado en la Function; una petición sin token devuelve HTTP 401.
* **Gobierno de acceso:** el service principal `func-dax-copilot-proxy-auth` tiene `appRoleAssignmentRequired=true` y el usuario `francisco.pino@tinitot.com` asignado; los analistas adicionales deben asignarse explícitamente.
* **Consentimiento pendiente:** el primer `az login --scope .../access_as_user` requiere aceptar el permiso en la ventana interactiva del navegador (acción manual del usuario).

---

## 8. Resumen de Gobernanza y Beneficios

* **🔒 Seguridad Grado Empresarial:** Cero claves en máquinas locales, autenticación corporativa Entra ID y código verificado criptográficamente.
* **⚡ Rendimiento y Confiabilidad:** Consultas DAX protegidas contra bloqueos de memoria y exportación directa a Excel `.xlsx` nativo.
* **📈 Mejora Continua Auto-Supervisada:** El agente evoluciona con el uso diario, pero cada cambio es validado por el Golden Dataset y aprobado por el Arquitecto de Datos.
