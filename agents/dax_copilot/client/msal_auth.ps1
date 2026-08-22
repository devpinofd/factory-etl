# ==============================================================================
# 🔐 MODULO DE AUTENTICACION NATIVA MICROSOFT ENTRA ID / M365 (MSAL.NET)
# Comercial Tinito - Agente Determinista DAX Copilot
# Permite autenticación Single Sign-On (SSO) con la misma cuenta de Power BI Pro / M365
# ==============================================================================

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.Security -ErrorAction SilentlyContinue

$script:GlobalMsalClient = $null
$script:MsalInitialized = $false

function Initialize-MsalAssemblies {
    [CmdletBinding()]
    param (
        [string]$LibsDirectory = "$env:LOCALAPPDATA\Tinito\PbiCopilot\libs\msal"
    )

    if ($script:MsalInitialized -and [Microsoft.Identity.Client.PublicClientApplicationBuilder]) {
        return $true
    }

    if (-not (Test-Path $LibsDirectory)) {
        New-Item -ItemType Directory -Path $LibsDirectory -Force | Out-Null
    }

    $absDll = Join-Path $LibsDirectory "Microsoft.IdentityModel.Abstractions.dll"
    $msalDll = Join-Path $LibsDirectory "Microsoft.Identity.Client.dll"

    # 1. Asegurar dependencia Microsoft.IdentityModel.Abstractions (v6.35.0)
    if (-not (Test-Path $absDll)) {
        try {
            Write-Host "[*] Descargando componentes de autenticación Entra ID (Abstractions)..." -ForegroundColor Cyan
            $absZip = Join-Path $LibsDirectory "abs.zip"
            $wc = New-Object System.Net.WebClient
            $wc.DownloadFile("https://www.nuget.org/api/v2/package/Microsoft.IdentityModel.Abstractions/6.35.0", $absZip)
            $absExtractDir = Join-Path $LibsDirectory "abs_extracted"
            Expand-Archive -Path $absZip -DestinationPath $absExtractDir -Force
            $foundAbs = Get-ChildItem -Path $absExtractDir -Filter "Microsoft.IdentityModel.Abstractions.dll" -Recurse | Where-Object { $_.FullName -like "*net462*" -or $_.FullName -like "*net472*" -or $_.FullName -like "*netstandard2.0*" } | Select-Object -First 1
            if (-not $foundAbs) {
                $foundAbs = Get-ChildItem -Path $absExtractDir -Filter "Microsoft.IdentityModel.Abstractions.dll" -Recurse | Select-Object -First 1
            }
            if ($foundAbs) {
                Copy-Item $foundAbs.FullName $absDll -Force
            }
            Remove-Item $absExtractDir -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item $absZip -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Warning "No se pudo descargar Microsoft.IdentityModel.Abstractions: $($_.Exception.Message)"
        }
    }

    # 2. Asegurar Microsoft.Identity.Client (MSAL.NET v4.61.3)
    if (-not (Test-Path $msalDll)) {
        try {
            Write-Host "[*] Descargando componentes de autenticación Entra ID (MSAL.NET)..." -ForegroundColor Cyan
            $msalZip = Join-Path $LibsDirectory "msal.zip"
            $wc = New-Object System.Net.WebClient
            $wc.DownloadFile("https://www.nuget.org/api/v2/package/Microsoft.Identity.Client/4.61.3", $msalZip)
            $msalExtractDir = Join-Path $LibsDirectory "msal_extracted"
            Expand-Archive -Path $msalZip -DestinationPath $msalExtractDir -Force
            $foundMsal = Get-ChildItem -Path $msalExtractDir -Filter "Microsoft.Identity.Client.dll" -Recurse | Where-Object { $_.FullName -like "*net462*" -or $_.FullName -like "*net472*" -or $_.FullName -like "*netstandard2.0*" } | Select-Object -First 1
            if (-not $foundMsal) {
                $foundMsal = Get-ChildItem -Path $msalExtractDir -Filter "Microsoft.Identity.Client.dll" -Recurse | Select-Object -First 1
            }
            if ($foundMsal) {
                Copy-Item $foundMsal.FullName $msalDll -Force
            }
            Remove-Item $msalExtractDir -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item $msalZip -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Warning "No se pudo descargar Microsoft.Identity.Client: $($_.Exception.Message)"
        }
    }

    # 3. Registrar resolvedor dinamico de ensamblados anti-recursion para AppDomain
    if (-not $script:AssemblyResolverRegistered) {
        $script:ResolveInProgress = $false
        [AppDomain]::CurrentDomain.add_AssemblyResolve({
            param($sender, $resolveArgs)
            if ($script:ResolveInProgress) { return $null }
            $script:ResolveInProgress = $true
            try {
                $assemblyName = ($resolveArgs.Name -split ',')[0].Trim()
                $candidate = [System.IO.Path]::Combine($LibsDirectory, "$assemblyName.dll")
                if ([System.IO.File]::Exists($candidate)) {
                    return [System.Reflection.Assembly]::LoadFrom($candidate)
                }
                return $null
            } finally {
                $script:ResolveInProgress = $false
            }
        })
        $script:AssemblyResolverRegistered = $true
    }

    # 4. Cargar ensamblados en el dominio de la aplicación
    if (Test-Path $absDll) {
        Unblock-File -Path $absDll -ErrorAction SilentlyContinue
        [System.Reflection.Assembly]::LoadFrom($absDll) | Out-Null
    }
    if (Test-Path $msalDll) {
        Unblock-File -Path $msalDll -ErrorAction SilentlyContinue
        [System.Reflection.Assembly]::LoadFrom($msalDll) | Out-Null
    }

    $script:MsalInitialized = ([Microsoft.Identity.Client.PublicClientApplicationBuilder] -ne $null)
    return $script:MsalInitialized
}

