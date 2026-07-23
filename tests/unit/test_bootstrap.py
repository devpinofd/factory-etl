"""Tests del composition root.

Verifican que ``build_extractor`` devuelve un ``Extractor`` con todas las
dependencias cableadas, y que cada dependencia satisface el ``Protocol``
correspondiente por asignacion (structural typing).
"""

from __future__ import annotations

from factory_etl.bootstrap import build_extractor
from factory_etl.config import Settings
from factory_etl.extractor import Extractor
from factory_etl.protocols import (
    BronzeWriterProtocol,
    ControlTablesProtocol,
    QuarantineProtocol,
    QueryRunnerProtocol,
)


def _make_settings() -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bucket",
        control_dataset="test_control",
    )


class TestBuildExtractor:
    def test_returns_extractor_instance(self) -> None:
        result = build_extractor(_make_settings())
        assert isinstance(result, Extractor)

    def test_wires_all_dependencies(self) -> None:
        extractor = build_extractor(_make_settings())
        assert extractor.settings is not None
        assert extractor.runner is not None
        assert extractor.writer is not None
        assert extractor.control is not None
        assert extractor.quarantine is not None

    def test_dependencies_satisfy_protocols(self) -> None:
        """Asignacion a variables tipadas como Protocol; pyright valida."""
        extractor = build_extractor(_make_settings())
        runner: QueryRunnerProtocol = extractor.runner
        writer: BronzeWriterProtocol = extractor.writer
        control: ControlTablesProtocol = extractor.control
        quarantine: QuarantineProtocol = extractor.quarantine
        assert runner is extractor.runner
        assert writer is extractor.writer
        assert control is extractor.control
        assert quarantine is extractor.quarantine
