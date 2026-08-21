# ==============================================================================
# POWER BI DAX & SEMANTIC COPILOT (AZURE AI FOUNDRY & MANAGED GATEWAY)
# Comercial Tinito - Agente Determinista de Alta Ejecucion y Salida Tabular
# Version: 1.2.0-PROD
# ==============================================================================

param (
    [Parameter(Mandatory=$false)]
    [string]$Server,

    [Parameter(Mandatory=$false)]
    [string]$Database,

    [Parameter(Mandatory=$false)]
    [string]$ProxyUrl = $env:DAX_COPILOT_PROXY_URL,

    [Parameter(Mandatory=$false)]
    [string]$ProxyKey = $env:DAX_COPILOT_FUNCTION_KEY,

    [Parameter(Mandatory=$false)]
    [string]$ProxyAudience = $env:DAX_COPILOT_AUDIENCE,

    [Parameter(Mandatory=$false)]
    [string]$ProxyScope = $(if ($env:DAX_COPILOT_SCOPE) { $env:DAX_COPILOT_SCOPE } else { "access_as_user" })
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
    throw "No se encontro el modulo de guardrails DAX: $guardrailPath"
}
. $guardrailPath

# 5. Modulo de Telemetria Outbox sin contenido sensible
function Get-PseudonymizedHash([string]$value) {
    if (-not $value) { return "anonymous" }
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($value.Trim().ToLower())
    $hashBytes = $hasher.ComputeHash($bytes)
    $sb = New-Object System.Text.StringBuilder
    foreach ($b in $hashBytes) { [void]$sb.Append($b.ToString("x2")) }
    return "usr_" + $sb.ToString().Substring(0, 16)
}

function Save-OutboxTelemetry {
    param (
        [string]$Question,
        [string]$DaxQuery = "",
        [int]$RowCount = 0,
        [long]$DurationMs = 0,
        [string]$Status = "SUCCESS",
        [string]$ErrorMessage = "",
        [string]$AssistantSummary = ""
    )

    $samplePercent = 10
    if ($env:DAX_COPILOT_SUCCESS_SAMPLE_PERCENT) {
        try { $samplePercent = [double]$env:DAX_COPILOT_SUCCESS_SAMPLE_PERCENT } catch { $samplePercent = 10 }
    }
    if ($Status -eq "SUCCESS" -and ((Get-Random -Minimum 0 -Maximum 100) -ge $samplePercent)) {
        return
    }

    try {
        $jsonlFile = Join-Path $logsDir "copilot_qa_history.jsonl"
        $mdFile    = Join-Path $logsDir "copilot_qa_history.md"
        $userHash  = Get-PseudonymizedHash -value $env:USERNAME
        $ts        = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

        $eventPayload = @{
            event_id      = [Guid]::NewGuid().ToString()
            timestamp_utc = $ts
            user_hash     = $userHash
            question_hash = Get-PseudonymizedHash -value $Question
            dax_query_hash = if ($DaxQuery) { Get-PseudonymizedHash -value $DaxQuery } else { $null }
            row_count     = $RowCount
            duration_ms   = $DurationMs
            status        = $Status
            has_error_detail = [bool]$ErrorMessage
            has_assistant_summary = [bool]$AssistantSummary
            sampled       = ($Status -ne "SUCCESS")
            model_version = "1.2.0"
        }

        $jsonStr = $eventPayload | ConvertTo-Json -Compress
        [System.IO.File]::AppendAllText($jsonlFile, "$jsonStr`r`n", [System.Text.Encoding]::UTF8)

        $statusIcon = if ($Status -eq "SUCCESS") { "✔" } else { "❌" }
        $mdEntry = "`r`n### [$statusIcon $Status] $ts | User: $userHash | Latencia: ${DurationMs}ms`r`n"
        $mdEntry += "**Pregunta hash:** $($eventPayload.question_hash)`r`n"
        $mdEntry += "**DAX hash:** $($eventPayload.dax_query_hash) | **Filas:** $RowCount`r`n"
        $mdEntry += "**Error detail presente:** $($eventPayload.has_error_detail) | **Resumen presente:** $($eventPayload.has_assistant_summary)`r`n`r`n---`r`n"
        [System.IO.File]::AppendAllText($mdFile, $mdEntry, [System.Text.Encoding]::UTF8)
    } catch {
        Write-Warning "No se pudo guardar la telemetría local: $($_.Exception.Message)"
    }
}

