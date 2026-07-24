---
mode: agent
description: Construye el proceso batch E2E del extractor FactorySoft hasta la capa Bronze del data lake en GCS, cumpliendo las "Reglas de aterrizaje en Bronze" del plan Fase 1.
---

<role>
Eres un ingeniero de datos senior trabajando en el repositorio `factory-etl`
(Python 3.12, uv, ruff strict, pyright strict, pytest con cobertura mínima,
bandit). Tu trabajo debe cumplir las reglas del proyecto ya establecidas en
`AGENTS.md` / `copilot-instructions.md` / `PLAN_IMPLEMENTACION_FASE_1.md` y
producir código que pase la CI existente sin excepciones.

No sugieras; **implementa**. No añadas features fuera del alcance. Prefiere
editar archivos existentes antes de crear nuevos.
</role>

<context>
Repositorio: `github.com/devpinofd/factory-etl` (público), rama `main`.
Estructura relevante ya construida (NO reescribir, solo consumir):

- `src/factory_etl/config.py` → `Settings` (pydantic-settings, `env_prefix=FACTORY_ETL_`, `frozen=True`).
- `src/factory_etl/ids.py` → `new_run_id`, `sql_hash`, `payload_hash`, `batch_id`, `row_hash` (usa `\x1f` como separador y `\x00NULL\x00` como sentinel).
- `src/factory_etl/factory_queries/catalog.py` → `get(query_id, source_empresa)` retorna `QueryDefinition`.
- `src/factory_etl/factory_queries/models.py` → `QueryDefinition(frozen, slots)` con `query_id, version, category, transport, load_strategy, natural_key, required_columns, sql_path, schema_path, allowed_companies, parameters, reject_empty`.
- `src/factory_etl/factory_queries/renderer.py` → `render(sql_template, param_defs, values) -> str` (valida y aplica placeholders `@nombre`).
- `src/factory_etl/protocols.py` → `SecretResolverProtocol`, `QueryRunnerProtocol`, `BronzeWriterProtocol`, `ControlTablesProtocol`, `QuarantineProtocol`.
- `src/factory_etl/secrets.py` → `SecretResolver` (Google Secret Manager, inyectable).
- `src/factory_etl/query_runner.py` → `QueryRunner.execute(...) -> HttpResult` (`payload_bytes`, `payload_hash`, `status_code`). Retries **solo** en 5xx/red vía `_TransientServerError`. 4xx no reintenta.
- `src/factory_etl/bronze_writer.py` → `BronzeWriter.stage(...) -> WriteResult` y `promote(...) -> str`. Escribe JSONL+gzip con `sort_keys=True`.
- `src/factory_etl/quarantine.py` → `Quarantine.dump(..., reason: QuarantineReason)` retorna URI.
- `src/factory_etl/control_tables.py` → `ControlTables` con `start_run`, `finish_run`, `register_batch`, `find_batch_by_hash`. Enums `RunStatus`, `BatchStatus`.
- `src/factory_etl/bootstrap.py` → `build_extractor(settings) -> Extractor` (composition root).
- `src/factory_etl/cli.py` → `typer` con comandos `version`, `run` (stub), `list-queries`.
- `src/factory_etl/factory_queries/schemas/articulos.json` → esquema de referencia (`columns[].name`, `columns[].required`, etc.).

Stack fijo (no negociar):
- `httpx` + `respx` (mock HTTP en tests).
- `tenacity` con `wait_exponential_jitter`.
- `google-cloud-{storage,bigquery,secretmanager}` **siempre detrás de Protocol**.
- `typer` (CLI), `structlog` (logging JSON via `configure_logging`).
- Tests en `tests/unit/` con fakes en memoria, **no mocks de librería**.

Referencia normativa: leer y respetar la sección **"Reglas de aterrizaje en Bronze"**
de `PLAN_IMPLEMENTACION_FASE_1.md` (Etapa 4). Las 9 columnas de sistema y el flujo
de estados WRITTEN → SUCCESS son de cumplimiento obligatorio.
</context>

<objective>
Construir el **proceso batch end-to-end** que, dado `(query_id, source_empresa, dt, run_id)`,
extrae de FactorySoft, valida, enriquece y aterriza en Bronze (GCS) con auditoría
completa en BigQuery. El pipeline debe ser:

