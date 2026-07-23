"""Composition Root: arma el grafo de dependencias del ETL.

Este modulo es el **unico lugar** de la aplicacion donde se instancian
las clases concretas y se cablean entre si. Todos los demas modulos
dependen de ``Protocol``s (ver ``factory_etl.protocols``).

Beneficio:

- El CLI no importa clases concretas, solo pide un ``Extractor`` armado.
- Los tests de integracion pueden proveer un composition root alternativo
  con fakes o dobles de prueba, sin tocar ``cli.py`` ni ``extractor.py``.
- Un futuro backend distinto (por ejemplo, ``S3BronzeWriter``) se enchufa
  aqui sin modificar codigo existente.

Este archivo es un *seam* de arquitectura: los cambios deben ser
conscientes y revisados en PR.
"""

from __future__ import annotations

from factory_etl.bronze_writer import BronzeWriter
from factory_etl.config import Settings
from factory_etl.control_tables import ControlTables
from factory_etl.extractor import Extractor
from factory_etl.quarantine import Quarantine
from factory_etl.query_runner import QueryRunner
from factory_etl.secrets import SecretResolver


def build_extractor(settings: Settings) -> Extractor:
    """Compone el grafo completo y devuelve un ``Extractor`` listo para usar.

    Cada dependencia se asigna a una variable con tipo ``Protocol`` para
    que el type checker verifique la conformidad estructural en el mismo
    punto de wiring. Si una implementacion concreta deja de satisfacer su
    contrato, el error surge aqui, no en produccion.
    """

    from factory_etl.protocols import (
        BronzeWriterProtocol,
        ControlTablesProtocol,
        QuarantineProtocol,
        QueryRunnerProtocol,
        SecretResolverProtocol,
    )

    secrets: SecretResolverProtocol = SecretResolver(settings)
    runner: QueryRunnerProtocol = QueryRunner(settings, secrets)
    writer: BronzeWriterProtocol = BronzeWriter(settings)
    control: ControlTablesProtocol = ControlTables(settings)
    quarantine: QuarantineProtocol = Quarantine(settings)

    return Extractor(
        settings=settings,
        runner=runner,
        writer=writer,
        control=control,
        quarantine=quarantine,
    )