# 6. Motor Nativo de Exportacion a Excel OpenXML (.XLSX)
function Export-NativeExcelXlsx {
    param (
        [Parameter(Mandatory=$true)]
        [object[]]$Data,
        [Parameter(Mandatory=$true)]
        [string]$FilePath,
        [string]$SheetName = "Reporte DAX"
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
        $props = $Data[0].PSObject.Properties | Select-Object -ExpandProperty Name
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

    $numRows = $Data.Count + 1
    $numCols = $props.Count
    $lastCol = Get-ColLetter $numCols

    $sheetXml = New-Object System.Text.StringBuilder
    [void]$sheetXml.AppendLine('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    [void]$sheetXml.AppendLine('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    [void]$sheetXml.AppendLine("<dimension ref=""A1:${lastCol}${numRows}""/>")
    [void]$sheetXml.AppendLine('<sheetViews><sheetView tabSelected="1" workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    [void]$sheetXml.AppendLine('<sheetFormatPr defaultRowHeight="16"/>')
    [void]$sheetXml.AppendLine('<sheetData>')

    # Header Row (Azul Corporativo Tinito #1F4E78 con texto blanco)
    [void]$sheetXml.AppendLine("<row r=""1"" spans=""1:$numCols"" customHeight=""1"" ht=""24"">")
    for ($c = 0; $c -lt $props.Count; $c++) {
        $colLetter = Get-ColLetter ($c + 1)
        $hText = [System.Security.SecurityElement]::Escape($props[$c])
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
        [void]$sheetXml.AppendLine("<row r=""$r"" spans=""1:$numCols"">")
        for ($c = 0; $c -lt $props.Count; $c++) {
            $colLetter = Get-ColLetter ($c + 1)
            $pName = $props[$c]
            $val = $row.$pName
            $cellRef = "${colLetter}${r}"

            if ($null -eq $val -or $val -eq "") { continue }

            $numVal = 0.0
            $isDouble = [double]::TryParse("$val", [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$numVal)
            if (-not $isDouble) {
                $isDouble = [double]::TryParse("$val", [System.Globalization.NumberStyles]::Any, (Get-Culture), [ref]$numVal)
            }

            if ($isDouble -and ($val -notmatch '^[0-9]{4}-[0-9]{2}-[0-9]{2}') -and ($val.ToString().Length -lt 15 -or $val -match '^-?[0-9]+(\.[0-9]+)?$')) {
                $strVal = $numVal.ToString([System.Globalization.CultureInfo]::InvariantCulture)
                $styleIdx = if ($val -is [int] -or $val -is [long] -or ($numVal % 1 -eq 0)) { "2" } else { "3" }
                [void]$sheetXml.AppendLine("<c r=""$cellRef"" s=""$styleIdx""><v>$strVal</v></c>")
            } elseif ($val -is [datetime] -or ($val -match '^\d{4}-\d{2}-\d{2}')) {
                $d = [datetime]::MinValue
                if ([datetime]::TryParse("$val", [ref]$d)) {
                    $oaDate = $d.ToOADate().ToString([System.Globalization.CultureInfo]::InvariantCulture)
                    [void]$sheetXml.AppendLine("<c r=""$cellRef"" s=""4""><v>$oaDate</v></c>")
                } else {
                    $esc = [System.Security.SecurityElement]::Escape("$val")
                    if (-not $strDict.ContainsKey($esc)) {
                        $idx = $sharedStrings.Add($esc)
                        $strDict[$esc] = $idx
                    } else {
                        $idx = $strDict[$esc]
                    }
                    [void]$sheetXml.AppendLine("<c r=""$cellRef"" s=""0"" t=""s""><v>$idx</v></c>")
                }
            } else {
                $esc = [System.Security.SecurityElement]::Escape("$val")
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

    [System.IO.File]::WriteAllText((Join-Path $worksheetsDir "sheet1.xml"), $sheetXml.ToString(), [System.Text.Encoding]::UTF8)

    # Shared Strings XML
    $ssXml = New-Object System.Text.StringBuilder
    [void]$ssXml.AppendLine('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    [void]$ssXml.AppendLine("<sst xmlns=""http://schemas.openxmlformats.org/spreadsheetml/2006/main"" count=""$($sharedStrings.Count)"" uniqueCount=""$($sharedStrings.Count)"">")
    foreach ($s in $sharedStrings) { [void]$ssXml.AppendLine("<si><t>$s</t></si>") }
    [void]$ssXml.AppendLine('</sst>')
    [System.IO.File]::WriteAllText((Join-Path $xlDir "sharedStrings.xml"), $ssXml.ToString(), [System.Text.Encoding]::UTF8)

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
    <font><sz val="10"/><name val="Segoe UI"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Segoe UI"/></font>
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
</styleSheet>
'@
    [System.IO.File]::WriteAllText((Join-Path $xlDir "styles.xml"), $stylesXml, [System.Text.Encoding]::UTF8)

    $wbXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="$SheetName" sheetId="1" r:id="rId1"/></sheets>
</workbook>
"@
    [System.IO.File]::WriteAllText((Join-Path $xlDir "workbook.xml"), $wbXml, [System.Text.Encoding]::UTF8)

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
    [System.IO.File]::WriteAllText((Join-Path $tempDir "[Content_Types].xml"), $ctXml, [System.Text.Encoding]::UTF8)

    $rootRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
'@
    [System.IO.File]::WriteAllText((Join-Path $relsDir ".rels"), $rootRels, [System.Text.Encoding]::UTF8)

    $xlRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>
'@
    [System.IO.File]::WriteAllText((Join-Path $xlRelsDir "workbook.xml.rels"), $xlRels, [System.Text.Encoding]::UTF8)

    [System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $FilePath)
    Remove-Item $tempDir -Recurse -Force
}

# 7. Deteccion automatica del puerto de Power BI Desktop
if (-not $Server -or $Server -eq "%server%") {
    $pbiProcesses = Get-Process msmdsrv -ErrorAction SilentlyContinue
    if ($pbiProcesses) {
        $ports = @()
        foreach ($p in $pbiProcesses) {
            $conns = Get-NetTCPConnection -OwningProcess $p.Id -State Listen -ErrorAction SilentlyContinue
            if ($conns) {
                foreach ($c in $conns) { $ports += $c.LocalPort }
            }
        }
        $ports = $ports | Select-Object -Unique
        if ($ports.Count -gt 0) {
            $Server = "localhost:$($ports[0])"
        }
    }
}

if (-not $Server) {
    Write-Host "Error: No se detecto ninguna instancia de Power BI Desktop abierta." -ForegroundColor Red
    pause
    exit
}

# 8. Invocacion Determinista de Consultas DAX
function Invoke-DaxQueryInternal([string]$query, [string]$serverEndpoint) {
    try {
        $guardrail = Test-DaxQuerySafe -DaxQuery $query
        $safeQuery = $guardrail.SanitizedQuery
        
        $connStr = "Provider=MSOLAP;Data Source=$serverEndpoint;Initial Catalog=;"
        $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection($connStr)
        $conn.Open()
        
        $cmd = $conn.CreateCommand()
        $cmd.CommandText = $safeQuery
        $cmd.CommandTimeout = $guardrail.TimeoutSeconds
        
        $reader = $cmd.ExecuteReader()
        $table = New-Object System.Data.DataTable
        $table.Load($reader)
        
        $reader.Close()
        $conn.Close()
        $conn.Dispose()

        $results = @()
        foreach ($row in $table.Rows) {
            $obj = [ordered]@{}
            foreach ($col in $table.Columns) {
                $obj[$col.ColumnName] = $row[$col.ColumnName]
            }
            $results += [PSCustomObject]$obj
        }
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

    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw "Azure CLI es requerida para obtener el token Entra del proxy."
    }
    $tokenJson = & az account get-access-token --scope "$ProxyAudience/$ProxyScope" --output json 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $tokenJson) {
        throw "No se pudo obtener un token Entra. Ejecuta 'az login' con tu cuenta corporativa."
    }
    $accessToken = ($tokenJson | ConvertFrom-Json).accessToken
    if (-not $accessToken) {
        throw "Azure CLI no devolvio un token Entra valido."
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
            if ($webEx.Response) { $statusCode = [int]($webEx.Response.StatusCode) }
            if (($statusCode -eq 429 -or $statusCode -eq 503) -and $attempt -lt $maxRetries) {
                Write-Host "[WARN] Gateway ocupado (HTTP $statusCode). Reintentando en $delaySec s..." -ForegroundColor Yellow
                Start-Sleep -Seconds $delaySec
                $delaySec = $delaySec * 2
                continue
            } else { throw $_ }
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

# Carga limpia del System Prompt desde archivo versionado
$promptFile = Join-Path (Split-Path $PSScriptRoot) "prompts\system_prompt_v1.0.md"
$BaseSystemPrompt = ""
if (Test-Path $promptFile) {
    $BaseSystemPrompt = [System.IO.File]::ReadAllText($promptFile, [System.Text.Encoding]::UTF8)
} else {
    $BaseSystemPrompt = "Eres el Agente Experto en DAX y Modelado Semantico de Comercial Tinito. Usa la herramienta execute_dax_query para consultar VertiPaq."
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
                            $toolOutput = "Error al ejecutar DAX: $errMsg"
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
                        }

                        $History += @{
                            role = "tool"
                            tool_call_id = $tc.id
                            name = $funcName
                            content = "[TOOL_RESULT: execute_dax_query]: $toolOutput. La tabla completa ya fue mostrada en consola. Entrega unicamente un diagnostico ejecutivo ultra-breve de 3 lineas con las conclusiones clave."
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
            Save-OutboxTelemetry -Question $Pregunta -DaxQuery $lastDaxQuery -RowCount $daxCnt -DurationMs $sw.ElapsedMilliseconds -Status "SUCCESS" -AssistantSummary $assistantContent

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
            Save-OutboxTelemetry -Question $Pregunta -DaxQuery $lastDaxQuery -Status "GATEWAY_ERROR" -ErrorMessage $_.Exception.Message
            break
        }
    }
    Write-Host "`n"
}