- **Idempotente**: mismos inputs → mismo `batch_id` → no reescribe si ya existe SUCCESS con el mismo `payload_hash`.
- **Determinístico**: mismos rows → mismo objeto GCS (byte-a-byte) y mismos `_row_hash`.
- **Auditable**: cada transición (INICIO, DUPLICADO, CUARENTENA, STAGED, PROMOTED, SUCCESS, FAILED) queda registrada.
- **Segurо**: sin secretos en logs, sin SQL construida por concatenación con input de usuario, sin PII de filas en mensajes de error.
- **Testeable**: 100 % del extractor y del CLI cubierto por unit tests con fakes; sin llamadas de red reales.
</objective>

<inputs_disponibles>
Los siguientes componentes ya existen y deben ser **consumidos vía Protocol**:

- `Settings` (leído del entorno con `Settings()`).
- `ids.{new_run_id, sql_hash, payload_hash, batch_id, row_hash}`.
- `get_query_definition(query_id, source_empresa) -> QueryDefinition`.
- `render_sql(template, parameters, values) -> str`.
- `QueryRunnerProtocol.execute(*, sql_rendered, source_empresa) -> HttpResult`.
- `BronzeWriterProtocol.stage(...) -> WriteResult` y `.promote(...) -> str`.
- `QuarantineProtocol.dump(...) -> str`.
- `ControlTablesProtocol.{start_run, finish_run, register_batch, find_batch_by_hash}`.
</inputs_disponibles>

<deliverables>
Se deben producir/modificar los siguientes artefactos. Firmas exactas.

<deliverable id="1" file="src/factory_etl/extractor.py" action="crear-o-reescribir">
Módulo orquestador. Contiene:

```python
@dataclass(frozen=True)
class BatchOutcome:
    batch_id: str
    status: str          # valor de BatchStatus (SUCCESS | SKIPPED_DUPLICATE | QUARANTINED | FAILED)
    object_uri: str | None
    record_count: int | None
    was_duplicate: bool

@dataclass
class Extractor:
    settings: Settings
    runner: QueryRunnerProtocol
    writer: BronzeWriterProtocol
    control: ControlTablesProtocol
    quarantine: QuarantineProtocol

    def run_batch(
        self,
        *,
        query_id: str,
        source_empresa: str,
        dt: str,                          # YYYY-MM-DD
        run_id: str,
        parameter_values: dict[str, object] | None = None,
    ) -> BatchOutcome: ...
```

Flujo obligatorio de `run_batch` (en este orden):

1. `qdef = get_query_definition(query_id, source_empresa)`.
2. `sql_rendered = render_sql(qdef.read_sql(), qdef.parameters, parameter_values or {})`.
3. `sql_hash_hex = ids.sql_hash(sql_rendered)`.
4. `http = self.runner.execute(sql_rendered=..., source_empresa=...)`.
5. Deduplicación: `existing = self.control.find_batch_by_hash(...)`; si no es `None`, retornar `SKIPPED_DUPLICATE` con `was_duplicate=True` (log_event `DUPLICATE_SKIPPED`).
6. Parseo del sobre (helper `_parse_payload`, ver deliverable 2). Si `InvalidPayloadError` → cuarentena `SCHEMA_MISMATCH`.
7. Si `not rows and qdef.reject_empty` → cuarentena `EMPTY_REJECTED`.
8. **Validación de esquema** (helper `_validate_required_columns`, ver deliverable 3): si alguna fila carece de columnas `required` → cuarentena `SCHEMA_MISMATCH`.
9. `computed_batch_id = ids.batch_id(...)`.
10. **Enriquecimiento** (helper `_enrich_rows`, ver deliverable 4): añadir 9 columnas `_*` a cada fila.
11. `write_result = self.writer.stage(rows=enriched_rows, ...)`.
12. `self.control.register_batch(status=WRITTEN, ...)` y `log_event PROMOTE_START`.
13. `final_uri = self.writer.promote(...)`.
14. `self.control.register_batch(status=SUCCESS, ...)` y `log_event BATCH_SUCCESS`.
15. Retornar `BatchOutcome(status=SUCCESS, object_uri=final_uri, ...)`.

Restricciones:
- Nunca importar clases concretas (ni `BronzeWriter`, ni `QueryRunner`, ni `bigquery`).
- No usar `logging`; usar `structlog.get_logger(__name__)` con eventos en snake_case.
- Cualquier excepción no controlada debe propagarse limpia (el CLI la enruta a `finish_run(FAILED)`).
</deliverable>

