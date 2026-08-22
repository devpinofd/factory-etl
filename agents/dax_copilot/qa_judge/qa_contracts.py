SUPPORTED_PROPOSAL_CRITERIA = {
    "ExactMatch",
    "ExactNumeric",
    "NonZeroNumeric",
    "PercentageRange",
    "RowCountExact",
    "RowCountMinimum",
    "NonNegativeNumeric",
    "ExpectedRejection",
}


def validate_proposal_schema(proposal):
    required = {
        "titulo_pr",
        "diagnostico",
        "regla_propuesta",
        "categoria",
        "test_caso_regresion",
    }
    missing = required.difference(proposal)
    if missing:
        raise ValueError(f"Propuesta QA incompleta; faltan campos: {sorted(missing)}")

    regression_case = proposal["test_caso_regresion"]
    for field in ("pregunta", "dax_correcto", "criterio"):
        if not regression_case.get(field):
            raise ValueError(f"Test de regresión incompleto; falta: {field}")

    if regression_case["criterio"] not in SUPPORTED_PROPOSAL_CRITERIA:
        raise ValueError(
            f"Criterio de regresión no soportado: {regression_case['criterio']}"
        )
    return proposal
