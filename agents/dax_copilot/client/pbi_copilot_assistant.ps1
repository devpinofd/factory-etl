# ==============================================================================
# POWER BI DAX & SEMANTIC COPILOT 
# Comercial Tinito - Agente # Version: 1.2.0-PROD
# ==============================================================================

param (
    [Parameter(Mandatory=$false)]
    [string]$Server,

    [Parameter(Mandatory=$false)]
    [string]$Database,

    [Parameter(Mandatory=$false)]
    [string]$ProxyUrl = $env:DAX_COPILOT_PROXY_URL,

    [Parameter(Mandatory=$false)]
    [string]$ProxyAudience = $env:DAX_COPILOT_AUDIENCE,

    [Parameter(Mandatory=$false)]
    [string]$ProxyScope = $(if ($env:DAX_COPILOT_SCOPE) { $env:DAX_COPILOT_SCOPE } else { "access_as_user" }),

    [Parameter(Mandatory=$false)]
    [string]$TenantId = $(if ($env:DAX_COPILOT_TENANT_ID) { $env:DAX_COPILOT_TENANT_ID } else { "e9545efd-83a8-4b56-a297-1c05c7d1f51b" }),

    [Parameter(Mandatory=$false)]
    [string]$ClientId = $(if ($env:DAX_COPILOT_CLIENT_ID) { $env:DAX_COPILOT_CLIENT_ID } else { "04b07795-8ddb-461a-bbee-02f9e1bf7b46" })
)

# 1. Configuracion de Consola UTF-8 y TLS 1.2
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if (-not $ProxyUrl) {
    throw "Configura DAX_COPILOT_PROXY_URL antes de iniciar el agente."
}
if (-not $ProxyAudience) {
    throw "Configura DAX_COPILOT_AUDIENCE antes de iniciar el agente."
}

# 1b. Autenticacion Proactiva Entra ID con SSO de Windows (WAM)
# Se ejecuta al abrir el agente, ANTES de aceptar cualquier pregunta. Con el
# broker de cuentas de Windows activo, el login reutiliza la misma sesion de
# Microsoft 365/Entra ID que ya esta conectada en el equipo (la misma que usa
# Power BI), en vez de pedir credenciales de nuevo en el navegador.
function Get-DaxProxyToken {
    param(
        [string]$Audience,
        [string]$Scope
    )
    $raw = & az account get-access-token --scope "$Audience/$Scope" --output json 2>&1
    if ($LASTEXITCODE -ne 0 -or -not $raw) {
        return [PSCustomObject]@{ Success = $false; Token = $null; ErrorText = ($raw | Out-String).Trim() }
    }
    try {
        $parsed = $raw | ConvertFrom-Json
    } catch {
        return [PSCustomObject]@{ Success = $false; Token = $null; ErrorText = "Azure CLI devolvio una respuesta invalida: $raw" }
    }
    if (-not $parsed.accessToken) {
        return [PSCustomObject]@{ Success = $false; Token = $null; ErrorText = "Azure CLI no devolvio un token de acceso." }
    }
    return [PSCustomObject]@{ Success = $true; Token = $parsed.accessToken; ErrorText = $null }
}

function Ensure-DaxProxyLogin {
    param(
        [string]$Audience,
        [string]$Scope
    )

    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw "Azure CLI ('az') no esta instalada. Instalala desde https://aka.ms/installazurecliwindows y reinicia el agente."
    }

    # Evita fallos silenciosos por extensiones de Azure CLI sin permisos de escritura
    # en el perfil del usuario actual (causa comun de "No se pudo obtener un token").
    if (-not $env:AZURE_EXTENSION_DIR) {
        $extDir = Join-Path $env:LOCALAPPDATA "AzureCli\extensions"
        if (-not (Test-Path $extDir)) { New-Item -ItemType Directory -Path $extDir -Force | Out-Null }
        $env:AZURE_EXTENSION_DIR = $extDir
    }

    # Activa el broker de cuentas de Windows (WAM): el inicio de sesion usa el
    # selector nativo con las cuentas de Microsoft 365/Entra ID ya conectadas al
    # equipo (misma identidad de Power BI), en vez de pedir credenciales otra vez.
    & az config set core.enable_broker_on_windows=true --only-show-errors 2>$null | Out-Null

    Write-Host "Verificando sesion corporativa de Azure..." -ForegroundColor Cyan
    $result = Get-DaxProxyToken -Audience $Audience -Scope $Scope
    if ($result.Success) {
        $account = & az account show --output json 2>$null | ConvertFrom-Json
        $userName = if ($account) { $account.user.name } else { "cuenta corporativa" }
        Write-Host "[OK] Sesion Azure activa: $userName`n" -ForegroundColor Green
        return
    }

    Write-Host "[INFO] Elige tu cuenta corporativa en la ventana de inicio de sesion (usa la misma sesion de Microsoft 365 del equipo)..." -ForegroundColor Yellow

    $tenantId = $null
    if ($Audience -match '^api://([0-9a-fA-F-]{36})/') {
        $tenantId = $Matches[1]
    }

    $loginArgs = @("login", "--scope", "$Audience/$Scope", "--allow-no-subscriptions")
    if ($tenantId) { $loginArgs += @("--tenant", $tenantId) }

    & az @loginArgs --output none
    if ($LASTEXITCODE -ne 0) {
        throw "El inicio de sesion en Azure fue cancelado o fallo. Vuelve a abrir el agente para reintentar."
    }

    $result = Get-DaxProxyToken -Audience $Audience -Scope $Scope
    if (-not $result.Success) {
        $adminContact = if ($env:DAX_COPILOT_ADMIN_CONTACT) { $env:DAX_COPILOT_ADMIN_CONTACT } else { "el administrador de BI" }
        $detail = if ($result.ErrorText) { " Detalle: $($result.ErrorText)" } else { "" }
        throw "El inicio de sesion se completo pero no se pudo obtener el token del proxy DAX Copilot.$detail Contacta a $adminContact."
    }

    $account = & az account show --output json 2>$null | ConvertFrom-Json
    $userName = if ($account) { $account.user.name } else { "cuenta corporativa" }
    Write-Host "[OK] Sesion Azure iniciada correctamente: $userName`n" -ForegroundColor Green
}

Ensure-DaxProxyLogin -Audience $ProxyAudience -Scope $ProxyScope

# 2. Configuracion de Directorios y Modulos
$baseDir  = "$env:LOCALAPPDATA\Tinito\PbiCopilot"
$logsDir  = Join-Path $baseDir "logs"
$libsDir  = Join-Path $baseDir "libs"
$cacheDir = Join-Path $baseDir "cache"