<deliverable id="2" file="src/factory_etl/extractor.py" action="incluir-helper">
`_parse_payload(payload_bytes: bytes) -> list[dict[str, object]]`

- Decodifica con `utf-8-sig` (tolerar BOM).
- Acepta sobre `{"d": {"laTablas": [[...]]}}` o `{"datos": {"laTablas": [[...]]}}`.
- Rechaza (`InvalidPayloadError`): JSON inválido, raíz no-objeto, `llError` truthy, `laTablas` ausente/no-lista/vacía, fila no-dict.
</deliverable>

<deliverable id="3" file="src/factory_etl/extractor.py" action="incluir-helper">
`_validate_required_columns(rows, qdef) -> None`

- Carga `qdef.schema_path` una sola vez (JSON con array `columns` y flag `required`).
- Construye `required = {c["name"] for c in schema["columns"] if c.get("required")}`.
- Si alguna fila **omite** alguna clave requerida → `raise SchemaValidationError(missing_columns=..., row_index=...)`.
- Columnas extra (drift): **no bloquean**; emitir `log_event(event_type="SCHEMA_DRIFT", extras={"extras_cols": [...]})` **una vez** por batch (no por fila).
- Nueva excepción: `SchemaValidationError` en `src/factory_etl/errors.py`.
</deliverable>

<deliverable id="4" file="src/factory_etl/extractor.py" action="incluir-helper">
`_enrich_rows(rows, *, entity, source_empresa, dt, run_id, batch_id_str, sql_hash_hex, payload_hash_hex, query_version) -> list[dict[str, object]]`

Para cada fila retorna un **dict nuevo** (no mutar el original) con:

1. Todas las columnas de negocio originales.
2. Las 9 columnas de sistema con prefijo `_`:
   - `_source_empresa` (str)
   - `_query_id` (str)                     # sin la versión
   - `_query_version` (str)                # `qdef.version`
   - `_query_sql_hash` (str)               # `ids.sql_hash(sql_rendered)`
   - `_run_id` (str)
   - `_lote_id` (str)                      # == `computed_batch_id`
   - `_payload_hash` (str)                 # `http.payload_hash`
   - `_ingested_at` (str)                  # `datetime.now(UTC).isoformat(timespec="microseconds")`
   - `_row_hash` (str)                     # `ids.row_hash(v for _, v in sorted(row.items()))` calculado **antes** de añadir columnas `_*`

Reglas:
- Si una fila trae ya una clave que empieza con `_` → `raise ValueError("column collision: source row already has system column '...'")`. Esto es un fallo del contrato, no de datos.
- `_ingested_at` **debe** ser el mismo timestamp para todas las filas del mismo batch (calcularlo una vez fuera del loop).
- Orden de claves irrelevante (JSONL usa `sort_keys=True` en writer).
</deliverable>

<deliverable id="5" file="src/factory_etl/control_tables.py" action="ampliar">
Añadir soporte para `etl_events`:

```python
_TABLE_EVENTS = "etl_events"

def log_event(
    self,
    *,
    run_id: str,
    event_type: str,                      # "DUPLICATE_SKIPPED" | "QUARANTINED_EMPTY" | "QUARANTINED_SCHEMA" | "SCHEMA_DRIFT" | "BATCH_STAGED" | "BATCH_PROMOTED" | "BATCH_SUCCESS" | "BATCH_FAILED"
    phase: str,                           # "extract" | "parse" | "validate" | "stage" | "promote" | "finalize"
    batch_id: str | None = None,
    entity: str | None = None,
    duration_ms: int | None = None,
    extras: dict[str, Any] | None = None,
) -> None: ...
```

- Shape del row: `{event_id (uuid4), run_id, batch_id, entity, phase, event_type, duration_ms, extras (json string), inserted_at (ISO UTC)}`.
- `row_ids=[event_id]` para idempotencia.
- `extras` se serializa con `json.dumps(sort_keys=True, default=str)`.
- No loguear `extras` completo si es grande (>2KB): truncar con marca `"__truncated": true`.

Actualizar `ControlTablesProtocol` en `protocols.py` con la nueva firma.
</deliverable>

<deliverable id="6" file="src/factory_etl/cli.py" action="reemplazar-comando-run-por-run-batch">
Comando funcional `run-batch`:

