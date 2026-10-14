from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from topo_v2 import engine, storage
from topo_v2.models import Account, Asset, ChangeRequest, Context, Goal


def account(identifier: str = "bank", amount: str | None = "10.00") -> Account:
    return Account(
        id=identifier,
        label=identifier,
        type="savings",
        balance=Decimal(amount) if amount is not None else None,
        as_of=date(2026, 10, 4),
    )


def apply(path: Path, request: ChangeRequest) -> None:
    preview = engine.change(path, request)
    engine.change(
        path,
        request.model_copy(update={"confirmation_token": preview.confirmation_token}),
    )


def test_unknown_zero_negative_currency_and_decimal() -> None:
    usd = account("usd", "0.20").model_copy(update={"currency": "USD"})
    context = Context(
        context_id="test",
        accounts=[
            account("unknown", None),
            account("zero", "0"),
            account("overdraft", "-0.10"),
            account("savings", "0.30"),
            usd,
        ],
    )
    summary = engine.summarize(context)
    eur, dollars = summary.subtotals
    assert eur.known_total == Decimal("0.20")
    assert eur.missing_ids == ["unknown"] and not eur.complete
    assert dollars.known_total == Decimal("0.20") and dollars.complete
    assert engine.summarize(Context(context_id="empty")).subtotals == []


def test_broker_cash_etfs_and_goal_deduplication() -> None:
    broker = account("broker", "50").model_copy(update={"type": "investment"})
    etf = Asset(
        id="etf",
        label="ETF",
        type="etf",
        value=Decimal("100.20"),
        as_of=date(2026, 10, 4),
        broker_account_id="broker",
    )
    unknown = Asset(id="unknown", label="Unknown", type="other")
    goal = Goal(
        id="goal",
        name="Buffer",
        target_amount=Decimal(200),
        account_ids=["broker", "broker"],
        asset_ids=["etf", "etf", "unknown"],
    )
    summary = engine.summarize(
        Context(
            context_id="test", accounts=[broker], assets=[etf, unknown], goals=[goal]
        )
    )
    assert summary.subtotals[0].known_total == Decimal("150.20")
    assert summary.goals[0].known_amount == Decimal("150.20")
    assert summary.goals[0].percentage == Decimal("75.10")
    assert summary.goals[0].missing_ids == ["unknown"]
    assert not summary.goals[0].complete


def test_validation_references_and_dates() -> None:
    with pytest.raises(ValidationError, match="requires as_of"):
        Account(id="bank", label="Bank", type="payment", balance=Decimal(5))
    for invalid in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ValidationError):
            account(amount=invalid)
    with pytest.raises(ValidationError, match="unknown linked"):
        Context(
            context_id="test",
            goals=[
                Goal(
                    id="goal",
                    name="Goal",
                    target_amount=Decimal(1),
                    account_ids=["absent"],
                )
            ],
        )
    with pytest.raises(ValidationError, match="currency differs"):
        Context(
            context_id="test",
            accounts=[account()],
            goals=[
                Goal(
                    id="goal",
                    name="Goal",
                    target_amount=Decimal(1),
                    currency="USD",
                    account_ids=["bank"],
                )
            ],
        )
    with pytest.raises(ValidationError, match="investment account"):
        Context(
            context_id="test",
            accounts=[account()],
            assets=[Asset(id="etf", label="ETF", type="etf", broker_account_id="bank")],
        )
    with pytest.raises(ValidationError, match="unique"):
        Context(context_id="test", accounts=[account(), account()])


def test_preview_invalid_batch_and_linked_delete_leave_file_unchanged(
    tmp_path: Path,
) -> None:
    path = tmp_path / "context.json"
    engine.initialize(path)
    raw = path.read_bytes()
    request = ChangeRequest.model_validate(
        {"accounts": {"add": [account().model_dump(mode="json")]}}
    )
    engine.change(path, request)
    assert path.read_bytes() == raw
    invalid = ChangeRequest.model_validate(
        {
            "accounts": {
                "add": [account().model_dump(mode="json")],
                "update": [account("absent").model_dump(mode="json")],
            }
        }
    )
    with pytest.raises(engine.ChangeError, match="unknown"):
        engine.change(path, invalid)
    assert path.read_bytes() == raw
    apply(path, request)
    apply(
        path,
        ChangeRequest.model_validate(
            {
                "goals": {
                    "add": [
                        {
                            "id": "goal",
                            "name": "Goal",
                            "target_amount": "100",
                            "account_ids": ["bank"],
                        }
                    ]
                }
            }
        ),
    )
    raw = path.read_bytes()
    with pytest.raises(ValidationError, match="unknown linked"):
        engine.change(
            path, ChangeRequest.model_validate({"accounts": {"delete": ["bank"]}})
        )
    assert path.read_bytes() == raw
    apply(
        path,
        ChangeRequest.model_validate(
            {"accounts": {"delete": ["bank"]}, "goals": {"delete": ["goal"]}}
        ),
    )
    assert storage.read(path)[1].accounts == []


