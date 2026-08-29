from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from topo.errors import ProposalDecisionError
from topo.models import (
    AssertionRecord,
    EntityRecord,
    ProposedAssertion,
    RecurringCashflowValue,
    TransactionCoverageValue,
)
from topo.modules import (
    ENGINE_CONTRACT_VERSION,
    ModuleCatalog,
    ModuleConstraint,
    ModuleDependency,
    module_descriptor,
)


def _validate_distribution(
    assertion: ProposedAssertion,
    existing: tuple[AssertionRecord, ...],
    entities: tuple[EntityRecord, ...],
) -> None:
    del existing, entities
    distribution = assertion.module_data.get("distribution")
    if not isinstance(distribution, dict) or distribution.get("complete") is not True:
        return
    shares = distribution.get("shares")
    values: tuple[Decimal, ...]
    if not isinstance(shares, list):
        values = ()
    else:
        try:
            values = tuple(Decimal(share) for share in shares if isinstance(share, str))
        except InvalidOperation:
            values = ()
    if (
        not isinstance(shares, list)
        or len(values) != len(shares)
        or not values
        or any(share < 0 or share > 1 for share in values)
        or sum(values) != 1
    ):
        raise ProposalDecisionError(
            "INVALID_COMPLETE_DISTRIBUTION",
            "/proposal/proposed_assertion/module_data/distribution/shares",
            "an explicitly complete distribution must contain shares totaling 1",
        )


def _validate_double_counting(
    assertion: ProposedAssertion,
    existing: tuple[AssertionRecord, ...],
    entities: tuple[EntityRecord, ...],
) -> None:
    del entities
    counting_key = assertion.module_data.get("economic_interest_ref")
    valuation_basis = assertion.module_data.get("valuation_basis")
    conflicting_bases = (
        {"account_balance", "asset_value"},
        {"portfolio_total", "position_sum"},
        {"credit_account", "debt_balance"},
    )
    if (
        isinstance(counting_key, str)
        and isinstance(valuation_basis, str)
        and any(
            stored.module_data.get("economic_interest_ref") == counting_key
            and isinstance(
                stored_basis := stored.module_data.get("valuation_basis"), str
            )
            and {stored_basis, valuation_basis} in conflicting_bases
            for stored in existing
        )
    ):
        raise ProposalDecisionError(
            "DEMONSTRABLE_DOUBLE_COUNTING",
            "/proposal/proposed_assertion/module_data/valuation_basis",
            "the proposed meaning demonstrably double counts another value",
        )


def _validate_dutch_semantics(
    assertion: ProposedAssertion,
    existing: tuple[AssertionRecord, ...],
    entities: tuple[EntityRecord, ...],
) -> None:
    if assertion.predicate == "jurisdiction.nl/valuation/woz":
        valuation_date = assertion.module_data.get("valuation_date")
        valid_valuation_date = False
        if isinstance(valuation_date, str):
            try:
                date.fromisoformat(valuation_date)
                valid_valuation_date = True
            except ValueError:
                pass
        if not valid_valuation_date:
            raise ProposalDecisionError(
                "NL_WOZ_AS_OF_DATE_REQUIRED",
                "/proposal/proposed_assertion/module_data/valuation_date",
                "a WOZ valuation requires a valid valuation_date",
            )
    if assertion.predicate.startswith("jurisdiction.nl/coverage/"):
        target = next(
            (
                entity
                for entity in entities
                if assertion.object_ref is not None
                and entity.id == assertion.object_ref.id
            ),
            None,
        )
        target_type = target.entity_type if target is not None else None
        coverage = assertion.predicate.rsplit("/", 1)[-1]
        allowed = {
            "basic_health": {"person"},
            "supplementary_health": {"person"},
            "dental": {"person"},
            "building": {"asset"},
            "contents": {"asset", "household"},
            "glass": {"asset"},
            "personal_liability": {"person", "household"},
            "motor_third_party": {"asset"},
            "motor_limited_casco": {"asset"},
            "motor_full_casco": {"asset"},
            "term_life": {"person"},
            "disability": {"person"},
            "accident": {"person"},
            "funeral": {"person"},
        }.get(coverage, {"person", "household", "asset", "liability"})
        if not isinstance(target_type, str) or target_type not in allowed:
            raise ProposalDecisionError(
                "INVALID_COVERAGE_TARGET_TYPE",
                "/proposal/proposed_assertion/module_data/target_type",
                f"{coverage} cannot cover target type {target_type!r}",
            )
        if coverage == "other" and not assertion.module_data.get("source_name"):
            raise ProposalDecisionError(
                "NL_OTHER_COVERAGE_SOURCE_NAME_REQUIRED",
                "/proposal/proposed_assertion/module_data/source_name",
                "other coverage requires its original source name",
            )
    if assertion.predicate.startswith("jurisdiction.nl/qualification/") and any(
        stored.subject_ref == assertion.subject_ref
        and stored.predicate == assertion.predicate
        and stored.valid_time.start < (assertion.valid_time.end_exclusive or date.max)
        and assertion.valid_time.start < (stored.valid_time.end_exclusive or date.max)
        for stored in existing
    ):
        raise ProposalDecisionError(
            "OVERLAPPING_EXCLUSIVE_CLASSIFICATION",
            "/proposal/proposed_assertion/valid_time",
            "an exclusive qualification already applies during this period",
        )


