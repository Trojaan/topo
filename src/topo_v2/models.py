from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

CONTRACT_VERSION: Literal["topo2.cli/1"] = "topo2.cli/1"
SCHEMA_VERSION: Literal["topo2.context/1"] = "topo2.context/1"
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


class Account(ValuedRecord):
    type: Literal["payment", "savings", "investment"]
    balance: Money | None = None

    @model_validator(mode="after")
    def dated_balance(self) -> Self:
        if self.balance is not None and self.as_of is None:
            raise ValueError("A balance requires as_of")
        return self


class Asset(ValuedRecord):
    type: Literal["etf", "property", "vehicle", "cash", "investment", "other"]
    value: Annotated[Money, Field(ge=0)] | None = None
    broker_account_id: Identifier | None = None

    @model_validator(mode="after")
    def dated_value(self) -> Self:
        if self.value is not None and self.as_of is None:
            raise ValueError("A value requires as_of")
        return self


class Goal(Model):
    id: Identifier
    name: Label
    target_amount: Annotated[Money, Field(gt=0)]
    currency: Currency = "EUR"
    target_date: date | None = None
    account_ids: list[Identifier] = Field(default_factory=list)
    asset_ids: list[Identifier] = Field(default_factory=list)


Record = Account | Asset | Goal


class Context(Model):
    schema_version: Literal["topo2.context/1"] = SCHEMA_VERSION
    context_id: str
    accounts: list[Account] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    goals: list[Goal] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self) -> Self:
        all_ids = (
            [account.id for account in self.accounts]
            + [asset.id for asset in self.assets]
            + [goal.id for goal in self.goals]
        )
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Record IDs must be unique across the context")
        accounts = {account.id: account for account in self.accounts}
        assets = {asset.id: asset for asset in self.assets}
        for asset in self.assets:
            if asset.broker_account_id is not None:
                broker = accounts.get(asset.broker_account_id)
                if broker is None or broker.type != "investment":
                    raise ValueError(
                        f"Asset {asset.id}: broker must be an investment account"
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


class GoalChanges(Model):
    add: list[Goal] = Field(default_factory=list)
    update: list[Goal] = Field(default_factory=list)
    delete: list[Identifier] = Field(default_factory=list)


class ChangeRequest(Model):
    contract_version: Literal["topo2.cli/1"] = CONTRACT_VERSION
    accounts: AccountChanges = Field(default_factory=AccountChanges)
    assets: AssetChanges = Field(default_factory=AssetChanges)
    goals: GoalChanges = Field(default_factory=GoalChanges)
    confirmation_token: str | None = None


class Difference(Model):
    section: Literal["accounts", "assets", "goals"]
    id: str
    before: Record | None
    after: Record | None


class ChangeResult(Model):
    status: Literal["preview", "applied"]
    confirmation_token: str
    changes: list[Difference]


class Subtotal(Model):
    currency: str
    known_total: Decimal
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


class Summary(Model):
    kind: Literal["wealth_overview"] = "wealth_overview"
    subtotals: list[Subtotal]
    goals: list[GoalProgress]