```
factory-etl run-batch \
    --query-id articulos_v1 \
    --source-empresa tinito \
    --dt 2026-07-24 \
    [--run-id <uuid>] \
    [--parameter key=value ...]
```

Flujo:

1. `settings = Settings()`.
2. `configure_logging(env=settings.env)`.
3. `run_id = run_id or ids.new_run_id()`.
4. `extractor = build_extractor(settings)`  (composition root).
5. `control.start_run(run_id=run_id, extras={"query_id":..., "source_empresa":..., "dt":..., "cli_version": __version__})`.
6. `try: outcome = extractor.run_batch(...)`
   `except Exception as exc: control.finish_run(run_id, status=RunStatus.FAILED, error=type(exc).__name__)` y `raise typer.Exit(code=1)`.
7. Al terminar: `control.finish_run(run_id, status=RunStatus.SUCCESS, extras={"batch_id": outcome.batch_id, "final_status": outcome.status})`.
8. Emitir a stdout `json.dumps(dataclasses.asdict(outcome), sort_keys=True)`.
9. Exit code: `0` si `status ∈ {SUCCESS, SKIPPED_DUPLICATE, QUARANTINED}`, `1` si `FAILED` o excepción.

**Nunca** loguear el mensaje de la excepción tal cual (puede contener detalles internos). Loguear solo `type(exc).__name__` y un `error_id` (uuid corto) para correlacionar con el evento en BigQuery.
</deliverable>

<deliverable id="7" file="src/factory_etl/errors.py" action="ampliar">
Añadir `SchemaValidationError(Exception)` con atributos `missing_columns: frozenset[str]` y `row_index: int`.
</deliverable>

<deliverable id="8" file="tests/unit/" action="crear-o-ampliar">
Cobertura mínima nueva:

- `test_extractor_enrichment.py`
  - 9 columnas `_*` presentes en cada fila.
  - `_row_hash` idéntico ante mismos datos, distinto ante cambio de una celda.
  - `_ingested_at` idéntico entre todas las filas del mismo batch.
  - Colisión `_x` en fila de origen → `ValueError`.

- `test_extractor_schema.py`
  - Filas con todas las requeridas → sigue.
  - Falta una requerida → cuarentena `SCHEMA_MISMATCH`, `register_batch(status=QUARANTINED)`, `log_event` con `QUARANTINED_SCHEMA`.
  - Columna extra → sigue, pero `log_event` con `SCHEMA_DRIFT` una sola vez.

- `test_control_tables_events.py`
  - `log_event` inserta 1 fila con `event_id` como `row_ids`.
  - `extras > 2KB` se trunca con marca.

- `test_cli_run_batch.py`
  - Usa `typer.testing.CliRunner`.
  - Fake `Extractor` inyectado vía monkeypatch de `build_extractor`.
  - Camino feliz → exit 0, stdout JSON con `status=SUCCESS`.
  - Excepción → exit 1, `finish_run(FAILED)` invocado.

Todos los tests deben poder correr sin variables de entorno reales (usar `monkeypatch.setenv("FACTORY_ETL_GCP_PROJECT","test")` etc.).
</deliverable>
</deliverables>

<constraints>
- **Protocol injection only**: el extractor y el CLI **no** importan clases concretas de `google-cloud-*`, `httpx`, `bigquery`. Todo pasa por `bootstrap`.
- **Sin estado global mutable**: nada de `_client` a nivel de módulo. Todo instanciado en composition root.
- **Seguridad**:
  - Nunca loguear `payload_bytes`, filas crudas, tokens ni URLs con querystrings sensibles.
  - `bandit` limpio; usar `# noqa: S608  # nosec B608` **solo** en SQL de control con `f"..."` de literales de dataset/tabla (ya establecido).
  - `pip-audit --disable-pip` limpio.
- **Determinismo**:
  - `json.dumps` siempre con `sort_keys=True`.
  - Ningún `datetime.now()` dentro de loops que produzcan datos persistidos.
- **Style**:
  - `ruff format` y `ruff check` limpios.
  - `pyright` en modo `strict` limpio; sin `# type: ignore` salvo comentario justificando el porqué.
  - Docstrings en español (siguiendo el repo).
  - Cero comentarios `TODO` sin issue asociado.
