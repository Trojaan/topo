#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "topo"

# Each entry describes imports that would reverse the intended dependency flow.
FORBIDDEN: dict[str, set[str]] = {
    "identifiers": {
        "builtin_modules",
        "canonical_validation",
        "cli",
        "contracts",
        "engine",
        "modules",
        "storage",
    },
    "models": {
        "builtin_modules",
        "canonical_validation",
        "cli",
        "contracts",
        "engine",
        "modules",
        "storage",
    },
    "errors": {
        "builtin_modules",
        "canonical_validation",
        "cli",
        "contracts",
        "engine",
        "modules",
        "storage",
    },
    "contracts": {
        "builtin_modules",
        "canonical_validation",
        "cli",
        "engine",
        "modules",
        "storage",
    },
    "modules": {
        "builtin_modules",
        "canonical_validation",
        "cli",
        "contracts",
        "engine",
        "storage",
    },
    "builtin_modules": {
        "canonical_validation",
        "cli",
        "contracts",
        "engine",
        "storage",
    },
    "rules": {
        "builtin_modules",
        "canonical_validation",
        "cli",
        "contracts",
        "engine",
        "modules",
        "storage",
    },
    "canonical_validation": {"builtin_modules", "cli", "contracts", "engine"},
    "storage": {
        "builtin_modules",
        "canonical_validation",
        "cli",
        "contracts",
        "engine",
        "modules",
    },
    "engine": {"cli"},
}


def topo_imports(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("topo.")
        ):
            found.append((node.lineno, node.module.split(".", 1)[1].split(".", 1)[0]))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("topo."):
                    found.append(
                        (node.lineno, alias.name.split(".", 1)[1].split(".", 1)[0])
                    )
    return found


def main() -> int:
    violations: list[str] = []
    for path in sorted(PACKAGE.glob("*.py")):
        source = path.stem
        forbidden = FORBIDDEN.get(source, set())
        tree = ast.parse(path.read_text(), filename=str(path))
        for line, target in topo_imports(tree):
            if target in forbidden:
                violations.append(
                    f"{path.relative_to(ROOT)}:{line}: topo.{source} may not import topo.{target}. "
                    "Move orchestration outward or introduce a foundation-level protocol; "
                    "do not reverse the dependency direction in docs/architecture.md."
                )
    # Topo 2 has its own boundary: no legacy imports, no orchestration inward.
    v2_forbidden = {
        "models": {"cli", "engine", "storage"},
        "storage": {"cli", "engine"},
        "engine": {"cli"},
    }
    for path in sorted((ROOT / "src" / "topo_v2").glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
                if node.module == "topo_v2":
                    modules.extend("topo_v2." + alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            for module in modules:
                parts = module.split(".")
                legacy = parts[0] == "topo"
                reversed_dependency = (
                    parts[0] == "topo_v2"
                    and len(parts) > 1
                    and parts[1] in v2_forbidden.get(path.stem, set())
                )
                if legacy or reversed_dependency:
                    violations.append(
                        f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', 0)}: forbidden import {module}"
                    )
    if violations:
        print("\n".join(violations))
        return 1
    print("architecture: dependency direction is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
