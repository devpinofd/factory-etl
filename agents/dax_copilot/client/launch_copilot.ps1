# ==============================================================================
# 🚀 LANZADOR SEGURO ZERO-TOUCH - COMERCIAL TINITO DAX COPILOT
# • Verificación de Integridad Criptográfica (SHA-256)
# • Resiliencia Offline con Caché Local
# • Ejecución Desacoplada sin Almacenar Credenciales
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$cacheDir = "$env:LOCALAPPDATA\Tinito\PbiCopilot\cache"
if (-not (Test-Path $cacheDir)) { New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null }

$localCachedScript = Join-Path $cacheDir "pbi_copilot_assistant.ps1"
$scriptUrl   = if ($env:DAX_COPILOT_SCRIPT_URL) { $env:DAX_COPILOT_SCRIPT_URL } else { "https://stpbicopilotprod.blob.core.windows.net/agent/pbi_copilot_assistant.ps1" }
$manifestUrl = if ($env:DAX_COPILOT_MANIFEST_URL) { $env:DAX_COPILOT_MANIFEST_URL } else { "https://stpbicopilotprod.blob.core.windows.net/agent/manifest.json" }

# LAN Fallback Path (opcional si se define explícitamente)
$lanScriptPath = $env:DAX_COPILOT_LAN_SCRIPT_PATH
$lanManifestPath = $env:DAX_COPILOT_LAN_MANIFEST_PATH
if (-not $lanScriptPath) {
    $protectedCandidate = Join-Path $PSScriptRoot "pbi_copilot_assistant.protected.ps1"
    $regularCandidate   = Join-Path $PSScriptRoot "pbi_copilot_assistant.ps1"
    $bundledScript = if (Test-Path $protectedCandidate) { $protectedCandidate } elseif (Test-Path $regularCandidate) { $regularCandidate } else { $null }
    $bundledManifest = Join-Path $PSScriptRoot "manifest.json"
    if ($bundledScript -and (Test-Path $bundledManifest)) {
        $lanScriptPath = $bundledScript
        $lanManifestPath = $bundledManifest
    }
}
if ($lanScriptPath -and -not $lanManifestPath) {
    $candidateManifest = Join-Path (Split-Path $lanScriptPath -Parent) "manifest.json"
    if (Test-Path $candidateManifest) {
        $lanManifestPath = $candidateManifest
    }
}
$adminContact = if ($env:DAX_COPILOT_ADMIN_CONTACT) {
    $env:DAX_COPILOT_ADMIN_CONTACT
} else {
    "el administrador de BI (francisco.pino@tinitot.com)"
}

Write-Host "Iniciando Tinito DAX Copilot..." -ForegroundColor Cyan

$scriptToRun = $null
$isOnline = $false

# 1. Intentar actualizar desde LAN o Azure si hay conectividad
function Test-ScriptSignature {
    param([string]$Path, $Manifest)
    if ($Manifest.signed -eq $true) {
        $sig = Get-AuthenticodeSignature -FilePath $Path
        if ($sig.Status -ne "Valid") {
            Write-Host "⚠ Firma Authenticode inválida o ausente: $($sig.Status)" -ForegroundColor Yellow
            return $false
        }
        if ($Manifest.signing_certificate_subject -and
            $sig.SignerCertificate.Subject -ne $Manifest.signing_certificate_subject) {
            Write-Host "⚠ Certificado de firma no coincide con el manifest." -ForegroundColor Yellow
            return $false
        }
        Write-Host "✔ Firma Authenticode válida: $($sig.SignerCertificate.Subject)" -ForegroundColor Green
    }
    return $true
}

if ($lanScriptPath -and (Test-Path $lanScriptPath)) {
    if (-not (Test-Path $lanManifestPath)) {
        Write-Host "⚠ La ruta LAN no tiene manifest; se descarta por seguridad." -ForegroundColor Yellow
    } else {
        $lanManifest = Get-Content $lanManifestPath -Raw | ConvertFrom-Json
        $lanHash = (Get-FileHash -Path $lanScriptPath -Algorithm SHA256).Hash
        
        # Si el hash no coincide con el archivo apuntado, probar si existe pbi_copilot_assistant.protected.ps1 hermano
        if ($lanManifest.sha256 -and ($lanHash.ToUpper() -ne $lanManifest.sha256.ToUpper())) {
            $siblingProtected = Join-Path (Split-Path $lanScriptPath -Parent) "pbi_copilot_assistant.protected.ps1"
            if (Test-Path $siblingProtected) {
                $pHash = (Get-FileHash -Path $siblingProtected -Algorithm SHA256).Hash
                if ($pHash.ToUpper() -eq $lanManifest.sha256.ToUpper()) {
                    $lanScriptPath = $siblingProtected
                    $lanHash = $pHash
                }
            }
        }

        if ($lanManifest.sha256 -and ($lanHash.ToUpper() -eq $lanManifest.sha256.ToUpper()) `
                -and (Test-ScriptSignature -Path $lanScriptPath -Manifest $lanManifest)) {
            Write-Host "✔ Repositorio detectado e integridad SHA-256 verificada." -ForegroundColor Green
            $scriptToRun = $lanScriptPath
            Copy-Item $lanScriptPath $localCachedScript -Force -ErrorAction SilentlyContinue
            $isOnline = $true
        } else {
            Write-Host "⚠ Discrepancia de checksum o firma en la ruta LAN. Se descarta la versión." -ForegroundColor Yellow
        }
    }
} else {
    try {
        # Intento de verificación contra Azure Storage / HTTPS
        $webClient = New-Object System.Net.WebClient
        $webClient.Encoding = [System.Text.Encoding]::UTF8
        
        # Descargar manifiesto con timeout corto (3 segundos)
        $manifestJson = $webClient.DownloadString($manifestUrl)
        $manifest = $manifestJson | ConvertFrom-Json
        
        $tempDownload = Join-Path $cacheDir "temp_download.ps1"
        $webClient.DownloadFile($scriptUrl, $tempDownload)
        
        # 2. Validación de Hash SHA-256
        $downloadedHash = (Get-FileHash -Path $tempDownload -Algorithm SHA256).Hash
        
        if ($manifest.sha256 -and ($downloadedHash.ToUpper() -eq $manifest.sha256.ToUpper()) `
                -and (Test-ScriptSignature -Path $tempDownload -Manifest $manifest)) {
            Write-Host "✔ Integridad SHA-256 verificada con éxito (Versión $($manifest.version))." -ForegroundColor Green
            Move-Item $tempDownload $localCachedScript -Force
            $scriptToRun = $localCachedScript
            $isOnline = $true
        } else {
            Write-Host "⚠ Advertencia: Discrepancia en checksum o firma. Descartando descarga por seguridad." -ForegroundColor Yellow
            Remove-Item $tempDownload -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # Fallo de red silencioso para activar fallback
    }
}

# 3. Fallback a Copia Local Cacheada si está Offline
if (-not $scriptToRun) {
    if (Test-Path $localCachedScript) {
        Write-Host "ℹ Modo Offline: Utilizando versión local cacheada previamente verificada." -ForegroundColor Yellow
        $scriptToRun = $localCachedScript
    }
}

# 4. Ejecución Segura
if ($scriptToRun -and (Test-Path $scriptToRun)) {
    & $scriptToRun
} else {
    Write-Host "❌ Error crítico: No se encontró ninguna versión válida del agente DAX Copilot." -ForegroundColor Red
    Write-Host "Verifica tu conexión o contacta a $adminContact." -ForegroundColor White
    Read-Host "Presiona Enter para salir..."
}
