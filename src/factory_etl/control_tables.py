"""Escritura de tablas de control en BigQuery.

Tablas destino en ``factory_control_<ambiente>``:

- ``etl_runs``: una fila por corrida completa.
- ``etl_batches``: una fila por (entidad, empresa, dt, run_id).
- ``etl_events``: eventos internos con fase y duracion.
- ``data_quality_results``: resultados de tests de calidad por batch.

Todas las escrituras usan streaming inserts (``insert_rows_json``) para
minimizar latencia. Los inserts son idempotentes por ``insertId`` derivado
del ``batch_id`` / ``run_id`` — dos llamadas con el mismo id son deduplicadas
por BigQuery en la ventana de 1 minuto.

Las lecturas (``find_batch_by_hash``) usan queries parametrizados para
evitar inyeccion; ``payload_hash`` en particular llega de una fuente
externa (HTTP body de FactorySoft) y no puede concatenarse en el SQL.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from factory_etl.config import Settings

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable

    from google.cloud.bigquery import QueryJobConfig


class _BigQueryClient(Protocol):
    """Subset del SDK google-cloud-bigquery que consumimos. Inyectable en tests."""

    def insert_rows_json(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        row_ids: list[str] | None = ...,
    ) -> list[dict[str, Any]]: ...  # pragma: no cover

    def query(
        self,
        query: str,
        *,
        job_config: QueryJobConfig | None = ...,
    ) -> Iterable[Any]: ...  # pragma: no cover


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class BatchStatus(StrEnum):
    WRITTEN = "written"
    SUCCESS = "success"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    QUARANTINED = "quarantined"


class ControlTablesError(Exception):
    """Error al escribir/consultar tablas de control."""


class ControlTables:
    """Interfaz para escribir eventos de auditoria."""

    _TABLE_RUNS = "etl_runs"
    _TABLE_BATCHES = "etl_batches"

    def __init__(
        self,
        settings: Settings,
        *,
        client: _BigQueryClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._project = settings.gcp_project
        self._dataset = settings.control_dataset

    # -- runs -----------------------------------------------------------------

    def start_run(self, *, run_id: str, extras: dict[str, Any] | None = None) -> None:
        """Registra el inicio de una corrida (status=RUNNING).

        Idempotente: dos ``start_run`` con el mismo ``run_id`` en < 1 min
        se deduplican en BigQuery via ``insertId``.
        """
        row: dict[str, Any] = {
            "run_id": run_id,
            "status": RunStatus.RUNNING.value,
            "started_at": _now_iso(),
            "ended_at": None,
            "error": None,
            "extras": extras or {},
        }
        self._insert(self._table_runs(), [row], row_ids=[run_id])

    def finish_run(
        self,
        *,
        run_id: str,
        status: RunStatus,
        error: str | None = None,
    ) -> None:
        """Cierra la corrida con el status final y timestamp.

        Implementacion: inserta una fila con ``ended_at`` que la vista
        materializada consumira via ``ARRAY_AGG(... ORDER BY inserted_at DESC)[0]``.
        (Este patron evita ``UPDATE`` en tablas append-only.)
        """
        row: dict[str, Any] = {
            "run_id": run_id,
            "status": status.value,
            "started_at": None,
            "ended_at": _now_iso(),
            "error": error,
            "extras": {},
        }
        # row_id distinto al de start_run para permitir la segunda insercion.
        self._insert(self._table_runs(), [row], row_ids=[f"{run_id}:finish"])

    # -- batches --------------------------------------------------------------

    def register_batch(
        self,
        *,
        batch_id: str,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
        status: BatchStatus,
        record_count: int | None = None,
        object_uri: str | None = None,
        payload_hash: str | None = None,
    ) -> None:
        """Inserta una fila en ``etl_batches`` con el estado del batch."""
        row: dict[str, Any] = {
            "batch_id": batch_id,
            "run_id": run_id,
            "entity": entity,
            "source_empresa": source_empresa,
            "dt": dt,
            "status": status.value,
            "record_count": record_count,
            "object_uri": object_uri,
            "payload_hash": payload_hash,
            "inserted_at": _now_iso(),
        }
        # row_id: batch_id + status para permitir progresion WRITTEN -> SUCCESS.
        self._insert(
            self._table_batches(),
            [row],
            row_ids=[f"{batch_id}:{status.value}"],
        )

    def find_batch_by_hash(
        self,
        *,
        source_empresa: str,
        query_id: str,
        dt: str,
        payload_hash: str,
    ) -> str | None:
        """Devuelve el ``batch_id`` de un batch previo con el mismo hash.

        Solo se consideran batches con status ``SUCCESS`` (o ``WRITTEN``
        promovido). Usa query parametrizado para evitar inyeccion en
        ``payload_hash`` y demas argumentos que llegan de fuentes externas.
        """
        # Import diferido para no arrastrar la dep en tests.
        from google.cloud import bigquery  # noqa: PLC0415

        # S608 no aplica: los unicos valores interpolados en el template son
        # `self._project`, `self._dataset` y la constante `self._TABLE_BATCHES`.
        # Ninguno viene de input externo; todos son de configuracion controlada
        # via env-vars validadas por pydantic. Los parametros de usuario
        # (payload_hash, source_empresa, entity, dt) usan @named-parameters de
        # BigQuery.
        sql = f"""
            SELECT batch_id
            FROM `{self._project}.{self._dataset}.{self._TABLE_BATCHES}`
            WHERE payload_hash = @payload_hash
              AND source_empresa = @source_empresa
              AND entity = @entity
              AND dt = @dt
              AND status IN ('success', 'written')
            ORDER BY inserted_at DESC
            LIMIT 1
        """  # noqa: S608  # nosec B608
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("payload_hash", "STRING", payload_hash),
                bigquery.ScalarQueryParameter("source_empresa", "STRING", source_empresa),
                bigquery.ScalarQueryParameter("entity", "STRING", query_id),
                bigquery.ScalarQueryParameter("dt", "STRING", dt),
            ]
        )

        rows = self._get_client().query(sql, job_config=job_config)
        for row in rows:
            # row soporta acceso por indice y por atributo; usamos indice
            # para no depender del row-mapper concreto.
            return str(row[0])
        return None

    # -- helpers privados -----------------------------------------------------

    def _insert(
        self,
        table_fqn: str,
        rows: list[dict[str, Any]],
        *,
        row_ids: list[str] | None = None,
    ) -> None:
        errors = self._get_client().insert_rows_json(table_fqn, rows, row_ids=row_ids)
        if errors:
            # BigQuery devuelve una lista de errores por-fila; no la loguearemos
            # tal cual porque puede contener contenido del row (que puede tener
            # PII). Solo el conteo.
            raise ControlTablesError(
                f"insert_rows_json fallo en {table_fqn}: {len(errors)} error(es)"
            )

    def _table_runs(self) -> str:
        return f"{self._project}.{self._dataset}.{self._TABLE_RUNS}"

    def _table_batches(self) -> str:
        return f"{self._project}.{self._dataset}.{self._TABLE_BATCHES}"

    def _get_client(self) -> _BigQueryClient:
        if self._client is None:
            from google.cloud import bigquery  # noqa: PLC0415

            # bigquery.Client tiene una firma real mas amplia que nuestro
            # Protocol (parameter name mismatch en insert_rows_json). Es
            # estructuralmente compatible en runtime; el cast es solo para
            # el type checker.
            self._client = cast(
                "_BigQueryClient", bigquery.Client(project=self._settings.gcp_project)
            )
        return self._client


def _now_iso() -> str:
    """Timestamp UTC en formato ISO 8601 (BigQuery TIMESTAMP-friendly)."""
    return datetime.now(UTC).isoformat()
