# ==============================================================================
# 📦 COMPILADOR Y GENERADOR DE PAQUETE PROTEGIDO (TINITO DAX COPILOT)
# • Consolida todos los módulos (.ps1, prompts, reglas) en un único artefacto monolítico
# • Aplica compresión DeflateStream y ejecución estrictamente en memoria (RAM)
# • Actualiza el manifest.json con el hash criptográfico SHA-256 para Azure Storage Hub
# ==============================================================================

param (
    [string]$ClientDir = $PSScriptRoot,
    [switch]$DeployToCache = $true
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "   📦 CONSTRUCCIÓN DEL PAQUETE PROTEGIDO DAX COPILOT    " -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Rutas de archivos fuente
$guardrailsFile = Join-Path $ClientDir "dax_guardrails.ps1"
$telemetryFile  = Join-Path $ClientDir "telemetry_outbox.ps1"
$msalFile       = Join-Path $ClientDir "msal_auth.ps1"
$assistantFile  = Join-Path $ClientDir "pbi_copilot_assistant.ps1"
$promptFile     = Join-Path (Split-Path $ClientDir) "prompts\system_prompt_v1.0.md"
$rulesFile      = Join-Path (Split-Path $ClientDir) "prompts\learned_rules.json"
$manifestFile   = Join-Path $ClientDir "manifest.json"

# 2. Validar existencia
$requiredFiles = @($guardrailsFile, $telemetryFile, $assistantFile, $manifestFile)
foreach ($f in $requiredFiles) {
    if (-not (Test-Path $f)) {
        throw "No se encontró el archivo requerido: $f"
    }
}

Write-Host "[*] Leyendo módulos fuente..." -ForegroundColor Cyan

$guardrailsCode = [System.IO.File]::ReadAllText($guardrailsFile, [System.Text.Encoding]::UTF8)
$telemetryCode  = [System.IO.File]::ReadAllText($telemetryFile, [System.Text.Encoding]::UTF8)
$msalCode       = if (Test-Path $msalFile) { [System.IO.File]::ReadAllText($msalFile, [System.Text.Encoding]::UTF8) } else { "" }
$assistantCode  = [System.IO.File]::ReadAllText($assistantFile, [System.Text.Encoding]::UTF8)
$promptText     = if (Test-Path $promptFile) { [System.IO.File]::ReadAllText($promptFile, [System.Text.Encoding]::UTF8) } else { "" }
$rulesText      = if (Test-Path $rulesFile) { [System.IO.File]::ReadAllText($rulesFile, [System.Text.Encoding]::UTF8) } else { "{}" }

# 3. Ensamblado Monolítico en Memoria
Write-Host "[*] Ensamblando módulos en un único bloque de ejecución..." -ForegroundColor Cyan

$header = @'
# ==============================================================================
# 🤖 COMERCIAL TINITO — DAX COPILOT RUNTIME ENGINE (MONOLITHIC IN-MEMORY BUILD)
# Versión: 1.6.0-PROD | Confidencial - Propiedad Intelectual de Comercial Tinito
# ==============================================================================
'@

# Reemplazar dot-sourcings externos para que use las funciones ya cargadas en memoria
$cleanAssistant = $assistantCode `
    -replace '(?m)^\s*\.\s+\$guardrailPath.*$', '# Guardrails cargados en memoria' `
    -replace '(?m)^\s*\.\s+\$msalAuthPath.*$', '# MSAL cargado en memoria' `
    -replace '(?m)^\s*\.\s+\$telemetryOutboxPath.*$', '# Telemetria cargada en memoria'

$monolithicCode = @"
$header

# --- [1. MÓDULO DE GUARDRAILS DAX] ---
$guardrailsCode

# --- [2. MÓDULO DE AUTENTICACIÓN ENTRA ID / MSAL.NET] ---
$msalCode

# --- [3. MÓDULO DE TELEMETRÍA OUTBOX ANONIMIZADA] ---
$telemetryCode

# --- [4. MOTOR PRINCIPAL ASISTENTE DAX COPILOT] ---
$cleanAssistant
"@

$rawBytes = [System.Text.Encoding]::UTF8.GetBytes($monolithicCode)
$rawKb = [math]::Round($rawBytes.Length / 1024, 2)
Write-Host "✔ Código ensamblado: $rawKb KiB ($($rawBytes.Length) bytes)." -ForegroundColor Green

# 4. Compresión DeflateStream
Write-Host "[*] Aplicando compresión y encapsulamiento en memoria..." -ForegroundColor Cyan

$memStream = New-Object System.IO.MemoryStream
$deflateStream = New-Object System.IO.Compression.DeflateStream($memStream, [System.IO.Compression.CompressionMode]::Compress, $true)
$deflateStream.Write($rawBytes, 0, $rawBytes.Length)
$deflateStream.Close()

$compressedBytes = $memStream.ToArray()
$memStream.Close()
$compressedBase64 = [System.Convert]::ToBase64String($compressedBytes)

$compKb = [math]::Round($compressedBytes.Length / 1024, 2)
$ratio = [math]::Round((1 - ($compressedBytes.Length / $rawBytes.Length)) * 100, 1)
Write-Host "✔ Compresión completada: $compKb KiB (Ahorro del $ratio%)." -ForegroundColor Green

# 5. Generar Cargador Protegido (RAM-Only Bootstrapper)
$protectedLoader = @"
# ==============================================================================
# 🔒 TINITO DAX COPILOT - PROTECTED RUNTIME ENGINE (v1.6.0)
# Comercial Tinito C.A. - All Rights Reserved
# Execution Boundary: Strictly In-Memory (RAM-Only)
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
`$OutputEncoding = [System.Text.Encoding]::UTF8

`$b64 = "$compressedBase64"
`$b = [System.Convert]::FromBase64String(`$b64)
`$ms = New-Object System.IO.MemoryStream(,@`$b)
`$ds = New-Object System.IO.Compression.DeflateStream(`$ms, [System.IO.Compression.CompressionMode]::Decompress)
`$sr = New-Object System.IO.StreamReader(`$ds, [System.Text.Encoding]::UTF8)
`$code = `$sr.ReadToEnd()
`$sr.Close(); `$ds.Close(); `$ms.Close()

`$sb = [ScriptBlock]::Create(`$code)
& `$sb
"@

# 6. Escribir archivo de distribución
$distFile = Join-Path $ClientDir "pbi_copilot_assistant.protected.ps1"
[System.IO.File]::WriteAllText($distFile, $protectedLoader, [System.Text.Encoding]::UTF8)

# Calcular nuevo Hash SHA-256 del artefacto protegido
$sha256 = (Get-FileHash -Path $distFile -Algorithm SHA256).Hash

Write-Host "✔ Artefacto protegido generado: $distFile" -ForegroundColor Green
Write-Host "✔ SHA-256: $sha256" -ForegroundColor Yellow

# 7. Actualizar manifest.json
$manifestObj = Get-Content $manifestFile -Raw | ConvertFrom-Json
$manifestObj.sha256 = $sha256
$manifestObj.releaseDate = (Get-Date).ToString("yyyy-MM-dd")
$manifestObj.changelog = "Release protegido para distribución segura en Azure Storage Hub y LAN."
$newManifestJson = $manifestObj | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($manifestFile, $newManifestJson, [System.Text.Encoding]::UTF8)

Write-Host "✔ manifest.json actualizado con nuevo hash SHA-256." -ForegroundColor Green

# 8. Generar Lanzador Protegido (launch_copilot.protected.ps1)
$launcherFile = Join-Path $ClientDir "launch_copilot.ps1"
if (Test-Path $launcherFile) {
    Write-Host "[*] Ofuscando el lanzador local (launch_copilot)..." -ForegroundColor Cyan
    $launcherRaw = [System.IO.File]::ReadAllText($launcherFile, [System.Text.Encoding]::UTF8)
    $launcherBytes = [System.Text.Encoding]::UTF8.GetBytes($launcherRaw)
    
    $lMemStream = New-Object System.IO.MemoryStream
    $lDeflateStream = New-Object System.IO.Compression.DeflateStream($lMemStream, [System.IO.Compression.CompressionMode]::Compress, $true)
    $lDeflateStream.Write($launcherBytes, 0, $launcherBytes.Length)
    $lDeflateStream.Close()
    $lCompBytes = $lMemStream.ToArray()
    $lMemStream.Close()
    $lB64 = [System.Convert]::ToBase64String($lCompBytes)
    
    $protectedLauncher = @"
# ==============================================================================
# 🚀 TINITO DAX COPILOT - PROTECTED LAUNCHER (v1.6.0)
# Comercial Tinito C.A. - Zero-Visibility Cloud Bootstrapper
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
`$OutputEncoding = [System.Text.Encoding]::UTF8
`$b64 = "$lB64"
`$b = [System.Convert]::FromBase64String(`$b64)
`$ms = New-Object System.IO.MemoryStream(,@`$b)
`$ds = New-Object System.IO.Compression.DeflateStream(`$ms, [System.IO.Compression.CompressionMode]::Decompress)
`$sr = New-Object System.IO.StreamReader(`$ds, [System.Text.Encoding]::UTF8)
`$code = `$sr.ReadToEnd()
`$sr.Close(); `$ds.Close(); `$ms.Close()
`$sb = [ScriptBlock]::Create(`$code)
& `$sb
"@
    $distLauncher = Join-Path $ClientDir "launch_copilot.protected.ps1"
    [System.IO.File]::WriteAllText($distLauncher, $protectedLauncher, [System.Text.Encoding]::UTF8)
    Write-Host "✔ Lanzador protegido generado: $distLauncher" -ForegroundColor Green
}

# 9. Sincronizar en caché local y launcher si se solicita
if ($DeployToCache) {
    $cacheDir = "$env:LOCALAPPDATA\Tinito\PbiCopilot\cache"
    $launchDir = "$env:LOCALAPPDATA\Tinito\PbiCopilot\launcher"
    
    if (Test-Path $cacheDir) {
        Copy-Item $distFile (Join-Path $cacheDir "pbi_copilot_assistant.ps1") -Force
        Copy-Item $manifestFile (Join-Path $cacheDir "manifest.json") -Force
    }
    if (Test-Path $launchDir) {
        Copy-Item $distFile (Join-Path $launchDir "pbi_copilot_assistant.ps1") -Force
        Copy-Item $manifestFile (Join-Path $launchDir "manifest.json") -Force
        if (Test-Path $distLauncher) {
            Copy-Item $distLauncher (Join-Path $launchDir "launch_copilot.ps1") -Force
        }
    }
    Write-Host "✔ Entorno local (%LOCALAPPDATA%) sincronizado con las versiones protegidas." -ForegroundColor Green
}

Write-Host "`n[COMPLETADO] Doble capa de protección (Lanzador + Artefacto Azure) generada exitosamente.`n" -ForegroundColor Green
