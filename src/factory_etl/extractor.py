"""Orquestador de un batch: catalogo -> render -> HTTP -> validar -> Bronze.

Este modulo es el corazon del ETL. Une los servicios inyectados y
implementa el flujo descrito en las "Reglas de aterrizaje en Bronze" del
plan Fase 1:

1. Resolver ``QueryDefinition`` desde el catalogo.
2. Renderizar SQL con parametros validados.
3. Consultar FactorySoft y calcular ``payload_hash``.
4. Calcular ``batch_id`` deterministico.
5. Consultar ``etl_batches``: si ya existe con mismo hash, terminar SKIPPED.
6. Escribir a ``_staging/``.
7. Validar contra el schema JSON.
8. Registrar batch WRITTEN.
9. Promover a prefijo final.
10. Registrar batch SUCCESS.

El ``Extractor`` depende **exclusivamente de protocolos** (ver
``factory_etl.protocols``), no de implementaciones concretas.

Implementacion pendiente: Fase 1 Etapa 4.
"""

from __future__ import annotations

from dataclasses import dataclass

from factory_etl.config import Settings
from factory_etl.protocols import (
    BronzeWriterProtocol,
    ControlTablesProtocol,
    QuarantineProtocol,
    QueryRunnerProtocol,
)


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
    """

    settings: Settings
    runner: QueryRunnerProtocol
    writer: BronzeWriterProtocol
    control: ControlTablesProtocol
    quarantine: QuarantineProtocol

    def run_batch(
        self,
        *,
        query_id: str,  # noqa: ARG002
        source_empresa: str,  # noqa: ARG002
        dt: str,  # noqa: ARG002
        run_id: str,  # noqa: ARG002
    ) -> BatchOutcome:
        """Ejecuta un batch completo end-to-end."""
        raise NotImplementedError("Extractor.run_batch pendiente (Fase 1 Etapa 4).")
