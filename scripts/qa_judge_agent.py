# ==============================================================================
# 🧑‍⚖️ AGENTE DE QA Y EVALUACIÓN DE CALIDAD - SHIM CANÓNICO
# Redirige la ejecución al módulo canónico en agents/dax_copilot/qa_judge/qa_judge_agent.py
# ==============================================================================

import os
import sys

# Agregar la raíz del repositorio al sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from agents.dax_copilot.qa_judge.qa_judge_agent import (
    get_judge_client,
    read_telemetry_incidents,
    generate_refinement_proposal,
    create_github_pull_request,
)

if __name__ == "__main__":
    import runpy
    canonic_script = os.path.join(_repo_root, "agents", "dax_copilot", "qa_judge", "qa_judge_agent.py")
    runpy.run_path(canonic_script, run_name="__main__")

