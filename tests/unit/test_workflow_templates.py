"""
Pruebas unitarias y linters estáticos para plantillas de Cloud Workflows (*.tftpl).

Valida que el renderizado de variables de Terraform (${var}), el desescape ($${ -> ${})
y la resolución de directivas (%{ if }/%{ endif }) produzcan YAML válido para
Cloud Workflows, verificando reglas de entrecomillado, prohibición de bytes (json.encode)
y compatibilidad de sintaxis de expresiones.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = REPO_ROOT / "terraform"

# Snippet representativo de la versión rota en commit 2ee2c3a
# Guardado como fallback en caso de clones superficiales (shallow clones) en CI
BROKEN_2EE2C3A_SNIPPET = """
    - set_bronze_details:
        assign:
          - bronze_details: $${json.encode({"target_dt": target_dt, "missing_companies": missing_companies})}
"""


# ---------------------------------------------------------------------------
# Evaluador y Renderer de Plantillas HCL2 / Terraform (.tftpl)
# ---------------------------------------------------------------------------
def evaluate_hcl_condition(expr: str, context: dict[str, Any]) -> bool:
    """
    Evalúa expresiones condicionales comunes en directivas %{ if <expr> } de HCL2.

    Soporta:
      - Negación: !var
      - Desigualdad: var != "valor" o var != ""
      - Igualdad: var == "valor"
      - Variables booleanas directas: var
    """
    expr = expr.strip()
    if expr.startswith("!"):
        var_name = expr[1:].strip()
        return not bool(context.get(var_name, False))
    if "!=" in expr:
        parts = expr.split("!=", 1)
        val = str(context.get(parts[0].strip(), ""))
        target = parts[1].strip(" \"'")
        return val != target
    if "==" in expr:
        parts = expr.split("==", 1)
        val = str(context.get(parts[0].strip(), ""))
        target = parts[1].strip(" \"'")
        return val == target
    return bool(context.get(expr, True))


def render_workflow_template(content: str, context: dict[str, Any]) -> str:
    """
    Renderiza una plantilla .tftpl simulando la función templatefile de Terraform.

    Manejo de directivas:
      1. Procesa bloques %{ if <cond> }, %{ else } y %{ endif } soportando anidamiento.
      2. Resuelve expresiones ternarias HCL: ${cond ? "true_val" : "false_val"}.
      3. Preserva expresiones escapadas ($${...} -> temporal -> ${...}).
      4. Reemplaza variables simples de Terraform ${var} por valores de context o dummies.

    Limitaciones documentadas:
      - Directivas %{ for ... } en plantillas de workflows no están presentes actualmente;
        si se añadieran, requerirán iteración sobre colecciones en el renderer.
      - Las expresiones condicionales evaluadas cubren booleanos y comparaciones de cadenas.
    """
    lines = content.splitlines()
    output_lines: list[str] = []
    # stack: lista de tuplas (condition_value, is_active)
    stack: list[tuple[bool, bool]] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("%{") and stripped.endswith("}"):
            directive = stripped[2:-1].strip()
            if directive.startswith("if "):
                cond_expr = directive[3:].strip()
                cond_val = evaluate_hcl_condition(cond_expr, context)
                parent_active = stack[-1][1] if stack else True
                stack.append((cond_val, parent_active and cond_val))
                continue
            if directive == "else":
                if stack:
                    cond_val, parent_active = stack.pop()
                    new_cond = not cond_val
                    stack.append((new_cond, parent_active and new_cond))
                continue
            if directive == "endif":
                if stack:
                    stack.pop()
                continue

        is_active = stack[-1][1] if stack else True
        if is_active:
            output_lines.append(line)

    rendered = "\n".join(output_lines)

    # Evaluar ternarios HCL: ${var ? "true" : "false"}
    def eval_ternary(match: re.Match[str]) -> str:
        cond_var = match.group(1).strip()
        true_val = match.group(2).strip()
        false_val = match.group(3).strip()
        c = context.get(cond_var, True)
        return true_val if c else false_val

    rendered = re.sub(
        r'\$\{\s*([a-zA-Z0-9_]+)\s*\?\s*"([^"]*)"\s*:\s*"([^"]*)"\s*\}', eval_ternary, rendered
    )

    # Proteger escapes de Terraform: $${ -> marcador nulo
    rendered = rendered.replace("$${", "\x00")

    # Reemplazar variables de Terraform ${var}
    def replace_tf_var(match: re.Match[str]) -> str:
        var_name = match.group(1).strip()
        if var_name in context:
            return str(context[var_name])
        return f"dummy_{var_name}"

    rendered = re.sub(r"\$\{([a-zA-Z0-9_]+)\}", replace_tf_var, rendered)

    # Restaurar expresiones de Workflows: marcador nulo -> ${
    return rendered.replace("\x00", "${")


# ---------------------------------------------------------------------------
# Reglas de Linting y Detección de Sintaxis de Cloud Workflows
# ---------------------------------------------------------------------------
def lint_workflow_yaml(rendered_yaml: str) -> list[str]:
    """
    Aplica linters estáticos sobre el YAML renderizado de Cloud Workflows.

    Reglas aplicadas:
      1. Regla 3c: Prohibir 'json.encode(' (devuelve bytes en Workflows). Exigir
         'json.encode_to_string(' o mapas declarados en bloques assign.
      2. Regla 3b (texto): Todo valor escalar no entrecomillado que empiece por '${'
         y contenga '{', '}' internos o ': ' debe fallar (exige comillas simples '${...}').
      3. Regla 3a: yaml.safe_load debe parsear sin error sintáctico.
      4. Regla 3b (árbol): Ningún valor o clave que empiece por '${' puede haberse
         convertido en dict/list tras el parseo.
      5. Sintaxis Workflows: En expresiones '${...}', literales de mapa '{...}'
         no están soportados por Cloud Workflows y provocan error en deploy.
    """
    errors: list[str] = []
    lines = rendered_yaml.splitlines()

    # Regla 3c: Prohibir bare json.encode(
    for line_num, line in enumerate(lines, 1):
        if re.search(r"\bjson\.encode\s*\((?!_to_string)", line):
            errors.append(
                f"Línea {line_num}: Uso prohibido de 'json.encode(' (devuelve bytes). "
                f"Use 'json.encode_to_string(' para strings/SQL o declare mapas bajo assign."
            )

    # Regla 3b: Escalares no entrecomillados que empiezan por ${ y contienen {, } o ': '
    for line_num, line in enumerate(lines, 1):
        # Detectar asignaciones o secuencias no entrecomilladas: ": ${..." o "- ${..." o "[${..."
        m = re.search(r"(?::\s+|-\s+|\[)(\$\{[^\r\n]+)", line)
        if m:
            expr_candidate = m.group(1).strip()
            prefix = line[: m.start(1)]
            if prefix.endswith(("'", '"')):
                continue

            inner = expr_candidate[2:]
            if "{" in inner or ": " in inner:
                errors.append(
                    f"Línea {line_num}: Expresión no entrecomillada que empieza por '${{' "
                    f"contiene '{{' interno o ': '. Debe encerrarse en comillas simples ('${{...}}'). "
                    f"Encontrado: {expr_candidate}"
                )
            elif expr_candidate.startswith("${") and ("}" in inner):
                first_close = inner.find("}")
                rest = inner[first_close + 1 :]
                if "}" in rest:
                    errors.append(
                        f"Línea {line_num}: Expresión no entrecomillada que empieza por '${{' "
                        f"contiene '}}' interno. Debe encerrarse en comillas simples ('${{...}}'). "
                        f"Encontrado: {expr_candidate}"
                    )

    # Regla 3a: yaml.safe_load
    try:
        parsed = yaml.safe_load(rendered_yaml)
    except yaml.YAMLError as exc:
        errors.append(f"Error de sintaxis YAML: yaml.safe_load falló: {exc}")
        return errors

    # Regla 3b (árbol): Validar que ninguna clave o estructura empiece por ${
    def check_parsed_nodes(node: Any, path: str = "root") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str) and k.startswith("${"):
                    errors.append(
                        f"Error estructural en {path}: La clave '{k}' empieza por '${{'. "
                        f"Cloud Workflows no permite expresiones como claves de mapa."
                    )
                check_parsed_nodes(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                check_parsed_nodes(item, f"{path}[{i}]")

    check_parsed_nodes(parsed)

    # Regla 5: Expresiones de Cloud Workflows no admiten literales de mapa {...}
    for line_num, line in enumerate(lines, 1):
        for expr_match in re.finditer(r"\$\{([^}]+)\}", line):
            expr_body = expr_match.group(1)
            if "{" in expr_body:
                errors.append(
                    f"Línea {line_num}: Expresión inválida de Cloud Workflows '${{{expr_body}}}'. "
                    f"Cloud Workflows no admite literales de mapa '{{...}}' dentro de expresiones."
                )

    return errors


# ---------------------------------------------------------------------------
# Contextos de prueba para plantillas
# ---------------------------------------------------------------------------
DQ_CONTEXT: dict[str, Any] = {
    "project_id": "dummy-project",
    "region": "us-central1",
    "control_dataset_id": "dummy_control",
    "staging_dataset_id": "dummy_stg",
    "gold_dataset_id": "dummy_gold",
    "bronze_bucket_name": "dummy-bronze-bucket",
    "bronze_prefix": "bronze/ventas_diarias_v3/",
    "staging_table_name": "stg_ventas_diarias_v3",
    "gold_table_name": "fct_ventas_gold",
    "expected_companies_count": 5,
    "expected_companies_array": "['ctb', 'ctm', 'daroan', 'roldan', 'tinito']",
    "expected_companies_json": '["ctb", "ctm", "daroan", "roldan", "tinito"]',
    "max_staleness_days": 2,
}

WORKFLOWS_CONTEXT_FULL: dict[str, Any] = {
    "project_id": "dummy-project",
    "region": "us-central1",
    "job_name": "dummy-job",
    "default_lookback_days": 1,
    "consolidation_workflow_name": "factory-etl-consolidation-prod",
    "enable_scd2": True,
    "service_account_email": "dummy@dummy.iam.gserviceaccount.com",
    "bucket_name": "dummy-bucket",
    "control_dataset_id": "dummy_control",
    "queries_json": '[{"id": "ventas_diarias_v3", "has_param": true}]',
    "enable_medallion_consolidation": True,
    "consolidation_only": False,
    "bronze_stg_dataset_id": "dummy_stg",
    "dataform_repository_id": "dummy-repo",
    "dataform_location": "us-central1",
    "staging_schemas_json": '{"ventas_diarias_v3": []}',
    "quarantine_bucket_name": "dummy-quarantine",
    "silver_dataset_id": "dummy_silver",
    "gold_dataset_id": "dummy_gold",
    "security_dataset_id": "dummy_security",
    "max_parallel_tasks": 10,
}

WORKFLOWS_CONTEXT_CONSOLIDATION_ONLY: dict[str, Any] = {
    **WORKFLOWS_CONTEXT_FULL,
    "consolidation_only": True,
    "consolidation_workflow_name": "",
    "enable_medallion_consolidation": False,
}


# ---------------------------------------------------------------------------
# Tests Parametrizados de Plantillas del Repositorio
# ---------------------------------------------------------------------------
def test_all_workflow_templates_exist():
    """Verifica que todas las plantillas esperadas de workflows existan en el repo."""
    dq_tpl = TERRAFORM_DIR / "modules/data_quality_workflow/templates/workflow.yaml.tftpl"
    wf_tpl = TERRAFORM_DIR / "modules/workflows/templates/workflow.yaml.tftpl"
    assert dq_tpl.exists(), f"No se encontró la plantilla {dq_tpl}"
    assert wf_tpl.exists(), f"No se encontró la plantilla {wf_tpl}"


def test_data_quality_workflow_template_passes_all_checks():
    """
    Verifica que la plantilla de Data Quality en HEAD pase todas las validaciones
    de YAML, entrecomillado y funciones permitidas sin errores.
    """
    dq_tpl = TERRAFORM_DIR / "modules/data_quality_workflow/templates/workflow.yaml.tftpl"
    content = dq_tpl.read_text(encoding="utf-8")
    rendered = render_workflow_template(content, DQ_CONTEXT)
    errors = lint_workflow_yaml(rendered)
    assert not errors, "La plantilla de Data Quality tiene errores de linting:\n" + "\n".join(
        errors
    )


@pytest.mark.parametrize(
    "profile_name,context",
    [
        pytest.param(
            "full_ingestion_and_medallion",
            WORKFLOWS_CONTEXT_FULL,
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    "Problema conocido en template productivo de ingesta: Líneas 24 y 198 usan "
                    "secuencias de flujo no entrecomilladas [- empresas: [$${target_empresa}]] y "
                    "[sourceUris: [$${source_prefix + '*'}]] que violan la sintaxis YAML 1.2 "
                    "al iniciar un escalar plano con '{' dentro de un corchete []."
                ),
            ),
        ),
        pytest.param(
            "consolidation_only",
            WORKFLOWS_CONTEXT_CONSOLIDATION_ONLY,
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    "Problema conocido en template productivo de ingesta: Líneas 24 y 198 usan "
                    "secuencias de flujo no entrecomilladas [- empresas: [$${target_empresa}]] y "
                    "[sourceUris: [$${source_prefix + '*'}]] que violan la sintaxis YAML 1.2."
                ),
            ),
        ),
    ],
)
def test_workflows_ingestion_template_syntax(profile_name: str, context: dict[str, Any]):
    """
    Ejecuta el linter contra la plantilla productiva de ingesta.
    Marcado como xfail(strict=True) para no modificar el template productivo
    en este PR mientras se reportan los hallazgos en líneas 24 y 198.
    """
    wf_tpl = TERRAFORM_DIR / "modules/workflows/templates/workflow.yaml.tftpl"
    content = wf_tpl.read_text(encoding="utf-8")
    rendered = render_workflow_template(content, context)
    errors = lint_workflow_yaml(rendered)
    assert not errors, f"Errores en workflows ({profile_name}):\n" + "\n".join(errors)


def test_workflows_ingestion_template_passes_when_flow_sequences_quoted():
    """
    Verifica que la plantilla de ingesta pasa al 100% (incluyendo reglas 3b y 3c)
    si únicamente se corrigen las secuencias de flujo no entrecomilladas [${...}].
    Demuestra que el resto de expresiones y llamadas a json.encode_to_string son válidas.
    """
    wf_tpl = TERRAFORM_DIR / "modules/workflows/templates/workflow.yaml.tftpl"
    content = wf_tpl.read_text(encoding="utf-8")
    rendered = render_workflow_template(content, WORKFLOWS_CONTEXT_FULL)

    # Sanitizar únicamente las secuencias de flujo [${...}] -> ['${...}']
    sanitized = re.sub(r"\[\$\{([^\]]+)\}\]", r"['${\1}']", rendered)
    errors = lint_workflow_yaml(sanitized)
    assert not errors, (
        "La plantilla de ingesta sanitizada aún presenta errores inesperados:\n" + "\n".join(errors)
    )


# ---------------------------------------------------------------------------
# Prueba de Regresión Obligatoria (Requisito 4)
# ---------------------------------------------------------------------------
def test_regression_broken_template_2ee2c3a_fails():
    """
    PRUEBA DE REGRESIÓN: Demuestra que el test FALLA contra la versión rota
    del template en commit 2ee2c3a (capturando error de safe_load, json.encode y
    falta de comillas simples).
    """
    broken_content: str | None = None

    try:
        res = subprocess.run(
            [
                "git",
                "show",
                "2ee2c3a:terraform/modules/data_quality_workflow/templates/workflow.yaml.tftpl",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        broken_content = res.stdout
    except Exception:
        # Fallback si el commit no está disponible localmente (ej. shallow clone)
        broken_content = None

    if broken_content:
        rendered = render_workflow_template(broken_content, DQ_CONTEXT)
        errors = lint_workflow_yaml(rendered)
        # Debe fallar con al menos 2 errores (json.encode prohibido y unquoted/yaml syntax)
        assert len(errors) >= 2, f"Se esperaban fallos en 2ee2c3a pero obtuvo: {errors}"
        assert any("json.encode(" in e for e in errors), "No detectó el bare json.encode("
        assert any(
            "yaml.safe_load" in e or "comillas simples" in e for e in errors
        ), "No detectó el error de parseo o comillas faltantes"
    else:
        # Validar el snippet exacto que causó la falla en 2ee2c3a
        sample_yaml = f"""
