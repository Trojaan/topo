from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

import yaml
from pydantic import Field, JsonValue, ValidationError, model_validator
from yaml.events import AliasEvent, NodeEvent

from topo.models import JsonObject, TopoModel

RuleType = Literal["recognition", "validation", "completeness", "question_priority"]
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]*(?:[./][a-z0-9_-]+)+$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_MAX_YAML_BYTES = 256 * 1024
_MAX_ALIASES = 20
_MAX_EXPANDED_BYTES = 1024 * 1024


class RulePackageError(ValueError):
    def __init__(self, code: str, path: str, reason: str) -> None:
        self.code = code
        self.path = path
        self.reason = reason
        super().__init__(reason)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class RuleCondition(TopoModel):
    predicate: str
    args: JsonObject


class RuleWhen(TopoModel):
    all: tuple[RuleCondition, ...] = Field(min_length=1, max_length=32)


class RuleOutcome(TopoModel):
    outcome: Literal[
        "proposal",
        "attention",
        "error",
        "warning",
        "completeness",
        "ranking",
    ]
    assertion_template: str | None = None
    code: str | None = None
    component: str | None = None
    state: (
        Literal[
            "present", "missing", "conflicting", "insufficiently_current", "unallocated"
        ]
        | None
    ) = None
    priority: Literal["blocking", "required", "helpful", "optional"] | None = None


class DeclarativeRule(TopoModel):
    rule_id: str
    rule_version: str
    rule_type: RuleType
    input_view: str
    when: RuleWhen
    then: RuleOutcome


