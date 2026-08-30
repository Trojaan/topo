from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from topo.engine import EngineCore
from topo.identifiers import uuid7
from topo.models import (
    Actor,
    Authorization,
    ContextInitRequest,
    ContextMigrateRequest,
    ContextPrivacyScrubRequest,
    ContextRestoreRequest,
    ContextRetentionRequest,
    Money,
    SourceAdapter,
    SourceImportRecord,
    SourceImportRequest,
)
from topo.storage import FileSystemStorageAdapter


def _initialize(package: Path) -> tuple[EngineCore, str, str]:
    engine = EngineCore(
        FileSystemStorageAdapter(package),
        clock=lambda: datetime(2026, 8, 29, 10, 0, tzinfo=UTC),
    )
    initialized = engine.initialize(
        ContextInitRequest(
            contract_version="topo.cli/0.1",
            package=str(package),
            operation_id=uuid7(),
            expected_generation=None,
            actor=Actor(actor_type="human", actor_id="beheerder"),
            reason="Maak testcontext",
        )
    ).result
    return engine, initialized.context_id, initialized.generation_id


def _module_versions(package: Path, generation: str) -> dict[str, str]:
    manifest = json.loads(
        (package / "generations" / generation / "manifest.json").read_text()
    )
    return {
        module["module_id"]: module["module_version"] for module in manifest["modules"]
    }


def test_compatible_migration_publishes_only_a_fully_valid_new_generation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context.topo"
    engine, context_id, original_generation = _initialize(package)

    outcome = engine.migrate_context(
        ContextMigrateRequest(
            contract_version="topo.cli/0.1",
            operation_id=uuid7(),
            context_id=context_id,
            expected_generation=original_generation,
            actor=Actor(actor_type="human", actor_id="beheerder"),
            reason="Valideer huidige schema- en moduleversies opnieuw",
            target_package_version="0.1",
            target_context_schema_version="topo.context/0.1",
            target_module_versions=_module_versions(package, original_generation),
        )
    )

    assert outcome.outcome == "succeeded"
    assert outcome.generation_after != original_generation
    assert (package / "CURRENT").read_text().strip() == outcome.generation_after
    current, loaded_context = engine.current_identity()
    assert current == outcome.generation_after
    assert loaded_context == context_id


