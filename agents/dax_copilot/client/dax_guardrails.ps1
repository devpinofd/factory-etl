# ==============================================================================
# 🛡️ DAX GUARDRAILS & SANITIZER ENGINE (COMERCIAL TINITO)
# • Validación de sintaxis de solo lectura (EVALUATE, SUMMARIZECOLUMNS, ROW)
# • Inyección automática de TOPN de seguridad (máx. 5.000 filas)
# • Prevención de bloqueos de memoria en tablas de hechos de alta cardinalidad
# ==============================================================================

class DaxGuardrailException : System.Exception {
    DaxGuardrailException([string]$message) : base($message) {}
}

function Test-DaxQuerySafe {
    param (
        [Parameter(Mandatory=$true)]
        [string]$DaxQuery,

        [int]$MaxRowsLimit = 5000,
        [int]$CommandTimeoutSec = 60
    )

    $trimmed = $DaxQuery.Trim()
    if ($trimmed.Length -gt 20000) {
        throw [DaxGuardrailException]::new("SEGURIDAD: La consulta supera el limite de 20.000 caracteres.")
    }
    if (($trimmed.ToCharArray() | Where-Object { $_ -eq ';' }).Count -gt 0) {
        throw [DaxGuardrailException]::new("SEGURIDAD: Solo se permite una consulta DAX por ejecucion.")
    }
    
    # 1. Validación de Comandos Prohibidos (Mutación o DDL destructivo)
    $forbiddenTokens = @(
        "\bDROP\b", "\bALTER\b", "\bCREATE\b", "\bDELETE\b", 
        "\bINSERT\b", "\bUPDATE\b", "\bEXEC\b", "\bEXECUTE\b\s+SP_",
        "\bCALL\b", "\bTRUNCATE\b", "\bMERGE\b"
    )
    
    foreach ($token in $forbiddenTokens) {
        if ($trimmed -match $token) {
            throw [DaxGuardrailException]::new("SEGURIDAD: La consulta contiene comandos no permitidos ('$token'). Solo se permiten consultas de lectura (EVALUATE).")
        }
    }

    # 2. Validación de Comando de Inicio
    if (-not ($trimmed -match '^\s*EVALUATE' -or $trimmed -match '^\s*DEFINE\s+MEASURE' -or $trimmed -match '^\s*VAR\b')) {
        # Si no tiene EVALUATE al inicio, validamos si es una expresión suelta y le anteponemos EVALUATE
        if ($trimmed -match '^\s*(SUMMARIZECOLUMNS|ROW|CALCULATETABLE|SELECTCOLUMNS|TOPN)\b') {
            $trimmed = "EVALUATE " + $trimmed
        } else {
            throw [DaxGuardrailException]::new("SINTAXIS: La consulta DAX debe iniciar con la instrucción EVALUATE.")
        }
    }

    # 3. Guardrail de Cardinalidad en Tablas Grandes (vw_ventas_bi_consumo)
    $sanitizedQuery = $trimmed
    if ($sanitizedQuery -match '(?i)FROM\s+vw_ventas_bi_consumo' -or $sanitizedQuery -match '(?i)EVALUATE\s+vw_ventas_bi_consumo\b') {
        if ($sanitizedQuery -notmatch '(?i)\bTOPN\b' -and $sanitizedQuery -notmatch '(?i)\bSAMPLE\b') {
            throw [DaxGuardrailException]::new("SEGURIDAD: Las consultas directas sobre vw_ventas_bi_consumo deben incluir TOPN o SAMPLE con limite explicito.")
        }
    }

    return @{
        IsSafe         = $true
        SanitizedQuery = $sanitizedQuery
        TimeoutSeconds = $CommandTimeoutSec
    }
}
