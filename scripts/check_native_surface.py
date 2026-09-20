"""Check that binding metadata covers the runtime's public native surface.

Generation freshness alone cannot detect an exported binding missing its
stub-generation annotation. This independent check complements stubtest,
which checks declarations against runtime objects in the other direction.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, TypeGuard

if TYPE_CHECKING:
    from types import ModuleType


def _is_class(value: object) -> TypeGuard[type[object]]:
    return isinstance(value, type)


def _members(node: ast.ClassDef, classes: dict[str, ast.ClassDef]) -> set[str]:
    members = {
        item.name
        for item in node.body
        if isinstance(item, ast.FunctionDef) and not item.name.startswith("_")
    }
    members.update(
        item.target.id
        for item in node.body
        if isinstance(item, ast.AnnAssign)
        and isinstance(item.target, ast.Name)
        and not item.target.id.startswith("_")
    )
    for base in node.bases:
        name = ast.unparse(base).rsplit(".", 1)[-1]
        if name in classes:
            members.update(_members(classes[name], classes))
    return members


def surface_errors(native: ModuleType, source: str) -> list[str]:
    """Return uncovered or stale public exports and class members."""
    tree = ast.parse(source)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    declarations = set(classes)
    declarations.update(
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    )
    declarations.update(
        node.target.id
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    )
    exports = {name for name in vars(native) if not name.startswith("_")}
    declarations = {name for name in declarations if not name.startswith("_")}
    errors = [
        f"missing native export: {name}" for name in sorted(exports - declarations)
    ]
    errors.extend(
        f"stale native export: {name}" for name in sorted(declarations - exports)
    )
    for name, node in sorted(classes.items()):
        value = getattr(native, name, None)
        if not _is_class(value) or issubclass(value, BaseException):
            continue
        runtime_members = {
            member for member in dir(value) if not member.startswith("_")
        }
        declared_members = _members(node, classes)
        errors.extend(
            f"missing native member: {name}.{member}"
            for member in sorted(runtime_members - declared_members)
        )
    return errors


def main() -> int:
    """Validate the canonical stub against the installed native extension."""
    native = importlib.import_module("hier_config._hier_config_rust")
    path = Path(__file__).resolve().parents[1] / "hier_config" / "_hier_config_rust.pyi"
    errors = surface_errors(native, path.read_text(encoding="utf-8"))
    for error in errors:
        print(error)  # ruff: ignore[print]
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
