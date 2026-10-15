from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Sequence
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import uuid4

from topo_v2 import storage
from topo_v2.goals import goal_summary
from topo_v2.models import (
    Account,
    Asset,
    AvailabilitySubtotal,
    Cashflow,
    ChangeRequest,
    ChangeResult,
    Context,
    Debt,
    Difference,
    Domain,
    Goal,
    Inventory,
    InventoryState,
    NetWealth,
    NetWealthSubtotal,
    Subtotal,
    Summary,
    Transaction,
    TransactionCoverage,
    TransactionImportOptions,
    TransactionImportResult,
)
from topo_v2.transactions import parse_transactions, prepare_import


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


def _apply[
    T: (
        Account,
        Asset,
        Debt,
        Goal,
        Transaction,
        Inventory,
        TransactionCoverage,
        Cashflow,
    )
](records: list[T], add: list[T], update: list[T], delete: Sequence[str]) -> list[T]:
    touched = [record.id for record in [*add, *update]] + list(delete)
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


def _token(path: Path, raw: bytes, payload: bytes, purpose: bytes) -> str:
    return hashlib.sha256(
        purpose + b"\0" + str(path.resolve()).encode() + b"\0" + raw + b"\0" + payload
    ).hexdigest()


def _check_token(provided: str | None, expected: str) -> None:
    if provided is not None and not hmac.compare_digest(
        provided.encode(), expected.encode()
    ):
        raise StaleConfirmation(
            "Request or context changed; obtain and approve a new preview"
        )


def _changed_context(before: Context, request: ChangeRequest) -> Context:
    settings = dict(before.cashflow_settings)
    for currency, value in request.cashflow_settings.items():
        if value is None:
            settings.pop(currency, None)
        else:
            settings[currency] = value
    return Context(
        schema_version="topo2.context/7"
        if (
            before.schema_version == "topo2.context/7"
            or any(
                goal.reserved_amount is not None
                or goal.monthly_contribution is not None
                or goal.priority is not None
                or goal.note is not None
                for goal in [*request.goals.add, *request.goals.update]
            )
        )
        else "topo2.context/6"
        if (
            before.schema_version == "topo2.context/6"
            or request.cashflows.add
            or request.cashflows.update
            or settings
        )
        else "topo2.context/5"
        if (
            before.schema_version == "topo2.context/5"
            or any(
                record.kind is not None
                for record in [*request.transactions.add, *request.transactions.update]
            )
        )
        else "topo2.context/4"
        if (
            before.schema_version == "topo2.context/4"
            or request.debts.add
            or request.debts.update
            or any(
                record.availability is not None or record.availability_note is not None
                for record in [
                    *request.accounts.add,
                    *request.accounts.update,
                    *request.assets.add,
                    *request.assets.update,
                ]
            )
        )
        else "topo2.context/3"
        if (
            before.schema_version == "topo2.context/3"
            or request.inventories.add
            or request.inventories.update
            or request.transaction_coverage.add
            or request.transaction_coverage.update
        )
        else "topo2.context/2",
        context_id=before.context_id,
        cashflows=_apply(
            before.cashflows,
            request.cashflows.add,
            request.cashflows.update,
            request.cashflows.delete,
        ),
        cashflow_settings=settings,
        inventories=_apply(
            before.inventories,
            request.inventories.add,
            request.inventories.update,
            request.inventories.delete,
        ),
        transaction_coverage=_apply(
            before.transaction_coverage,
            request.transaction_coverage.add,
            request.transaction_coverage.update,
            request.transaction_coverage.delete,
        ),
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
        debts=_apply(
            before.debts, request.debts.add, request.debts.update, request.debts.delete
        ),
        goals=_apply(
            before.goals, request.goals.add, request.goals.update, request.goals.delete
        ),
        transactions=_apply(
            before.transactions,
            request.transactions.add,
            request.transactions.update,
            request.transactions.delete,
        ),
    )


def _differences(before: Context, after: Context) -> list[Difference]:
    differences: list[Difference] = []
    for section in (
        "accounts",
        "assets",
        "debts",
        "goals",
        "transactions",
        "inventories",
        "transaction_coverage",
        "cashflows",
    ):
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
    for currency in sorted(
        before.cashflow_settings.keys() | after.cashflow_settings.keys()
    ):
        old_setting = before.cashflow_settings.get(currency)
        new_setting = after.cashflow_settings.get(currency)
        if old_setting != new_setting:
            differences.append(
                Difference(
                    section="cashflow_settings",
                    id=currency,
                    before=old_setting,
                    after=new_setting,
                )
            )
    return differences


