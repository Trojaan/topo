from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

CONTRACT_VERSION: Literal["topo2.cli/3"] = "topo2.cli/3"
# Base contexts stay compatible; optional records opt into newer storage versions.
SCHEMA_VERSION: Literal["topo2.context/2"] = "topo2.context/2"
Identifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
]
Label = Annotated[str, Field(min_length=1, max_length=256, pattern=r"\S")]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


def decimal_input(value: object) -> Decimal:
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Money must be a decimal string")  # noqa: TRY004 -- Pydantic validators require ValueError
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid decimal money") from error
    if not amount.is_finite():
        raise ValueError("Money must be finite")
    # Decimal.normalize otherwise uses the ambient precision (normally 28),
    # which can round a large input before Pydantic counts its digits.
    with localcontext() as arithmetic:
        arithmetic.prec = max(28, len(amount.as_tuple().digits)) + 1
        _, digits, exponent = amount.normalize().as_tuple()
    assert isinstance(exponent, int)
    places = max(0, -exponent)
    integer_digits = max(0, len(digits) + exponent)
    if places > 8 or integer_digits + places > 28:
        raise ValueError("Money allows at most 28 digits and 8 decimal places")
    return amount


Money = Annotated[
    Decimal,
    BeforeValidator(decimal_input, json_schema_input_type=str),
    Field(max_digits=28, decimal_places=8, allow_inf_nan=False),
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValuedRecord(Model):
    id: Identifier
    label: Label
    currency: Currency = "EUR"
    as_of: date | None = None


class AvailableRecord(ValuedRecord):
    availability: Literal["free", "restricted", "unknown"] | None = None
    availability_note: Label | None = None


class Account(AvailableRecord):
    type: Literal["payment", "savings", "investment"]
    balance: Money | None = None

    @model_validator(mode="after")
    def dated_balance(self) -> Self:
        if self.balance is not None and self.as_of is None:
            raise ValueError("A balance requires as_of")
        return self


class Asset(AvailableRecord):
    type: Literal["etf", "property", "vehicle", "cash", "investment", "other"]
    value: Annotated[Money, Field(ge=0)] | None = None
    broker_account_id: Identifier | None = None

    @model_validator(mode="after")
    def dated_value(self) -> Self:
        if self.value is not None and self.as_of is None:
            raise ValueError("A value requires as_of")
        return self


class Debt(ValuedRecord):
    type: Literal["mortgage", "loan", "credit_card", "overdraft", "other"]
    amount: Annotated[Money, Field(ge=0)] | None = None
    interest_rate: Annotated[Money, Field(ge=0)] | None = None
    end_date: date | None = None
    account_id: Identifier | None = None

    @model_validator(mode="after")
    def dated_amount(self) -> Self:
        if self.amount is not None and self.as_of is None:
            raise ValueError("A debt amount requires as_of")
        if self.account_id is not None and self.type != "overdraft":
            raise ValueError("Only overdraft debts can link an account")
        return self


class Goal(Model):
    id: Identifier
    name: Label
    target_amount: Annotated[Money, Field(gt=0)]
    currency: Currency = "EUR"
    target_date: date | None = None
    reserved_amount: Annotated[Money, Field(ge=0)] | None = None
    monthly_contribution: Annotated[Money, Field(ge=0)] | None = None
    priority: Literal["low", "normal", "high"] | None = None
    note: Label | None = None
    account_ids: list[Identifier] = Field(default_factory=list)
    asset_ids: list[Identifier] = Field(default_factory=list)


TransactionKind = Literal["income", "expense", "internal_transfer", "unknown"]


class Transaction(Model):
    id: Identifier
    account_id: Identifier
    booking_date: date
    amount: Money
    currency: Currency
    description: str
    category: Label | None = None
    source: Label | None = None
    kind: TransactionKind | None = None


Domain = Literal["accounts", "assets", "debts", "goals", "cashflows"]


class Inventory(Model):
    id: Domain
    status: Literal["unknown", "partial", "complete"]
    checked_on: date


class TransactionCoverage(Model):
    id: Identifier
    account_id: Identifier
    from_date: date
    to_date: date
    checked_on: date

    @model_validator(mode="after")
    def ordered_interval(self) -> Self:
        if self.from_date > self.to_date:
            raise ValueError("from_date must not follow to_date")
        return self


class ExpectedRange(Model):
    lower: Annotated[Money, Field(ge=0)]
    upper: Annotated[Money, Field(ge=0)]

    @model_validator(mode="after")
    def ordered_bounds(self) -> Self:
        if self.lower > self.upper:
            raise ValueError("lower must not exceed upper")
        return self


class Cashflow(Model):
    id: Identifier
    label: Label
    kind: Literal["income", "expense"]
    amount: Annotated[Money, Field(ge=0)] | ExpectedRange | None = None
    currency: Currency = "EUR"
    frequency: Literal["weekly", "four_weekly", "monthly", "quarterly", "yearly"]
    start_date: date
    end_date: date | None = None
    category: Label | None = None
    source: Label | None = None
    debt_id: Identifier | None = None

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class CashflowSettings(Model):
    minimum_reserve: Annotated[Money, Field(ge=0)] | None = None
    note: Label | None = None


Record = (
    Account
    | Asset
    | Debt
    | Goal
    | Transaction
    | Inventory
    | TransactionCoverage
    | Cashflow
    | CashflowSettings
)


class Context(Model):
    schema_version: Literal[
        "topo2.context/1",
        "topo2.context/2",
        "topo2.context/3",
        "topo2.context/4",
        "topo2.context/5",
        "topo2.context/6",
        "topo2.context/7",
    ] = SCHEMA_VERSION
    context_id: str
    accounts: list[Account] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    debts: list[Debt] = Field(default_factory=list)
    goals: list[Goal] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)
    cashflows: list[Cashflow] = Field(default_factory=list)
    cashflow_settings: dict[Currency, CashflowSettings] = Field(default_factory=dict)

    inventories: list[Inventory] = Field(default_factory=list)
    transaction_coverage: list[TransactionCoverage] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self) -> Self:
        if self.schema_version not in (
            "topo2.context/3",
            "topo2.context/4",
            "topo2.context/5",
            "topo2.context/6",
            "topo2.context/7",
        ) and (self.inventories or self.transaction_coverage):
            raise ValueError("Context declarations require topo2.context/3")
        if self.schema_version not in (
            "topo2.context/4",
            "topo2.context/5",
            "topo2.context/6",
            "topo2.context/7",
        ) and (
            self.debts
            or any(
                record.availability is not None or record.availability_note is not None
                for record in [*self.accounts, *self.assets]
            )
        ):
            raise ValueError("Debts and availability require topo2.context/4")
        if self.schema_version not in (
            "topo2.context/5",
            "topo2.context/6",
            "topo2.context/7",
        ) and any(record.kind is not None for record in self.transactions):
            raise ValueError("Transaction kinds require topo2.context/5")
        if self.schema_version not in ("topo2.context/6", "topo2.context/7") and (
            self.cashflows or self.cashflow_settings
        ):
            raise ValueError("Cashflows and settings require topo2.context/6")
        if self.schema_version != "topo2.context/7" and any(
            goal.reserved_amount is not None
            or goal.monthly_contribution is not None
            or goal.priority is not None
            or goal.note is not None
            for goal in self.goals
        ):
            raise ValueError("Goal enrichments require topo2.context/7")
        domains = [record.id for record in self.inventories]
        if len(domains) != len(set(domains)):
            raise ValueError("Inventory domains must be unique")
        all_ids = (
            [account.id for account in self.accounts]
            + [asset.id for asset in self.assets]
            + [debt.id for debt in self.debts]
            + [goal.id for goal in self.goals]
            + [transaction.id for transaction in self.transactions]
            + [coverage.id for coverage in self.transaction_coverage]
            + [cashflow.id for cashflow in self.cashflows]
        )
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Record IDs must be unique across the context")
        accounts = {account.id: account for account in self.accounts}
        assets = {asset.id: asset for asset in self.assets}
        if self.schema_version == "topo2.context/1" and self.transactions:
            raise ValueError("Transactions require topo2.context/2")
        for coverage in self.transaction_coverage:
            if coverage.account_id not in accounts:
                raise ValueError(
                    f"Coverage {coverage.id}: unknown account {coverage.account_id}"
                )
        for transaction in self.transactions:
            if transaction.account_id not in accounts:
                raise ValueError(
                    f"Transaction {transaction.id}: unknown account {transaction.account_id}"
                )
        for asset in self.assets:
            if asset.broker_account_id is not None:
                broker = accounts.get(asset.broker_account_id)
                if broker is None or broker.type != "investment":
                    raise ValueError(
                        f"Asset {asset.id}: broker must be an investment account"
                    )
        linked_accounts: set[str] = set()
        for debt in self.debts:
            if debt.account_id is None:
                continue
            account = accounts.get(debt.account_id)
            if debt.account_id in linked_accounts:
                raise ValueError("An account can have only one linked overdraft")
            linked_accounts.add(debt.account_id)
            if (
                account is None
                or account.balance is None
                or debt.amount is None
                or account.balance > 0
                or debt.amount != account.balance.copy_negate()
                or debt.currency != account.currency
                or debt.as_of != account.as_of
            ):
                raise ValueError(f"Debt {debt.id}: inconsistent overdraft account")
        debts = {debt.id: debt for debt in self.debts}
        for cashflow in self.cashflows:
            if cashflow.debt_id is not None:
                linked_debt = debts.get(cashflow.debt_id)
                if linked_debt is None or linked_debt.currency != cashflow.currency:
                    raise ValueError(
                        f"Cashflow {cashflow.id}: debt must exist in the same currency"
                    )
        for goal in self.goals:
            for refs, records in (
                (goal.account_ids, accounts),
                (goal.asset_ids, assets),
            ):
                for ref in refs:
                    record = records.get(ref)
                    if record is None:
                        raise ValueError(f"Goal {goal.id}: unknown linked record {ref}")
                    if record.currency != goal.currency:
                        raise ValueError(f"Goal {goal.id}: currency differs from {ref}")
        return self