def _classification_ids(module_id: str, names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"{module_id}/classification/{name}" for name in names)


def _exclusive_classification_constraint(
    module_id: str, names: tuple[str, ...]
) -> ModuleConstraint:
    exclusive_predicates = set(_classification_ids(module_id, names))

    def validate(
        assertion: ProposedAssertion,
        existing: tuple[AssertionRecord, ...],
        entities: tuple[EntityRecord, ...],
    ) -> None:
        del entities
        if assertion.predicate not in exclusive_predicates:
            return
        if any(
            stored.subject_ref == assertion.subject_ref
            and stored.predicate in exclusive_predicates
            and stored.predicate != assertion.predicate
            and stored.valid_time.start
            < (assertion.valid_time.end_exclusive or date.max)
            and assertion.valid_time.start
            < (stored.valid_time.end_exclusive or date.max)
            for stored in existing
        ):
            raise ProposalDecisionError(
                "OVERLAPPING_EXCLUSIVE_CLASSIFICATION",
                "/proposal/proposed_assertion/valid_time",
                "an exclusive classification already applies during this period",
            )

    return ModuleConstraint(f"{module_id}.exclusive-classification", validate)


def _validate_recurring_cashflow(
    assertion: ProposedAssertion,
    existing: tuple[AssertionRecord, ...],
    entities: tuple[EntityRecord, ...],
) -> None:
    del existing
    if assertion.predicate != "domain.cashflow/recurring_cashflow":
        return
    subject = next(
        (entity for entity in entities if entity.id == assertion.subject_ref.id), None
    )
    if subject is None or subject.entity_type not in {"person", "household"}:
        raise ProposalDecisionError(
            "INVALID_RECURRING_CASHFLOW_SCOPE",
            "/proposal/proposed_assertion/subject_ref",
            "a recurring cashflow must belong to a person or household",
        )
    if (
        assertion.object_value is None
        or assertion.object_value.value_type != "recurring_cashflow"
    ):
        raise ProposalDecisionError(
            "INVALID_RECURRING_CASHFLOW",
            "/proposal/proposed_assertion/object_value",
            "a recurring cashflow requires a typed value",
        )
    try:
        RecurringCashflowValue.model_validate_json(
            json.dumps(assertion.object_value.value), strict=True
        )
    except ValidationError as error:
        raise ProposalDecisionError(
            "INVALID_RECURRING_CASHFLOW",
            "/proposal/proposed_assertion/object_value/value",
            str(error),
        ) from error


