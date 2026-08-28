from __future__ import annotations

import hashlib
import inspect
import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from topo.errors import ProposalDecisionError, SemanticModulesUnavailableError
from topo.models import AssertionRecord, EntityRecord, ModulePin, ProposedAssertion

ENGINE_CONTRACT_VERSION = "topo.engine/0.1"
_MODULE_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_]*$")
_PUBLIC_IDENTIFIER = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+(?:/[a-z][a-z0-9_]*)+$"
)
ConstraintValidator = Callable[
    [ProposedAssertion, tuple[AssertionRecord, ...], tuple[EntityRecord, ...]], None
]


class ModuleCatalogError(ValueError):
    """A trusted module catalog cannot be loaded safely."""


@dataclass(frozen=True)
class ModuleDependency:
    module_id: str
    version: str


@dataclass(frozen=True)
class ModuleConstraint:
    constraint_id: str
    validate: ConstraintValidator


@dataclass(frozen=True)
class ModuleDescriptor:
    module_id: str
    module_version: str
    engine_contract_versions: tuple[str, ...]
    dependencies: tuple[ModuleDependency, ...]
    capabilities: tuple[str, ...]
    public_identifiers: tuple[str, ...]
    checksum: str
    constraints: tuple[ModuleConstraint, ...] = ()