- **Tests**:
  - `pytest --cov-fail-under=70` sigue verde; el extractor y CLI deben quedar por encima de 90 % de cobertura de línea.
  - Fakes en memoria implementados con `@dataclass` o clase simple que satisface el Protocol estructural; nada de `unittest.mock.Mock` para el core del extractor.
</constraints>

<workflow>
Orden sugerido para minimizar rework:

1. Ampliar `errors.py` con `SchemaValidationError`.
2. Ampliar `control_tables.py` con `log_event` + actualizar `protocols.py`.
3. Escribir tests de `log_event` y hacerlos pasar.
4. Escribir `extractor.py` completo (BatchOutcome, Extractor, helpers).
5. Tests de enrichment + schema validation.
6. Actualizar `bootstrap.py` si cambia la firma del extractor.
7. Reescribir `cli.py` con `run-batch`.
8. Tests de CLI con `CliRunner`.
9. Ejecutar la batería de validación completa (siguiente sección).
10. Commit único con mensaje: `feat(fase1-etapa4): E2E batch extractor hasta bronze (system cols, schema, events, CLI)`.
</workflow>

<validation>
Antes de reportar "hecho", ejecutar en este orden y **todos** deben pasar:

```powershell
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
uv sync
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run bandit -r src -c pyproject.toml
uv run pip-audit --disable-pip
uv run pytest -q
```

Verificaciones manuales adicionales:

1. `uv run factory-etl run-batch --help` muestra las 4 opciones esperadas.
2. `grep -R "from google.cloud" src/factory_etl/extractor.py src/factory_etl/cli.py` → **sin resultados**.
3. `grep -R "print(" src/factory_etl/` → solo en el `typer.echo` del CLI (no en extractor).
4. `grep -R "TODO" src/factory_etl/` → cero coincidencias sin issue.
5. Coverage report: `extractor.py ≥ 90 %`, `cli.py ≥ 85 %`.
</validation>

<definition_of_done>
- Al ejecutar `factory-etl run-batch --query-id articulos_v1 --source-empresa <empresa-permitida> --dt 2026-07-24` con `Settings` válidos y credenciales dummy inyectadas, el extractor:
  - Renderiza SQL, llama `runner`, dedup en control, valida schema, enriquece con las 9 `_*`, escribe a `_staging/`, promueve, registra WRITTEN y SUCCESS, emite eventos en `etl_events`.
  - En caso de payload inválido / vacío / schema mismatch: vuelca a `quarantine_bucket`, registra QUARANTINED, emite evento correspondiente, exit code 0.
  - En caso de excepción no controlada: `finish_run(FAILED, error=<ExceptionType>)`, exit code 1, sin fuga de PII en stderr/logs.
- Idempotencia verificada: segunda ejecución con mismos inputs → `SKIPPED_DUPLICATE`, no reescribe GCS.
- CI verde en GitHub Actions.
- El commit **no** modifica `main.tf` ni ningún `.tf`; toda infraestructura queda para tarea posterior.
</definition_of_done>

<anti_patterns>
Evitar explícitamente:

- Importar `google.cloud.bigquery` fuera de `control_tables.py` o `secrets.py`.
- Mutar el dict de la fila original en `_enrich_rows`.
- Calcular `_row_hash` **después** de añadir las columnas `_*` (contaminaría el hash).
- Usar `logging.getLogger`; solo `structlog.get_logger`.
- Serializar `payload_bytes` en cualquier evento o log.
- Reintentar 4xx en `query_runner.py` (ya resuelto con `_TransientServerError`; no revertir).
- Añadir `--force` / `--overwrite` al CLI: la idempotencia es por diseño, no opcional.
- Escribir tests que hagan I/O real (red, disco fuera de `tmp_path`, BigQuery real).
</anti_patterns>

<final_instruction>
Ejecuta el `<workflow>` completo, deja todos los checks de `<validation>` en verde,
crea **un único commit** que cierre Etapa 4 y confirma el resultado citando:

- Nombres de archivos tocados.
- Conteo de tests nuevos y cobertura de `extractor.py` y `cli.py`.
- Salida de `uv run factory-etl run-batch --help`.
- SHA del commit creado.

Si algo del `<validation>` falla y no puedes resolverlo en 3 intentos, **detente**
y reporta el bloqueo con el error exacto — no bypasses checks (`--no-verify`, `# type: ignore`, `# noqa` sin justificación).
</final_instruction>