class AccountChanges(Model):
    add: list[Account] = Field(default_factory=list)
    update: list[Account] = Field(default_factory=list)
    delete: list[Identifier] = Field(default_factory=list)


class AssetChanges(Model):
    add: list[Asset] = Field(default_factory=list)
    update: list[Asset] = Field(default_factory=list)
    delete: list[Identifier] = Field(default_factory=list)


class DebtChanges(Model):
    add: list[Debt] = Field(default_factory=list)
    update: list[Debt] = Field(default_factory=list)
    delete: list[Identifier] = Field(default_factory=list)


class GoalChanges(Model):
    add: list[Goal] = Field(default_factory=list)
    update: list[Goal] = Field(default_factory=list)
    delete: list[Identifier] = Field(default_factory=list)


class TransactionChanges(Model):
    add: list[Transaction] = Field(default_factory=list)
    update: list[Transaction] = Field(default_factory=list)
    delete: list[Identifier] = Field(default_factory=list)


class InventoryChanges(Model):
    add: list[Inventory] = Field(default_factory=list)
    update: list[Inventory] = Field(default_factory=list)
    delete: list[Domain] = Field(default_factory=list)


class CoverageChanges(Model):
    add: list[TransactionCoverage] = Field(default_factory=list)
    update: list[TransactionCoverage] = Field(default_factory=list)
    delete: list[Identifier] = Field(default_factory=list)


