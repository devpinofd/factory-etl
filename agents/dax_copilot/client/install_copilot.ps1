param (
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string]$ProxyUrl,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^api://')]
    [string]$Audience,

    [Parameter(Mandatory = $false)]
    [string]$Scope = "access_as_user",

    [Parameter(Mandatory = $false)]
    [string]$ClientId,

    [Parameter(Mandatory = $false)]
    [string]$TenantId,

    [Parameter(Mandatory = $false)]
    [ValidatePattern('^https://')]
    [string]$ScriptUrl,

    [Parameter(Mandatory = $false)]
    [ValidatePattern('^https://')]
    [string]$ManifestUrl,

    [Parameter(Mandatory = $false)]
    [string]$LanScriptPath,

    [Parameter(Mandatory = $false)]
    [string]$LanManifestPath,

    [Parameter(Mandatory = $false)]
    [string]$AdminContact = "el administrador de BI"
)

if ((-not $ScriptUrl -or -not $ManifestUrl) -and (-not $LanScriptPath -or -not $LanManifestPath)) {
    throw "Configura ScriptUrl y ManifestUrl, o bien LanScriptPath y LanManifestPath."
}

if (-not $ClientId) {
    $ClientId = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
}
if (-not $TenantId -and $Audience -match 'api://([0-9a-fA-F\-]{36})') {
    $TenantId = $Matches[1]
}
if (-not $TenantId) {
    $TenantId = "e9545efd-83a8-4b56-a297-1c05c7d1f51b"
}

$scriptDir = if (![string]::IsNullOrEmpty($PSScriptRoot)) { 
    $PSScriptRoot 
} elseif ($MyInvocation.MyCommand.Path) { 
    Split-Path -Parent $MyInvocation.MyCommand.Path 
} else { 
    (Get-Location).Path 
}

$installDir = Join-Path $env:LOCALAPPDATA "Tinito\PbiCopilot\launcher"
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item (Join-Path $scriptDir "launch_copilot.ps1") (Join-Path $installDir "launch_copilot.ps1") -Force
Copy-Item (Join-Path $scriptDir "launch_copilot.bat") (Join-Path $installDir "launch_copilot.bat") -Force
if (Test-Path (Join-Path $scriptDir "msal_auth.ps1")) {
    Copy-Item (Join-Path $scriptDir "msal_auth.ps1") (Join-Path $installDir "msal_auth.ps1") -Force
}
if (Test-Path (Join-Path $scriptDir "dax_guardrails.ps1")) {
    Copy-Item (Join-Path $scriptDir "dax_guardrails.ps1") (Join-Path $installDir "dax_guardrails.ps1") -Force
}

[Environment]::SetEnvironmentVariable("DAX_COPILOT_PROXY_URL", $ProxyUrl, "User")
[Environment]::SetEnvironmentVariable("DAX_COPILOT_AUDIENCE", $Audience, "User")
[Environment]::SetEnvironmentVariable("DAX_COPILOT_SCOPE", $Scope, "User")
if ($ClientId) { [Environment]::SetEnvironmentVariable("DAX_COPILOT_CLIENT_ID", $ClientId, "User") }
if ($TenantId) { [Environment]::SetEnvironmentVariable("DAX_COPILOT_TENANT_ID", $TenantId, "User") }
[Environment]::SetEnvironmentVariable("DAX_COPILOT_SCRIPT_URL", $ScriptUrl, "User")
[Environment]::SetEnvironmentVariable("DAX_COPILOT_MANIFEST_URL", $ManifestUrl, "User")
if (-not $LanManifestPath -and $LanScriptPath) {
    $candidateManifest = Join-Path (Split-Path $LanScriptPath -Parent) "manifest.json"
    if (Test-Path $candidateManifest) {
        $LanManifestPath = $candidateManifest
    }
}

[Environment]::SetEnvironmentVariable("DAX_COPILOT_LAN_SCRIPT_PATH", $LanScriptPath, "User")
[Environment]::SetEnvironmentVariable("DAX_COPILOT_LAN_MANIFEST_PATH", $LanManifestPath, "User")
[Environment]::SetEnvironmentVariable("DAX_COPILOT_ADMIN_CONTACT", $AdminContact, "User")

Write-Host "Tinito DAX Copilot instalado para el usuario actual." -ForegroundColor Green
Write-Host "Ejecuta '$installDir\launch_copilot.bat' para iniciar el agente con tu cuenta corporativa de Microsoft 365." -ForegroundColor Cyan