function Get-MsalPublicClient {
    [CmdletBinding()]
    param (
        [string]$ClientId,
        [string]$TenantId,
        [string]$CacheFilePath = "$env:LOCALAPPDATA\Tinito\PbiCopilot\cache\msal_token_cache.bin"
    )

    if ($script:GlobalMsalClient) {
        return $script:GlobalMsalClient
    }

    $initialized = Initialize-MsalAssemblies
    if (-not $initialized) {
        throw "No se pudieron inicializar los ensamblados de MSAL.NET."
    }

    $authority = "https://login.microsoftonline.com/$TenantId"
    
    $builder = [Microsoft.Identity.Client.PublicClientApplicationBuilder]::Create($ClientId)
    $builder = $builder.WithAuthority($authority)
    $builder = $builder.WithRedirectUri("http://localhost")
    
    $app = $builder.Build()

    # Configuración de Token Cache persistente con cifrado DPAPI (CurrentUser)
    $script:MsalTokenCacheFile = if ($CacheFilePath) { $CacheFilePath } else { "$env:LOCALAPPDATA\Tinito\PbiCopilot\cache\msal_token_cache.bin" }

    [Microsoft.Identity.Client.TokenCacheCallback]$beforeAccess = {
        param($args)
        $cacheFile = $script:MsalTokenCacheFile
        if ([System.IO.File]::Exists($cacheFile)) {
            try {
                $encrypted = [System.IO.File]::ReadAllBytes($cacheFile)
                if ($encrypted -and $encrypted.Length -gt 0) {
                    $decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect(
                        $encrypted,
                        $null,
                        [System.Security.Cryptography.DataProtectionScope]::CurrentUser
                    )
                    $args.TokenCache.DeserializeMsalV3($decrypted)
                }
            } catch { }
        }
    }

    [Microsoft.Identity.Client.TokenCacheCallback]$afterAccess = {
        param($args)
        if ($args.HasStateChanged) {
            try {
                $cacheFile = $script:MsalTokenCacheFile
                $bytes = $args.TokenCache.SerializeMsalV3()
                $encrypted = [System.Security.Cryptography.ProtectedData]::Protect(
                    $bytes,
                    $null,
                    [System.Security.Cryptography.DataProtectionScope]::CurrentUser
                )
                $dir = [System.IO.Path]::GetDirectoryName($cacheFile)
                if (-not [System.IO.Directory]::Exists($dir)) {
                    [System.IO.Directory]::CreateDirectory($dir) | Out-Null
                }
                [System.IO.File]::WriteAllBytes($cacheFile, $encrypted)
            } catch { }
        }
    }

    $app.UserTokenCache.SetBeforeAccess($beforeAccess)
    $app.UserTokenCache.SetAfterAccess($afterAccess)

    $script:GlobalMsalClient = $app
    return $app
}