class CashflowChanges(Model):
    add: list[Cashflow] = Field(default_factory=list)
    update: list[Cashflow] = Field(default_factory=list)
    delete: list[Identifier] = Field(default_factory=list)


class ChangeRequest(Model):
    contract_version: Literal["topo2.cli/3"] = CONTRACT_VERSION
    accounts: AccountChanges = Field(default_factory=AccountChanges)
    assets: AssetChanges = Field(default_factory=AssetChanges)
    debts: DebtChanges = Field(default_factory=DebtChanges)
    goals: GoalChanges = Field(default_factory=GoalChanges)
    transactions: TransactionChanges = Field(default_factory=TransactionChanges)
    inventories: InventoryChanges = Field(default_factory=InventoryChanges)
    transaction_coverage: CoverageChanges = Field(default_factory=CoverageChanges)
    cashflows: CashflowChanges = Field(default_factory=CashflowChanges)
    cashflow_settings: dict[Currency, CashflowSettings | None] = Field(
        default_factory=dict
    )
    confirmation_token: str | None = None

    @model_validator(mode="before")
    @classmethod
    def current_contract(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("contract_version") == "topo2.cli/2":
            raise ValueError(
                "topo2.cli/2 change requests are unsupported; discover topo2 contract "
                "and prepare a topo2.cli/3 request. Import now preserves omitted labels."
            )
        return value


class Difference(Model):
    section: Literal[
        "accounts",
        "assets",
        "debts",
        "goals",
        "transactions",
        "inventories",
        "transaction_coverage",
        "cashflows",
        "cashflow_settings",
    ]
    id: str
    before: Record | None
    after: Record | None


class ChangeResult(Model):
    status: Literal["preview", "applied", "unchanged"]
    confirmation_token: str | None
    changes: list[Difference]


class Subtotal(Model):
    currency: str
    known_total: Decimal
    missing_ids: list[str]
    complete: bool


class GoalLinkedValue(Model):
    known_amount: Decimal
    percentage: Decimal
    missing_ids: list[str]
    complete: bool


class GoalProgress(Model):
    id: str
    name: str
    currency: str
    target_amount: Decimal
    known_amount: Decimal
    percentage: Decimal
    missing_ids: list[str]
    complete: bool
    target_date: date | None
    reserved_amount: Decimal | None
    monthly_contribution: Decimal | None
    priority: Literal["low", "normal", "high"] | None
    note: str | None
    remaining_amount: Decimal | None
    linked_value: GoalLinkedValue


class InventoryState(Model):
    id: Domain
    status: Literal["unknown", "partial", "complete"]
    checked_on: date | None


class NetWealthSubtotal(Subtotal):
    known_account_asset_total: Decimal
    known_debt_total: Decimal
    linked_debt_ids: list[str]
    inventory_complete: bool


class NetWealth(Model):
    subtotals: list[NetWealthSubtotal]
    inventories: list[InventoryState]


class AvailabilitySubtotal(Model):
    currency: str
    known_free_total: Decimal
    known_restricted_total: Decimal
    unknown_availability_ids: list[str]
    missing_ids: list[str]


class ReservationComparison(Model):
    currency: str
    goal_ids: list[str]
    known_reserved_total: Decimal
    unknown_reservation_ids: list[str]
    known_free_total: Decimal | None
    missing_value_ids: list[str]
    unknown_availability_ids: list[str]
    inventories: list[InventoryState]
    possible_excess: bool | None
    coverage_unknown: bool


class Summary(Model):
    kind: Literal["wealth_overview"] = "wealth_overview"
    subtotals: list[Subtotal]
    goals: list[GoalProgress]
    net_wealth: NetWealth
    availability: list[AvailabilitySubtotal]
    reservation_comparison: list[ReservationComparison]


class TransactionImportOptions(Model):
    format: Literal["json", "csv"]
    confirmation_token: str | None = None
    details: bool = False


class TransactionImportResult(Model):
    status: Literal["preview", "applied", "unchanged"]
    confirmation_token: str | None
    added: int
    updated: int
    skipped: int
    total_changes: int
    truncated: bool
    changes: list[Difference]


class TransactionFilters(Model):
    account_id: Identifier | None = None
    from_date: date | None = None
    to_date: date | None = None
    currency: Currency | None = None
    category: Label | None = None
    min_amount: Money | None = None
    max_amount: Money | None = None
    search: str | None = None

    @model_validator(mode="after")
    def valid_ranges(self) -> Self:
        if (
            self.from_date is not None
            and self.to_date is not None
            and self.from_date > self.to_date
        ):
            raise ValueError("from_date must not follow to_date")
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValueError("min_amount must not exceed max_amount")
        return self


class TransactionQuery(TransactionFilters):
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=1000)] = 100


