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

$installDir = Join-Path $env:LOCALAPPDATA "Tinito\PbiCopilot\launcher"
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item (Join-Path $PSScriptRoot "launch_copilot.ps1") (Join-Path $installDir "launch_copilot.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "launch_copilot.bat") (Join-Path $installDir "launch_copilot.bat") -Force

[Environment]::SetEnvironmentVariable("DAX_COPILOT_PROXY_URL", $ProxyUrl, "User")
[Environment]::SetEnvironmentVariable("DAX_COPILOT_AUDIENCE", $Audience, "User")
[Environment]::SetEnvironmentVariable("DAX_COPILOT_SCOPE", $Scope, "User")
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
Write-Host "Ejecuta '$installDir\launch_copilot.bat' despues de iniciar Azure CLI con 'az login'." -ForegroundColor Cyan
