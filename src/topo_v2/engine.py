from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import uuid4

from topo_v2 import storage
from topo_v2.models import (
    Account,
    Asset,
    ChangeRequest,
    ChangeResult,
    Context,
    Difference,
    Goal,
    GoalProgress,
    Subtotal,
    Summary,
)


class ChangeError(ValueError):
    pass


class StaleConfirmation(ChangeError):
    pass


def initialize(path: Path) -> Context:
    with storage.write_lock(path):
        if path.exists():
            raise ChangeError("Context already exists; choose a new file")
        context = Context(context_id=str(uuid4()))
        storage.save(path, context)
        return context


def _apply[T: (Account, Asset, Goal)](
    records: list[T], add: list[T], update: list[T], delete: list[str]
) -> list[T]:
    touched = [record.id for record in [*add, *update]] + delete
    if len(touched) != len(set(touched)):
        raise ChangeError("An ID can occur only once per change section")
    current = {record.id: record for record in records}
    for record in add:
        if record.id in current:
            raise ChangeError(f"Record {record.id} already exists; use update")
        current[record.id] = record
    for record in update:
        if record.id not in current:
            raise ChangeError(f"Cannot update unknown record {record.id}")
        current[record.id] = record
    for identifier in delete:
        if identifier not in current:
            raise ChangeError(f"Cannot delete unknown record {identifier}")
        del current[identifier]
    return list(current.values())


def change(path: Path, request: ChangeRequest) -> ChangeResult:
    with storage.write_lock(path):
        raw, before = storage.read(path)
        normalized = json.dumps(
            request.model_dump(mode="json", exclude={"confirmation_token"}),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        token = hashlib.sha256(
            str(path.resolve()).encode() + b"\0" + raw + b"\0" + normalized
        ).hexdigest()
        if request.confirmation_token is not None and not hmac.compare_digest(
            request.confirmation_token, token
        ):
            raise StaleConfirmation(
                "Request or context changed; obtain and approve a new preview"
            )
        after = Context(
            context_id=before.context_id,
            accounts=_apply(
                before.accounts,
                request.accounts.add,
                request.accounts.update,
                request.accounts.delete,
            ),
            assets=_apply(
                before.assets,
                request.assets.add,
                request.assets.update,
                request.assets.delete,
            ),
            goals=_apply(
                before.goals,
                request.goals.add,
                request.goals.update,
                request.goals.delete,
            ),
        )
        differences: list[Difference] = []
        for section in ("accounts", "assets", "goals"):
            old = {record.id: record for record in getattr(before, section)}
            new = {record.id: record for record in getattr(after, section)}
            for identifier in sorted(old.keys() | new.keys()):
                if old.get(identifier) != new.get(identifier):
                    differences.append(
                        Difference(
                            section=section,
                            id=identifier,
                            before=old.get(identifier),
                            after=new.get(identifier),
                        )
                    )
        if not differences:
            raise ChangeError("Request makes no changes")
        if request.confirmation_token is not None:
            storage.save(path, after)
        return ChangeResult(
            status="applied" if request.confirmation_token is not None else "preview",
            confirmation_token=token,
            changes=differences,
        )


def summarize(context: Context) -> Summary:
    with localcontext() as arithmetic:
        arithmetic.prec = 100
        amounts = {account.id: account.balance for account in context.accounts}
        amounts.update({asset.id: asset.value for asset in context.assets})
        currencies: dict[str, list[str]] = {}
        for record in [*context.accounts, *context.assets]:
            currencies.setdefault(record.currency, []).append(record.id)
        subtotals: list[Subtotal] = []
        for currency, ids in sorted(currencies.items()):
            missing = [identifier for identifier in ids if amounts[identifier] is None]
            total = sum(
                (amounts[identifier] or Decimal(0) for identifier in ids), Decimal(0)
            )
            subtotals.append(
                Subtotal(
                    currency=currency,
                    known_total=total,
                    missing_ids=missing,
                    complete=not missing,
                )
            )
        goals: list[GoalProgress] = []
        for goal in context.goals:
            ids = list(dict.fromkeys([*goal.account_ids, *goal.asset_ids]))
            missing = [identifier for identifier in ids if amounts[identifier] is None]
            total = sum(
                (amounts[identifier] or Decimal(0) for identifier in ids), Decimal(0)
            )
            goals.append(
                GoalProgress(
                    id=goal.id,
                    name=goal.name,
                    currency=goal.currency,
                    target_amount=goal.target_amount,
                    known_amount=total,
                    percentage=total / goal.target_amount * 100,
                    missing_ids=missing,
                    complete=not missing,
                    target_date=goal.target_date,
                )
            )
        return Summary(subtotals=subtotals, goals=goals)