class TransactionQueryResult(Model):
    records: list[Transaction]
    total: int
    offset: int
    limit: int


class ContextQuery(Model):
    reference_date: date | None = None
    max_age_days: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def explicit_age_policy(self) -> Self:
        if (self.reference_date is None) != (self.max_age_days is None):
            raise ValueError(
                "reference_date and max_age_days must be supplied together"
            )
        return self


class ValueAge(Model):
    id: str
    age_days: int | None
    stale: bool | None


class CoverageState(Model):
    account_id: str
    status: Literal["unknown", "declared"]
    intervals: list[TransactionCoverage]


class Limitation(Model):
    outcome: Literal[
        "wealth_overview",
        "net_wealth",
        "goal_progress",
        "transaction_analysis",
        "monthly_room",
        "availability",
    ]
    code: Literal[
        "inventory_unknown",
        "inventory_partial",
        "missing_values",
        "stale_values",
        "coverage_unknown",
        "coverage_limited",
        "not_supported",
        "availability_unknown",
    ]
    ids: list[str]


class MonthlyRoomQuery(Model):
    reference_date: date


class MonthlyBand(Model):
    lower: Decimal
    upper: Decimal


class NormalizedCashflow(Model):
    id: str
    kind: Literal["income", "expense"]
    monthly_amount: MonthlyBand | None


