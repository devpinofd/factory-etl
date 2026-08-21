# ==============================================================================
# 🧪 REGRESSION TEST SUITE RUNNER FOR DAX COPILOT (GOLDEN DATASET)
# ==============================================================================

import os
import json
import time
import subprocess

def find_active_pbi_port():
    ps_cmd = "Get-NetTCPConnection -State Listen | Where-Object { $_.OwningProcess -in (Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) -and $_.LocalPort -ne 2383 -and $_.LocalPort -ne 2382 } | Select-Object -ExpandProperty LocalPort -First 1"
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd], capture_output=True, text=True)
    out = res.stdout.strip()
    return int(out) if out.isdigit() else None

def execute_dax_via_powershell(dax_query, port):
    adomd_dll = r"C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.AnalysisServices.AdomdClient.dll"
    if not os.path.exists(adomd_dll):
        local_app = os.path.expandvars(r"%LOCALAPPDATA%\Tinito\PbiCopilot\libs\adomd\lib\net472\Microsoft.AnalysisServices.AdomdClient.dll")
        if os.path.exists(local_app):
            adomd_dll = local_app

    tom_dll = r"C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.AnalysisServices.Tabular.dll"
    if not os.path.exists(tom_dll):
        local_tom = os.path.expandvars(r"%LOCALAPPDATA%\Tinito\PbiCopilot\libs\extracted\lib\net472\Microsoft.AnalysisServices.Tabular.dll")
        if os.path.exists(local_tom):
            tom_dll = local_tom

    ps_code = f"""
    [System.Reflection.Assembly]::LoadFrom("{adomd_dll}") | Out-Null
    if (Test-Path "{tom_dll}") {{ [System.Reflection.Assembly]::LoadFrom("{tom_dll}") | Out-Null }}

    $dbName = ""
    try {{
        $srv = New-Object Microsoft.AnalysisServices.Tabular.Server
        $srv.Connect("localhost:{port}")
        if ($srv.Databases.Count -gt 0) {{ $dbName = $srv.Databases[0].Name }}
        $srv.Disconnect()
    }} catch {{ }}

    $connStr = "Provider=MSOLAP;Data Source=localhost:{port};Initial Catalog=$dbName;"
    $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection($connStr)
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = @'
{dax_query}
'@
    $cmd.CommandTimeout = 60
    $reader = $cmd.ExecuteReader()
    $table = New-Object System.Data.DataTable
    $table.Load($reader)
    $conn.Close()
    
    $results = @()
    foreach ($row in $table.Rows) {{
        $obj = [ordered]@{{}}
        foreach ($col in $table.Columns) {{
            $obj[$col.ColumnName] = $row[$col.ColumnName]
        }}
        $results += [PSCustomObject]$obj
    }}
    $results | ConvertTo-Json -Depth 5 -Compress
    """
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_code], capture_output=True, text=True, encoding="utf-8")
    return res.stdout.strip(), res.stderr.strip()

def run_suite():
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(curr_dir, "golden_dataset.json")
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        tests = json.load(f)
    
    port = find_active_pbi_port()
    if not port:
        print("❌ Error: No se detectó ninguna instancia dinámica de Power BI Desktop abierta.")
        return
    
    print(f"========================================================================")
    print(f"🧪 EJECUCIÓN DEL BANCO DE PRUEBAS DE REGRESIÓN (GOLDEN DATASET)")
    print(f"   Modelo: Comercial_Tinito_Semantico_PROD (localhost:{port})")
    print(f"   Total de Casos de Prueba: {len(tests)}")
    print(f"========================================================================")
    
    passed = 0
    failed = 0
    latencies = []
    
    for i, test in enumerate(tests, 1):
        tid = test.get("id")
        domain = test.get("dominio")
        query = test.get("dax_esperado")
        expected = test.get("resultado_esperado", {})
        criterion = test.get("criterio")
        
        t0 = time.time()
        out, err = execute_dax_via_powershell(query, port)
        duration_ms = int((time.time() - t0) * 1000)
        latencies.append(duration_ms)
        
        test_ok = False
        reason = ""
        
        if err or not out:
            test_ok = False
            reason = f"Error DAX: {err[:100]}"
        else:
            try:
                data = json.loads(out)
                if isinstance(data, list) and len(data) > 0:
                    row0 = data[0]
                elif isinstance(data, dict):
                    row0 = data
                else:
                    row0 = {}
                
                if criterion == "ExactNumeric":
                    col = expected.get("columna")
                    exp_val = expected.get("valor")
                    actual_val = row0.get(col)
                    if actual_val == exp_val:
                        test_ok = True
                    else:
                        reason = f"Esperado {exp_val}, obtenido {actual_val}"
                elif criterion == "NonZeroNumeric":
                    col = expected.get("columna")
                    actual_val = row0.get(col, 0)
                    if actual_val and float(actual_val) > 0:
                        test_ok = True
                    else:
                        reason = f"Valor {actual_val} no es mayor a 0"
                elif criterion == "PercentageRange":
                    col = expected.get("columna")
                    actual_val = float(row0.get(col, 0))
                    if 0.0 <= actual_val <= 1.0:
                        test_ok = True
                    else:
                        reason = f"Porcentaje {actual_val} fuera de rango [0, 1]"
                elif criterion == "RowCountExact":
                    cnt = len(data) if isinstance(data, list) else 1
                    exp_cnt = expected.get("min_filas")
                    if cnt == exp_cnt:
                        test_ok = True
                    else:
                        reason = f"Filas esperadas {exp_cnt}, obtenidas {cnt}"
                elif criterion == "RowCountMinimum":
                    cnt = len(data) if isinstance(data, list) else 1
                    exp_cnt = expected.get("min_filas", 1)
                    if cnt >= exp_cnt:
                        test_ok = True
                    else:
                        reason = f"Filas mínimas esperadas {exp_cnt}, obtenidas {cnt}"
                elif criterion == "NonNegativeNumeric":
                    col = expected.get("columna")
                    actual_val = row0.get(col, -1)
                    if actual_val is not None and float(actual_val) >= 0:
                        test_ok = True
                    else:
                        reason = f"Valor {actual_val} no es un número >= 0"
                else:
                    test_ok = True
            except Exception as ex:
                test_ok = False
                reason = f"Excepción parseando resultado: {str(ex)}"
        
        status_icon = "✔ PASS" if test_ok else "❌ FAIL"
        if test_ok:
            passed += 1
            print(f"[{status_icon}] {tid} ({domain}) - Latencia: {duration_ms}ms")
        else:
            failed += 1
            print(f"[{status_icon}] {tid} ({domain}) - Falló: {reason} (Latencia: {duration_ms}ms)")
    
    accuracy = (passed / len(tests)) * 100 if tests else 0
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
    
    print(f"\n========================================================================")
    print(f"📊 RESUMEN EJECUTIVO DE CALIDAD:")
    print(f"   Pruebas Exitosas:  {passed}/{len(tests)} ({accuracy:.1f}%)")
    print(f"   Pruebas Fallidas:  {failed}/{len(tests)}")
    print(f"   Latencia P95:      {p95} ms")
    print(f"   Estado de Calidad: {'✅ CERTIFICADO PARA PRODUCCIÓN' if failed == 0 else '⚠ REQUIERE REVISIÓN'}")
    print(f"========================================================================")

if __name__ == "__main__":
    run_suite()