main:
  steps:
    - init:
        assign:
          - target_dt: "2026-10-02"
{BROKEN_2EE2C3A_SNIPPET}
"""
        rendered = render_workflow_template(sample_yaml, DQ_CONTEXT)
        errors = lint_workflow_yaml(rendered)
        assert len(errors) >= 2, f"Se esperaban fallos en el snippet roto pero obtuvo: {errors}"
        assert any("json.encode(" in e for e in errors)


# ---------------------------------------------------------------------------
# Fixtures Parametrizados de Snippets Rotos vs Correctos (Requisito 4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "snippet,expected_error_keyword",
    [
        pytest.param(
            '- bronze_details: ${json.encode({"target_dt": dt})}',
            "comillas simples",
            id="unquoted_with_braces_and_colon",
        ),
        pytest.param(
            "- bronze_details: '${json.encode(my_map)}'",
            "json.encode(",
            id="bare_json_encode_returns_bytes",
        ),
        pytest.param(
            "- bronze_details: '${json.encode_to_string({\"dt\": dt})}'",
            "literales de mapa",
            id="map_literal_inside_workflows_expression",
        ),
        pytest.param(
            "- config: ${param: default_val}",
            "comillas simples",
            id="unquoted_with_colon_space",
        ),
        pytest.param(
            "${key_expression}: value",
            "claves de mapa",
            id="expression_as_yaml_key",
        ),
    ],
)
def test_lint_rules_reject_broken_snippets(snippet: str, expected_error_keyword: str):
    """Verifica que cada patrón erróneo sea rechazado con el mensaje esperado."""
    test_yaml = f"""
