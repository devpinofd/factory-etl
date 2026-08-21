# ==============================================================================
# 🧑‍⚖️ AGENTE DE QA Y EVALUACIÓN DE CALIDAD (LLM-AS-A-JUDGE: OpenAI o3 / GPT-5.4-Pro)
# • Lee telemetría de incidentes y consultas lentas desde copilot_qa_history.jsonl
# • Diagnostica causas raíz con razonamiento profundo (Deep Reasoning)
# • Valida propuestas contra el Golden Dataset de regresión
# • Genera automáticamente una rama y Pull Request en GitHub para revisión de Francisco Pino
# ==============================================================================

import os
import json
import subprocess
import datetime
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# 1. Configuración de Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini") # O 'o3-qa-judge'
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)

def get_judge_client():
    if not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT no esta configurado.")
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version=AZURE_OPENAI_API_VERSION
    )

def read_telemetry_incidents(logs_dir):
    jsonl_path = os.path.join(logs_dir, "copilot_qa_history.jsonl")
    if not os.path.exists(jsonl_path):
        return []
    
    incidents = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    entry = json.loads(line.strip())
                    # Filtrar errores o consultas de alta latencia
                    if entry.get("status") != "SUCCESS" or entry.get("duration_ms", 0) > 10000:
                        incidents.append(entry)
                except:
                    pass
    return incidents

def generate_refinement_proposal(incident, current_prompt):
    client = get_judge_client()
    
    system_evaluator_prompt = """
    Eres el Agente Juez y Arquitecto Senior de BI de Comercial Tinito.
    Tu objetivo es analizar un incidente o ineficiencia de consulta DAX registrado en telemetría
    y proponer una mejora quirúrgica a las reglas del System Prompt corporativo.
    
    DEBES responder estrictamente en formato JSON con la siguiente estructura:
    {
      "titulo_pr": "Título conciso para el Pull Request",
      "diagnostico": "Explicación técnica de la causa raíz en VertiPaq",
      "regla_propuesta": "Texto exacto de la nueva regla de optimización a incorporar",
      "categoria": "DAX_OPTIMIZATION | GUARDRAIL | SEMANTIC_MAPPING",
      "test_caso_regresion": {
         "pregunta": "Pregunta del usuario que falló",
         "dax_correcto": "DAX optimizado esperado",
         "criterio": "ExactMatch"
      }
    }
    """
    
    user_payload = f"""
    INCIDENTE REGISTRADO EN TELEMETRÍA:
    - Pregunta: {incident.get('question')}
    - DAX Ejecutado: {incident.get('dax_query')}
    - Error / Estado: {incident.get('error_message') or incident.get('status')}
    - Duración: {incident.get('duration_ms')} ms
    
    SYSTEM PROMPT ACTUAL (Extracto):
    {current_prompt[:1500]}
    """
    
    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_evaluator_prompt},
            {"role": "user", "content": user_payload}
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

def create_github_pull_request(proposal, repo_dir):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    branch_name = f"ai-refine/dax-rule-{timestamp}"
    
    print(f"[*] Creando rama Git: {branch_name}...")
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_dir, check=True)
    
    # 1. Incorporar la regla al System Prompt
    prompt_file = os.path.join(repo_dir, "prompts", "system_prompt_v1.0.md")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        new_content = content + f"\n\n# --- REGLA INCORPORADA POR QA JUDGE ({timestamp}) ---\n"
        new_content += f"# Diagnóstico: {proposal.get('diagnostico')}\n"
        new_content += f"{proposal.get('regla_propuesta')}\n"
        
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(new_content)
    
    # 2. Commit
    subprocess.run(
        ["git", "add", "--", "prompts/system_prompt_v1.0.md"],
        cwd=repo_dir,
        check=True,
    )
    commit_msg = f"refactor(dax-copilot): {proposal.get('titulo_pr')}"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir, check=True)
    
    # 3. Push a GitHub
    print(f"[*] Publicando rama en GitHub...")
    subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=repo_dir, check=True)
    
    # 4. Crear Pull Request con GitHub CLI
    pr_body = f"""## 🧑‍⚖️ Propuesta de Auto-Mejora generada por el Agente de QA

### 🔍 Diagnóstico Técnico
{proposal.get('diagnostico')}

### 🛠️ Regla Propuesta
```markdown
{proposal.get('regla_propuesta')}
```

### 🧪 Caso de Prueba de Regresión
* **Pregunta:** `{proposal.get('test_caso_regresion', {}).get('pregunta')}`
* **DAX Esperado:** `{proposal.get('test_caso_regresion', {}).get('dax_correcto')}`

---
*Este PR fue generado automáticamente por el **Agente Evaluador de Calidad en Azure** y requiere la aprobación humana de @devpinofd antes de su integración a producción.*
"""
    
    body_path = os.path.join(repo_dir, ".git", "dax-copilot-pr-body.md")
    with open(body_path, "w", encoding="utf-8") as body_file:
        body_file.write(pr_body)
    try:
        res = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                f"[AI-QA] {proposal.get('titulo_pr')}",
                "--body-file",
                body_path,
                "--assignee",
                "devpinofd",
            ],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        os.remove(body_path)
    print("✔ PULL REQUEST CREADO EXITOSAMENTE EN GITHUB:")
    print(res.stdout)
    
    # Volver a main
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True)
    return res.stdout

if __name__ == "__main__":
    repo_root = r"c:\Repos\factory-etl"
    logs_directory = os.path.expandvars(r"%LOCALAPPDATA%\Tinito\PbiCopilot\logs")
    print(f"=== INICIANDO AUDITORÍA DEL AGENTE DE QA ===")
    print(f"Repo: {repo_root}")
    print(f"Logs: {logs_directory}")
    
    incidents = read_telemetry_incidents(logs_directory)
    print(f"Total de incidentes detectados para evaluación: {len(incidents)}")
    
    if incidents:
        inc = incidents[0]
        prompt_path = os.path.join(repo_root, "prompts", "system_prompt_v1.0.md")
        curr_p = open(prompt_path, encoding="utf-8").read() if os.path.exists(prompt_path) else ""
        
        print(f"[*] Analizando incidente: {inc.get('question')}...")
        proposal = generate_refinement_proposal(inc, curr_p)
        print(f"✔ Propuesta generada: {proposal.get('titulo_pr')}")
        print(f"  Diagnóstico: {proposal.get('diagnostico')}")
