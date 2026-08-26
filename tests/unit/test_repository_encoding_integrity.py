"""
Suite de pruebas automatizadas para garantizar la integridad de codificación,
ausencia de UTF-8 BOM y consistencia de archivos en todo el repositorio.
"""

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".gemini",
    "scratch",
}

CHECKED_EXTENSIONS = {
    ".sqlx",
    ".js",
    ".json",
    ".yaml",
    ".yml",
    ".tf",
    ".hcl",
    ".tftest.hcl",
    ".py",
    ".md",
    ".sh",
    ".ps1",
}


def get_all_repository_files() -> list[Path]:
    """Obtiene todos los archivos del repositorio sujetos a auditoria de encoding."""
    files_to_check: list[Path] = []
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for f in files:
            p = Path(root) / f
            if any(f.endswith(ext) for ext in CHECKED_EXTENSIONS):
                files_to_check.append(p)
    return files_to_check


@pytest.mark.parametrize(
    "file_path", get_all_repository_files(), ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_no_utf8_bom_and_valid_encoding(file_path: Path):
    """
    Verifica que ningun archivo contenga el caracter BOM (\xef\xbb\xbf)
    ni caracteres zero-width no-break space (\ufeff) y que sea UTF-8 estricto.
    """
    raw = file_path.read_bytes()

    # 1. No debe iniciar con UTF-8 BOM
    assert not raw.startswith(
        b"\xef\xbb\xbf"
    ), f"El archivo {file_path.relative_to(REPO_ROOT)} contiene UTF-8 BOM (\xef\xbb\xbf). Guardar como UTF-8 sin BOM."

    # 2. Debe ser decodificable como UTF-8 estricto
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as ex:
        pytest.fail(
            f"El archivo {file_path.relative_to(REPO_ROOT)} contiene bytes no validos en UTF-8: {ex}"
        )
        return

    # 3. No debe contener caracteres de espacio de no-separacion de ancho cero (BOM embebido)
    assert (
        "\ufeff" not in text
    ), f"El archivo {file_path.relative_to(REPO_ROOT)} contiene caracter invisible \ufeff (zero-width no-break space)."


def test_dataform_declarations_and_refs_integrity():
    """
    Valida que todos los ${ref('...')} usados en archivos .sqlx
    tengan un archivo .sqlx de declaracion, tabla o vista correspondiente.
    """
    dataform_dir = REPO_ROOT / "dataform" / "definitions"
    if not dataform_dir.exists():
        pytest.skip("Directorio dataform/definitions no encontrado")

    declared_names = set()
    ref_usages = []

    for root, _, files in os.walk(dataform_dir):
        for f in files:
            if f.endswith(".sqlx"):
                p = Path(root) / f
                text = p.read_text(encoding="utf-8")

                # Buscar name en bloque config
                name_match = re.search(r'name:\s*["\']([^"\']+)["\']', text)
                if name_match:
                    declared_names.add(name_match.group(1))
                else:
                    # Por defecto Dataform usa el nombre del archivo sin extension
                    declared_names.add(p.stem)

                # Buscar todas las llamadas ref(...)
                refs = re.findall(r'\$\{ref\(\s*["\']([^"\']+)["\']\s*\)\}', text)
                for r in refs:
                    ref_usages.append((p.relative_to(REPO_ROOT), r))

    # Validar que toda referencia tenga definicion
    missing_refs = []
    for source_file, ref_target in ref_usages:
        if ref_target not in declared_names:
            missing_refs.append(
                f"{source_file} -> ref('{ref_target}') no existe en dataform/definitions"
            )

    assert not missing_refs, "Se encontraron referencias rotas en Dataform:\n" + "\n".join(
        missing_refs
    )
