# 🧠 Power BI DAX & Semantic Copilot (Azure OpenAI GPT-5 Mini)
> **Comercial Tinito** — Agente Autónomo con Motor DAX Determinista en Vivo

---

## 📌 ¿Cómo Funciona el Agente Determinista?

El agente combina **Inteligencia Artificial (Azure GPT-5 Mini)** con el **Motor Tabular Local de Power BI Desktop (MSOLAP / VertiPaq)**:

1. **Preguntas de Negocio y Cifras Reales:** Si preguntas por ventas de hoy, venta cero de marcas, top clientes o variaciones YoY, el agente **ejecuta una consulta DAX matemática en segundo plano en menos de 50 ms**, obtiene las filas reales y redacta el diagnóstico comercial.
2. **Creación de Medidas:** Si pides crear una medida, redacta la fórmula y te ofrece inyectarla automáticamente en `_Medidas` con 1 solo clic.

---

## 📄 Código Completo del Script (`pbi_copilot_assistant.ps1`)

```powershell
# ==============================================================================
# 🧠 POWER BI DAX & SEMANTIC COPILOT (AZURE OPENAI GPT-5 MINI)
# Comercial Tinito - Agente Autónomo de Business Intelligence & DAX Determinista
# ==============================================================================

param (
    [Parameter(Mandatory=$false)]
    [string]$Server,

    [Parameter(Mandatory=$false)]
    [string]$Database
)

# 1. Configuración de codificación UTF-8 y TLS 1.2
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# 2. Cargar conectores oficiales de Microsoft TOM
$libsDir = "$env:LOCALAPPDATA\Tinito\PbiCopilot\libs"
$net472Dir = Join-Path $libsDir "extracted\lib\net472"
$tabDll = Join-Path $net472Dir "Microsoft.AnalysisServices.Tabular.dll"
$coreDll = Join-Path $net472Dir "Microsoft.AnalysisServices.Core.dll"

if (-not (Test-Path $tabDll)) {
    $localTab = (Get-ChildItem "C:\Program Files\Microsoft SQL Server", "C:\Program Files\Microsoft Power BI Desktop" -Filter "Microsoft.AnalysisServices.Tabular.dll" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
    if ($localTab) {
        $tabDll = $localTab
        $coreDll = (Get-ChildItem (Split-Path $localTab) -Filter "Microsoft.AnalysisServices.Core.dll" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
    }
}

if (-not (Test-Path $tabDll)) {
    Write-Host "Instalando conectores TOM oficiales..." -ForegroundColor Yellow
    if (-not (Test-Path $libsDir)) { New-Item -ItemType Directory -Path $libsDir -Force | Out-Null }
    $zipPath = Join-Path $libsDir "amo.zip"
    try {
        (New-Object System.Net.WebClient).DownloadFile("https://www.nuget.org/api/v2/package/Microsoft.AnalysisServices/19.114.12", $zipPath)
        Expand-Archive -Path $zipPath -DestinationPath (Join-Path $libsDir "extracted") -Force
        Remove-Item $zipPath -Force
        $tabDll = Join-Path $net472Dir "Microsoft.AnalysisServices.Tabular.dll"
        $coreDll = Join-Path $net472Dir "Microsoft.AnalysisServices.Core.dll"
    } catch { }
}

if ($coreDll -and (Test-Path $coreDll)) { [System.Reflection.Assembly]::LoadFrom($coreDll) | Out-Null }
if ($tabDll -and (Test-Path $tabDll))   { [System.Reflection.Assembly]::LoadFrom($tabDll)  | Out-Null }

# 3. Detección automática del puerto de Power BI Desktop
if (-not $Server -or $Server -eq "%server%") {
    $pbiProcesses = Get-Process msmdsrv | Where-Object { $_.Path -like "*Power BI Desktop*" }
    if (-not $pbiProcesses) { $pbiProcesses = Get-Process msmdsrv -ErrorAction SilentlyContinue }
    
    foreach ($proc in $pbiProcesses) {
        $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)"
        if ($cim -and $cim.CommandLine -match '-s\s+"?([^"]+)"?') {
            $portFile = Join-Path $matches[1].Trim() "msmdsrv.port.txt"
            if (Test-Path $portFile) {
                $PbiPort = [System.IO.File]::ReadAllText($portFile, [System.Text.Encoding]::Unicode).Trim()
                $Server = "localhost:$PbiPort"
                break
            }
        }
    }
    
    if (-not $Server) {
        $conns = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $pbiProcesses.Id }
        if ($conns) { $Server = "localhost:$($conns[0].LocalPort)" } else { $Server = "localhost:56739" }
    }
}

# Función para ejecutar DAX de forma determinista contra el motor local
function Invoke-DaxQueryInternal([string]$query, [string]$serverEndpoint) {
    try {
        $connStr = "Provider=MSOLAP;Data Source=$serverEndpoint;"
        $conn = New-Object System.Data.OleDb.OleDbConnection($connStr)
        $conn.Open()
        $cmd = New-Object System.Data.OleDb.OleDbCommand($query, $conn)
        $reader = $cmd.ExecuteReader()
        
        $rows = @()
        while ($reader.Read()) {
            $row = [ordered]@{}
            for ($i = 0; $i -lt $reader.FieldCount; $i++) {
                $colName = $reader.GetName($i)
                $row[$colName] = $reader.GetValue($i)
            }
            $rows += [PSCustomObject]$row
        }
        $reader.Close()
        $conn.Close()
        return $rows
    } catch {
        return "ERROR_DAX: $_"
    }
}

Clear-Host
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "       🧠 POWER BI DAX & VISUALS COPILOT (AZURE GPT-5 MINI)             " -ForegroundColor Yellow
Write-Host "         Comercial Tinito - Agente con Motor DAX Determinista           " -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "Conectado a Power BI Desktop en $Server con motor analitico en vivo." -ForegroundColor Green

$ENDPOINT   = "https://aoai-pbi-tinito-prod-a7135.openai.azure.com/"
$API_KEY    = $env:AZURE_OPENAI_API_KEY
$DEPLOYMENT = "gpt-5-mini"
$Url        = "$($ENDPOINT)openai/deployments/$DEPLOYMENT/chat/completions?api-version=2024-10-21"

$BaseSystemPrompt = @"
Eres "Power BI DAX & Semantic Copilot", el arquitecto experto en DAX y Business Intelligence de Comercial Tinito.

Tienes una HERRAMIENTA DETERMINISTA DE EJECUCIÓN DAX en vivo conectada al archivo .pbix abierto del usuario.

REGLAS DE OPERACIÓN (CUÁNDO EJECUTAR DAX VS CUÁNDO RESPONDER):
1. Si el usuario hace una PREGUNTA DE NEGOCIO O PIDE CIFRAS REALES (ej. "Dime las ventas de hoy", "Clientes con venta cero de PepsiCo", "¿Cuánto vendió Tinito en agosto?", "Top 5 vendedores"), NUNCA inventes números.
   Debes emitir ÚNICAMENTE el comando de ejecución DAX en tu primera respuesta con este formato exacto:
   [EXECUTE_DAX:EVALUATE <TU_CONSULTA_DAX>]
   El sistema ejecutará la consulta en el motor de Power BI y te devolverá las filas reales para que tú redactes el diagnóstico final.

2. Si el usuario pide EXPLICAR DAX, CREAR UNA MEDIDA o DISEÑAR UN VISUAL, responde con la explicación técnica y la medida en formato:
   [INJECT_MEASURE:Nombre_Medida:FormatString:Formula_DAX_En_Una_Linea]

CONOCIMIENTO CLAVE DEL MODELO DE NEGOCIO:
- Tabla de ventas: 'vw_ventas_bi_consumo'
- Columna numérica de venta USD: 'vw_ventas_bi_consumo'[neto_dcto]
- Columna de kilos: 'vw_ventas_bi_consumo'[peso_total_kg]
- Columna de cajas: 'vw_ventas_bi_consumo'[cajas_vendidas]
- Columna de empresa: 'vw_ventas_bi_consumo'[source_empresa] ('tinito', 'ctb', 'ctm', 'daroan', 'roldan')
- Columna de fecha: 'dim_tiempo'[fecha] o 'vw_ventas_bi_consumo'[fec_ini]
- Medidas Oficiales en '_Medidas': [Total_Ventas_Netas], [Total_Kilos], [Total_Cajas], [Total_Unidades], [Clientes_Activados], [Cartera_Activable_90D], [Venta_Cero_Clientes].

REGLAS DE SINTAXIS DAX ESTRICTAS:
- En SUMMARIZECOLUMNS, los filtros usan SIEMPRE TREATAS:
  * TREATAS({DATE(2026, 8, 18)}, dim_tiempo[fecha])
  * TREATAS({"tinito"}, vw_ventas_bi_consumo[source_empresa])
- Las columnas numéricas (neto_dcto, peso_total_kg) NUNCA van en el bloque de agrupación. Van como métricas con CALCULATE(SUM(...)) o medidas.
"@

$History = @(
    @{ role = "system"; content = $BaseSystemPrompt }
)

Write-Host "`nEscribe tu requerimiento (escribe 'limpiar' para reiniciar o 'salir' para terminar):`n" -ForegroundColor White

while ($true) {
    Write-Host "Pregunta > " -NoNewline -ForegroundColor Green
    $Pregunta = Read-Host
    if (-not $Pregunta) { continue }
    
    $pTrim = $Pregunta.Trim().ToLower()
    if ($pTrim -eq "salir" -or $pTrim -eq "exit") { break }
    if ($pTrim -in @("reset", "limpiar", "clear")) {
        $History = @(@{ role = "system"; content = $BaseSystemPrompt })
        Write-Host "✔ Conversacion reiniciada.`n" -ForegroundColor Yellow
        continue
    }

    $History += @{ role = "user"; content = $Pregunta }

    # Bucle ReAct con Azure OpenAI y Motor DAX Determinista
    $maxIter = 3
    $iter = 0
    
    while ($iter -lt $maxIter) {
        $iter++
        $Payload = @{ messages = $History }
        $JsonBody = $Payload | ConvertTo-Json -Depth 10 -Compress

        Write-Host "`nConsultando a GPT-5 Mini en Azure..." -ForegroundColor Cyan
        try {
            $Headers = @{ "api-key" = $API_KEY }
            $Response = Invoke-RestMethod -Uri $Url -Method Post -Headers $Headers -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($JsonBody))
            
            $Contenido = $Response.choices[0].message.content
            $History += @{ role = "assistant"; content = $Contenido }

            # Caso A: El modelo solicita ejecutar una consulta DAX determinista
            if ($Contenido -match '\[EXECUTE_DAX:(.*?)\]') {
                $daxQuery = $matches[1].Trim()
                Write-Host "⚡ Ejecutando calculo determinista en el motor de Power BI..." -ForegroundColor Magenta
                $daxResult = Invoke-DaxQueryInternal -query $daxQuery -serverEndpoint $Server
                
                $resultSummary = ""
                if ($daxResult -is [string] -and $daxResult.StartsWith("ERROR_DAX")) {
                    $resultSummary = "Error al ejecutar DAX: $daxResult"
                    Write-Host "⚠ $resultSummary" -ForegroundColor Yellow
                } else {
                    $cnt = if ($daxResult) { $daxResult.Count } else { 0 }
                    Write-Host "✔ Calculo completado con exito ($cnt filas obtenidas)." -ForegroundColor Green
                    $resultSummary = ($daxResult | ConvertTo-Json -Depth 5 -Compress)
                }
                
                $History += @{ role = "user"; content = "[DAX_EXECUTION_RESULT]: $resultSummary. Analiza estos datos reales y responde a la pregunta original del usuario con precision ejecutiva." }
                continue
            }

            # Caso B: Respuesta final o explicación
            Write-Host "`n========================================================" -ForegroundColor Green
            Write-Host "🤖 RESPUESTA DEL ASISTENTE:" -ForegroundColor Yellow
            Write-Host $Contenido
            Write-Host "========================================================" -ForegroundColor Green

            # Inyección de medida si aplica
            if ($Contenido -match '\[INJECT_MEASURE:([^:]+):([^:]+):(.*?)\]') {
                $mName = $matches[1].Trim()
                $mFmt  = $matches[2].Trim()
                $mExp  = $matches[3].Trim()

                Write-Host "`n¿Deseas inyectar automaticamente la medida [$mName] en tu Power BI Desktop? (S/N): " -NoNewline -ForegroundColor Yellow
                $resp = Read-Host
                if ($resp -and ($resp.Trim().ToUpper() -eq "S" -or $resp.Trim().ToUpper() -eq "SI")) {
                    try {
                        $srv = New-Object Microsoft.AnalysisServices.Tabular.Server
                        $srv.Connect($Server)
                        $db = $null
                        if ($Database -and $Database -ne "%database%") {
                            $db = $srv.Databases[$Database]
                        } else {
                            $db = $srv.Databases[0]
                        }
                        $tblMed = $db.Model.Tables["_Medidas"]
                        if (-not $tblMed) { $tblMed = $db.Model.Tables[0] }
                        
                        if ($tblMed) {
                            if (-not $tblMed.Measures.Contains($mName)) {
                                $m = New-Object Microsoft.AnalysisServices.Tabular.Measure
                                $m.Name = $mName
                                $tblMed.Measures.Add($m)
                            } else {
                                $m = $tblMed.Measures[$mName]
                            }
                            $m.Expression = $mExp
                            if ($mFmt) { $m.FormatString = $mFmt }
                            $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Calculate)
                            $db.Model.SaveChanges()
                            Write-Host "✔ Medida [$mName] inyectada y guardada con exito en tu archivo .pbix abierto." -ForegroundColor Green
                        }
                        $srv.Disconnect()
                    } catch {
                        Write-Host "Error al inyectar medida: $_" -ForegroundColor Red
                    }
                }
            }
            break
        } catch {
            Write-Host "Error al consultar Azure OpenAI: $_" -ForegroundColor Red
            break
        }
    }
    Write-Host "`n"
}
```