def module_checksum(
    *,
    module_id: str,
    module_version: str,
    engine_contract_versions: tuple[str, ...],
    dependencies: tuple[ModuleDependency, ...],
    capabilities: tuple[str, ...],
    public_identifiers: tuple[str, ...],
    constraints: tuple[ModuleConstraint, ...] = (),
) -> str:
    """Digest the public contract and exact executable constraint source."""
    artifact = {
        "module_id": module_id,
        "module_version": module_version,
        "engine_contract_versions": list(engine_contract_versions),
        "dependencies": [
            {"module_id": item.module_id, "version": item.version}
            for item in dependencies
        ],
        "capabilities": list(capabilities),
        "public_identifiers": list(public_identifiers),
        "constraints": [
            {
                "constraint_id": constraint.constraint_id,
                "source": inspect.getsource(constraint.validate),
            }
            for constraint in constraints
        ],
    }
    payload = json.dumps(
        artifact, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def module_descriptor(
    module_id: str,
    *,
    dependencies: tuple[ModuleDependency, ...] = (),
    capabilities: tuple[str, ...] = ("classifications",),
    public_identifiers: tuple[str, ...] = (),
    constraints: tuple[ModuleConstraint, ...] = (),
) -> ModuleDescriptor:
    module_version = "0.1.0"
    checksum = module_checksum(
        module_id=module_id,
        module_version=module_version,
        engine_contract_versions=(ENGINE_CONTRACT_VERSION,),
        dependencies=dependencies,
        capabilities=capabilities,
        public_identifiers=public_identifiers,
        constraints=constraints,
    )
    return ModuleDescriptor(
        module_id=module_id,
        module_version=module_version,
        engine_contract_versions=(ENGINE_CONTRACT_VERSION,),
        dependencies=dependencies,
        capabilities=capabilities,
        public_identifiers=public_identifiers,
        checksum=checksum,
        constraints=constraints,
    )


class ModuleCatalog:
    """Validated, dependency-ordered registry of trusted semantic modules."""

    def __init__(
        self,
        modules: tuple[ModuleDescriptor, ...],
        *,
        engine_contract_version: str,
    ) -> None:
        by_id: dict[str, ModuleDescriptor] = {}
        for module in modules:
            self._validate_descriptor(module, engine_contract_version)
            if module.module_id in by_id:
                raise ModuleCatalogError(
                    f"duplicate module identifier: {module.module_id}"
                )
            by_id[module.module_id] = module
        self._validate_dependencies(modules, by_id)
        self._modules = self._dependency_order(by_id)
        self._by_id = by_id

    @property
    def modules(self) -> tuple[ModuleDescriptor, ...]:
        return self._modules

    @property
    def pins(self) -> tuple[ModulePin, ...]:
        return tuple(
            ModulePin(
                module_id=module.module_id,
                module_version=module.module_version,
                checksum=module.checksum,
            )
            for module in self._modules
        )

    def require_capability(self, module_id: str, capability: str) -> ModuleDescriptor:
        module = self._by_id.get(module_id)
        if module is None:
            raise ModuleCatalogError(f"missing module: {module_id}")
        if capability not in module.capabilities:
            raise ModuleCatalogError(
                f"module {module_id} does not provide capability {capability}"
            )
        return module

    def owner_of(self, identifier: str) -> ModuleDescriptor:
        for module in self._modules:
            if identifier in module.public_identifiers:
                return module
        raise ModuleCatalogError(
            f"identifier is not in a public contract: {identifier}"
        )

    def validate_proposed_assertion(
        self,
        assertion: ProposedAssertion,
        pins: tuple[ModulePin, ...],
        existing_assertions: tuple[AssertionRecord, ...],
        entities: tuple[EntityRecord, ...],
    ) -> None:
        try:
            owner = self.owner_of(assertion.predicate)
        except ModuleCatalogError as error:
            namespace = assertion.predicate.split("/", 1)[0]
            if any(pin.module_id == namespace for pin in pins):
                raise SemanticModulesUnavailableError((namespace,)) from error
            raise ProposalDecisionError(
                "UNKNOWN_SEMANTIC_IDENTIFIER",
                "/proposal/proposed_assertion/predicate",
                str(error),
            ) from error
        self._require_pinned(owner, pins)
        for constraint in owner.constraints:
            constraint.validate(assertion, existing_assertions, entities)

    def _require_pinned(
        self, module: ModuleDescriptor, pins: tuple[ModulePin, ...]
    ) -> None:
        pinned = {pin.module_id: pin for pin in pins}
        required: dict[str, ModuleDescriptor] = {}

        def include(candidate: ModuleDescriptor) -> None:
            if candidate.module_id in required:
                return
            required[candidate.module_id] = candidate
            for dependency in candidate.dependencies:
                include(self._by_id[dependency.module_id])

        include(module)
        unavailable = tuple(
            candidate.module_id
            for candidate in required.values()
            if (pin := pinned.get(candidate.module_id)) is None
            or pin.module_version != candidate.module_version
            or pin.checksum != candidate.checksum
        )
        if unavailable:
            raise SemanticModulesUnavailableError(unavailable)

    @staticmethod
    def _validate_dependencies(
        modules: tuple[ModuleDescriptor, ...], by_id: dict[str, ModuleDescriptor]
    ) -> None:
        for module in modules:
            for dependency in module.dependencies:
                installed = by_id.get(dependency.module_id)
                if installed is None:
                    raise ModuleCatalogError(
                        f"missing dependency {dependency.module_id} for {module.module_id}"
                    )
                if installed.module_version != dependency.version:
                    raise ModuleCatalogError(
                        "incompatible dependency version "
                        f"{dependency.module_id}: expected {dependency.version}, "
                        f"found {installed.module_version}"
                    )

    @staticmethod
    def _validate_descriptor(
        module: ModuleDescriptor, engine_contract_version: str
    ) -> None:
        if _MODULE_ID.fullmatch(module.module_id) is None:
            raise ModuleCatalogError(f"invalid module identifier: {module.module_id}")
        if _VERSION.fullmatch(module.module_version) is None:
            raise ModuleCatalogError(f"invalid module version: {module.module_version}")
        if not module.capabilities or any(
            _CAPABILITY.fullmatch(capability) is None
            for capability in module.capabilities
        ):
            raise ModuleCatalogError(f"invalid capabilities for {module.module_id}")
        if len(module.capabilities) != len(set(module.capabilities)):
            raise ModuleCatalogError(f"duplicate capability for {module.module_id}")
        if engine_contract_version not in module.engine_contract_versions:
            raise ModuleCatalogError(
                f"module {module.module_id} is incompatible with {engine_contract_version}"
            )
        for dependency in module.dependencies:
            if _MODULE_ID.fullmatch(dependency.module_id) is None:
                raise ModuleCatalogError(
                    f"invalid dependency identifier: {dependency.module_id}"
                )
            if _VERSION.fullmatch(dependency.version) is None:
                raise ModuleCatalogError(
                    f"invalid dependency version: {dependency.version}"
                )
        if len(module.public_identifiers) != len(set(module.public_identifiers)) or any(
            _PUBLIC_IDENTIFIER.fullmatch(identifier) is None
            or not identifier.startswith(module.module_id + "/")
            for identifier in module.public_identifiers
        ):
            raise ModuleCatalogError(
                f"public identifier outside module namespace: {module.module_id}"
            )
        expected = module_checksum(
            module_id=module.module_id,
            module_version=module.module_version,
            engine_contract_versions=module.engine_contract_versions,
            dependencies=module.dependencies,
            capabilities=module.capabilities,
            public_identifiers=module.public_identifiers,
            constraints=module.constraints,
        )
        if module.checksum != expected:
            raise ModuleCatalogError(f"checksum mismatch for {module.module_id}")

    @staticmethod
    def _dependency_order(
        modules: dict[str, ModuleDescriptor],
    ) -> tuple[ModuleDescriptor, ...]:
        ordered: list[ModuleDescriptor] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(module_id: str) -> None:
            if module_id in visiting:
                raise ModuleCatalogError("dependency cycle detected")
            if module_id in visited:
                return
            visiting.add(module_id)
            module = modules[module_id]
            for dependency in sorted(
                module.dependencies, key=lambda item: item.module_id
            ):
                visit(dependency.module_id)
            visiting.remove(module_id)
            visited.add(module_id)
            ordered.append(module)

        for module_id in sorted(modules):
            visit(module_id)
        return tuple(ordered)
