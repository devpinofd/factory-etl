"""Tests de conformidad de los Protocols.

Estos tests verifican que:

1. Las implementaciones concretas satisfacen sus respectivos Protocols
   (structural typing por asignacion, sin herencia).
2. Fakes en memoria escritos ad-hoc tambien los satisfacen. Esto es la
   demostracion practica del beneficio de Dependency Inversion + Interface
   Segregation: los servicios se pueden mockear sin heredar de nada.

Si un cambio de firma en un Protocol rompe estos tests, el compromiso es
version mayor del paquete.
"""

from __future__ import annotations

from typing import Any

from factory_etl.bronze_writer import BronzeWriter, WriteResult
from factory_etl.config import Settings
from factory_etl.control_tables import BatchStatus, ControlTables, RunStatus
from factory_etl.protocols import (
    BronzeWriterProtocol,
    ControlTablesProtocol,
    QuarantineProtocol,
    QueryRunnerProtocol,
    SecretResolverProtocol,
)
from factory_etl.quarantine import Quarantine, QuarantineReason
from factory_etl.query_runner import HttpResult, QueryRunner
from factory_etl.secrets import SecretResolver


def _make_settings() -> Settings:
    """Settings minimo para instanciar los servicios concretos en tests."""
    return Settings(  # pyright: ignore[reportCallIssue]
        gcp_project="test-project",
        bronze_bucket="test-bucket",
        control_dataset="test_control",
    )


class TestConcreteImplementationsSatisfyProtocols:
    """Cada clase concreta se asigna a su Protocol sin quejas del type checker."""

    def test_secret_resolver(self) -> None:
        settings = _make_settings()
        impl: SecretResolverProtocol = SecretResolver(settings)
        assert impl is not None

    def test_query_runner(self) -> None:
        settings = _make_settings()
        secrets = SecretResolver(settings)
        impl: QueryRunnerProtocol = QueryRunner(settings, secrets)
        assert impl is not None

    def test_bronze_writer(self) -> None:
        impl: BronzeWriterProtocol = BronzeWriter(_make_settings())
        assert impl is not None

    def test_control_tables(self) -> None:
        impl: ControlTablesProtocol = ControlTables(_make_settings())
        assert impl is not None

    def test_quarantine(self) -> None:
        impl: QuarantineProtocol = Quarantine(_make_settings())
        assert impl is not None


class TestFakesSatisfyProtocols:
    """Fakes escritos sin heredar de nada satisfacen el mismo contrato."""

    def test_fake_secret_resolver(self) -> None:
        class FakeSecrets:
            def __init__(self, values: dict[str, str]) -> None:
                self._values = values

            def get(self, secret_name: str) -> str:
                return self._values[secret_name]

        impl: SecretResolverProtocol = FakeSecrets({"factory-api-key": "fake-key"})
        assert impl.get("factory-api-key") == "fake-key"

    def test_fake_query_runner(self) -> None:
        class FakeRunner:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload

            def execute(self, *, sql_rendered: str, source_empresa: str) -> HttpResult:  # noqa: ARG002
                return HttpResult(
                    payload_bytes=self._payload,
                    payload_hash="deadbeef" * 8,
                    status_code=200,
                    elapsed_ms=1,
                )

        impl: QueryRunnerProtocol = FakeRunner(b'{"d": {"laTablas": [[]]}}')
        result = impl.execute(sql_rendered="select 1", source_empresa="tinito")
        assert result.status_code == 200

    def test_fake_bronze_writer(self) -> None:
        class FakeWriter:
            def __init__(self) -> None:
                self.staged: list[dict[str, object]] = []

            def stage(
                self,
                *,
                run_id: str,  # noqa: ARG002
                entity: str,  # noqa: ARG002
                source_empresa: str,  # noqa: ARG002
                dt: str,  # noqa: ARG002
                rows: list[dict[str, object]],
            ) -> WriteResult:
                self.staged.extend(rows)
                return WriteResult(
                    object_uri="gs://fake/staging/",
                    record_count=len(rows),
                    byte_count=0,
                )

            def promote(
                self,
                *,
                run_id: str,
                entity: str,
                source_empresa: str,
                dt: str,
            ) -> str:
                return f"gs://fake/bronze/{entity}/source_empresa={source_empresa}/dt={dt}/run_id={run_id}/"

        impl: BronzeWriterProtocol = FakeWriter()
        result = impl.stage(
            run_id="r1",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            rows=[{"cod_art": "0001"}, {"cod_art": "0002"}],
        )
        assert result.record_count == 2

    def test_fake_control_tables(self) -> None:
        class FakeControl:
            def __init__(self) -> None:
                self.events: list[str] = []

            def start_run(self, *, run_id: str, extras: dict[str, Any] | None = None) -> None:  # noqa: ARG002
                self.events.append(f"start:{run_id}")

            def finish_run(
                self,
                *,
                run_id: str,
                status: RunStatus,
                error: str | None = None,  # noqa: ARG002
            ) -> None:
                self.events.append(f"finish:{run_id}:{status}")

            def register_batch(
                self,
                *,
                batch_id: str,
                run_id: str,  # noqa: ARG002
                entity: str,  # noqa: ARG002
                source_empresa: str,  # noqa: ARG002
                dt: str,  # noqa: ARG002
                status: BatchStatus,
                record_count: int | None = None,  # noqa: ARG002
                object_uri: str | None = None,  # noqa: ARG002
                payload_hash: str | None = None,  # noqa: ARG002
            ) -> None:
                self.events.append(f"batch:{batch_id}:{status}")

            def find_batch_by_hash(
                self,
                *,
                source_empresa: str,  # noqa: ARG002
                query_id: str,  # noqa: ARG002
                dt: str,  # noqa: ARG002
                payload_hash: str,  # noqa: ARG002
            ) -> str | None:
                return None

        impl: ControlTablesProtocol = FakeControl()
        impl.start_run(run_id="r1")
        impl.finish_run(run_id="r1", status=RunStatus.SUCCESS)
        assert impl.find_batch_by_hash(
            source_empresa="tinito",
            query_id="articulos_v1",
            dt="2026-07-22",
            payload_hash="x",
        ) is None

    def test_fake_quarantine(self) -> None:
        class FakeQuarantine:
            def dump(
                self,
                *,
                run_id: str,
                entity: str,
                source_empresa: str,
                dt: str,
                payload_bytes: bytes,  # noqa: ARG002
                reason: QuarantineReason,  # noqa: ARG002
            ) -> str:
                return f"gs://fake/quarantine/{entity}/{source_empresa}/{dt}/{run_id}/"

        impl: QuarantineProtocol = FakeQuarantine()
        uri = impl.dump(
            run_id="r1",
            entity="articulos",
            source_empresa="tinito",
            dt="2026-07-22",
            payload_bytes=b"{}",
            reason=QuarantineReason.EMPTY_REJECTED,
        )
        assert uri.startswith("gs://fake/quarantine/")