foreach ($d in @($logsDir, $libsDir, $cacheDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

# 3. Cargar conectores oficiales ADOMD.NET y Microsoft TOM
$adomdDir = Join-Path $libsDir "adomd"
$adomdDll = Join-Path $adomdDir "lib\net472\Microsoft.AnalysisServices.AdomdClient.dll"

if (-not (Test-Path $adomdDll)) {
    $localAdomd = (Get-ChildItem "C:\Program Files\Microsoft Power BI Desktop", "C:\Program Files (x86)\Microsoft Power BI Desktop", "C:\Program Files\Microsoft SQL Server" -Filter "*AdomdClient.dll" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
    if ($localAdomd) {
        $adomdDll = $localAdomd
    } else {
        try {
            $adomdZip = Join-Path $libsDir "adomd.zip"
            (New-Object System.Net.WebClient).DownloadFile("https://www.nuget.org/api/v2/package/Microsoft.AnalysisServices.AdomdClient/19.114.12", $adomdZip)
            Expand-Archive -Path $adomdZip -DestinationPath $adomdDir -Force
            Remove-Item $adomdZip -Force
        } catch { }
    }
}

if (Test-Path $adomdDll) {
    Unblock-File -Path $adomdDll -ErrorAction SilentlyContinue
    [System.Reflection.Assembly]::LoadFrom($adomdDll) | Out-Null
}

$tomDir  = Join-Path $libsDir "extracted"
$tomDll  = Join-Path $tomDir "lib\net472\Microsoft.AnalysisServices.Tabular.dll"
$coreDll = Join-Path $tomDir "lib\net472\Microsoft.AnalysisServices.Core.dll"

if (-not (Test-Path $tomDll)) {
    $localTab = (Get-ChildItem "C:\Program Files\Microsoft SQL Server", "C:\Program Files\Microsoft Power BI Desktop" -Filter "Microsoft.AnalysisServices.Tabular.dll" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
    if ($localTab) {
        $tomDll = $localTab
        $coreDll = (Get-ChildItem (Split-Path $localTab) -Filter "Microsoft.AnalysisServices.Core.dll" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
    }
}

if ($coreDll -and (Test-Path $coreDll)) {
    Unblock-File -Path $coreDll -ErrorAction SilentlyContinue
    [System.Reflection.Assembly]::LoadFrom($coreDll) | Out-Null
}
if ($tomDll -and (Test-Path $tomDll)) {
    Unblock-File -Path $tomDll -ErrorAction SilentlyContinue
    [System.Reflection.Assembly]::LoadFrom($tomDll) | Out-Null
}

# 4. Modulo unico de Guardrails de Seguridad DAX
$guardrailPath = Join-Path $PSScriptRoot "dax_guardrails.ps1"
if (-not (Test-Path $guardrailPath)) {
    $candidate = Join-Path "$env:LOCALAPPDATA\Tinito\PbiCopilot\launcher" "dax_guardrails.ps1"
    if (Test-Path $candidate) { $guardrailPath = $candidate }
}
if (-not (Test-Path $guardrailPath)) {
    $candidate = Join-Path "$env:LOCALAPPDATA\Tinito\PbiCopilot\cache" "dax_guardrails.ps1"
    if (Test-Path $candidate) { $guardrailPath = $candidate }
}
if (-not (Test-Path $guardrailPath)) {
    throw "No se encontro el modulo de guardrails DAX: $guardrailPath"
}
. $guardrailPath

# 4.1. Modulo de Autenticacion Microsoft Entra ID / M365 (MSAL.NET)
$msalAuthPath = Join-Path $PSScriptRoot "msal_auth.ps1"
if (-not (Test-Path $msalAuthPath)) {
    $candidate = Join-Path "$env:LOCALAPPDATA\Tinito\PbiCopilot\launcher" "msal_auth.ps1"
    if (Test-Path $candidate) { $msalAuthPath = $candidate }
}
if (Test-Path $msalAuthPath) {
    . $msalAuthPath
}

# 5. Modulo de Telemetria Outbox canonico
$telemetryOutboxPath = Join-Path $PSScriptRoot "telemetry_outbox.ps1"
if (-not (Test-Path $telemetryOutboxPath)) {
    $candidate = Join-Path "$env:LOCALAPPDATA\Tinito\PbiCopilot\launcher" "telemetry_outbox.ps1"
    if (Test-Path $candidate) { $telemetryOutboxPath = $candidate }
}
if (Test-Path $telemetryOutboxPath) {
    . $telemetryOutboxPath
}

function Save-OutboxTelemetryWrapper {
    param (
        [string]$Question,
        [string]$DaxQuery = "",
        [int]$RowCount = 0,
        [long]$DurationMs = 0,
        [string]$Status = "SUCCESS",
        [string]$ErrorMessage = "",
        [string]$AssistantSummary = ""
    )
    $evt = New-TelemetryEvent -User $env:USERNAME `
                              -Question $Question `
                              -DaxQuery $DaxQuery `
                              -RowCount $RowCount `
                              -DurationMs $DurationMs `
                              -Status $Status `
                              -ErrorMessage $ErrorMessage `
                              -AssistantSummary $AssistantSummary
    Save-OutboxTelemetry -EventData $evt -LogDirectory $logsDir | Out-Null
}

# 6. Motor Nativo de Exportacion a Excel OpenXML (.XLSX)
function Clean-DaxColumnHeader([string]$rawHeader) {
    if (-not $rawHeader) { return "Columna" }
    $clean = $rawHeader.Trim()
    if ($clean -match '\[([^\]]+)\]$') {
        $clean = $Matches[1]
    } elseif ($clean.StartsWith("[") -and $clean.EndsWith("]")) {
        $clean = $clean.Substring(1, $clean.Length - 2)
    }
    return $clean
}

function Export-NativeExcelXlsx {
    param (
        [Parameter(Mandatory=$true)]
        [object[]]$Data,
        [Parameter(Mandatory=$true)]
        [string]$FilePath,
        [string]$SheetName = "Datos DAX"
    )

    Add-Type -AssemblyName System.IO.Compression -ErrorAction SilentlyContinue
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue

    if (Test-Path $FilePath) { Remove-Item $FilePath -Force }

    $tempDir = Join-Path $env:TEMP ("xlsx_" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    $xlDir = Join-Path $tempDir "xl"
    $worksheetsDir = Join-Path $xlDir "worksheets"
    $relsDir = Join-Path $tempDir "_rels"
    $xlRelsDir = Join-Path $xlDir "_rels"

    New-Item -ItemType Directory -Path $worksheetsDir -Force | Out-Null
    New-Item -ItemType Directory -Path $relsDir -Force | Out-Null
    New-Item -ItemType Directory -Path $xlRelsDir -Force | Out-Null

    $props = @()
    if ($Data -and $Data.Count -gt 0) {
        $firstItem = $Data[0]
        if ($firstItem -is [System.Collections.IDictionary]) {
            $props = @($firstItem.Keys)
        } else {
            $props = @($firstItem.PSObject.Properties | Select-Object -ExpandProperty Name)
        }
    }

    if ($props.Count -eq 0) {
        throw "No hay columnas disponibles para exportar en el conjunto de datos."
    }

    $cleanHeaders = @()
    foreach ($p in $props) {
        $cleanHeaders += (Clean-DaxColumnHeader -rawHeader $p)
    }

    $sharedStrings = New-Object System.Collections.ArrayList
    $strDict = @{}

    function Get-ColLetter([int]$colIndex) {
        $colName = ""
        while ($colIndex -gt 0) {
            $rem = ($colIndex - 1) % 26
            $colName = [char](65 + $rem) + $colName
            $colIndex = [math]::Floor(($colIndex - $rem) / 26)
        }
        return $colName
    }

    $colWidths = @{}
    for ($c = 0; $c -lt $props.Count; $c++) {
        $colWidths[$c] = [math]::Max(12, $cleanHeaders[$c].Length + 4)
    }

    # Pre-calcular anchos de columnas
    foreach ($row in $Data) {
        for ($c = 0; $c -lt $props.Count; $c++) {
            $pName = $props[$c]
            $val = if ($row -is [System.Collections.IDictionary]) { $row[$pName] } else { $row.$pName }
            if ($val) {
                $len = "$val".Length + 3
                if ($len -gt $colWidths[$c]) {
                    $colWidths[$c] = [math]::Min(50, $len)
                }
            }
        }
    }

    $numRows = $Data.Count + 1
    $numCols = $props.Count
    $lastCol = Get-ColLetter $numCols

    $sheetXml = New-Object System.Text.StringBuilder
    [void]$sheetXml.AppendLine('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    [void]$sheetXml.AppendLine('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    [void]$sheetXml.AppendLine("<dimension ref=""A1:${lastCol}${numRows}""/>")
    [void]$sheetXml.AppendLine('<sheetViews><sheetView tabSelected="1" workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    [void]$sheetXml.AppendLine('<sheetFormatPr defaultRowHeight="18"/>')

    # Column Widths
    [void]$sheetXml.AppendLine('<cols>')
    for ($c = 0; $c -lt $props.Count; $c++) {
        $cIdx = $c + 1
        $w = $colWidths[$c]
        [void]$sheetXml.AppendLine("<col min=""$cIdx"" max=""$cIdx"" width=""$w"" customWidth=""1""/>")
    }
    [void]$sheetXml.AppendLine('</cols>')

    [void]$sheetXml.AppendLine('<sheetData>')

    # Header Row (Azul Corporativo Tinito #1F4E78 con texto blanco)
    [void]$sheetXml.AppendLine("<row r=""1"" spans=""1:$numCols"" customHeight=""1"" ht=""26"">")
    for ($c = 0; $c -lt $props.Count; $c++) {
        $colLetter = Get-ColLetter ($c + 1)
        $hText = [System.Security.SecurityElement]::Escape($cleanHeaders[$c])
        if (-not $strDict.ContainsKey($hText)) {
            $idx = $sharedStrings.Add($hText)
            $strDict[$hText] = $idx
        } else {
            $idx = $strDict[$hText]
        }
        [void]$sheetXml.AppendLine("<c r=""${colLetter}1"" s=""1"" t=""s""><v>$idx</v></c>")
    }
    [void]$sheetXml.AppendLine('</row>')

    # Data Rows
    $r = 2
    foreach ($row in $Data) {
        [void]$sheetXml.AppendLine("<row r=""$r"" spans=""1:$numCols"" customHeight=""1"" ht=""20"">")
        for ($c = 0; $c -lt $props.Count; $c++) {
            $colLetter = Get-ColLetter ($c + 1)
            $pName = $props[$c]
            $val = if ($row -is [System.Collections.IDictionary]) { $row[$pName] } else { $row.$pName }
            $cellRef = "${colLetter}${r}"

            if ($null -eq $val -or "$val" -eq "") {
                [void]$sheetXml.AppendLine("<c r=""$cellRef"" s=""0""/>")
                continue
            }

            $strRaw = "$val".Trim()
            $hasLeadingZero = ($strRaw.Length -gt 1 -and $strRaw.StartsWith("0") -and ($strRaw -match '^\d+$'))

            $numVal = 0.0
            $isDouble = $false
            if (-not $hasLeadingZero) {
                $isDouble = [double]::TryParse($strRaw, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$numVal)
                if (-not $isDouble) {
                    $isDouble = [double]::TryParse($strRaw, [System.Globalization.NumberStyles]::Any, (Get-Culture), [ref]$numVal)
                }
            }

            if ($isDouble -and ($strRaw -notmatch '^[0-9]{4}-[0-9]{2}-[0-9]{2}') -and ($strRaw.Length -lt 15 -or $strRaw -match '^-?[0-9]+(\.[0-9]+)?$')) {
                $strVal = $numVal.ToString([System.Globalization.CultureInfo]::InvariantCulture)
                $styleIdx = if ($val -is [int] -or $val -is [long] -or ($numVal % 1 -eq 0)) { "2" } else { "3" }
                [void]$sheetXml.AppendLine("<c r=""$cellRef"" s=""$styleIdx""><v>$strVal</v></c>")
            } elseif ($val -is [datetime] -or ($strRaw -match '^\d{4}-\d{2}-\d{2}')) {
                $d = [datetime]::MinValue
                if ([datetime]::TryParse($strRaw, [ref]$d)) {
                    $oaDate = $d.ToOADate().ToString([System.Globalization.CultureInfo]::InvariantCulture)
                    [void]$sheetXml.AppendLine("<c r=""$cellRef"" s=""4""><v>$oaDate</v></c>")
                } else {
                    $esc = [System.Security.SecurityElement]::Escape($strRaw)
                    if (-not $strDict.ContainsKey($esc)) {
                        $idx = $sharedStrings.Add($esc)
                        $strDict[$esc] = $idx
                    } else {
                        $idx = $strDict[$esc]
                    }
                    [void]$sheetXml.AppendLine("<c r=""$cellRef"" s=""0"" t=""s""><v>$idx</v></c>")
                }
            } else {
                $esc = [System.Security.SecurityElement]::Escape($strRaw)
                if (-not $strDict.ContainsKey($esc)) {
                    $idx = $sharedStrings.Add($esc)
                    $strDict[$esc] = $idx
                } else {
                    $idx = $strDict[$esc]
                }
                [void]$sheetXml.AppendLine("<c r=""$cellRef"" s=""0"" t=""s""><v>$idx</v></c>")
            }
        }
        [void]$sheetXml.AppendLine('</row>')
        $r++
    }
    [void]$sheetXml.AppendLine('</sheetData>')
    [void]$sheetXml.AppendLine("<autoFilter ref=""A1:${lastCol}${numRows}""/>")
    [void]$sheetXml.AppendLine('</worksheet>')

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Join-Path $worksheetsDir "sheet1.xml"), $sheetXml.ToString(), $utf8NoBom)

    # Shared Strings XML
    $ssXml = New-Object System.Text.StringBuilder
    [void]$ssXml.AppendLine('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    [void]$ssXml.AppendLine("<sst xmlns=""http://schemas.openxmlformats.org/spreadsheetml/2006/main"" count=""$($sharedStrings.Count)"" uniqueCount=""$($sharedStrings.Count)"">")
    foreach ($s in $sharedStrings) { [void]$ssXml.AppendLine("<si><t>$s</t></si>") }
    [void]$ssXml.AppendLine('</sst>')
    [System.IO.File]::WriteAllText((Join-Path $xlDir "sharedStrings.xml"), $ssXml.ToString(), $utf8NoBom)

    # Styles XML
    $stylesXml = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="3">
    <numFmt numFmtId="164" formatCode="#,##0"/>
    <numFmt numFmtId="165" formatCode="#,##0.00"/>
    <numFmt numFmtId="166" formatCode="yyyy-mm-dd"/>
  </numFmts>
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/></border>
    <border><left style="thin"><color rgb="FFD9D9D9"/></left><right style="thin"><color rgb="FFD9D9D9"/></right><top style="thin"><color rgb="FFD9D9D9"/></top><bottom style="thin"><color rgb="FFD9D9D9"/></bottom></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="5">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="166" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment horizontal="center"/></xf>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>
'@
    [System.IO.File]::WriteAllText((Join-Path $xlDir "styles.xml"), $stylesXml, $utf8NoBom)

    $wbXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="$SheetName" sheetId="1" r:id="rId1"/></sheets>
</workbook>
"@
    [System.IO.File]::WriteAllText((Join-Path $xlDir "workbook.xml"), $wbXml, $utf8NoBom)

    $ctXml = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>
'@
    [System.IO.File]::WriteAllText((Join-Path $tempDir "[Content_Types].xml"), $ctXml, $utf8NoBom)

    $rootRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
'@
    [System.IO.File]::WriteAllText((Join-Path $relsDir ".rels"), $rootRels, $utf8NoBom)

    $xlRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>
'@
    [System.IO.File]::WriteAllText((Join-Path $xlRelsDir "workbook.xml.rels"), $xlRels, $utf8NoBom)

    [System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $FilePath)
    Remove-Item $tempDir -Recurse -Force
}

# 7. Deteccion automatica del puerto y catalogo activo de Power BI Desktop
function Get-PbiDesktopConnectionInfo {
    param ([string]$preferredServer, [string]$preferredDatabase)

    $candidatePorts = @()
    if ($preferredServer -and $preferredServer -ne "%server%") {
        if ($preferredServer -match '^(?:localhost:)?(\d+)$') {
            $candidatePorts += [int]$Matches[1]
        }
    }

    $pbiProcesses = Get-Process msmdsrv -ErrorAction SilentlyContinue
    if ($pbiProcesses) {
        foreach ($p in $pbiProcesses) {
            $conns = Get-NetTCPConnection -OwningProcess $p.Id -State Listen -ErrorAction SilentlyContinue |
                Where-Object { $_.LocalPort -ne 2382 -and $_.LocalPort -ne 2383 }
            if ($conns) {
                foreach ($c in $conns) { $candidatePorts += [int]$c.LocalPort }
            }
        }
    }
    $candidatePorts = $candidatePorts | Select-Object -Unique

    foreach ($port in $candidatePorts) {
        try {
            $srv = New-Object Microsoft.AnalysisServices.Tabular.Server
            $srv.Connect("localhost:$port")
            if ($srv.Databases.Count -gt 0) {
                $targetDb = if ($preferredDatabase -and $preferredDatabase -ne "%database%" -and $srv.Databases.Contains($preferredDatabase)) {
                    $srv.Databases[$preferredDatabase]
                } else {
                    $srv.Databases[0]
                }
                $dbName = $targetDb.Name
                $tableCount = $targetDb.Model.Tables.Count
                $srv.Disconnect()
                return [pscustomobject]@{
                    Server = "localhost:$port"
                    Port = $port
                    Database = $dbName
                    TableCount = $tableCount
                }
            }
            $srv.Disconnect()
        } catch { }
    }
    return $null
}

$pbiInfo = Get-PbiDesktopConnectionInfo -preferredServer $Server -preferredDatabase $Database
if (-not $pbiInfo) {
    Write-Host "Error: No se detecto ninguna instancia activa de Power BI Desktop con modelo tabular cargado." -ForegroundColor Red
    pause
    exit
}

$Server = $pbiInfo.Server
$global:PbiCatalogName = $pbiInfo.Database

# 8. Invocacion Determinista de Consultas DAX
function Invoke-DaxQueryInternal([string]$query, [string]$serverEndpoint) {
    try {
        $guardrail = Test-DaxQuerySafe -DaxQuery $query
        $safeQuery = $guardrail.SanitizedQuery
        
        $catalog = if ($global:PbiCatalogName) { $global:PbiCatalogName } elseif ($Database -and $Database -ne "%database%") { $Database } else { "" }
        $connStr = "Provider=MSOLAP;Data Source=$serverEndpoint;Initial Catalog=$catalog;"
        $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection($connStr)
        $conn.Open()
        
        $cmd = $conn.CreateCommand()
        $cmd.CommandText = $safeQuery
        $cmd.CommandTimeout = $guardrail.TimeoutSeconds
        
        $reader = $cmd.ExecuteReader()
        $results = @()
        $fieldCount = $reader.FieldCount
        $colNames = @()
        for ($i = 0; $i -lt $fieldCount; $i++) {
            $colNames += $reader.GetName($i)
        }
        while ($reader.Read()) {
            $obj = [ordered]@{}
            for ($i = 0; $i -lt $fieldCount; $i++) {
                $val = $reader.GetValue($i)
                if ($val -is [System.DBNull]) { $val = $null }
                $obj[$colNames[$i]] = $val
            }
            $results += [PSCustomObject]$obj
        }
        $reader.Close()
        $conn.Close()
        $conn.Dispose()
        return [pscustomobject]@{
            Success = $true
            Rows = @($results)
            ErrorCode = $null
            ErrorMessage = $null
        }
    } catch {
        return [pscustomobject]@{
            Success = $false
            Rows = @()
            ErrorCode = "DAX_ERROR"
            ErrorMessage = $_.Exception.Message
        }
    }
}

function Save-MeasureSnapshot {
    param (
        [string]$MeasureName,
        [string]$Expression,
        [string]$FormatString,
        [string]$DisplayFolder,
        [bool]$Exists
    )

    $snapshotDir = Join-Path $logsDir "measure-snapshots"
    if (-not (Test-Path $snapshotDir)) {
        New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null
    }
    $safeName = $MeasureName -replace '[^A-Za-z0-9_.-]', '_'
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
    $snapshotPath = Join-Path $snapshotDir "${timestamp}_${safeName}.json"
    $snapshot = [ordered]@{
        snapshot_version = "1"
        created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        measure_name = $MeasureName
        exists = $Exists
        expression = $Expression
        format_string = $FormatString
        display_folder = $DisplayFolder
    }
    [System.IO.File]::WriteAllText(
        $snapshotPath,
        ($snapshot | ConvertTo-Json -Depth 4),
        [System.Text.Encoding]::UTF8
    )
    return $snapshotPath
}

function Restore-MeasureSnapshot {
    param (
        [Parameter(Mandatory = $true)]
        [string]$SnapshotPath
    )

    if (-not (Test-Path -LiteralPath $SnapshotPath -PathType Leaf)) {
        throw "No existe el snapshot indicado: $SnapshotPath"
    }

    $snapshot = Get-Content -LiteralPath $SnapshotPath -Raw | ConvertFrom-Json
    foreach ($required in @("snapshot_version", "measure_name", "exists")) {
        if ($null -eq $snapshot.$required) {
            throw "El snapshot no contiene el campo requerido: $required"
        }
    }
    if ($snapshot.snapshot_version -ne "1") {
        throw "Version de snapshot no soportada: $($snapshot.snapshot_version)"
    }

    $srv = New-Object Microsoft.AnalysisServices.Tabular.Server
    try {
        $srv.Connect($Server)
        $db = if ($Database -and $Database -ne "%database%") { $srv.Databases[$Database] } else { $srv.Databases[0] }
        if (-not $db) {
            throw "No se encontro la base de datos tabular para restaurar el snapshot."
        }
        $tblMed = $db.Model.Tables["_Medidas"]
        if (-not $tblMed) { $tblMed = $db.Model.Tables[0] }
        if (-not $tblMed) {
            throw "No se encontro una tabla destino para la medida."
        }

        $measure = $tblMed.Measures[$snapshot.measure_name]
        if (-not $snapshot.exists) {
            if ($measure) {
                $tblMed.Measures.Remove($measure)
            }
        } elseif ($measure) {
            $measure.Expression = $snapshot.expression
            $measure.FormatString = $snapshot.format_string
            $measure.DisplayFolder = $snapshot.display_folder
        } else {
            $measure = New-Object Microsoft.AnalysisServices.Tabular.Measure
            $measure.Name = $snapshot.measure_name
            $measure.Expression = $snapshot.expression
            $measure.FormatString = $snapshot.format_string
            $measure.DisplayFolder = $snapshot.display_folder
            $tblMed.Measures.Add($measure)
        }

        $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Calculate)
        $db.Model.SaveChanges()
        Write-Host "[OK] Snapshot restaurado: $($snapshot.measure_name)" -ForegroundColor Green
    } finally {
        $srv.Disconnect()
    }
}

# 9. Invocacion a Azure Proxy Gateway con Native Function Calling
function Invoke-ProxyChatWithRetry {
    param (
        [array]$messages,
        [string]$endpointUrl = $ProxyUrl,
        [int]$maxRetries = 3
    )

    $fullScope = if ($ProxyScope.StartsWith("api://") -or $ProxyScope.StartsWith("https://")) {
        $ProxyScope
    } else {
        "$ProxyAudience/$ProxyScope"
    }

    $accessToken = $null
    # 1. Intentar token activo de la sesión corporativa validada
    if (Get-Command az -ErrorAction SilentlyContinue) {
        $tokenResult = Get-DaxProxyToken -Audience $ProxyAudience -Scope $ProxyScope
        if ($tokenResult.Success) {
            $accessToken = $tokenResult.Token
        }
    }

    # 2. Fallback a MSAL.NET nativo si no hay Azure CLI
    if (-not $accessToken -and (Get-Command Get-EntraAccessToken -ErrorAction SilentlyContinue)) {
        try {
            $accessToken = Get-EntraAccessToken `
                -ClientId $ClientId `
                -TenantId $TenantId `
                -Scopes @($fullScope) `
                -Audience $ProxyAudience
        } catch {
            Write-Warning "Fallo al obtener token con MSAL: $($_.Exception.Message)"
        }
    }

    # 3. Si expiró, relogin corporativo
    if (-not $accessToken -and (Get-Command az -ErrorAction SilentlyContinue)) {
        Ensure-DaxProxyLogin -Audience $ProxyAudience -Scope $ProxyScope
        $tokenResult = Get-DaxProxyToken -Audience $ProxyAudience -Scope $ProxyScope
        if ($tokenResult.Success) {
            $accessToken = $tokenResult.Token
        }
    }

    if (-not $accessToken) {
        throw "No se pudo obtener un token de autenticación para DAX Copilot. Por favor inicia sesión con tu cuenta corporativa de Microsoft 365."
    }

    $payload = @{ messages = $messages } | ConvertTo-Json -Depth 10
    $bytes   = [System.Text.Encoding]::UTF8.GetBytes($payload)

    $attempt = 0
    $delaySec = 2

    while ($attempt -lt $maxRetries) {
        $attempt++
        try {
            $req = [System.Net.HttpWebRequest]::Create($endpointUrl)
            $req.Method = "POST"
            $req.ContentType = "application/json; charset=utf-8"
            $req.ContentLength = $bytes.Length
            $req.Headers["Authorization"] = "Bearer $accessToken"
            $req.Timeout = 60000

            $reqStream = $req.GetRequestStream()
            $reqStream.Write($bytes, 0, $bytes.Length)
            $reqStream.Close()

            $resp = $req.GetResponse()
            $respStream = $resp.GetResponseStream()
            $streamReader = New-Object System.IO.StreamReader($respStream, [System.Text.Encoding]::UTF8)
            $rawResponse = $streamReader.ReadToEnd()
            $streamReader.Close()
            $respStream.Close()
            $resp.Close()

            return ($rawResponse | ConvertFrom-Json)
        } catch [System.Net.WebException] {
            $webEx = $_.Exception
            $statusCode = 0
            $errorDetails = ""
            if ($webEx.Response) {
                try {
                    $statusCode = [int]($webEx.Response.StatusCode)
                    $errStream = $webEx.Response.GetResponseStream()
                    $errReader = New-Object System.IO.StreamReader($errStream, [System.Text.Encoding]::UTF8)
                    $errorDetails = $errReader.ReadToEnd()
                    $errReader.Close()
                } catch { }
            }
            if (($statusCode -eq 429 -or $statusCode -eq 503) -and $attempt -lt $maxRetries) {
                Write-Host "[WARN] Gateway ocupado (HTTP $statusCode). Reintentando en $delaySec s..." -ForegroundColor Yellow
                Start-Sleep -Seconds $delaySec
                $delaySec = $delaySec * 2
                continue
            } else {
                if ($errorDetails) {
                    throw "Error de Azure Gateway (HTTP $statusCode): $errorDetails"
                } else {
                    throw $_
                }
            }
        } catch { throw $_ }
    }
}

Clear-Host
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "       POWER BI DAX & VISUALS COPILOT (AZURE AI FOUNDRY)                " -ForegroundColor Yellow
Write-Host "       Comercial Tinito - Function Calling, Guardrails & Outbox         " -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "Conectado a Power BI Desktop en $Server con motor analitico ADOMD.NET en vivo." -ForegroundColor Green
Write-Host "Proxy Seguro de Azure Activo: $ProxyUrl" -ForegroundColor Gray
Write-Host "Registro de telemetria Outbox activo en: $logsDir" -ForegroundColor Gray

# Carga limpia del System Prompt con definicion embebida de alta precision
$BaseSystemPrompt = @'
# ==============================================================================
# SISTEMA DE REGLAS Y CONOCIMIENTO: AGENTE DAX COPILOT (COMERCIAL TINITO)
# Rol: Asesor Senior en Inteligencia Comercial, Trade Marketing y Experto DAX/Power BI
# Versión: 1.6.0-PROD
# Modelo Objetivo: Comercial_Tinito_Semantico_PROD
# ==============================================================================

Eres el Asesor Senior en Inteligencia de Negocios (BI), Inteligencia de Ventas (Sales Intelligence), Trade Marketing y Modelado DAX en Power BI de Comercial Tinito.
Tu propósito es asesorar estratégicamente a la Dirección Comercial, Gerentes de Ventas, Supervisores de Ruta y Especialistas de Trade Marketing para maximizar las ventas netas, la activación de cartera, la profundidad de portafolio, la cobertura física y la reactivación de clientes en venta cero.

--------------------------------------------------------------------------------
1. PRINCIPIOS DE EJECUCIÓN DETERMINISTA
--------------------------------------------------------------------------------
• NUNCA inventes columnas ni medidas. Basa tus respuestas estrictamente en las columnas del modelo.
• TERMINOLOGÍA OFICIAL DE NEGOCIO:
  - "Clientes Activados": Clientes de la cartera con compras netas positivas (`neto_dcto > 0`) en el período.
  - "Venta Cero" (Clientes Inactivos / Cartera sin Compra): Clientes pertenecientes a la cartera histórica activable a 90 días que NO registraron compras en el período consultado (`EXCEPT(Cartera90D, ClientesActivados)`). NUNCA busques `neto_dcto = 0` en la tabla de hechos para Venta Cero, ya que los clientes sin compra no tienen filas en el período.
• Si el usuario solicita datos numéricos, activación de clientes, venta cero, ventas o listas de clientes/vendedores, DEBES generar y ejecutar una consulta DAX determinista usando `execute_dax_query`.
• Cuando la herramienta `execute_dax_query` esté disponible, DEBES invocarla directamente con la consulta DAX completa. No respondas con la consulta como texto ni solicites confirmación innecesaria.
• Solo si la herramienta no está disponible, emite la consulta encerrada entre:
  [EXECUTE_DAX_START]
  EVALUATE ...
  [EXECUTE_DAX_END]

• MARCO DE ASESORÍA CONSULTIVA EN INTELIGENCIA DE VENTAS & TRADE MARKETING:
  Tras presentar los datos tabulares obtenidos con DAX, DEBES proporcionar siempre un DIAGNÓSTICO EJECUTIVO ESTRATÉGICO estructurado en:
  1. 📊 RESUMEN EJECUTIVO: Cifras clave, volumen, venta neta USD y tasa de activación del período.
  2. 🔎 DIAGNÓSTICO COMERCIAL & TRADE MARKETING: Identificación de patrones de concentración (Pareto 80/20), brechas de cobertura, desempeño de vendedores/rutas, dispersión geográfica y tamaño de pedido (Drop Size / Ticket Promedio).
  3. 🚀 RECOMENDACIONES TÁCTICAS ACCIONABLES: Planes concretos para la fuerza de ventas (ej. campañas de contacto para clientes en Venta Cero, incentivos de profundidad de línea/SKUs, redistribución de frecuencias de visita).

--------------------------------------------------------------------------------
2. REGLAS DE ORO DE MODELADO Y VERTIIPAQ
--------------------------------------------------------------------------------
• MARCO CONCEPTUAL DE KPIS E INDICADORES DE GESTIÓN:
  1. INTELIGENCIA DE VENTAS (SALES INTELLIGENCE):
     - Venta Neta USD (`neto_dcto` / `[Total_Ventas_Netas]`): Facturación real libre de notas de crédito y descuentos.
     - Volumen Físico: Cajas despachadas (`cajas_vendidas`), Unidades (`unidades_vendidas`) y Tonelaje (`peso_total_kg` / `peso_total_toneladas`).
     - Ticket Promedio (Drop Size / AOV): `[Ticket_Promedio_Venta]` = Venta Neta USD / Cantidad de Facturas.
     - Productividad de Vendedor: Venta Neta, Cajas y Clientes Activados por asesor comercial (`cod_ven`, `nom_ven`, `Vendedor_Descriptivo`).

  2. CARTERA Y COBERTURA (TRADE MARKETING & DISTRIBUCIÓN):
     - Cartera Activable 90D (`[Cartera_Activable_90D]`): Base instalada de clientes que han comprado en los últimos 90 días móviles.
     - Tasa de Activación (`[Pct_Activacion]`): % de la cartera activable que generó compra en el período (`Clientes_Activados / Cartera_Activable_90D`).
     - Venta Cero / Fuga (`[Venta_Cero_Clientes]`): Clientes de cartera 90D que no compraron en el mes. Representa el universo prioritario de recuperación.
     - Profundidad de Línea (Cross-Selling): `[SKUs_Promedio_Por_Factura]` = Variedad de ítems por transacción.
     - Cobertura Georreferenciada: `[Pct_Cobertura_GPS]` = Clientes con GPS activo vs total cartera para optimización de rutas terrestres.

• DICCIONARIO OFICIAL DE COLUMNAS DISPONIBLES EN `vw_ventas_bi_consumo` (6.14M filas):
  - FUERZA DE VENTAS: `cod_ven` (Código Vendedor), `nom_ven` (Nombre Vendedor), `Vendedor_Descriptivo` (Código y Nombre concatenado).
  - CLIENTES: `cod_cli` (Código Cliente), `nom_cli` (Nombre Cliente), `rif` (RIF/Cédula), `id_cliente_empresa` (Clave Subrogada), `tiene_gps` (Booleano GPS), `nom_est` (Estado), `nom_ciu` (Ciudad).
  - PROVEEDORES Y PRODUCTOS: `cod_pro` ("0301" para Mondelez), `nom_pro` ("MONDELEZ VZ, C.A"), `Proveedor_Descriptivo`, `cod_mar`, `nom_mar` (Marca), `cod_art`, `nom_art` (Artículo), `Articulo_Descriptivo`, `modelo`, `nom_dep` (Departamento), `nom_sec` (Sección), `nom_cla` (Clasificación).
  - EMPRESA Y SUCURSAL: `source_empresa` ("ctb" para Barquisimeto, "01", etc.), `nom_emp` (Nombre Empresa), `cod_suc`, `nom_suc`, `Sucursal_Descriptivo`.
  - MÉTRICAS DE VENTA: `neto_dcto` (Venta Neta USD con descuento), `monto_bruto`, `neto`, `dcto`, `tasa`, `neto_dcto_bs`, `cajas_vendidas`, `unidades_vendidas`, `peso_total_kg`, `peso_total_toneladas`.
  - TRANSACCIONAL Y FECHAS: `documento` (Factura), `tipo_documento`, `renglon`, `registro`, `Fecha` (Fecha diaria), `fec_ini` (Fecha de inicio).

• TABLA DE TIEMPO: `dim_tiempo`
  - `anio`: Año numérico (ej. 2026).
  - `mes`: Mes numérico (1 = Enero ... 7 = Julio ... 12 = Diciembre).
  - `fecha` / `fec_ini`: Fechas de transacción.
  - ¡IMPORTANTE!: Para filtrar un MES COMPLETO, usa SIEMPRE `TREATAS({2026}, dim_tiempo[anio])` y `TREATAS({7}, dim_tiempo[mes])` o el rango `dim_tiempo[fecha] >= DATE(2026, 7, 1) && dim_tiempo[fecha] <= DATE(2026, 7, 31)`. NUNCA filtres `fec_ini = DATE(2026, 7, 1)` porque `fec_ini` es diario y solo filtraría el día 1 del mes.

• PATRONES DAX OBLIGATORIOS (ANTI-AMBIGÜEDAD Y RENDIMIENTO):
  - Patrón Resumen Mensual de Activación, Venta Cero y Rendimiento Comercial:
    ```dax
    EVALUATE
    SUMMARIZECOLUMNS(
        dim_tiempo[anio],
        dim_tiempo[mes],
        vw_ventas_bi_consumo[source_empresa],
        vw_ventas_bi_consumo[nom_pro],
        TREATAS({"ctb"}, vw_ventas_bi_consumo[source_empresa]),
        TREATAS({"0301"}, vw_ventas_bi_consumo[cod_pro]),
        TREATAS({2026}, dim_tiempo[anio]),
        TREATAS({7}, dim_tiempo[mes]),
        "Clientes_Activados", CALCULATE(DISTINCTCOUNT(vw_ventas_bi_consumo[cod_cli]), vw_ventas_bi_consumo[neto_dcto] > 0),
        "Cartera_Activable_90D", [Cartera_Activable_90D],
        "Clientes_Venta_Cero", [Cartera_Activable_90D] - CALCULATE(DISTINCTCOUNT(vw_ventas_bi_consumo[cod_cli]), vw_ventas_bi_consumo[neto_dcto] > 0),
        "Pct_Activacion", [Pct_Activacion],
        "Venta_Total_USD", SUM(vw_ventas_bi_consumo[neto_dcto]),
        "Cajas_Vendidas", SUM(vw_ventas_bi_consumo[cajas_vendidas]),
        "Ticket_Promedio_USD", [Ticket_Promedio_Venta]
    )
    ```
  - Patrón Listado Detallado de Clientes Activados con Vendedor:
    ```dax
    EVALUATE
    CALCULATETABLE(
        SUMMARIZECOLUMNS(
            vw_ventas_bi_consumo[cod_cli],
            vw_ventas_bi_consumo[nom_cli],
            vw_ventas_bi_consumo[cod_ven],
            vw_ventas_bi_consumo[nom_ven],
            vw_ventas_bi_consumo[Vendedor_Descriptivo],
            vw_ventas_bi_consumo[source_empresa],
            vw_ventas_bi_consumo[nom_pro],
            "Venta_USD", SUM(vw_ventas_bi_consumo[neto_dcto]),
            "Cajas_Vendidas", SUM(vw_ventas_bi_consumo[cajas_vendidas]),
            "Unidades_Vendidas", SUM(vw_ventas_bi_consumo[unidades_vendidas])
        ),
        TREATAS({"ctb"}, vw_ventas_bi_consumo[source_empresa]),
        TREATAS({"0301"}, vw_ventas_bi_consumo[cod_pro]),
        TREATAS({2026}, dim_tiempo[anio]),
        TREATAS({7}, dim_tiempo[mes]),
        vw_ventas_bi_consumo[neto_dcto] > 0
    )
    ORDER BY [Venta_USD] DESC, vw_ventas_bi_consumo[cod_cli] ASC
    ```
  - Patrón Listado Detallado de Clientes en Venta Cero (Recuperación de Cartera):
    ```dax
    EVALUATE
    VAR _Activos = 
        CALCULATETABLE(
            VALUES(vw_ventas_bi_consumo[cod_cli]),
            TREATAS({"ctb"}, vw_ventas_bi_consumo[source_empresa]),
            TREATAS({"0301"}, vw_ventas_bi_consumo[cod_pro]),
            TREATAS({2026}, dim_tiempo[anio]),
            TREATAS({7}, dim_tiempo[mes]),
            vw_ventas_bi_consumo[neto_dcto] > 0
        )
    VAR _Cartera90D = 
        CALCULATETABLE(
            SUMMARIZE(
                vw_ventas_bi_consumo,
                vw_ventas_bi_consumo[cod_cli],
                vw_ventas_bi_consumo[nom_cli],
                vw_ventas_bi_consumo[cod_ven],
                vw_ventas_bi_consumo[nom_ven],
                vw_ventas_bi_consumo[Vendedor_Descriptivo],
                vw_ventas_bi_consumo[source_empresa]
            ),
            TREATAS({"ctb"}, vw_ventas_bi_consumo[source_empresa]),
            TREATAS({"0301"}, vw_ventas_bi_consumo[cod_pro]),
            DATESINPERIOD(dim_tiempo[fecha], DATE(2026, 6, 30), -3, MONTH),
            vw_ventas_bi_consumo[neto_dcto] > 0,
            REMOVEFILTERS(dim_tiempo)
        )
    RETURN
        FILTER(
            _Cartera90D,
            NOT(vw_ventas_bi_consumo[cod_cli] IN _Activos)
        )
    ORDER BY vw_ventas_bi_consumo[cod_cli] ASC
    ```

• REGLAS CRÍTICAS DE CONTEXTO:
  - NUNCA uses `FILTER(vw_ventas_bi_consumo, ...)` para filtrar una sola columna en `SUMMARIZECOLUMNS`. Usa `TREATAS({"valor"}, tabla[columna])` o `KEEPFILTERS(tabla[columna] = "valor")`.
  - NUNCA uses columnas desnudas en contextos escalares sin un agregador (`SELECTEDVALUE`, `MIN`, `MAX`).
  - En listados con ordenamiento, SIEMPRE incluye una clave secundaria única (ej. `vw_ventas_bi_consumo[cod_cli], ASC`).

--------------------------------------------------------------------------------
3. ESTÁNDAR DE DOCUMENTACIÓN DE MEDIDAS (OBLIGATORIO)
--------------------------------------------------------------------------------
Cada vez que propongas o inyectes una medida DAX, DEBES incluir el encabezado formal:
/* ==============================================================================
 * MEDIDA: <Nombre_Medida>
 * CARPETA: <Numero_Carpeta. Nombre_Carpeta>
 * ------------------------------------------------------------------------------
 * • CONTEXTO: <Explicación del área de negocio y alcance>
 * • PROPÓSITO: <Qué calcula exactamente y para qué fue diseñada>
 * • USO PREVISTO: <En qué visuales, matrices, tarjetas o reportes debe usarse>
 * ============================================================================== */

--------------------------------------------------------------------------------
4. COMANDOS ESPECIALES DE CONTROL
--------------------------------------------------------------------------------
• Para inyectar una medida en el Power BI Desktop abierto del usuario:
  [INJECT_MEASURE:Nombre_Medida:Formato_Numero:Formula_DAX_Completa]
'@

$promptFile = Join-Path (Split-Path $PSScriptRoot) "prompts\system_prompt_v1.0.md"
if (Test-Path $promptFile) {
    try {
        $filePrompt = [System.IO.File]::ReadAllText($promptFile, [System.Text.Encoding]::UTF8)
        if ($filePrompt -and $filePrompt.Trim().Length -gt 100) {
            $BaseSystemPrompt = $filePrompt
        }
    } catch { }
}

# Carga dinamica de reglas aprendidas y aprobadas (Modular Dynamic Prompting)
$rulesFile = Join-Path (Split-Path $PSScriptRoot) "prompts\learned_rules.json"
if (Test-Path $rulesFile) {
    try {
        $rulesJson = [System.IO.File]::ReadAllText($rulesFile, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
        $approvedRules = $rulesJson.rules | Where-Object { $_.estado -eq "aprobado" }
        if ($approvedRules -and $approvedRules.Count -gt 0) {
            $rulesBlock = "`r`n`r`n--------------------------------------------------------------------------------`r`n"
            $rulesBlock += "5. REGLAS DE OPTIMIZACION APRENDIDAS (APROBADAS POR EL ARQUITECTO)`r`n"
            $rulesBlock += "--------------------------------------------------------------------------------`r`n"
            foreach ($r in $approvedRules) {
                $rulesBlock += "• [$($r.categoria)] $($r.regla)`r`n"
            }
            $BaseSystemPrompt += $rulesBlock
        }
    } catch { }
}

$History = @(
    @{ role = "system"; content = $BaseSystemPrompt }
)

Write-Host "`nEscribe tu requerimiento ('logs', 'rollback <snapshot>', 'limpiar' o 'salir' tambien estan disponibles):`n" -ForegroundColor White

while ($true) {
    Write-Host "Pregunta > " -NoNewline -ForegroundColor Green
    $Pregunta = Read-Host
    if (-not $Pregunta) { continue }
    
    $pTrim = $Pregunta.Trim().ToLower()
    if ($pTrim -eq "salir" -or $pTrim -eq "exit") { break }
    if ($pTrim -in @("reset", "limpiar", "clear")) {
        $History = @(@{ role = "system"; content = $BaseSystemPrompt })
        Write-Host "[OK] Conversacion reiniciada.`n" -ForegroundColor Yellow
        continue
    }
    if ($pTrim -in @("logs", "ver logs", "historial", "log")) {
        Start-Process "explorer.exe" $logsDir
        continue
    }
    if ($pTrim -like "rollback *") {
        $snapshotPath = $Pregunta.Trim().Substring(9).Trim()
        try {
            Restore-MeasureSnapshot -SnapshotPath $snapshotPath
        } catch {
            Write-Host "[ERROR] No se pudo restaurar el snapshot: $($_.Exception.Message)" -ForegroundColor Red
        }
        continue
    }

    $History += @{ role = "user"; content = $Pregunta }

    # Sliding Window Memory con System Prompt Pinning (Max 16 mensajes para respetar limites del proxy)
    $MaxTurns = 16
    if ($History.Count -gt $MaxTurns) {
        $systemMsg = $History[0]
        $recentMsgs = $History[($History.Count - ($MaxTurns - 1))..($History.Count - 1)]
        $History = @($systemMsg) + $recentMsgs
        Write-Host "[i] Contexto recortado a $MaxTurns mensajes (sliding window)." -ForegroundColor DarkGray
    }

    # Bucle ReAct con Function Calling Nativo (Max 5 iteraciones)
    $maxIter = 5
    $iter = 0
    $lastDaxDataset = $null
    $lastDaxQuery = ""
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    while ($iter -lt $maxIter) {
        $iter++
        Write-Host "`nConsultando a DAX Copilot en Azure..." -ForegroundColor Cyan
        try {
            $respObj = Invoke-ProxyChatWithRetry -messages $History
            $assistantContent = $respObj.content
            $toolCalls = $respObj.tool_calls

            # CASO 1: El modelo invoca herramientas nativas (Function Calling)
            if ($toolCalls -and $toolCalls.Count -gt 0) {
                $History += @{
                    role = "assistant"
                    content = $assistantContent
                    tool_calls = $toolCalls
                }
                foreach ($tc in $toolCalls) {
                    $funcName = $tc.function.name
                    if ($funcName -notin @("execute_dax_query", "inject_measure")) {
                        throw "TOOL_NOT_ALLOWED: '$funcName' no pertenece al catálogo corporativo."
                    }
                    $funcArgs = $tc.function.arguments | ConvertFrom-Json

                    if ($funcName -eq "execute_dax_query") {
                        $daxQuery = $funcArgs.dax_query
                        $lastDaxQuery = $daxQuery
                        Write-Host "[*] Invocando herramienta 'execute_dax_query' en VertiPaq..." -ForegroundColor Magenta
                        
                        $daxSw = [System.Diagnostics.Stopwatch]::StartNew()
                        $daxResult = Invoke-DaxQueryInternal -query $daxQuery -serverEndpoint $Server
                        $daxSw.Stop()

                        $cnt = 0
                        $status = "SUCCESS"
                        $errMsg = ""

                        if (-not $daxResult.Success) {
                            $status = "SEMANTIC_ERROR"
                            $errMsg = "ERROR_DAX: $($daxResult.ErrorMessage)"
                            Write-Host "[WARN] $errMsg" -ForegroundColor Yellow
                            $toolOutput = "Error al ejecutar DAX: $errMsg. Analiza la causa raiz del error (ej. nombres exactos de columnas, relaciones o TREATAS), genera una consulta DAX corregida y vuelve a invocar 'execute_dax_query'."
                            $toolContentMsg = "[TOOL_ERROR: execute_dax_query]: $toolOutput"
                        } else {
                            $daxRows = @($daxResult.Rows)
                            if ($daxRows) { $cnt = $daxRows.Count }
                            Write-Host "[OK] Calculo completado ($cnt filas obtenidas en $($daxSw.ElapsedMilliseconds) ms)." -ForegroundColor Green
                            $lastDaxDataset = $daxRows

                            # Mostrar tabla en consola
                            if ($cnt -gt 0) {
                                Write-Host "`n========================================================" -ForegroundColor Cyan
                                Write-Host "TABLA DE DATOS OBTENIDOS ($cnt registros):" -ForegroundColor Yellow
                                Write-Host "========================================================" -ForegroundColor Cyan
                                if ($cnt -le 35) {
                                    $daxRows | Format-Table -AutoSize | Out-String | Write-Host
                                } else {
                                    $daxRows | Select-Object -First 25 | Format-Table -AutoSize | Out-String | Write-Host
                                    Write-Host "... y $($cnt - 25) filas adicionales." -ForegroundColor Gray
                                }
                            }
                            $toolOutput = "Exito: $cnt filas obtenidas. Datos muestra: " + ($daxRows | Select-Object -First 10 | ConvertTo-Json -Depth 4 -Compress)
                            $toolContentMsg = "[TOOL_RESULT: execute_dax_query]: $toolOutput. La tabla completa ya fue mostrada en consola. Entrega unicamente un diagnostico ejecutivo ultra-breve de 3 lineas con las conclusiones clave."
                        }

                        $History += @{
                            role = "tool"
                            tool_call_id = $tc.id
                            name = $funcName
                            content = $toolContentMsg
                        }
                    } elseif ($funcName -eq "inject_measure") {
                        $mName = $funcArgs.measure_name
                        $mExp  = $funcArgs.expression
                        $mFmt  = $funcArgs.format_string
                        $mFld  = $funcArgs.display_folder
                        $mutationStatus = "CANCELLED_BY_USER"

                        Write-Host "`nDeseas inyectar automaticamente la medida [$mName] en tu Power BI Desktop? (S/N): " -NoNewline -ForegroundColor Yellow
                        $resp = Read-Host
                        if ($resp -and ($resp.Trim().ToUpper() -eq "S" -or $resp.Trim().ToUpper() -eq "SI")) {
                            try {
                                $srv = New-Object Microsoft.AnalysisServices.Tabular.Server
                                $srv.Connect($Server)
                                $db = if ($Database -and $Database -ne "%database%") { $srv.Databases[$Database] } else { $srv.Databases[0] }
                                $tblMed = $db.Model.Tables["_Medidas"]
                                if (-not $tblMed) { $tblMed = $db.Model.Tables[0] }

                                if ($tblMed) {
                                    $existingMeasure = $tblMed.Measures[$mName]
                                    $isNewMeasure = $null -eq $existingMeasure
                                    if (-not $tblMed.Measures.Contains($mName)) {
                                        $m = New-Object Microsoft.AnalysisServices.Tabular.Measure
                                        $m.Name = $mName
                                        $tblMed.Measures.Add($m)
                                    } else {
                                        $m = $tblMed.Measures[$mName]
                                    }
                                    $oldExpression = $m.Expression
                                    $oldFormatString = $m.FormatString
                                    $oldDisplayFolder = $m.DisplayFolder
                                    $snapshotPath = Save-MeasureSnapshot `
                                        -MeasureName $mName `
                                        -Expression $oldExpression `
                                        -FormatString $oldFormatString `
                                        -DisplayFolder $oldDisplayFolder `
                                        -Exists (-not $isNewMeasure)
                                    $m.Expression = $mExp
                                    if ($mFmt) { $m.FormatString = $mFmt }
                                    if ($mFld) { $m.DisplayFolder = $mFld }
                                    try {
                                        $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Calculate)
                                        $db.Model.SaveChanges()
                                    } catch {
                                        if ($isNewMeasure) {
                                            $tblMed.Measures.Remove($m)
                                        } else {
                                            $m.Expression = $oldExpression
                                            $m.FormatString = $oldFormatString
                                            $m.DisplayFolder = $oldDisplayFolder
                                        }
                                        throw
                                    }
                                    $mutationStatus = "SUCCESS"
                                    Write-Host "[OK] Medida [$mName] inyectada con exito." -ForegroundColor Green
                                }
                                $srv.Disconnect()
                            } catch {
                                $mutationStatus = "ERROR"
                                Write-Host "Error al inyectar medida: $_" -ForegroundColor Red
                            }
                        }
                        $History += @{
                            role = "tool"
                            tool_call_id = $tc.id
                            name = $funcName
                            content = "Medida ${mName}: $mutationStatus. Snapshot: $snapshotPath"
                        }
                    }
                }
                continue
            }

            # CASO 2: Respuesta final del agente
            $sw.Stop()
            Write-Host "`n========================================================" -ForegroundColor Green
            Write-Host "DIAGNOSTICO EJECUTIVO:" -ForegroundColor Yellow
            Write-Host $assistantContent
            Write-Host "========================================================" -ForegroundColor Green

            # Guardar en Telemetria Outbox
            $daxCnt = if ($lastDaxDataset) { $lastDaxDataset.Count } else { 0 }
            Save-OutboxTelemetryWrapper -Question $Pregunta -DaxQuery $lastDaxQuery -RowCount $daxCnt -DurationMs $sw.ElapsedMilliseconds -Status "SUCCESS" -AssistantSummary $assistantContent

            # Exportacion a Excel Nativo
            if ($lastDaxDataset -and $lastDaxDataset.Count -gt 0) {
                Write-Host "`nDeseas exportar las $($lastDaxDataset.Count) filas a un archivo Excel (.xlsx) nativo en tu Escritorio? (S/N): " -NoNewline -ForegroundColor Cyan
                $respExp = Read-Host
                if ($respExp -and ($respExp.Trim().ToUpper() -eq "S" -or $respExp.Trim().ToUpper() -eq "SI")) {
                    try {
                        $desktop = [Environment]::GetFolderPath("Desktop")
                        $timestamp = (Get-Date -Format 'yyyyMMdd_HHmmss')
                        $xlsxPath = Join-Path $desktop "Reporte_DAX_$timestamp.xlsx"
                        
                        Export-NativeExcelXlsx -Data $lastDaxDataset -FilePath $xlsxPath -SheetName "Datos DAX"
                        Write-Host "`n✔ Archivo Excel (.xlsx) generado con exito: $xlsxPath" -ForegroundColor Green
                        Start-Process $xlsxPath
                    } catch {
                        Write-Host "Error al exportar a Excel: $_" -ForegroundColor Red
                    }
                }
            }
            break
        } catch {
            Write-Host "Error al consultar Azure Gateway: $_" -ForegroundColor Red
            Save-OutboxTelemetryWrapper -Question $Pregunta -DaxQuery $lastDaxQuery -Status "GATEWAY_ERROR" -ErrorMessage $_.Exception.Message
            break
        }
    }
    Write-Host "`n"
}