def _validate_transaction_coverage(
    assertion: ProposedAssertion,
    existing: tuple[AssertionRecord, ...],
    entities: tuple[EntityRecord, ...],
) -> None:
    del existing
    if assertion.predicate != "domain.accounts/transaction_coverage":
        return
    subject = next(
        (entity for entity in entities if entity.id == assertion.subject_ref.id), None
    )
    if subject is None or subject.entity_type != "account":
        raise ProposalDecisionError(
            "INVALID_TRANSACTION_COVERAGE_SUBJECT",
            "/proposal/proposed_assertion/subject_ref",
            "transaction coverage must belong to an account",
        )
    if (
        assertion.object_value is None
        or assertion.object_value.value_type != "transaction_coverage"
    ):
        raise ProposalDecisionError(
            "INVALID_TRANSACTION_COVERAGE",
            "/proposal/proposed_assertion/object_value",
            "transaction coverage requires a typed period",
        )
    try:
        coverage = TransactionCoverageValue.model_validate_json(
            json.dumps(assertion.object_value.value), strict=True
        )
    except ValidationError as error:
        raise ProposalDecisionError(
            "INVALID_TRANSACTION_COVERAGE",
            "/proposal/proposed_assertion/object_value/value",
            str(error),
        ) from error
    if (
        coverage.start_date != assertion.valid_time.start
        or coverage.end_exclusive != assertion.valid_time.end_exclusive
    ):
        raise ProposalDecisionError(
            "INVALID_TRANSACTION_COVERAGE",
            "/proposal/proposed_assertion/valid_time",
            "coverage value and validity period must match",
        )