def test_incompatible_migration_leaves_current_generation_intact(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context.topo"
    engine, context_id, original_generation = _initialize(package)
    supported_modules = _module_versions(package, original_generation)
    unsupported_modules = dict(supported_modules)
    unsupported_modules["topo.core"] = "1.0.0"

    for package_version, schema_version, module_versions in (
        ("1.0", "topo.context/1.0", supported_modules),
        ("0.1", "topo.context/0.1", unsupported_modules),
    ):
        outcome = engine.migrate_context(
            ContextMigrateRequest(
                contract_version="topo.cli/0.1",
                operation_id=uuid7(),
                context_id=context_id,
                expected_generation=original_generation,
                actor=Actor(actor_type="human", actor_id="beheerder"),
                reason="Probeer incompatibele migratie",
                target_package_version=package_version,
                target_context_schema_version=schema_version,
                target_module_versions=module_versions,
            )
        )

        assert outcome.outcome == "rejected"
        assert outcome.generation_before == original_generation
        assert outcome.generation_after == original_generation
    assert (package / "CURRENT").read_text().strip() == original_generation


def test_restore_validates_an_old_generation_and_publishes_a_new_generation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context.topo"
    engine, context_id, original_generation = _initialize(package)
    migrated = engine.migrate_context(
        ContextMigrateRequest(
            contract_version="topo.cli/0.1",
            operation_id=uuid7(),
            context_id=context_id,
            expected_generation=original_generation,
            actor=Actor(actor_type="human", actor_id="beheerder"),
            reason="Maak een tweede generatie",
            target_package_version="0.1",
            target_context_schema_version="topo.context/0.1",
            target_module_versions=_module_versions(package, original_generation),
        )
    )

    restored = engine.restore_context(
        ContextRestoreRequest(
            contract_version="topo.cli/0.1",
            operation_id=uuid7(),
            context_id=context_id,
            expected_generation=migrated.generation_after,
            actor=Actor(actor_type="human", actor_id="beheerder"),
            reason="Herstel de eerste vertrouwde toestand",
            restore_generation=original_generation,
        )
    )

    assert restored.outcome == "succeeded"
    assert restored.generation_after not in {
        original_generation,
        migrated.generation_after,
    }
    assert (package / "CURRENT").read_text().strip() == restored.generation_after
    original = package / "generations" / original_generation
    current = package / "generations" / restored.generation_after
    for filename in (
        "entities.json",
        "assertions.json",
        "evidence.json",
        "proposals.json",
    ):
        assert (current / filename).read_bytes() == (original / filename).read_bytes()


def test_bounded_retention_keeps_current_latest_and_explicit_restore_points(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context.topo"
    engine, context_id, original_generation = _initialize(package)
    generations = [original_generation]
    for _ in range(3):
        migrated = engine.migrate_context(
            ContextMigrateRequest(
                contract_version="topo.cli/0.1",
                operation_id=uuid7(),
                context_id=context_id,
                expected_generation=generations[-1],
                actor=Actor(actor_type="human", actor_id="beheerder"),
                reason="Maak retentiehistorie",
                target_package_version="0.1",
                target_context_schema_version="topo.context/0.1",
                target_module_versions=_module_versions(package, generations[-1]),
            )
        )
        generations.append(migrated.generation_after)

    compacted = engine.apply_retention(
        ContextRetentionRequest(
            contract_version="topo.cli/0.1",
            operation_id=uuid7(),
            context_id=context_id,
            expected_generation=generations[-1],
            actor=Actor(actor_type="human", actor_id="beheerder"),
            reason="Bewaar actuele generatie en gekozen herstelpunt",
            retain_latest=2,
            restore_generations=(original_generation,),
        )
    )

    retained = {path.name for path in (package / "generations").iterdir()}
    assert retained == {
        original_generation,
        generations[-1],
        compacted.generation_after,
    }
    assert engine.current_identity() == (compacted.generation_after, context_id)


def test_privacy_scrub_removes_selected_evidence_from_the_whole_package(
    tmp_path: Path,
) -> None:
    package = tmp_path / "context.topo"
    engine, context_id, original_generation = _initialize(package)
    original_evidence = json.loads(
        (package / "generations" / original_generation / "evidence.json").read_text()
    )["records"][0]["id"]
    migrated = engine.migrate_context(
        ContextMigrateRequest(
            contract_version="topo.cli/0.1",
            operation_id=uuid7(),
            context_id=context_id,
            expected_generation=original_generation,
            actor=Actor(actor_type="human", actor_id="beheerder"),
            reason="Maak privacyhistorie",
            target_package_version="0.1",
            target_context_schema_version="topo.context/0.1",
            target_module_versions=_module_versions(package, original_generation),
        )
    )

    scrubbed = engine.scrub_privacy(
        ContextPrivacyScrubRequest(
            contract_version="topo.cli/0.1",
            operation_id=uuid7(),
            context_id=context_id,
            expected_generation=migrated.generation_after,
            actor=Actor(actor_type="human", actor_id="beheerder"),
            reason="Verwijder geselecteerd bewijs",
            evidence_ids=(original_evidence,),
        )
    )

    assert scrubbed.outcome == "succeeded"
    for generation in (package / "generations").iterdir():
        evidence = json.loads((generation / "evidence.json").read_text())
        assertions = json.loads((generation / "assertions.json").read_text())
        assert all(record["id"] != original_evidence for record in evidence["records"])
        affected = [
            record
            for record in assertions["records"]
            if record["predicate"] == "domain.parties/household_membership"
        ]
        assert affected[0]["verification_status"] == "unverifiable"
        assert affected[0]["provenance"] == []
    assert original_evidence not in (package / "history" / "journal.json").read_text()
    for path in package.rglob("*"):
        if path.is_file():
            assert original_evidence.encode() not in path.read_bytes()
    assert engine.current_identity() == (scrubbed.generation_after, context_id)


def test_privacy_scrub_removes_normalized_source_record_bytes(tmp_path: Path) -> None:
    package = tmp_path / "context.topo"
    engine, context_id, original_generation = _initialize(package)
    operation_id = uuid7()
    source_request = SourceImportRequest(
        contract_version="topo.cli/0.1",
        operation_id=operation_id,
        context_id=context_id,
        expected_generation=original_generation,
        actor=Actor(actor_type="source_adapter", actor_id="normalized-json"),
        reason="Importeer synthetisch bronrecord",
        adapter=SourceAdapter(adapter_id="normalized-json", adapter_version="0.1"),
        records=(
            SourceImportRecord(
                source_id="synthetic-account",
                record_id="synthetic-posting",
                booking_date=date(2026, 8, 1),
                money=Money(amount="12.34", currency="EUR"),
                description="SYNTHETIC-PRIVATE-DESCRIPTION",
            ),
        ),
        authorization=None,
    )
    preview = engine.import_source(source_request)
    imported = engine.import_source(
        source_request.model_copy(
            update={
                "authorization": Authorization(
                    preview_ref=str(preview.result["preview_ref"]),
                    authorized_by=Actor(actor_type="human", actor_id="beheerder"),
                    authorized_at=datetime(2026, 8, 29, 10, 0, tzinfo=UTC),
                )
            }
        )
    )
    evidence_refs = imported.result["evidence_refs"]
    assert isinstance(evidence_refs, list)
    first_evidence_ref = evidence_refs[0]
    assert isinstance(first_evidence_ref, dict)
    evidence_id = str(first_evidence_ref["id"])
    raw_record = package / "evidence" / "records" / f"{evidence_id}.json"
    assert raw_record.is_file()

    scrubbed = engine.scrub_privacy(
        ContextPrivacyScrubRequest(
            contract_version="topo.cli/0.1",
            operation_id=uuid7(),
            context_id=context_id,
            expected_generation=imported.generation_after,
            actor=Actor(actor_type="human", actor_id="beheerder"),
            reason="Verwijder bronbewijs",
            evidence_ids=(evidence_id,),
        )
    )

    assert scrubbed.outcome == "succeeded"
    assert not raw_record.exists()
    for path in package.rglob("*"):
        if path.is_file():
            assert evidence_id.encode() not in path.read_bytes()