def test_confirmation_binds_request_context_and_file(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    engine.initialize(path)
    request = ChangeRequest.model_validate(
        {"accounts": {"add": [account().model_dump(mode="json")]}}
    )
    token = engine.change(path, request).confirmation_token
    altered = request.model_dump(mode="json")
    altered["accounts"]["add"][0]["balance"] = "999"
    altered["confirmation_token"] = token
    with pytest.raises(engine.StaleConfirmation):
        engine.change(path, ChangeRequest.model_validate(altered))
    other = tmp_path / "other.json"
    other.write_bytes(path.read_bytes())
    confirmed = request.model_copy(update={"confirmation_token": token})
    with pytest.raises(engine.StaleConfirmation):
        engine.change(other, confirmed)
    apply(path, request)
    with pytest.raises(engine.StaleConfirmation):
        engine.change(path, confirmed)


def test_failed_replace_preserves_context_and_cleans_staging(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    context = engine.initialize(path)
    raw = path.read_bytes()
    context.accounts.append(account())
    with (
        patch("topo_v2.storage.os.replace", side_effect=OSError("disk failure")),
        pytest.raises(OSError, match="disk failure"),
    ):
        storage.save(path, context)
    assert path.read_bytes() == raw
    assert list(tmp_path.glob(".context.json.*")) == []
    with pytest.raises(engine.ChangeError, match="already exists"):
        engine.initialize(path)
    assert path.read_bytes() == raw


def test_concurrent_confirmations_only_publish_once(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    engine.initialize(path)
    request = ChangeRequest.model_validate(
        {"accounts": {"add": [account().model_dump(mode="json")]}}
    )
    request.confirmation_token = engine.change(path, request).confirmation_token

    def confirm() -> str:
        try:
            return engine.change(path, request).status
        except engine.StaleConfirmation:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: confirm(), range(2))) == ["applied", "stale"]
    assert len(storage.read(path)[1].accounts) == 1


def test_duplicate_operations_and_unknown_schema(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    engine.initialize(path)
    with pytest.raises(engine.ChangeError, match="only once"):
        engine.change(
            path,
            ChangeRequest.model_validate(
                {
                    "accounts": {
                        "add": [account().model_dump(mode="json")],
                        "delete": ["bank"],
                    }
                }
            ),
        )
    with pytest.raises(ValidationError):
        ChangeRequest.model_validate({"contract_version": "topo2.cli/99"})
    path.write_text('{"schema_version":"topo2.context/99","context_id":"x"}')
    with pytest.raises(ValidationError):
        storage.read(path)


def test_money_contract_rejects_floats_and_preserves_large_decimals() -> None:
    with pytest.raises(ValidationError, match="decimal string"):
        Account.model_validate(
            {
                "id": "bank",
                "label": "Bank",
                "type": "payment",
                "balance": 0.1,
                "as_of": "2026-10-04",
            }
        )
    value = "99999999999999999999.12345678"
    result = engine.summarize(
        Context(
            context_id="test",
            accounts=[account(amount=value), account("small", "0.00000001")],
        )
    )
    assert result.subtotals[0].known_total == Decimal("99999999999999999999.12345679")
    for invalid in ("100000000000000000000.12345678", "0.123456789"):
        with pytest.raises(ValidationError):
            account(amount=invalid)


def test_failed_flush_preserves_context(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    context = engine.initialize(path)
    raw = path.read_bytes()
    context.accounts.append(account())
    with (
        patch("topo_v2.storage.os.fsync", side_effect=OSError("flush failed")),
        pytest.raises(OSError, match="flush failed"),
    ):
        storage.save(path, context)
    assert path.read_bytes() == raw
    assert list(tmp_path.glob(".context.json.*")) == []


def test_identical_update_is_unchanged_but_empty_request_is_invalid(
    tmp_path: Path,
) -> None:
    path = tmp_path / "context.json"
    engine.initialize(path)
    record = account().model_dump(mode="json")
    apply(path, ChangeRequest.model_validate({"accounts": {"add": [record]}}))
    raw = path.read_bytes()
    request = ChangeRequest.model_validate({"accounts": {"update": [record]}})
    result = engine.change(path, request)
    assert result.status == "unchanged" and result.confirmation_token is None
    assert result.changes == [] and path.read_bytes() == raw
    request.confirmation_token = "stale"
    with pytest.raises(engine.StaleConfirmation):
        engine.change(path, request)
    with pytest.raises(engine.ChangeError, match="no operations"):
        engine.change(path, ChangeRequest())
    assert path.read_bytes() == raw


def test_source_binding_exact_bytes_path_and_membership(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    engine.initialize(path)
    sources = [tmp_path / "export.csv", tmp_path / "goal.txt"]
    for source in sources:
        source.write_bytes(b"synthetic")
    request = ChangeRequest.model_validate(
        {"accounts": {"add": [account().model_dump(mode="json")]}}
    )
    token = engine.change(path, request, sources).confirmation_token
    assert (
        engine.change(path, request, list(reversed(sources))).confirmation_token
        == token
    )
    request.confirmation_token = token
    raw = path.read_bytes()
    for altered in (sources[:1], []):
        with pytest.raises(engine.StaleConfirmation):
            engine.change(path, request, altered)
    sources[0].write_bytes(b"synthetic\n")
    with pytest.raises(engine.StaleConfirmation):
        engine.change(path, request, sources)
    sources[0].write_bytes(b"synthetic")
    other = tmp_path / "same-content.csv"
    other.write_bytes(b"synthetic")
    with pytest.raises(engine.StaleConfirmation):
        engine.change(path, request, [other, sources[1]])
    sources[0].unlink()
    with pytest.raises(OSError):
        engine.change(path, request, sources)
    assert path.read_bytes() == raw


def test_version_two_requests_require_explicit_migration() -> None:
    with pytest.raises(ValidationError, match="discover topo2 contract"):
        ChangeRequest.model_validate({"contract_version": "topo2.cli/2"})
