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

    # 3. Cargar ensamblados en el dominio de la aplicación
    if (Test-Path $absDll) {
        Unblock-File -Path $absDll -ErrorAction SilentlyContinue
        [System.Reflection.Assembly]::LoadFrom($absDll) | Out-Null
    }
    if (Test-Path $msalDll) {
        Unblock-File -Path $msalDll -ErrorAction SilentlyContinue
        [System.Reflection.Assembly]::LoadFrom($msalDll) | Out-Null
    }

    # 4. Compilar Helper C# Nativo para ejecución async thread-safe (sin ScriptBlock Runspace issues)
    if (-not ([System.Management.Automation.PSTypeName]'Tinito.Auth.MsalNativeHelper').Type) {
        $csharpCode = @"
using System;
using System.IO;
using System.Security.Cryptography;
using System.Threading.Tasks;
using System.Collections.Generic;
using Microsoft.Identity.Client;

namespace Tinito.Auth
{
    public static class MsalNativeHelper
    {
        public static void ConfigureTokenCache(IPublicClientApplication app, string cacheFilePath)
        {
            app.UserTokenCache.SetBeforeAccess(args =>
            {
                if (File.Exists(cacheFilePath))
                {
                    try
                    {
                        byte[] encrypted = File.ReadAllBytes(cacheFilePath);
                        if (encrypted != null && encrypted.Length > 0)
                        {
                            byte[] decrypted = ProtectedData.Unprotect(encrypted, null, DataProtectionScope.CurrentUser);
                            args.TokenCache.DeserializeMsalV3(decrypted);
                        }
                    }
                    catch { }
                }
            });

            app.UserTokenCache.SetAfterAccess(args =>
            {
                if (args.HasStateChanged)
                {
                    try
                    {
                        byte[] bytes = args.TokenCache.SerializeMsalV3();
                        byte[] encrypted = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
                        string dir = Path.GetDirectoryName(cacheFilePath);
                        if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                        {
                            Directory.CreateDirectory(dir);
                        }
                        File.WriteAllBytes(cacheFilePath, encrypted);
                    }
                    catch { }
                }
            });
        }

        public static string AcquireToken(IPublicClientApplication app, IEnumerable<string> scopes)
        {
            // 1. Silent Acquisition from DPAPI cache
            try
            {
                var accounts = app.GetAccountsAsync().ConfigureAwait(false).GetAwaiter().GetResult();
                var first = System.Linq.Enumerable.FirstOrDefault(accounts);
                if (first != null)
                {
                    var silent = app.AcquireTokenSilent(scopes, first).ExecuteAsync().ConfigureAwait(false).GetAwaiter().GetResult();
                    if (silent != null && !string.IsNullOrEmpty(silent.AccessToken))
                    {
                        return silent.AccessToken;
                    }
                }
            }
            catch { }

            // 2. Interactive Browser Acquisition
            try
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("\n[*] Autenticando con cuenta corporativa Microsoft 365 (Power BI Pro)...");
                Console.ForegroundColor = ConsoleColor.Gray;
                Console.WriteLine("    Selecciona tu cuenta corporativa en la ventana emergente.");
                Console.ResetColor();

                var interactive = app.AcquireTokenInteractive(scopes)
                    .WithPrompt(Prompt.SelectAccount)
                    .ExecuteAsync().ConfigureAwait(false).GetAwaiter().GetResult();

                if (interactive != null && !string.IsNullOrEmpty(interactive.AccessToken))
                {
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("[OK] Autenticado exitosamente como: " + interactive.Account.Username);
                    Console.ResetColor();
                    return interactive.AccessToken;
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.DarkYellow;
                Console.WriteLine("Fallo inicio de sesion interactivo por navegador: " + ex.Message);
                Console.ResetColor();
            }

            // 3. Fallback to Device Code Flow
            try
            {
                Console.ForegroundColor = ConsoleColor.Cyan;
                Console.WriteLine("\n[*] Iniciando flujo de autenticación por código de dispositivo (Device Code)...");
                Console.ResetColor();

                var deviceResult = app.AcquireTokenWithDeviceCode(scopes, dcr =>
                {
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine("\n========================================================");
                    Console.ForegroundColor = ConsoleColor.Cyan;
                    Console.WriteLine(" INICIO DE SESIÓN REQUERIDO: ");
                    Console.ResetColor();
                    Console.Write(" 1. Abre tu navegador en: ");
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine(dcr.VerificationUrl);
                    Console.ResetColor();
                    Console.Write(" 2. Ingresa el código:    ");
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine(dcr.UserCode);
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine("========================================================\n");
                    Console.ResetColor();
                    return Task.FromResult<object>(null);
                }).ExecuteAsync().ConfigureAwait(false).GetAwaiter().GetResult();

                if (deviceResult != null && !string.IsNullOrEmpty(deviceResult.AccessToken))
                {
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("[OK] Autenticado exitosamente como: " + deviceResult.Account.Username);
                    Console.ResetColor();
                    return deviceResult.AccessToken;
                }
            }
            catch (Exception devEx)
            {
                throw new InvalidOperationException("No se pudo completar la autenticacion Entra ID: " + devEx.Message, devEx);
            }

            throw new InvalidOperationException("No se pudo obtener un token de acceso valido de Microsoft Entra ID.");
        }
    }
}
"@
        Add-Type -TypeDefinition $csharpCode -ReferencedAssemblies @("System.Security", "System.Core", $msalDll, $absDll) -ErrorAction SilentlyContinue
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
    $cacheFile = if ($CacheFilePath) { $CacheFilePath } else { "$env:LOCALAPPDATA\Tinito\PbiCopilot\cache\msal_token_cache.bin" }
    [Tinito.Auth.MsalNativeHelper]::ConfigureTokenCache($app, $cacheFile)

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
    return [Tinito.Auth.MsalNativeHelper]::AcquireToken($app, [string[]]$Scopes)
}
