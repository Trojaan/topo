from __future__ import annotations

from copy import deepcopy

import pytest

from topo.rules import (
    RulePackageError,
    default_rule_registry,
    parse_rule_package,
    validate_rule_package,
)


def complete_package() -> str:
    return """
package_id: domain.cashflow.rules
package_version: 0.1.0
module_id: domain.cashflow
module_version: 0.1.0
rules:
  - rule_id: cashflow.salary-monthly
    rule_version: 0.1.0
    rule_type: recognition
    input_view: domain.cashflow.transactions-by-counterparty/0.1
    when:
      all:
        - predicate: transaction_count_at_least
          args: {count: 3}
        - predicate: interval_matches
          args: {frequency: monthly}
    then:
      outcome: proposal
      assertion_template: domain.cashflow/recurring_cashflow
  - rule_id: cashflow.value-required
    rule_version: 0.1.0
    rule_type: validation
    input_view: domain.cashflow.assertion-validation/0.1
    when:
      all:
        - predicate: field_present
          args: {field: value_type}
    then: {outcome: warning, code: VALUE_TYPE_REQUIRED}
  - rule_id: cashflow.requirement-missing
    rule_version: 0.1.0
    rule_type: completeness
    input_view: domain.cashflow.analysis-requirements/0.1
    when:
      all:
        - predicate: requirement_state_is
          args: {state: missing}
    then:
      outcome: completeness
      component: analysis.normalized_monthly_cashflow/total
      state: missing
  - rule_id: cashflow.required-first
    rule_version: 0.1.0
    rule_type: question_priority
    input_view: domain.cashflow.open-questions/0.1
    when:
      all:
        - predicate: question_priority_is
          args: {priority: required}
    then: {outcome: ranking, priority: required}
"""


def validate(payload: str) -> None:
    validate_rule_package(
        parse_rule_package(payload),
        default_rule_registry(),
        pinned_modules={"domain.cashflow": "0.1.0"},
    )


def test_all_four_registered_rule_types_are_accepted() -> None:
    validate(complete_package())


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        ("transaction_count_at_least", "execute_python", "UNKNOWN_RULE_PREDICATE"),
        (
            "args: {field: value_type}",
            "args: {field: transaction_count}",
            "CROSS_VIEW_FIELD",
        ),
        ("outcome: proposal", "outcome: warning", "INVALID_RULE_OUTCOME"),
        (
            "args: {count: 3}",
            "args: {count: 3, eval: dangerous}",
            "INVALID_PREDICATE_ARGUMENTS",
        ),
        (
            "assertion_template: domain.cashflow/recurring_cashflow",
            "assertion_template: domain.cashflow/recurring_cashflow\n      code: NOT_ALLOWED",
            "INVALID_RULE_OUTCOME",
        ),
    ],
)
def test_unknown_capabilities_cross_view_fields_and_free_expressions_are_rejected(
    old: str, new: str, code: str
) -> None:
    payload = complete_package().replace(old, new, 1)

    with pytest.raises(RulePackageError) as captured:
        validate(payload)

    assert captured.value.code == code


def test_custom_yaml_tags_are_rejected() -> None:
    payload = complete_package().replace(
        "package_id: domain.cashflow.rules",
        "package_id: !custom domain.cashflow.rules",
    )

    with pytest.raises(RulePackageError) as captured:
        validate(payload)

    assert captured.value.code in {"UNSAFE_YAML_TAG", "INVALID_RULE_YAML"}


def test_rule_type_cannot_read_another_capability_view() -> None:
    package = parse_rule_package(complete_package())
    value = package.model_dump(mode="json")
    changed = deepcopy(value)
    changed["rules"][0]["input_view"] = "domain.cashflow.assertion-validation/0.1"

    with pytest.raises(RulePackageError) as captured:
        validate_rule_package(
            type(package).model_validate(changed),
            default_rule_registry(),
            pinned_modules={"domain.cashflow": "0.1.0"},
        )

    assert captured.value.code == "CROSS_CAPABILITY_VIEW"
