from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import pytest

from topo.engine import _collection_update_bytes, _json_bytes
from topo.identifiers import uuid7
from topo.models import CanonicalCollection, EntityRecord


@pytest.mark.parametrize("change", ["append", "remove", "replace", "version", "layout"])
def test_fragment_reuse_matches_full_canonical_serialization(change: str) -> None:
    records = tuple(
        sorted(
            (
                EntityRecord(
                    id=uuid7(),
                    entity_type="transaction",
                    module_id="domain.cashflow",
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
                for _ in range(3)
            ),
            key=lambda item: item.id,
        )
    )
    old = CanonicalCollection[EntityRecord](
        schema_version="topo.context/0.2", records=records
    )
    payload = _json_bytes(old)
    updated = records
    version: Literal["topo.context/0.1", "topo.context/0.2"] = "topo.context/0.2"
    if change == "append":
        updated = (*records, records[-1].model_copy(update={"id": uuid7()}))
    elif change == "remove":
        updated = records[1:]
    elif change == "replace":
        updated = (
            records[0].model_copy(
                update={"created_at": datetime(2026, 2, 1, tzinfo=UTC)}
            ),
            *records[1:],
        )
    elif change == "version":
        version = "topo.context/0.1"
    elif change == "layout":
        payload = old.model_dump_json().encode()
    ordered = tuple(sorted(updated, key=lambda item: item.id))
    full = CanonicalCollection[EntityRecord](schema_version=version, records=ordered)
    assert _collection_update_bytes(
        payload, records, ordered, version, full
    ) == _json_bytes(full)


@pytest.mark.parametrize("value", [True, 1.0])
def test_json_numeric_type_changes_are_not_reused(value: bool | float) -> None:
    import json

    from topo.canonical_validation import _ValidationRound
    from topo.models import EvidenceRecord, UserStatementEvidenceRecord

    record = UserStatementEvidenceRecord(
        id=uuid7(),
        evidence_type="user_statement",
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
        statement_type="context_initialization",
        statement={"value": 1},
    )
    old = CanonicalCollection[EvidenceRecord](
        schema_version="topo.context/0.2", records=(record,)
    )
    changed = record.model_copy(update={"statement": {"value": value}})
    new = CanonicalCollection[EvidenceRecord](
        schema_version="topo.context/0.2", records=(changed,)
    )
    actual = _collection_update_bytes(
        _json_bytes(old), (record,), (changed,), "topo.context/0.2", new
    )
    assert actual == _json_bytes(new)
    reuse = _ValidationRound()
    reuse.collection("evidence.json", _json_bytes(old), EvidenceRecord)
    reused = reuse.collection("evidence.json", actual, EvidenceRecord)
    full = CanonicalCollection[EvidenceRecord].model_validate_json(actual, strict=True)
    assert reused.model_dump_json() == full.model_dump_json()
    assert type(
        json.loads(reused.model_dump_json())["records"][0]["statement"]["value"]
    ) is type(value)