function Get-EntraAccessToken {
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [string]$ClientId,

        [Parameter(Mandatory = $true)]
        [string]$TenantId,

        [Parameter(Mandatory = $true)]
        [string[]]$Scopes,

        [Parameter(Mandatory = $false)]
        [string]$Audience
    )

    $app = Get-MsalPublicClient -ClientId $ClientId -TenantId $TenantId

    # Paso 1: Intentar adquisición silenciosa (Cache DPAPI / SSO)
    try {
        $accounts = $app.GetAccountsAsync().GetAwaiter().GetResult()
        if ($accounts -and ($accounts | Measure-Object).Count -gt 0) {
            $account = $accounts | Select-Object -First 1
            $silentResult = $app.AcquireTokenSilent($Scopes, $account).ExecuteAsync().GetAwaiter().GetResult()
            if ($silentResult -and $silentResult.AccessToken) {
                return $silentResult.AccessToken
            }
        }
    } catch [Microsoft.Identity.Client.MsalUiRequiredException] {
        # Se requiere interacción de usuario
    } catch {
        # Otro error en silent acquire, proceder a interactivo
    }

    # Paso 2: Adquisición interactiva (Navegador del sistema / SSO de Microsoft 365)
    Write-Host "`n[*] Autenticando con cuenta corporativa Microsoft 365 (Power BI Pro)..." -ForegroundColor Yellow
    Write-Host "    Selecciona tu cuenta corporativa en la ventana emergente." -ForegroundColor Gray

    try {
        $interactiveBuilder = $app.AcquireTokenInteractive($Scopes)
        $interactiveBuilder = $interactiveBuilder.WithPrompt([Microsoft.Identity.Client.Prompt]::SelectAccount)
        
        $authResult = $interactiveBuilder.ExecuteAsync().GetAwaiter().GetResult()
        if ($authResult -and $authResult.AccessToken) {
            Write-Host "[OK] Autenticado exitosamente como: $($authResult.Account.Username)" -ForegroundColor Green
            return $authResult.AccessToken
        }
    } catch {
        Write-Warning "Fallo el inicio de sesión interactivo por navegador: $($_.Exception.Message)"
        
        # Paso 3: Fallback a Device Code Flow (para entornos con consola restringida o sin GUI)
        try {
            Write-Host "`n[*] Iniciando flujo de autenticación por código de dispositivo (Device Code)..." -ForegroundColor Cyan
            
            $deviceCodeTask = $app.AcquireTokenWithDeviceCode($Scopes, [System.Func[Microsoft.Identity.Client.DeviceCodeResult, System.Threading.Tasks.Task]]{
                param($deviceCode)
                Write-Host "`n========================================================" -ForegroundColor Yellow
                Write-Host " INICIO DE SESION REQUERIDO: " -ForegroundColor Cyan
                Write-Host " 1. Abre tu navegador en: " -NoNewline; Write-Host $deviceCode.VerificationUrl -ForegroundColor Green
                Write-Host " 2. Ingresa el código:    " -NoNewline; Write-Host $deviceCode.UserCode -ForegroundColor Yellow
                Write-Host "========================================================`n" -ForegroundColor Yellow
                return [System.Threading.Tasks.Task]::FromResult($null)
            }).ExecuteAsync().GetAwaiter().GetResult()

            if ($deviceCodeTask -and $deviceCodeTask.AccessToken) {
                Write-Host "[OK] Autenticado exitosamente como: $($deviceCodeTask.Account.Username)" -ForegroundColor Green
                return $deviceCodeTask.AccessToken
            }
        } catch {
            throw "No se pudo completar la autenticación con Microsoft Entra ID: $($_.Exception.Message)"
        }
    }

    throw "No se pudo obtener un token de acceso válido de Microsoft Entra ID."
}