def default_module_catalog() -> ModuleCatalog:
    parties = module_descriptor(
        "domain.parties",
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=(
            "domain.parties/household_membership",
            "domain.parties/ownership",
            "domain.parties/household_allocation",
            "domain.parties/account_holder",
            "domain.parties/debtor",
            "domain.parties/practical_use",
            "domain.parties/scope",
            "domain.parties/beneficiary",
        ),
        constraints=(
            ModuleConstraint("complete-distribution", _validate_distribution),
        ),
    )
    accounts = module_descriptor(
        "domain.accounts",
        dependencies=(ModuleDependency("domain.parties", "0.1.0"),),
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=(
            *_classification_ids(
                "domain.accounts",
                ("payment_account", "savings_account", "investment_account"),
            ),
            "domain.accounts/operator",
            "domain.accounts/posting",
            "domain.accounts/position",
            "domain.accounts/transaction_coverage",
        ),
        constraints=(
            _exclusive_classification_constraint(
                "domain.accounts",
                ("payment_account", "savings_account", "investment_account"),
            ),
            ModuleConstraint("account-double-counting", _validate_double_counting),
            ModuleConstraint(
                "transaction-coverage-shape", _validate_transaction_coverage
            ),
        ),
    )
    cashflow_names = (
        "income",
        "expense",
        "internal_transfer",
        "unclassified",
        "salary",
        "holiday_allowance",
        "self_employment",
        "pension_payment",
        "social_benefit",
        "allowance",
        "alimony",
        "interest",
        "dividend",
        "housing",
        "groceries_household",
        "transport",
        "healthcare",
        "insurance",
        "taxes",
        "childcare_education",
        "subscriptions",
        "leisure",
        "debt_payment",
        "other_expense",
    )
    cashflow = module_descriptor(
        "domain.cashflow",
        dependencies=(ModuleDependency("domain.accounts", "0.1.0"),),
        capabilities=("classifications", "constraints", "input_views", "recognition"),
        public_identifiers=(
            "domain.cashflow/monthly_salary",
            "domain.cashflow/booking_date",
            "domain.cashflow/money",
            "domain.cashflow/description",
            "domain.cashflow/source_classification",
            "domain.cashflow/counterparty",
            "domain.cashflow/transfer_counterpart",
            "domain.cashflow/pattern_evidence",
            "domain.cashflow/recurring_cashflow",
            *_classification_ids("domain.cashflow", cashflow_names),
        ),
        constraints=(
            _exclusive_classification_constraint("domain.cashflow", cashflow_names),
            ModuleConstraint("recurring-cashflow-shape", _validate_recurring_cashflow),
        ),
    )
    assets = module_descriptor(
        "domain.assets",
        dependencies=(ModuleDependency("domain.parties", "0.1.0"),),
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=_classification_ids(
            "domain.assets",
            (
                "real_estate",
                "vehicle",
                "investment",
                "cash",
                "valuable",
                "other_asset",
                "etf",
            ),
        ),
        constraints=(
            _exclusive_classification_constraint(
                "domain.assets",
                (
                    "real_estate",
                    "vehicle",
                    "investment",
                    "cash",
                    "valuable",
                    "other_asset",
                ),
            ),
            ModuleConstraint("asset-double-counting", _validate_double_counting),
        ),
    )
    debts = module_descriptor(
        "domain.debts",
        dependencies=(ModuleDependency("domain.parties", "0.1.0"),),
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=(
            *_classification_ids(
                "domain.debts",
                (
                    "mortgage_loan",
                    "student_loan",
                    "personal_loan",
                    "informal_loan",
                    "other_debt",
                ),
            ),
            "domain.debts/collateral",
        ),
        constraints=(
            _exclusive_classification_constraint(
                "domain.debts",
                (
                    "mortgage_loan",
                    "student_loan",
                    "personal_loan",
                    "informal_loan",
                    "other_debt",
                ),
            ),
            ModuleConstraint("debt-double-counting", _validate_double_counting),
        ),
    )
    contracts = module_descriptor(
        "domain.contracts",
        dependencies=(ModuleDependency("domain.parties", "0.1.0"),),
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=(
            *_classification_ids(
                "domain.contracts",
                (
                    "employment",
                    "rental",
                    "loan",
                    "mortgage",
                    "insurance",
                    "pension",
                    "service",
                    "subscription",
                    "other_contract",
                ),
            ),
            "domain.contracts/contract_party",
            "domain.contracts/contract_link",
            "domain.contracts/caused_cashflow",
        ),
        constraints=(
            _exclusive_classification_constraint(
                "domain.contracts",
                (
                    "employment",
                    "rental",
                    "loan",
                    "mortgage",
                    "insurance",
                    "pension",
                    "service",
                    "subscription",
                    "other_contract",
                ),
            ),
        ),
    )
    insurance = module_descriptor(
        "domain.insurance",
        dependencies=(ModuleDependency("domain.contracts", "0.1.0"),),
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=("domain.insurance/insured_subject",),
    )
    pensions = module_descriptor(
        "domain.pensions",
        dependencies=(
            ModuleDependency("domain.accounts", "0.1.0"),
            ModuleDependency("domain.contracts", "0.1.0"),
        ),
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=("domain.pensions/entitlement",),
    )
    goals = module_descriptor(
        "domain.goals",
        dependencies=(ModuleDependency("domain.parties", "0.1.0"),),
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=("domain.goals/affects", "domain.goals/affected_event"),
    )
    dutch = module_descriptor(
        "jurisdiction.nl",
        dependencies=(
            ModuleDependency("domain.accounts", "0.1.0"),
            ModuleDependency("domain.assets", "0.1.0"),
            ModuleDependency("domain.cashflow", "0.1.0"),
            ModuleDependency("domain.debts", "0.1.0"),
            ModuleDependency("domain.insurance", "0.1.0"),
            ModuleDependency("domain.pensions", "0.1.0"),
        ),
        capabilities=("classifications", "constraints", "input_views"),
        public_identifiers=tuple(
            f"jurisdiction.nl/{path}"
            for path in (
                "qualification/retirement_restriction",
                "qualification/annuity_restriction",
                "qualification/owner_occupied_home_debt",
                "valuation/woz",
                "pension_origin/aow",
                "pension_origin/employer",
                "pension_origin/individual",
                "income/aow",
                "income/allowance",
                "expense/health_insurance_premium",
                "expense/municipal_tax",
                "expense/water_authority_tax",
                "coverage/basic_health",
                "coverage/supplementary_health",
                "coverage/dental",
                "coverage/building",
                "coverage/contents",
                "coverage/glass",
                "coverage/personal_liability",
                "coverage/motor_third_party",
                "coverage/motor_limited_casco",
                "coverage/motor_full_casco",
                "coverage/travel",
                "coverage/cancellation",
                "coverage/term_life",
                "coverage/disability",
                "coverage/accident",
                "coverage/funeral",
                "coverage/legal_assistance",
                "coverage/other",
            )
        ),
        constraints=(
            ModuleConstraint("dutch-semantics", _validate_dutch_semantics),
            ModuleConstraint("dutch-double-counting", _validate_double_counting),
        ),
    )
    core = module_descriptor("topo.core", capabilities=("graph_invariants",))
    return ModuleCatalog(
        (
            core,
            parties,
            accounts,
            cashflow,
            assets,
            debts,
            contracts,
            insurance,
            pensions,
            goals,
            dutch,
        ),
        engine_contract_version=ENGINE_CONTRACT_VERSION,
    )
