"""Protocolos estructurales para los servicios inyectados en el ETL.

Estos ``typing.Protocol`` son la definicion formal del contrato que cada
servicio debe cumplir. El ``Extractor`` y todos los orquestadores dependen
**exclusivamente** de estos protocolos, no de las implementaciones
concretas (Dependency Inversion Principle).

Beneficios concretos:

- Tests pueden inyectar fakes/stubs sin heredar de ninguna clase base.
- Nuevas implementaciones (por ejemplo un ``FileSystemBronzeWriter`` para
  desarrollo local) solo necesitan satisfacer la firma; ningun import
  cruzado con las clases GCS/BQ reales.
- El contrato queda documentado en un solo archivo, revisable como pieza
  aislada de arquitectura.

Convencion: los protocolos declaran solo los metodos publicos que el
consumidor externo (Extractor / CLI) invoca. Metodos internos de cada
servicio quedan fuera del contrato.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from factory_etl.bronze_writer import WriteResult
    from factory_etl.control_tables import BatchStatus, RunStatus
    from factory_etl.query_runner import HttpResult
    from factory_etl.quarantine import QuarantineReason


class SecretResolverProtocol(Protocol):
    """Resuelve nombres logicos de secretos a su valor actual."""

    def get(self, secret_name: str) -> str:
        """Devuelve el valor del secreto. Lanza si no existe o no hay permisos."""
        ...


class QueryRunnerProtocol(Protocol):
    """Ejecuta un SQL renderizado contra el transporte configurado."""

    def execute(self, *, sql_rendered: str, source_empresa: str) -> HttpResult:
        """Envia la consulta y devuelve el payload crudo con su hash."""
        ...


class BronzeWriterProtocol(Protocol):
    """Escritor atomico de Bronze con separacion staging / final."""

    def stage(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
        rows: list[dict[str, object]],
    ) -> WriteResult:
        """Escribe el batch a ``_staging/`` sin publicar aun."""
        ...

    def promote(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
    ) -> str:
        """Mueve los objetos desde ``_staging/`` al prefijo final. Devuelve el URI."""
        ...


class ControlTablesProtocol(Protocol):
    """Persistencia de eventos de auditoria en tablas de control."""

    def start_run(self, *, run_id: str, extras: dict[str, Any] | None = None) -> None:
        """Registra el inicio de una corrida (INSERT etl_runs status=RUNNING)."""
        ...

    def finish_run(
        self,
        *,
        run_id: str,
        status: RunStatus,
        error: str | None = None,
    ) -> None:
        """Cierra la corrida (UPDATE etl_runs con status final y ended_at)."""
        ...

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
        """Inserta o actualiza una fila en etl_batches."""
        ...

    def find_batch_by_hash(
        self,
        *,
        source_empresa: str,
        query_id: str,
        dt: str,
        payload_hash: str,
    ) -> str | None:
        """Devuelve el batch_id existente con exito para ese hash, si existe."""
        ...


class QuarantineProtocol(Protocol):
    """Aterrizaje de payloads sospechosos fuera de Bronze."""

    def dump(
        self,
        *,
        run_id: str,
        entity: str,
        source_empresa: str,
        dt: str,
        payload_bytes: bytes,
        reason: QuarantineReason,
    ) -> str:
        """Escribe el payload en cuarentena y devuelve el URI."""
        ...
