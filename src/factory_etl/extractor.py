"""Orquestador de un batch: catalogo -> render -> HTTP -> validar -> Bronze.

Este modulo es el corazon del ETL. Une los servicios inyectados y
implementa el flujo descrito en las "Reglas de aterrizaje en Bronze" del
plan Fase 1:

1. Resolver ``QueryDefinition`` desde el catalogo.
2. Renderizar SQL con parametros validados.
3. Consultar FactorySoft y calcular ``payload_hash``.
4. Consultar ``etl_batches``: si ya existe con mismo hash, terminar SKIPPED.
5. Parsear el payload (``d.laTablas[0]`` o ``datos.laTablas[0]``) fielmente.
6. Si vacio y ``reject_empty``: cuarentena + terminar QUARANTINED.
7. Calcular ``batch_id`` deterministico.
8. Escribir a ``_staging/``.
9. Registrar batch WRITTEN.
10. Promover a prefijo final.
11. Registrar batch SUCCESS.

El ``Extractor`` depende **exclusivamente de protocolos** (ver
``factory_etl.protocols``), no de implementaciones concretas. Esto hace
que los tests puedan usar fakes en memoria sin herencia.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from factory_etl import ids
from factory_etl.config import Settings
from factory_etl.control_tables import BatchStatus
from factory_etl.errors import InvalidPayloadError, SchemaValidationError
from factory_etl.factory_queries.catalog import get as get_query_definition
from factory_etl.factory_queries.models import QueryDefinition
from factory_etl.factory_queries.renderer import render as render_sql
from factory_etl.protocols import (
    BronzeWriterProtocol,
    ControlTablesProtocol,
    QuarantineProtocol,
    QueryRunnerProtocol,
)
from factory_etl.quarantine import QuarantineReason


@dataclass(frozen=True)
class BatchOutcome:
    """Resultado de un batch."""

    batch_id: str
    status: str
    object_uri: str | None
    record_count: int | None
    was_duplicate: bool


@dataclass
class Extractor:
    """Servicio de orquestacion.

    Todas las dependencias se reciben por constructor tipadas contra
    ``Protocol``. Esto permite inyectar fakes en tests sin herencia y
    hace explicito el contrato que cada servicio debe cumplir.

    :param settings: configuracion inmutable (proyecto GCP, buckets, etc).
    :param runner: cliente HTTP hacia FactorySoft.
    :param writer: escritor atomico de Bronze.
    :param control: registro de tablas de control en BigQuery.
    :param quarantine: destino de payloads sospechosos.
    """

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
        dt: str,
        run_id: str,
        parameter_values: dict[str, object] | None = None,
    ) -> BatchOutcome:
        """Ejecuta un batch end-to-end.

        :param query_id: identificador de la consulta en el catalogo
            (ej. ``articulos_v1``).
        :param source_empresa: empresa FactorySoft (ej. ``tinito``).
        :param dt: fecha logica de la corrida, ``YYYY-MM-DD``.
        :param run_id: UUID de la corrida (ya iniciada por el orquestador padre).
        :param parameter_values: valores de los parametros declarados por la
            consulta. Vacio si la consulta no tiene parametros.
        :returns: :class:`BatchOutcome` con el estado final del batch.
        :raises QueryNotFoundError, CompanyNotAllowedError, RenderError,
            TransportError, AuthenticationError, ControlTablesError:
            cualquier error del dominio se propaga tal cual (el caller
            decide si finish_run(FAILED) o reintenta).
        """
        qdef = get_query_definition(query_id, source_empresa=source_empresa)
        # NOTA: en el catalogo actual `query_id` coincide con `entity` (ej.
        # ``articulos_v1``). Se conserva la variable separada por si en el
        # futuro el catalogo distingue entre query_id (versionado) y entity
        # (nombre logico).
        entity = qdef.query_id

        sql_template = qdef.read_sql()
        sql_rendered = render_sql(
            sql_template,
            qdef.parameters,
            parameter_values or {},
        )
        sql_hash_hex = ids.sql_hash(sql_rendered)

        http_result = self.runner.execute(
            sql_rendered=sql_rendered,
            source_empresa=source_empresa,
        )

        # Deduplicacion por hash: si ya existe un batch exitoso con este
        # payload, no reescribimos Bronze. Defensa contra reejecucion.
        existing_batch_id = self.control.find_batch_by_hash(
            source_empresa=source_empresa,
            query_id=entity,
            dt=dt,
            payload_hash=http_result.payload_hash,
        )
        if existing_batch_id is not None:
            self.control.log_event(
                run_id=run_id,
                event_type="DUPLICATE_SKIPPED",
                phase="validate",
                batch_id=existing_batch_id,
                entity=entity,
            )
            return BatchOutcome(
                batch_id=existing_batch_id,
                status=BatchStatus.SKIPPED_DUPLICATE.value,
                object_uri=None,
                record_count=None,
                was_duplicate=True,
            )

        # Parseo del payload. Cualquier fallo estructural va a cuarentena.
        try:
            rows = _parse_payload(http_result.payload_bytes)
        except InvalidPayloadError:
            return self._quarantine_and_register(
                run_id=run_id,
                entity=entity,
                source_empresa=source_empresa,
                dt=dt,
                payload_bytes=http_result.payload_bytes,
                payload_hash=http_result.payload_hash,
                reason=QuarantineReason.SCHEMA_MISMATCH,
                event_type="QUARANTINED_SCHEMA",
                event_phase="parse",
                event_extras=None,
            )

        # Payload vacio: cuarentena si la consulta asi lo declara.
        if not rows and qdef.reject_empty:
            return self._quarantine_and_register(
                run_id=run_id,
                entity=entity,
                source_empresa=source_empresa,
                dt=dt,
                payload_bytes=http_result.payload_bytes,
                payload_hash=http_result.payload_hash,
                reason=QuarantineReason.EMPTY_REJECTED,
                event_type="QUARANTINED_EMPTY",
                event_phase="validate",
                event_extras=None,
            )

        # Validacion de esquema: filas incompletas van a cuarentena; columnas
        # extra solo emiten un evento de SCHEMA_DRIFT una unica vez.
        try:
            _validate_required_columns(
                rows,
                qdef,
                control=self.control,
                run_id=run_id,
                entity=entity,
            )
        except SchemaValidationError as exc:
            return self._quarantine_and_register(
                run_id=run_id,
                entity=entity,
                source_empresa=source_empresa,
                dt=dt,
                payload_bytes=http_result.payload_bytes,
                payload_hash=http_result.payload_hash,
                reason=QuarantineReason.SCHEMA_MISMATCH,
                event_type="QUARANTINED_SCHEMA",
                event_phase="validate",
                event_extras={
                    "row_index": exc.row_index,
                    "missing_columns": sorted(exc.missing_columns),
                },
            )

        # A partir de aqui es un batch valido.
        computed_batch_id = ids.batch_id(
            source_empresa=source_empresa,
            query_id=entity,
            dt=dt,
            payload_hash_hex=http_result.payload_hash,
        )

        enriched_rows = _enrich_rows(
            rows,
            entity=entity,
            source_empresa=source_empresa,
            run_id=run_id,
            batch_id_str=computed_batch_id,
            sql_hash_hex=sql_hash_hex,
            payload_hash_hex=http_result.payload_hash,
            query_version=qdef.version,
        )

        write_result = self.writer.stage(
            run_id=run_id,
            entity=entity,
            source_empresa=source_empresa,
            dt=dt,
            rows=enriched_rows,
        )

        # WRITTEN: objeto ya en _staging/. Si algo falla en promote queda la
        # marca de "escrito pero no promovido" para diagnostico.
        self.control.register_batch(
            batch_id=computed_batch_id,
            run_id=run_id,
            entity=entity,
            source_empresa=source_empresa,
            dt=dt,
            status=BatchStatus.WRITTEN,
            record_count=write_result.record_count,
            object_uri=write_result.object_uri,
            payload_hash=http_result.payload_hash,
        )
        self.control.log_event(
            run_id=run_id,
            event_type="BATCH_STAGED",
            phase="stage",
            batch_id=computed_batch_id,
            entity=entity,
        )

        final_uri = self.writer.promote(
            run_id=run_id,
            entity=entity,
            source_empresa=source_empresa,
            dt=dt,
        )
        self.control.log_event(
            run_id=run_id,
            event_type="BATCH_PROMOTED",
            phase="promote",
            batch_id=computed_batch_id,
            entity=entity,
        )

        self.control.register_batch(
            batch_id=computed_batch_id,
            run_id=run_id,
            entity=entity,
            source_empresa=source_empresa,
            dt=dt,
            status=BatchStatus.SUCCESS,
            record_count=write_result.record_count,
            object_uri=final_uri,
            payload_hash=http_result.payload_hash,
        )
        self.control.log_event(
            run_id=run_id,
            event_type="BATCH_SUCCESS",
            phase="finalize",
            batch_id=computed_batch_id,
            entity=entity,
        )

        return BatchOutcome(
            batch_id=computed_batch_id,
            status=BatchStatus.SUCCESS.value,
            object_uri=final_uri,
            record_count=write_result.record_count,
            was_duplicate=False,
        )

    def _quarantine_and_register(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
        payload_bytes: bytes,
        payload_hash: str,
        reason: QuarantineReason,
        event_type: str,
        event_phase: str,
        event_extras: dict[str, Any] | None,
    ) -> BatchOutcome:
        """Vuelca a cuarentena, registra el batch y emite el evento correspondiente."""
        quarantine_uri = self.quarantine.dump(
            run_id=run_id,
            entity=entity,
            source_empresa=source_empresa,
            dt=dt,
            payload_bytes=payload_bytes,
            reason=reason,
        )
        computed_batch_id = ids.batch_id(
            source_empresa=source_empresa,
            query_id=entity,
            dt=dt,
            payload_hash_hex=payload_hash,
        )
        self.control.register_batch(
            batch_id=computed_batch_id,
            run_id=run_id,
            entity=entity,
            source_empresa=source_empresa,
            dt=dt,
            status=BatchStatus.QUARANTINED,
            record_count=None,
            object_uri=quarantine_uri,
            payload_hash=payload_hash,
        )
        self.control.log_event(
            run_id=run_id,
            event_type=event_type,
            phase=event_phase,
            batch_id=computed_batch_id,
            entity=entity,
            extras=event_extras,
        )
        return BatchOutcome(
            batch_id=computed_batch_id,
            status=BatchStatus.QUARANTINED.value,
            object_uri=quarantine_uri,
            record_count=None,
            was_duplicate=False,
        )


def _parse_payload(payload_bytes: bytes) -> list[dict[str, object]]:
    """Extrae las filas del sobre de FactorySoft.

    El servicio admite dos formas de sobre:

    - ``{"d": {"laTablas": [[...filas...]]}}`` (nuevo)
    - ``{"datos": {"laTablas": [[...filas...]]}}`` (heredado)

    Se decodifica con ``utf-8-sig`` para tolerar el BOM que a veces envia
    el servidor. Cualquier discrepancia estructural (raiz no-objeto,
    ``laTablas`` ausente/malformado, filas no-dict) levanta
    :class:`InvalidPayloadError` y el caller lo enruta a cuarentena.

    :raises InvalidPayloadError: la respuesta no cumple el contrato.
    """
    try:
        document: Any = json.loads(payload_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidPayloadError("respuesta no es JSON UTF-8 valido") from exc

    if not isinstance(document, dict):
        raise InvalidPayloadError("raiz JSON no es un objeto")

    if document.get("llError"):
        raise InvalidPayloadError("FactorySoft reporto un error interno")

    root = document.get("d") or document.get("datos")
    if not isinstance(root, dict):
        raise InvalidPayloadError("no existe 'd' ni 'datos' en la raiz")

    tables = root.get("laTablas")
    if not isinstance(tables, list) or not tables:
        raise InvalidPayloadError("'laTablas' ausente o vacio")
    first_table = tables[0]
    if not isinstance(first_table, list):
        raise InvalidPayloadError("'laTablas[0]' no es lista")

    rows: list[dict[str, object]] = []
    for row in first_table:
        if not isinstance(row, dict):
            raise InvalidPayloadError("fila no-dict en laTablas[0]")
        # Normalizar claves a minusculas: eFactory devuelve Pascal_Case
        # (Tipo_Documento, Cod_Suc) pero los esquemas usan snake_case.
        rows.append({k.lower(): v for k, v in row.items()})
    return rows


@lru_cache(maxsize=64)
def _load_schema_columns(schema_path: str) -> tuple[frozenset[str], frozenset[str]]:
    """Lee ``columns`` del esquema y devuelve ``(required, known)``.

    - ``required``: nombres con ``required: true`` (fila que los omita va a
      cuarentena).
    - ``known``: todos los nombres declarados en el esquema. Cualquier
      columna en la fila fuera de este set dispara un evento
      ``SCHEMA_DRIFT`` (informativo, no bloquea).

    Cacheado por ruta: el esquema se empaqueta con el codigo y no cambia
    en runtime. ``frozenset`` para asegurar que ningun caller lo mute.
    """
    content = Path(schema_path).read_text(encoding="utf-8")
    document = json.loads(content)
    columns = document.get("columns", [])
    if not isinstance(columns, list):
        return frozenset(), frozenset()
    required: set[str] = set()
    known: set[str] = set()
    for entry in columns:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        known.add(name)
        if entry.get("required") is True:
            required.add(name)
    return frozenset(required), frozenset(known)


def _validate_required_columns(
    rows: list[dict[str, object]],
    qdef: QueryDefinition,
    *,
    control: ControlTablesProtocol,
    run_id: str,
    entity: str,
) -> None:
    """Verifica que cada fila contenga todas las columnas requeridas.

    - Si una fila omite columnas requeridas: levanta :class:`SchemaValidationError`
      con el indice y el conjunto de columnas faltantes (para cuarentena).
    - Si aparecen columnas no declaradas en el esquema (drift):
      emite **una unica** entrada ``SCHEMA_DRIFT`` con el listado ordenado
      y continua sin fallar.
    """
    schema_path = qdef.schema_path
    required, known = _load_schema_columns(str(schema_path))
    if not required and not known:
        return

    extras_seen: set[str] = set()
    for idx, row in enumerate(rows):
        row_keys = set(row.keys())
        missing = required - row_keys
        if missing:
            raise SchemaValidationError(
                missing_columns=frozenset(missing),
                row_index=idx,
            )
        extras_seen.update(row_keys - known)

    if extras_seen:
        control.log_event(
            run_id=run_id,
            event_type="SCHEMA_DRIFT",
            phase="validate",
            entity=entity,
            extras={"extra_columns": sorted(extras_seen)},
        )


def _enrich_rows(
    rows: list[dict[str, object]],
    *,
    entity: str,
    source_empresa: str,
    run_id: str,
    batch_id_str: str,
    sql_hash_hex: str,
    payload_hash_hex: str,
    query_version: str,
) -> list[dict[str, object]]:
    """Devuelve una nueva lista con las columnas de trazabilidad del lote.

    Columnas anadidas (todas con prefijo ``_``):

    - ``_ingested_at``: timestamp UTC unico para el batch entero, formateado
      con ``timespec="microseconds"`` para producir un string estable.
    - ``source_empresa``, ``_query_id``, ``_query_version``.
    - ``_query_sql_hash``, ``_run_id``, ``_lote_id``.
    - ``_payload_hash``.
    - ``_row_hash``: SHA-256 canonico de la fila **original** (sin las
      columnas ``_*``), calculado sobre los **valores** ordenados por
      clave. Estable para deduplicacion cruzada.

    La fecha logica ``dt`` **no** se persiste como columna de sistema
    (el spec define exactamente 9 columnas); solo aguas arriba se usa
    para el ``_lote_id`` (via ``batch_id_str``) y el particionado del
    bucket.

    :raises ValueError: si alguna fila trae una clave con prefijo ``_``,
        que colisionaria con las columnas de sistema.
    """
    ingested_at = datetime.now(UTC).isoformat(timespec="microseconds")
    enriched: list[dict[str, object]] = []
    for row in rows:
        for key in row:
            if key.startswith("_"):
                raise ValueError(f"la fila trae la clave reservada {key!r} con prefijo '_'")
        # Hash canonico: solo los valores, ordenados por clave. Estable ante
        # reordenamientos del backend y sin filtrar los nombres de columna.
        row_hash = ids.row_hash(v for _, v in sorted(row.items()))

        enriched_row: dict[str, object] = dict(row)
        enriched_row["_ingested_at"] = ingested_at
        enriched_row["source_empresa"] = source_empresa
        enriched_row["_query_id"] = entity
        enriched_row["_query_version"] = query_version
        enriched_row["_query_sql_hash"] = sql_hash_hex
        enriched_row["_run_id"] = run_id
        enriched_row["_lote_id"] = batch_id_str
        enriched_row["_payload_hash"] = payload_hash_hex
        enriched_row["_row_hash"] = row_hash
        enriched.append(enriched_row)
    return enriched


__all__ = [
    "BatchOutcome",
    "Extractor",
]