main:
  steps:
    - step1:
        assign:
          {snippet}
"""
    errors = lint_workflow_yaml(test_yaml)
    assert errors, f"El snippet erróneo '{snippet}' fue aceptado sin errores."
    assert any(expected_error_keyword.lower() in e.lower() for e in errors), (
        f"No se encontró '{expected_error_keyword}' en los errores:\n" + "\n".join(errors)
    )


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param(
            "- bronze_details: '${json.encode_to_string(bronze_details_map)}'",
            id="quoted_json_encode_to_string",
        ),
        pytest.param(
            "- total_queries: ${len(manifest)}",
            id="valid_unquoted_simple_expression",
        ),
        pytest.param(
            "- target_dt: '${text.substring(time.format(sys.now() - 86400, \"America/Caracas\"), 0, 10)}'",
            id="quoted_complex_function_expression",
        ),
        pytest.param(
            "- bronze_details_map:\n              target_dt: '${target_dt}'\n              missing: []\n          - bronze_details: '${json.encode_to_string(bronze_details_map)}'",
            id="yaml_dict_under_assign_encoded_to_string",
        ),
    ],
)
def test_lint_rules_accept_valid_snippets(snippet: str):
    """Verifica que los patrones recomendados y válidos sean aceptados limpiamente."""
    test_yaml = f"""
main:
  steps:
    - step1:
        assign:
          {snippet}
"""
    errors = lint_workflow_yaml(test_yaml)
    assert not errors, f"El snippet válido '{snippet}' fue rechazado con errores:\n" + "\n".join(
        errors
    )
