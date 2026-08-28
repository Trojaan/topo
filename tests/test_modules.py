from __future__ import annotations

from dataclasses import replace

import pytest

from topo.builtin_modules import default_module_catalog
from topo.models import AssertionRecord, EntityRecord, ProposedAssertion
from topo.modules import (
    ModuleCatalog,
    ModuleCatalogError,
    ModuleConstraint,
    ModuleDependency,
    ModuleDescriptor,
    module_checksum,
)


def accept_semantics(
    assertion: ProposedAssertion,
    existing: tuple[AssertionRecord, ...],
    entities: tuple[EntityRecord, ...],
) -> None:
    del assertion, existing, entities


def reject_semantics(
    assertion: ProposedAssertion,
    existing: tuple[AssertionRecord, ...],
    entities: tuple[EntityRecord, ...],
) -> None:
    del assertion, existing, entities
    raise ValueError


def descriptor(
    module_id: str,
    *,
    version: str = "0.1.0",
    dependencies: tuple[ModuleDependency, ...] = (),
    capabilities: tuple[str, ...] = ("classifications",),
    constraints: tuple[ModuleConstraint, ...] = (),
) -> ModuleDescriptor:
    checksum = module_checksum(
        module_id=module_id,
        module_version=version,
        engine_contract_versions=("topo.engine/0.1",),
        dependencies=dependencies,
        capabilities=capabilities,
        public_identifiers=(),
        constraints=constraints,
    )
    return ModuleDescriptor(
        module_id=module_id,
        module_version=version,
        engine_contract_versions=("topo.engine/0.1",),
        dependencies=dependencies,
        capabilities=capabilities,
        public_identifiers=(),
        checksum=checksum,
        constraints=constraints,
    )


def test_catalog_loads_versioned_capabilities_in_dependency_order() -> None:
    parties = descriptor("domain.parties")
    dutch = descriptor(
        "jurisdiction.nl",
        dependencies=(ModuleDependency(module_id="domain.parties", version="0.1.0"),),
        capabilities=("classifications", "constraints"),
    )

    catalog = ModuleCatalog((dutch, parties), engine_contract_version="topo.engine/0.1")

    assert [module.module_id for module in catalog.modules] == [
        "domain.parties",
        "jurisdiction.nl",
    ]
    assert catalog.require_capability("jurisdiction.nl", "constraints") == dutch


@pytest.mark.parametrize(
    ("modules", "reason"),
    [
        ((descriptor("Domain.Parties"),), "invalid module identifier"),
        ((descriptor("domain.parties", version="next"),), "invalid module version"),
        (
            (
                replace(
                    descriptor("domain.parties"),
                    checksum="sha256:" + "0" * 64,
                ),
            ),
            "checksum mismatch",
        ),
        (
            (
                descriptor(
                    "domain.parties",
                    dependencies=(
                        ModuleDependency(module_id="domain.assets", version="0.1.0"),
                    ),
                ),
            ),
            "missing dependency",
        ),
        (
            (
                descriptor(
                    "domain.parties",
                    dependencies=(
                        ModuleDependency(module_id="domain.assets", version="0.1.0"),
                    ),
                ),
                descriptor(
                    "domain.assets",
                    dependencies=(
                        ModuleDependency(module_id="domain.parties", version="0.1.0"),
                    ),
                ),
            ),
            "dependency cycle",
        ),
    ],
)
def test_catalog_rejects_invalid_or_incompatible_descriptors(
    modules: tuple[ModuleDescriptor, ...], reason: str
) -> None:
    with pytest.raises(ModuleCatalogError, match=reason):
        ModuleCatalog(modules, engine_contract_version="topo.engine/0.1")


def test_default_catalog_exposes_universal_and_dutch_public_identifiers() -> None:
    catalog = default_module_catalog()

    assert catalog.owner_of(
        "domain.accounts/classification/payment_account"
    ).module_id == ("domain.accounts")
    assert catalog.owner_of("jurisdiction.nl/valuation/woz").module_id == (
        "jurisdiction.nl"
    )
    with pytest.raises(ModuleCatalogError, match="public contract"):
        catalog.owner_of("jurisdiction.nl/valuation/not_declared")


def test_module_checksum_covers_executable_constraint_semantics() -> None:
    original = descriptor(
        "domain.parties",
        constraints=(ModuleConstraint("example", accept_semantics),),
    )

    changed = replace(
        original,
        constraints=(ModuleConstraint("example", reject_semantics),),
    )

    with pytest.raises(ModuleCatalogError, match="checksum mismatch"):
        ModuleCatalog((changed,), engine_contract_version="topo.engine/0.1")