class MonthlyCurrency(Model):
    currency: str
    records: list[NormalizedCashflow]
    known_income: MonthlyBand
    known_expenses: MonthlyBand
    known_room: MonthlyBand
    missing_ids: list[str]
    complete: bool
    room: MonthlyBand | None
    minimum_reserve: Decimal | None
    note: str | None


class MonthlyRoom(Model):
    reference_date: date
    inventory: InventoryState
    currencies: list[MonthlyCurrency]
    limitations: list[Limitation]


class CompactContext(Model):
    context_id: str
    accounts: list[Account]
    assets: list[Asset]
    debts: list[Debt]
    goals: list[Goal]
    cashflows: list[Cashflow]
    cashflow_settings: dict[Currency, CashflowSettings]
    monthly_room: MonthlyRoom | None
    summary: Summary
    inventories: list[InventoryState]
    transaction_coverage: list[CoverageState]
    age_policy: ContextQuery
    value_age: list[ValueAge]
    limitations: list[Limitation]


class TransactionAggregateQuery(TransactionFilters):
    group_by: list[Literal["month", "category"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_groups(self) -> Self:
        if len(self.group_by) != len(set(self.group_by)):
            raise ValueError("group_by dimensions must be unique")
        return self


class Movement(Model):
    count: int = 0
    receipts: Decimal = Decimal(0)
    outflows: Decimal = Decimal(0)
    net_movement: Decimal = Decimal(0)


class TransactionTotals(Movement):
    currency: str
    income: Decimal = Decimal(0)
    expenses: Decimal = Decimal(0)
    classified_net_cashflow: Decimal = Decimal(0)
    classified_count: int = 0
    unknown_count: int = 0
    classification_complete: bool | None = None
    internal_transfers: Movement = Field(default_factory=Movement)
    unknown: Movement = Field(default_factory=Movement)


class TransactionGroup(TransactionTotals):
    month: str | None = None
    category: str | None = None


class AggregateCoverage(Model):
    account_id: str
    status: Literal["complete", "partial", "unknown", "declared"]
    intervals: list[TransactionCoverage]


class TransactionAggregateResult(Model):
    filters: TransactionAggregateQuery
    count: int
    classification_complete: bool | None
    totals: list[TransactionTotals]
    groups: list[TransactionGroup]
    coverage: list[AggregateCoverage]
