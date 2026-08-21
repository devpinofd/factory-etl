# 🤖 Comercial Tinito — DAX Copilot Agent Module

Módulo integral del **Agente DAX Copilot** para Power BI, modelado semántico VertiPaq y analítica de datos en Comercial Tinito.

---

## 📁 Estructura del Módulo

```
agents/dax_copilot/
├── client/                     # 💻 Aplicación cliente y scripts de terminal
│   ├── pbi_copilot_assistant.ps1   # Asistente interactivo v1.2.0 (Function Calling + Excel .xlsx)
│   ├── dax_guardrails.ps1          # Guardrails de seguridad DAX (TOPN 5000 + Timeout 60s)
│   ├── telemetry_outbox.ps1        # Telemetría Outbox con pseudonimización PII SHA-256
│   ├── launch_copilot.ps1          # Lanzador Zero-Touch con verificación SHA-256
│   ├── launch_copilot.bat          # Acceso directo de 1 clic para analistas
│   └── manifest.json               # Manifiesto de release criptográfico
│
├── proxy/                      # ☁️ Proxy Gateway Backend (Azure Function)
│   ├── function_app.py             # Endpoint /api/chat-stream con Managed Identity
│   ├── host.json                   # Configuración del runtime de Azure Functions
│   ├── requirements.txt            # Dependencias Python (openai, azure-identity)
│   └── proxy_package.zip           # Paquete de despliegue
│
├── prompts/                    # 📚 Reglas del Sistema y Metadatos Semánticos
│   └── system_prompt_v1.0.md       # Reglas de negocio, documentación obligatoria y modelo
│
├── qa_judge/                   # 🧑‍⚖️ Agente Evaluador y Calidad (LLM-as-a-Judge)
│   └── qa_judge_agent.py           # Auditoría nocturna y creación de Pull Requests en GitHub
│
├── foundry/                    # 🏛️ Definición para Azure AI Foundry (Agent Service)
│   └── agent_definition_v1.2.json  # Esquema de herramientas, modelos y guardrails
│
└── docs/                       # 📑 Documentación y Arquitectura
    ├── plan_mejora_agente_dax_copilot_telemetria_qa.md
    └── arquitectura_dax_copilot_vs_best_in_class.md
```

---

## 🚀 Inicio Rápido

### 1. Para Analistas de Negocio:
Ejecutar el archivo:
```cmd
agents/dax_copilot/client/launch_copilot.bat
```
* Valida automáticamente la integridad criptográfica contra Azure Blob Storage.
* Si hay conexión, descarga la última versión aprobada en memoria.
* Si está offline, inicia con la copia local en caché.

### 2. Para Desplegar el Proxy Backend en Azure:
```bash
az functionapp deployment source config-zip \
  --name func-dax-copilot-proxy \
  --resource-group rg-powerbi-ai-prod \
  --src agents/dax_copilot/proxy/proxy_package.zip \
  --build-remote true
```

El endpoint requiere autenticación de Azure Functions (`FUNCTION`). El cliente
debe recibir la clave mediante la variable de entorno
`DAX_COPILOT_FUNCTION_KEY`; nunca debe escribirse en el script ni en el
repositorio. Las herramientas disponibles se fijan en el proxy y no pueden
sobrescribirse desde el request.

En Azure, Easy Auth debe inyectar `x-ms-client-principal`. Para exigir Entra ID,
configura `REQUIRE_ENTRA_AUTH=true`, `AZURE_TENANT_ID` con el tenant corporativo
y, opcionalmente, `AZURE_REQUIRED_SCOPE`. En desarrollo local la validación se
mantiene desactivada por defecto.

Para validaciones locales, el MCP se configura por defecto en modo solo lectura
con confirmación de escrituras. El modo `ReadWrite` debe reservarse para una
sesión administrativa explícita.

El proxy emite eventos estructurados `dax_copilot_event` mediante el logger de
Azure Functions (Application Insights) y, cuando están configuradas las
variables `DAX_COPILOT_DCE_INGESTION_ENDPOINT`, `DAX_COPILOT_DCR_IMMUTABLE_ID`
y `DAX_COPILOT_DCR_STREAM`, también ingiere en Log Analytics vía el DCE
`dce-dax-copilot` y el DCR `dcr-dax-copilot` hacia la tabla
`DaxCopilotEvent_CL` (retención 90 días), usando la Managed Identity de la
Function con el rol `Monitoring Metrics Publisher`. Los eventos no incluyen
prompts, consultas DAX ni identificadores de usuario en claro. El cliente
conserva únicamente hashes y métricas en el outbox local. También conserva
snapshots TOM en `measure-snapshots`; se puede restaurar uno con
`rollback <ruta-al-snapshot>` antes de reintentar una publicación.

El workflow de release usa `azure/login@v2` con OpenID Connect. La app
registration es `github-actions-factory-etl-deploy` con federated credentials
para `main` y `pull_request` del repo `devpinofd/factory-etl`. Configura en
GitHub Actions los secrets:

- `AZURE_CLIENT_ID` = `8ed83e88-37ce-4b08-a131-ca051c309b6c`
- `AZURE_TENANT_ID` = `e9545efd-83a8-4b56-a297-1c05c7d1f51b`
- `AZURE_SUBSCRIPTION_ID` = `42bf5029-cccc-4331-a1b6-ce286a4f88ee`

La identidad federada ya tiene `Contributor` sobre `rg-powerbi-ai-prod` y
`Storage Blob Data Contributor` sobre `stpbicopilotprod`.

Comandos para registrar los tres valores no secretos en el repositorio:

```powershell
gh secret set AZURE_CLIENT_ID --repo devpinofd/factory-etl --body "8ed83e88-37ce-4b08-a131-ca051c309b6c"
gh secret set AZURE_TENANT_ID --repo devpinofd/factory-etl --body "e9545efd-83a8-4b56-a297-1c05c7d1f51b"
gh secret set AZURE_SUBSCRIPTION_ID --repo devpinofd/factory-etl --body "42bf5029-cccc-4331-a1b6-ce286a4f88ee"
```

El cliente requiere estas variables de entorno, sin valores por defecto
productivos: `DAX_COPILOT_PROXY_URL`, `DAX_COPILOT_SCRIPT_URL`,
`DAX_COPILOT_MANIFEST_URL`, `DAX_COPILOT_LAN_SCRIPT_PATH` y
`DAX_COPILOT_ADMIN_CONTACT`. El proxy y el QA Judge requieren
`AZURE_OPENAI_ENDPOINT` y usan exclusivamente Managed Identity.
El cliente solicita el scope delegado `access_as_user` mediante Azure CLI; el
primer uso requiere `az login --tenant <tenant> --scope
<audiencia>/access_as_user` y el consentimiento corporativo correspondiente.
La telemetría aplica muestreo configurable con `DAX_COPILOT_SUCCESS_SAMPLE_PERCENT`;
por defecto conserva el 10% de los éxitos y el 100% de los errores.
En producción conviene exigir asignación explícita del principal Entra del proxy
(`appRoleAssignmentRequired=true`) para limitar el uso a analistas autorizados.
El launcher intenta inferir `manifest.json` en la misma carpeta cuando solo se
proporciona una ruta LAN al script. El pipeline también valida que el system
prompt versionado conserve sus secciones obligatorias antes de liberar.

### 3. Para Ejecutar la Auditoría del Agente Juez:
```bash
python agents/dax_copilot/qa_judge/qa_judge_agent.py
```

### 4. Distribución a analistas

El paquete de instalación debe distribuirse mediante Intune, GPO, SCCM o un
recurso compartido interno. Ejemplo para una estación Windows:

```powershell
az login --tenant e9545efd-83a8-4b56-a297-1c05c7d1f51b `
  --scope api://e9545efd-83a8-4b56-a297-1c05c7d1f51b/func-dax-copilot-proxy-auth/access_as_user

$packageDir = (Get-Location).Path
.\install_copilot.ps1 `
  -ProxyUrl "https://func-dax-copilot-proxy.azurewebsites.net/api/chat-stream" `
  -Audience "api://e9545efd-83a8-4b56-a297-1c05c7d1f51b/func-dax-copilot-proxy-auth" `
  -LanScriptPath (Join-Path $packageDir "pbi_copilot_assistant.ps1") `
  -LanManifestPath (Join-Path $packageDir "manifest.json")
```

La cuenta de Storage de distribución es privada; no se deben abrir los blobs
al público ni incrustar SAS permanentes en el instalador. El pipeline publica
los artefactos y el mecanismo corporativo de distribución debe entregar
`install_copilot.ps1`, `launch_copilot.ps1` y `launch_copilot.bat` desde una
fuente interna aprobada, junto con `pbi_copilot_assistant.ps1` y
`manifest.json`. Si el launcher se ejecuta directamente desde ese paquete,
autodetecta ambos artefactos y verifica el hash antes de iniciar.

### Firma Authenticode (opcional, recomendada)

El workflow se ejecuta en `windows-latest` para poder usar
`Set-AuthenticodeSignature` y firma el script del cliente automáticamente si
están configurados los secrets `CODE_SIGNING_CERT_PFX` (base64 del PFX) y
`CODE_SIGNING_CERT_PASSWORD`. Los artefactos firmados se transfieren al job de
despliegue mediante `actions/upload-artifact`; nunca se debe guardar el PFX en
el repositorio.
Tras firmar, recalcula el hash del manifest y marca `signed: true`. El launcher
exige firma válida cuando el manifest indica `signed: true` y rechaza scripts
sin firma o con certificado no coincidente. Si los secrets no existen, el
pipeline omite la firma con una advertencia y el launcher valida solo el hash.