def change(
    path: Path, request: ChangeRequest, sources: list[Path] | None = None
) -> ChangeResult:
    with storage.write_lock(path):
        raw, before = storage.read(path)
        normalized = json.dumps(
            request.model_dump(mode="json", exclude={"confirmation_token"}),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        # Hash each exact byte snapshot with its resolved path. Canonical ordering
        # makes repeated --source flags independent of argument order.
        source_bindings = [
            (str(source), hashlib.sha256(source.read_bytes()).hexdigest())
            for source in sorted({source.resolve() for source in sources or []})
        ]
        payload = json.dumps(
            {"request": normalized.decode(), "sources": source_bindings},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        token = _token(path, raw, payload, b"change")
        _check_token(request.confirmation_token, token)
        after = _changed_context(before, request)
        differences = _differences(before, after)
        if not differences:
            if (
                not any(
                    section.add or section.update or section.delete
                    for section in (
                        request.accounts,
                        request.assets,
                        request.debts,
                        request.goals,
                        request.transactions,
                        request.inventories,
                        request.transaction_coverage,
                        request.cashflows,
                    )
                )
                and not request.cashflow_settings
            ):
                raise ChangeError("Request contains no operations")
            return ChangeResult(status="unchanged", confirmation_token=None, changes=[])
        if request.confirmation_token is not None:
            storage.save(path, after)
        return ChangeResult(
            status="applied" if request.confirmation_token is not None else "preview",
            confirmation_token=token,
            changes=differences,
        )


def import_transactions(
    path: Path, data: bytes, options: TransactionImportOptions
) -> TransactionImportResult:
    records = parse_transactions(data, options.format)
    with storage.write_lock(path):
        raw, before = storage.read(path)
        token = _token(
            path, raw, options.format.encode() + b"\0" + data, b"import-transactions"
        )
        _check_token(options.confirmation_token, token)
        try:
            changes, skipped = prepare_import(before.transactions, records)
        except ValueError as error:
            raise ChangeError(str(error)) from error
        after = _changed_context(before, ChangeRequest(transactions=changes))
        differences = _differences(before, after)
        if differences and options.confirmation_token is not None:
            storage.save(path, after)
        return TransactionImportResult(
            status=("applied" if options.confirmation_token is not None else "preview")
            if differences
            else "unchanged",
            confirmation_token=token if differences else None,
            added=len(changes.add),
            updated=len(changes.update),
            skipped=skipped,
            total_changes=len(differences),
            truncated=not options.details and len(differences) > 20,
            changes=differences if options.details else differences[:20],
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
        availability = _availability(context)
        goals, comparisons = goal_summary(
            context.goals, amounts, availability, context.inventories
        )
        return Summary(
            subtotals=subtotals,
            goals=goals,
            net_wealth=_net_wealth(context, subtotals),
            availability=availability,
            reservation_comparison=comparisons,
        )


def _net_wealth(context: Context, subtotals: list[Subtotal]) -> NetWealth:
    declared = {item.id: item for item in context.inventories}
    domains: tuple[Domain, ...] = ("accounts", "assets", "debts")
    inventories = [
        InventoryState(
            id=domain,
            status=declared[domain].status if domain in declared else "unknown",
            checked_on=declared[domain].checked_on if domain in declared else None,
        )
        for domain in domains
    ]
    complete = all(item.status == "complete" for item in inventories)
    by_currency = {item.currency: item for item in subtotals}
    debts: dict[str, list[Debt]] = {}
    for debt in context.debts:
        debts.setdefault(debt.currency, []).append(debt)
    result: list[NetWealthSubtotal] = []
    for currency in sorted(by_currency.keys() | debts.keys()):
        base = by_currency.get(currency)
        records = debts.get(currency, [])
        known = base.known_total if base else Decimal(0)
        debt_total = sum(
            (
                item.amount
                for item in records
                if item.account_id is None and item.amount is not None
            ),
            Decimal(0),
        )
        missing = (base.missing_ids.copy() if base else []) + [
            item.id for item in records if item.amount is None
        ]
        result.append(
            NetWealthSubtotal(
                currency=currency,
                known_total=known - debt_total,
                known_account_asset_total=known,
                known_debt_total=debt_total,
                linked_debt_ids=[
                    item.id for item in records if item.account_id is not None
                ],
                missing_ids=missing,
                complete=not missing,
                inventory_complete=complete,
            )
        )
    return NetWealth(subtotals=result, inventories=inventories)


def _availability(context: Context) -> list[AvailabilitySubtotal]:
    groups: dict[str, list[Account | Asset]] = {}
    available: list[Account | Asset] = [*context.accounts, *context.assets]
    for record in available:
        groups.setdefault(record.currency, []).append(record)
    result: list[AvailabilitySubtotal] = []
    for currency, records in sorted(groups.items()):
        totals = {"free": Decimal(0), "restricted": Decimal(0)}
        unknown: list[str] = []
        missing: list[str] = []
        for record in records:
            value = record.balance if isinstance(record, Account) else record.value
            if value is None:
                missing.append(record.id)
            if record.availability in ("free", "restricted"):
                if value is not None:
                    totals[record.availability] += max(value, Decimal(0))
            else:
                unknown.append(record.id)
        result.append(
            AvailabilitySubtotal(
                currency=currency,
                known_free_total=totals["free"],
                known_restricted_total=totals["restricted"],
                unknown_availability_ids=unknown,
                missing_ids=missing,
            )
        )
    return result
