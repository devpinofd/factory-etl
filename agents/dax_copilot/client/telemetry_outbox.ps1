# ==============================================================================
# 📊 TELEMETRY OUTBOX & PII PSEUDONYMIZATION ENGINE (AZURE MONITOR / APP INSIGHTS)
# • Pseudonimización SHA-256 de identificadores de usuario (Cumplimiento GDPR/PII)
# • Cola Outbox Local Persistente (copilot_qa_history.jsonl)
# • Batching asíncrono hacia Azure Application Insights / Log Analytics
# • No persiste preguntas, consultas DAX, respuestas ni errores en claro
# ==============================================================================

function Get-PseudonymizedHash([string]$value) {
    if (-not $value) { return "anonymous" }
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($value.Trim().ToLower())
    $hashBytes = $hasher.ComputeHash($bytes)
    $sb = New-Object System.Text.StringBuilder
    foreach ($b in $hashBytes) { [void]$sb.Append($b.ToString("x2")) }
    return "usr_" + $sb.ToString().Substring(0, 16)
}

function Get-TelemetryContentHash([string]$value) {
    if (-not $value) { return $null }
    return Get-PseudonymizedHash -value $value
}

function New-TelemetryEvent {
    param (
        [string]$User = $env:USERNAME,
        [string]$Question,
        [string]$DaxQuery = "",
        [int]$RowCount = 0,
        [long]$DurationMs = 0,
        [string]$Status = "SUCCESS",
        [string]$ErrorMessage = "",
        [string]$AssistantSummary = ""
    )

    $userHash = Get-PseudonymizedHash -value $User
    
    return @{
        event_id          = [Guid]::NewGuid().ToString()
        timestamp_utc     = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        user_hash         = $userHash
        question_hash     = Get-TelemetryContentHash -value $Question
        dax_query_hash    = Get-TelemetryContentHash -value $DaxQuery
        row_count         = $RowCount
        duration_ms       = $DurationMs
        status            = $Status
        has_error_detail  = [bool]$ErrorMessage
        has_assistant_summary = [bool]$AssistantSummary
        environment       = "PROD"
        model_version     = "1.1.0"
    }
}

function Save-OutboxTelemetry {
    param (
        [hashtable]$EventData,
        [string]$LogDirectory = "$env:LOCALAPPDATA\Tinito\PbiCopilot\logs"
    )

    $samplePercent = 10
    if ($env:DAX_COPILOT_SUCCESS_SAMPLE_PERCENT) {
        try { $samplePercent = [double]$env:DAX_COPILOT_SUCCESS_SAMPLE_PERCENT } catch { $samplePercent = 10 }
    }
    if ($EventData.status -eq "SUCCESS" -and ((Get-Random -Minimum 0 -Maximum 100) -ge $samplePercent)) {
        return $true
    }

    try {
        if (-not (Test-Path $LogDirectory)) {
            New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
        }

        $jsonlFile = Join-Path $LogDirectory "copilot_qa_history.jsonl"
        $mdFile    = Join-Path $LogDirectory "copilot_qa_history.md"

        # 1. Guardar en JSONL comprimido
        $jsonStr = $EventData | ConvertTo-Json -Compress
        [System.IO.File]::AppendAllText($jsonlFile, "$jsonStr`r`n", [System.Text.Encoding]::UTF8)

        # 2. Guardar únicamente metadatos operativos para auditoría humana
        $statusIcon = if ($EventData.status -eq "SUCCESS") { "✔" } else { "❌" }
        $mdEntry = "`r`n### [$statusIcon $($EventData.status)] $($EventData.timestamp_utc) | User: $($EventData.user_hash) | Latencia: $($EventData.duration_ms)ms`r`n"
        $mdEntry += "**Pregunta hash:** $($EventData.question_hash)`r`n"
        $mdEntry += "**DAX hash:** $($EventData.dax_query_hash) | **Filas:** $($EventData.row_count)`r`n"
        $mdEntry += "**Error detail presente:** $($EventData.has_error_detail) | **Resumen presente:** $($EventData.has_assistant_summary)`r`n`r`n---`r`n"
        [System.IO.File]::AppendAllText($mdFile, $mdEntry, [System.Text.Encoding]::UTF8)

        return $true
    } catch {
        Write-Warning "No se pudo guardar la telemetría local: $($_.Exception.Message)"
        return $false
    }
}
