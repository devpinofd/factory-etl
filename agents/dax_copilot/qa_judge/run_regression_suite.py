# ==============================================================================
# 🧪 REGRESSION TEST SUITE RUNNER FOR DAX COPILOT (GOLDEN DATASET)
# ==============================================================================

import os
import json
import time
import subprocess
import argparse
import hashlib
import math
import re
import urllib.request
import urllib.error

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
    $results = @()
    while ($reader.Read()) {{
        $obj = [ordered]@{{}}
        for ($index = 0; $index -lt $reader.FieldCount; $index++) {{
            $value = $reader.GetValue($index)
            if ($value -is [System.DBNull]) {{ $value = $null }}
            $obj[$reader.GetName($index)] = $value
        }}
        $results += [PSCustomObject]$obj
    }}
    $reader.Close()
    $conn.Close()
    $results | ConvertTo-Json -Depth 5 -Compress
    """
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_code], capture_output=True, text=True, encoding="utf-8")
    return res.stdout.strip(), res.stderr.strip()


def get_model_metadata(port):
    ps_code = f"""
    [System.Reflection.Assembly]::LoadWithPartialName("Microsoft.AnalysisServices.Tabular") | Out-Null
    $srv = New-Object Microsoft.AnalysisServices.Tabular.Server
    $srv.Connect("localhost:{port}")
    if ($srv.Databases.Count -eq 0) {{ throw "No hay bases de datos en el modelo conectado." }}
    $db = $srv.Databases[0]
    [ordered]@{{
        name = $db.Name
        compatibility_level = $db.CompatibilityLevel
        table_count = $db.Model.Tables.Count
        measure_count = (($db.Model.Tables | ForEach-Object {{ $_.Measures.Count }} | Measure-Object -Sum).Sum)
    }} | ConvertTo-Json -Compress
    $srv.Disconnect()
    """
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_code],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Preflight del modelo falló: {result.stderr.strip()[:300]}")
    metadata = json.loads(result.stdout.strip())
    if not metadata.get("name"):
        raise RuntimeError("Preflight del modelo no devolvió identidad.")
    return metadata


def generate_dax_from_agent(question):
    proxy_url = os.getenv("DAX_COPILOT_PROXY_URL")
    token = os.getenv("DAX_COPILOT_AGENT_TOKEN")
    if not proxy_url or not token:
        raise RuntimeError(
            "agent-evaluation requiere DAX_COPILOT_PROXY_URL y "
            "DAX_COPILOT_AGENT_TOKEN, o --generated-dax-file."
        )
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "prompts",
        "system_prompt_v1.0.md",
    )
    with open(prompt_path, "r", encoding="utf-8-sig") as prompt_file:
        system_prompt = prompt_file.read()
    body = json.dumps(
        {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]
        }
    ).encode()
    request = urllib.request.Request(
        proxy_url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-correlation-id": f"qa-judge-{int(time.time() * 1000)}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Invocación del agente falló: {exc}") from exc
    for tool_call in payload.get("tool_calls", []):
        function = tool_call.get("function", {})
        if function.get("name") != "execute_dax_query":
            continue
        arguments = json.loads(function.get("arguments", "{}"))
        dax_query = arguments.get("dax_query")
        if dax_query:
            return dax_query
    raise RuntimeError("El agente no devolvió una tool call execute_dax_query.")

SUPPORTED_CRITERIA = {
    "ExactNumeric",
    "NonZeroNumeric",
    "PercentageRange",
    "RowCountExact",
    "RowCountMinimum",
    "NonNegativeNumeric",
    "ExpectedRejection",
}


def _numeric_value(row, column, allow_single_numeric_fallback=False):
    if column not in row:
        numeric_candidates = [
            value
            for value in row.values()
            if not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(float(value))
        ]
        if not allow_single_numeric_fallback or len(numeric_candidates) != 1:
            raise ValueError(f"Columna ausente: {column}")
        value = numeric_candidates[0]
    else:
        value = row[column]
    if value is None or isinstance(value, bool):
        raise ValueError(f"Valor no numérico en {column}: {value}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Valor no numérico en {column}: {value}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Valor no finito en {column}: {value}")
    return number


def evaluate_result(data, expected, criterion):
    if criterion not in SUPPORTED_CRITERIA:
        return False, f"Criterio no soportado: {criterion}"

    rows = data if isinstance(data, list) else [data]
    rows = [
        {
            key[1:-1] if key.startswith("[") and key.endswith("]") else key: value
            for key, value in row.items()
        }
        if isinstance(row, dict)
        else row
        for row in rows
    ]
    if not rows or not isinstance(rows[0], dict):
        return False, "Resultado vacío o con esquema inválido"
    row0 = rows[0]

    try:
        if criterion == "ExactNumeric":
            actual = _numeric_value(
                row0,
                expected["columna"],
                expected.get("allow_single_numeric_fallback", False),
            )
            target = float(expected["valor"])
            tolerance = float(expected.get("tolerancia", 0))
            relative_tolerance = float(expected.get("tolerancia_relativa", 0))
            allowed = max(tolerance, abs(target) * relative_tolerance)
            return (
                abs(actual - target) <= allowed,
                f"Esperado {target} +/- {allowed}, obtenido {actual}",
            )

        if criterion == "NonZeroNumeric":
            actual = _numeric_value(
                row0,
                expected["columna"],
                expected.get("allow_single_numeric_fallback", False),
            )
            minimum = float(expected.get("minimo", 0))
            valid = actual > minimum
            return valid, (
                f"Valor {actual} es mayor a {minimum}"
                if valid
                else f"Valor {actual} no es mayor a {minimum}"
            )

        if criterion == "PercentageRange":
            actual = _numeric_value(
                row0,
                expected["columna"],
                expected.get("allow_single_numeric_fallback", False),
            )
            lower, upper = expected.get("rango", [0.0, 1.0])
            valid = lower <= actual <= upper
            return valid, (
                f"Porcentaje {actual} dentro de [{lower}, {upper}]"
                if valid
                else f"Porcentaje {actual} fuera de [{lower}, {upper}]"
            )

        count = len(rows)
        if criterion == "RowCountExact":
            minimum = expected.get("min_filas")
            maximum = expected.get("max_filas", minimum)
            valid = (minimum is None or count >= minimum) and (maximum is None or count <= maximum)
            return valid, f"Filas esperadas entre {minimum} y {maximum}, obtenidas {count}"

        if criterion == "RowCountMinimum":
            minimum = expected.get("min_filas", 1)
            return count >= minimum, f"Filas mínimas esperadas {minimum}, obtenidas {count}"

        actual = _numeric_value(
            row0,
            expected["columna"],
            expected.get("allow_single_numeric_fallback", False),
        )
        valid = actual >= 0
        return valid, (
            f"Valor {actual} es un número >= 0"
            if valid
            else f"Valor {actual} no es un número >= 0"
        )
    except (KeyError, TypeError, ValueError) as exc:
        return False, str(exc)


def load_tests(dataset_path):
    with open(dataset_path, "r", encoding="utf-8-sig") as dataset_file:
        tests = json.load(dataset_file)
    if not isinstance(tests, list) or not tests:
        raise ValueError("El Golden Dataset debe ser una lista no vacía")
    ids = [test.get("id") for test in tests]
    if any(not test_id for test_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("El Golden Dataset contiene IDs ausentes o duplicados")
    for test in tests:
        criterion = test.get("criterio")
        if criterion not in SUPPORTED_CRITERIA:
            raise ValueError(f"Criterio no soportado en {test.get('id')}: {criterion}")
    return tests


def select_test_batch(tests, batch_size=None, batch_number=1):
    if batch_size is None:
        return tests
    if batch_size < 1:
        raise ValueError("--batch-size debe ser mayor a cero")
    if batch_number < 1:
        raise ValueError("--batch-number debe ser mayor a cero")
    batch_start = (batch_number - 1) * batch_size
    selected = tests[batch_start : batch_start + batch_size]
    if not selected:
        raise ValueError(
            f"El lote {batch_number} no contiene casos para un tamaño de {batch_size}"
        )
    return selected


def analyze_dax(query):
    normalized = query.upper()
    compact = re.sub(r"\s+", "", normalized)
    dates = {
        (int(year), int(month), int(day))
        for year, month, day in re.findall(
            r"DATE\s*\(\s*(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*\)",
            normalized,
        )
    }
    top_n_matches = re.findall(r"TOPN\s*\(\s*(\d+)", normalized)
    return {
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "dates": [f"{year:04d}-{month:02d}-{day:02d}" for year, month, day in sorted(dates)],
        "top_n": [int(value) for value in top_n_matches],
        "functions": sorted(
            function
            for function in (
                "CALCULATETABLE",
                "DATESBETWEEN",
                "FILTER",
                "ROW",
                "SUMMARIZECOLUMNS",
                "TOPN",
                "TREATAS",
            )
            if f"{function}(" in compact
        ),
    }


def _has_required_string_filter(query, column, value):
    escaped_column = re.escape(column)
    escaped_value = re.escape(value)
    treatas_pattern = (
        rf'TREATAS\s*\(\s*\{{\s*"{escaped_value}"\s*\}}\s*,'
        rf"\s*[^,\)]*\[{escaped_column}\]\s*\)"
    )
    equality_pattern = rf'\[{escaped_column}\]\s*=\s*"{escaped_value}"'
    return bool(
        re.search(treatas_pattern, query, re.IGNORECASE)
        or re.search(equality_pattern, query, re.IGNORECASE)
    )


def validate_query_contract(query, contract):
    if not contract:
        return True, ""
    normalized_query = query.upper()
    compact_query = re.sub(r"\s+", "", normalized_query)
    for fragment in contract.get("required_measures", []):
        if f"[{fragment.upper()}]" not in compact_query:
            return False, f"Medida requerida ausente: {fragment}"
    for fragment in contract.get("required_fragments", []):
        if re.sub(r"\s+", "", fragment.upper()) not in compact_query:
            return False, f"Fragmento requerido ausente: {fragment}"
    analysis = analyze_dax(query)
    available_dates = set(analysis["dates"])
    for required_date in contract.get("required_dates", []):
        if required_date not in available_dates:
            return False, f"Fecha requerida ausente: {required_date}"
    for required_year in contract.get("required_years", []):
        if not re.search(rf"\b{int(required_year)}\b", normalized_query):
            return False, f"Año requerido ausente: {required_year}"
    for column, value in contract.get("required_scope", {}).items():
        if not _has_required_string_filter(query, column, value):
            return False, f"Filtro de alcance requerido ausente: {column}={value}"
    expected_top_n = contract.get("top_n")
    if expected_top_n is not None and expected_top_n not in analysis["top_n"]:
        return False, f"Ranking TOPN requerido ausente: {expected_top_n}"
    for fragment in contract.get("forbidden_fragments", []):
        if re.sub(r"\s+", "", fragment.upper()) in compact_query:
            return False, f"Fragmento prohibido encontrado: {fragment}"
    return True, ""


def run_suite(
    mode="model-smoke",
    generated_dax_file=None,
    requested_port=None,
    dataset_name="golden_dataset.json",
    report_file=None,
    batch_size=None,
    batch_number=1,
):
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(curr_dir, dataset_name)
    tests = load_tests(dataset_path)
    total_dataset_tests = len(tests)
    tests = select_test_batch(tests, batch_size, batch_number)

    port = requested_port or find_active_pbi_port()
    if not port and any(test.get("criterio") != "ExpectedRejection" for test in tests):
        print("❌ Error: No se detectó ninguna instancia dinámica de Power BI Desktop abierta.")
        return 1

    generated = {}
    if mode == "agent-evaluation" and generated_dax_file:
        with open(generated_dax_file, "r", encoding="utf-8-sig") as generated_file:
            generated = json.load(generated_file)

    metadata = None
    if any(test.get("criterio") != "ExpectedRejection" for test in tests):
        metadata = get_model_metadata(port)
        expected_model = os.getenv("DAX_COPILOT_EXPECTED_MODEL")
        if expected_model and metadata["name"] != expected_model:
            raise RuntimeError(
                f"Modelo inesperado: esperado {expected_model}, conectado {metadata['name']}"
            )

    print(f"========================================================================")
    print(f"🧪 EJECUCIÓN DEL BANCO DE PRUEBAS ({mode})")
    model_name = metadata["name"] if metadata else "N/A"
    print(f"   Modelo: {model_name} (localhost:{port})")
    if metadata:
        print(
            f"   Compatibilidad: {metadata['compatibility_level']} | "
            f"Tablas: {metadata['table_count']} | Medidas: {metadata['measure_count']}"
        )
    print(f"   Total de Casos de Prueba: {len(tests)}")
    if batch_size is not None:
        print(
            f"   Lote: {batch_number} | Tamaño: {batch_size} | "
            f"Dataset completo: {total_dataset_tests}"
        )
    print(f"========================================================================")
    
    passed = 0
    failed = 0
    latencies = []
    report_cases = []

    def write_report_checkpoint():
        if not report_file:
            return
        checkpoint_passed = sum(case["status"] == "PASS" for case in report_cases)
        checkpoint_failed = sum(case["status"] == "FAIL" for case in report_cases)
        checkpoint_p95 = (
            sorted(case["duration_ms"] for case in report_cases)[
                int(len(report_cases) * 0.95)
            ]
            if report_cases
            else 0
        )
        report = {
            "mode": mode,
            "model": metadata,
            "batch": {
                "number": batch_number,
                "size": batch_size,
                "dataset_total": total_dataset_tests,
            },
            "summary": {
                "total": len(tests),
                "completed": len(report_cases),
                "passed": checkpoint_passed,
                "failed": checkpoint_failed,
                "accuracy": round(
                    checkpoint_passed / len(report_cases) * 100, 1
                )
                if report_cases
                else 0,
                "p95_ms": checkpoint_p95,
            },
            "cases": report_cases,
        }
        temporary_report = f"{report_file}.tmp"
        with open(temporary_report, "w", encoding="utf-8") as report_output:
            json.dump(report, report_output, ensure_ascii=False, indent=2)
        os.replace(temporary_report, report_file)
    
    for i, test in enumerate(tests, 1):
        case_started_at = time.time()
        tid = test.get("id")
        domain = test.get("dominio")
        reference_query = test.get("dax_referencia", test.get("dax_esperado"))
        if mode == "agent-evaluation":
            try:
                query = (
                    generated.get(tid)
                    if generated_dax_file
                    else generate_dax_from_agent(test["pregunta"])
                )
            except RuntimeError as exc:
                duration_ms = int((time.time() - case_started_at) * 1000)
                latencies.append(duration_ms)
                failed += 1
                print(
                    f"[❌ FAIL] {tid} ({domain}) - Falló: "
                    f"Generación del agente: {exc} (Latencia: {duration_ms}ms)"
                )
                report_cases.append(
                    {
                        "id": tid,
                        "status": "FAIL",
                        "category": "AGENT_GENERATION",
                        "reason": str(exc),
                        "duration_ms": duration_ms,
                    }
                )
                write_report_checkpoint()
                continue
            if not query:
                duration_ms = int((time.time() - case_started_at) * 1000)
                latencies.append(duration_ms)
                failed += 1
                print(
                    f"[❌ FAIL] {tid} ({domain}) - Falló: "
                    f"No hay DAX generado (Latencia: {duration_ms}ms)"
                )
                report_cases.append(
                    {
                        "id": tid,
                        "status": "FAIL",
                        "category": "AGENT_GENERATION",
                        "reason": "No hay DAX generado",
                        "duration_ms": duration_ms,
                    }
                )
                write_report_checkpoint()
                continue
        else:
            query = reference_query
        expected = test.get("resultado_esperado", {})
        criterion = test.get("criterio")
        contract_ok, contract_reason = validate_query_contract(
            query, test.get("semantic_contract")
        )

        if criterion == "ExpectedRejection":
            test_ok = not contract_ok
            reason = "La consulta no fue rechazada" if test_ok else contract_reason
            out, err = "", ""
            duration_ms = 0
            latencies.append(duration_ms)
        else:
            out, err = ("", contract_reason) if not contract_ok else execute_dax_via_powershell(query, port)
            duration_ms = int((time.time() - case_started_at) * 1000)
            latencies.append(duration_ms)

        if criterion != "ExpectedRejection":
            test_ok = False
            reason = ""
            if err or not out:
                test_ok = False
                reason = f"Error DAX: {err[:100]}"
            else:
                try:
                    data = json.loads(out)
                    test_ok, reason = evaluate_result(data, expected, criterion)
                except (json.JSONDecodeError, TypeError, ValueError) as ex:
                    test_ok = False
                    reason = f"Excepción parseando resultado: {str(ex)}"
        else:
            try:
                if not test_ok:
                    raise ValueError(reason)
            except ValueError as ex:
                test_ok = False
                reason = str(ex)
        
        status_icon = "✔ PASS" if test_ok else "❌ FAIL"
        if test_ok:
            passed += 1
            print(f"[{status_icon}] {tid} ({domain}) - Latencia: {duration_ms}ms")
        else:
            failed += 1
            print(f"[{status_icon}] {tid} ({domain}) - Falló: {reason} (Latencia: {duration_ms}ms)")
        report_cases.append(
            {
                "id": tid,
                "status": "PASS" if test_ok else "FAIL",
                "category": (
                    "PASS"
                    if test_ok
                    else "SEMANTIC_CONTRACT"
                    if not contract_ok
                    else "EXECUTION_OR_RESULT"
                ),
                "reason": reason,
                "duration_ms": duration_ms,
                "dax_analysis": analyze_dax(query),
            }
        )
        write_report_checkpoint()
    
    accuracy = (passed / len(tests)) * 100 if tests else 0
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
    
    print(f"\n========================================================================")
    print(f"📊 RESUMEN EJECUTIVO DE CALIDAD:")
    print(f"   Pruebas Exitosas:  {passed}/{len(tests)} ({accuracy:.1f}%)")
    print(f"   Pruebas Fallidas:  {failed}/{len(tests)}")
    print(f"   Latencia P95:      {p95} ms")
    print(f"   Estado de Calidad: {'✅ CERTIFICADO PARA PRODUCCIÓN' if failed == 0 else '⚠ REQUIERE REVISIÓN'}")
    print(f"========================================================================")
    write_report_checkpoint()
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["model-smoke", "agent-evaluation"], default="model-smoke")
    parser.add_argument("--dataset", default="golden_dataset.json")
    parser.add_argument("--generated-dax-file")
    parser.add_argument("--port", type=int)
    parser.add_argument("--expected-model")
    parser.add_argument("--report-file")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--batch-number", type=int, default=1)
    args = parser.parse_args()
    if args.expected_model:
        os.environ["DAX_COPILOT_EXPECTED_MODEL"] = args.expected_model
    raise SystemExit(
        run_suite(
            args.mode,
            args.generated_dax_file,
            args.port,
            args.dataset,
            args.report_file,
            args.batch_size,
            args.batch_number,
        )
    )