class DeclarativeRulePackage(TopoModel):
    package_id: str
    package_version: str
    module_id: str
    module_version: str
    rules: tuple[DeclarativeRule, ...] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def unique_rule_ids(self) -> DeclarativeRulePackage:
        ids = [rule.rule_id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule ids must be unique within a package")
        return self


@dataclass(frozen=True)
class PredicateCapability:
    predicate: str
    input_view: str
    arguments: dict[str, tuple[type[object], tuple[JsonValue, ...] | None]]


@dataclass(frozen=True)
class InputViewCapability:
    input_view: str
    rule_type: RuleType
    fields: tuple[str, ...]


class RuleCapabilityRegistry:
    """Trusted, closed registry for effect-free rule inputs and predicates."""

    def __init__(
        self,
        views: tuple[InputViewCapability, ...],
        predicates: tuple[PredicateCapability, ...],
    ) -> None:
        self.views = {item.input_view: item for item in views}
        self.predicates = {item.predicate: item for item in predicates}


def default_rule_registry() -> RuleCapabilityRegistry:
    prefix = "domain.cashflow"
    views = (
        InputViewCapability(
            f"{prefix}.transactions-by-counterparty/0.1",
            "recognition",
            ("transaction_count", "intervals", "frequency"),
        ),
        InputViewCapability(
            f"{prefix}.assertion-validation/0.1",
            "validation",
            ("predicate", "value_type"),
        ),
        InputViewCapability(
            f"{prefix}.analysis-requirements/0.1",
            "completeness",
            ("requirement", "state"),
        ),
        InputViewCapability(
            f"{prefix}.open-questions/0.1",
            "question_priority",
            ("priority", "module_score", "age_days", "rule_id"),
        ),
    )
    predicates = (
        PredicateCapability(
            "transaction_count_at_least",
            views[0].input_view,
            {"count": (int, None)},
        ),
        PredicateCapability(
            "interval_matches",
            views[0].input_view,
            {
                "frequency": (
                    str,
                    ("weekly", "four_weekly", "monthly", "quarterly", "annual"),
                )
            },
        ),
        PredicateCapability(
            "field_present",
            views[1].input_view,
            {"field": (str, views[1].fields)},
        ),
        PredicateCapability(
            "requirement_state_is",
            views[2].input_view,
            {
                "state": (
                    str,
                    (
                        "present",
                        "missing",
                        "conflicting",
                        "insufficiently_current",
                        "unallocated",
                    ),
                )
            },
        ),
        PredicateCapability(
            "question_priority_is",
            views[3].input_view,
            {
                "priority": (
                    str,
                    ("blocking", "required", "helpful", "optional"),
                )
            },
        ),
    )
    return RuleCapabilityRegistry(views, predicates)


def parse_rule_package(payload: str) -> DeclarativeRulePackage:
    encoded = payload.encode("utf-8")
    if len(encoded) > _MAX_YAML_BYTES:
        raise RulePackageError(
            "RULE_PACKAGE_TOO_LARGE", "", "rule YAML exceeds 256 KiB"
        )
    try:
        events = tuple(yaml.parse(payload, Loader=yaml.SafeLoader))
        if sum(isinstance(event, AliasEvent) for event in events) > _MAX_ALIASES:
            raise RulePackageError(
                "RULE_PACKAGE_TOO_COMPLEX", "", "rule YAML has too many aliases"
            )
        if any(
            isinstance(event, NodeEvent)
            and getattr(event, "tag", None) is not None
            and not str(getattr(event, "tag", "")).startswith("tag:yaml.org,2002:")
            for event in events
        ):
            raise RulePackageError(
                "UNSAFE_YAML_TAG", "", "custom YAML tags are not allowed"
            )
        value = yaml.load(payload, Loader=_UniqueKeySafeLoader)
    except RulePackageError:
        raise
    except yaml.YAMLError as error:
        raise RulePackageError("INVALID_RULE_YAML", "", str(error)) from error
    if not isinstance(value, dict):
        raise RulePackageError("INVALID_RULE_PACKAGE", "", "package must be a mapping")
    try:
        expanded_json = json.dumps(value)
    except (TypeError, ValueError) as error:
        raise RulePackageError("INVALID_RULE_PACKAGE", "", str(error)) from error
    if len(expanded_json.encode()) > _MAX_EXPANDED_BYTES:
        raise RulePackageError(
            "RULE_PACKAGE_TOO_COMPLEX",
            "",
            "expanded rule package exceeds 1 MiB",
        )
    try:
        package = DeclarativeRulePackage.model_validate_json(expanded_json, strict=True)
    except ValidationError as error:
        location = "/" + "/".join(str(item) for item in error.errors()[0]["loc"])
        raise RulePackageError("INVALID_RULE_PACKAGE", location, str(error)) from error
    _validate_identifiers(package)
    return package


def validate_rule_package(
    package: DeclarativeRulePackage,
    registry: RuleCapabilityRegistry,
    *,
    pinned_modules: dict[str, str],
) -> None:
    if pinned_modules.get(package.module_id) != package.module_version:
        raise RulePackageError(
            "INCOMPATIBLE_RULE_PACKAGE",
            "/module_version",
            "rule package module version is not pinned by the context manifest",
        )
    outcomes: dict[RuleType, set[str]] = {
        "recognition": {"proposal", "attention"},
        "validation": {"error", "warning"},
        "completeness": {"completeness"},
        "question_priority": {"ranking"},
    }
    for index, rule in enumerate(package.rules):
        base = f"/rules/{index}"
        view = registry.views.get(rule.input_view)
        if view is None:
            raise RulePackageError(
                "UNKNOWN_INPUT_VIEW", f"{base}/input_view", rule.input_view
            )
        if view.rule_type != rule.rule_type:
            raise RulePackageError(
                "CROSS_CAPABILITY_VIEW",
                f"{base}/input_view",
                "input view is not registered for this rule type",
            )
        if rule.then.outcome not in outcomes[rule.rule_type]:
            raise RulePackageError(
                "INVALID_RULE_OUTCOME",
                f"{base}/then/outcome",
                "outcome is outside the rule type capability",
            )
        _validate_outcome_shape(rule, base)
        for condition_index, condition in enumerate(rule.when.all):
            condition_path = f"{base}/when/all/{condition_index}"
            predicate = registry.predicates.get(condition.predicate)
            if predicate is None:
                raise RulePackageError(
                    "UNKNOWN_RULE_PREDICATE",
                    f"{condition_path}/predicate",
                    condition.predicate,
                )
            if predicate.input_view != rule.input_view:
                raise RulePackageError(
                    "CROSS_VIEW_PREDICATE",
                    f"{condition_path}/predicate",
                    "predicate belongs to a different input view",
                )
            _validate_args(condition.args, predicate, condition_path)


def canonical_rule_package_bytes(package: DeclarativeRulePackage) -> bytes:
    return (
        json.dumps(
            package.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def package_checksum(package: DeclarativeRulePackage) -> str:
    return "sha256:" + hashlib.sha256(canonical_rule_package_bytes(package)).hexdigest()


def preview_ref(package: DeclarativeRulePackage, generation_id: str) -> str:
    basis = f"{generation_id}\x1f{package_checksum(package)}".encode()
    return "preview:sha256:" + hashlib.sha256(basis).hexdigest()


def preview_traces(package: DeclarativeRulePackage) -> list[JsonValue]:
    traces: list[JsonValue] = []
    for rule in sorted(package.rules, key=lambda item: item.rule_id):
        conditions: list[JsonValue] = []
        for condition in rule.when.all:
            conditions.append(
                {
                    "predicate": condition.predicate,
                    "args": condition.args,
                    "result": False,
                    "reason": "preview_input_view_is_empty",
                }
            )
        traces.append(
            {
                "package_id": package.package_id,
                "package_version": package.package_version,
                "rule_id": rule.rule_id,
                "rule_version": rule.rule_version,
                "rule_type": rule.rule_type,
                "input_view": rule.input_view,
                "conditions": conditions,
                "matched": False,
                "outcome": rule.then.outcome,
            }
        )
    return traces


def _validate_identifiers(package: DeclarativeRulePackage) -> None:
    values = {
        "/package_id": package.package_id,
        "/module_id": package.module_id,
        **{
            f"/rules/{index}/rule_id": rule.rule_id
            for index, rule in enumerate(package.rules)
        },
    }
    for path, value in values.items():
        if _IDENTIFIER.fullmatch(value) is None:
            raise RulePackageError("INVALID_RULE_IDENTIFIER", path, value)
    versions = {
        "/package_version": package.package_version,
        "/module_version": package.module_version,
        **{
            f"/rules/{index}/rule_version": rule.rule_version
            for index, rule in enumerate(package.rules)
        },
    }
    for path, value in versions.items():
        if _VERSION.fullmatch(value) is None:
            raise RulePackageError("INVALID_RULE_VERSION", path, value)


def _validate_args(
    args: JsonObject, predicate: PredicateCapability, condition_path: str
) -> None:
    if set(args) != set(predicate.arguments):
        raise RulePackageError(
            "INVALID_PREDICATE_ARGUMENTS",
            f"{condition_path}/args",
            "predicate arguments do not match its registered contract",
        )
    for name, (expected_type, allowed) in predicate.arguments.items():
        value = args[name]
        if expected_type is int:
            valid_type = type(value) is int and value >= 0
        else:
            valid_type = isinstance(value, expected_type)
        if not valid_type or (allowed is not None and value not in allowed):
            code = (
                "CROSS_VIEW_FIELD" if name == "field" else "INVALID_PREDICATE_ARGUMENTS"
            )
            raise RulePackageError(code, f"{condition_path}/args/{name}", str(value))


def _validate_outcome_shape(rule: DeclarativeRule, base: str) -> None:
    then = rule.then
    required: dict[str, str | None] = {}
    allowed = {"outcome"}
    if then.outcome == "proposal":
        required["assertion_template"] = then.assertion_template
        allowed.add("assertion_template")
    elif then.outcome in {"attention", "error", "warning"}:
        required["code"] = then.code
        allowed.add("code")
    elif then.outcome == "completeness":
        required.update(component=then.component, state=then.state)
        allowed.update(("component", "state"))
    elif then.outcome == "ranking":
        required["priority"] = then.priority
        allowed.add("priority")
    unexpected = then.model_fields_set - allowed
    if unexpected:
        raise RulePackageError(
            "INVALID_RULE_OUTCOME",
            f"{base}/then",
            f"{then.outcome} does not allow {', '.join(sorted(unexpected))}",
        )
    if any(value is None for value in required.values()):
        raise RulePackageError(
            "INVALID_RULE_OUTCOME",
            f"{base}/then",
            f"{then.outcome} requires {', '.join(required)}",
        )
