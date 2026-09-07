#!/usr/bin/env python3
"""Validate ``@pytest.mark.displaced_by`` references in test files.

Every test marked as displaced must point to a real native target:
- ``corpus:<path>`` must point to an existing ``testdata/cases/<path>/case.json``.
- ``rust:<file>::<test>`` must point to a file under ``crates/hier_config_core/<file>``
  containing the named test function.

Fails with exit status 1 if any target does not exist or has an invalid format.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTDATA_DIR = REPO_ROOT / "testdata" / "cases"
RUST_CORE_DIR = REPO_ROOT / "crates" / "hier_config_core"
TESTS_DIR = REPO_ROOT / "tests"


def _extract_marker_targets(filepath: Path) -> list[tuple[str, int]]:
    """Extract (target, line_number) from @pytest.mark.displaced_by decorators."""
    targets: list[tuple[str, int]] = []
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError:
        return targets

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            # Identify pytest.mark.displaced_by decorator call
            func = decorator.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "displaced_by"
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                targets.append((decorator.args[0].value, decorator.lineno))
    return targets


def _verify_corpus_target(path: str) -> str | None:
    """Verify that a corpus case manifest exists."""
    manifest_path = TESTDATA_DIR / path / "case.json"
    if not manifest_path.is_file():
        return f"Corpus case manifest not found: {manifest_path.relative_to(REPO_ROOT)}"
    return None


def _verify_rust_target(spec: str) -> str | None:
    """Verify that a Rust test file and function exist."""
    if "::" not in spec:
        return f"Invalid Rust target format (expected file::function): {spec}"
    file_rel, fn_name = spec.split("::", 1)
    rust_file = RUST_CORE_DIR / file_rel
    if not rust_file.is_file():
        return f"Rust file not found: {rust_file.relative_to(REPO_ROOT)}"

    content = rust_file.read_text(encoding="utf-8")
    # Match fn <name> definition
    pattern = rf"\bfn\s+{re.escape(fn_name)}\b"
    if not re.search(pattern, content):
        return f"Rust test function '{fn_name}' not found in {rust_file.relative_to(REPO_ROOT)}"
    return None


def _validate_target(target: str) -> str | None:
    """Validate a single displacement target string."""
    if target.startswith("corpus:"):
        return _verify_corpus_target(target.removeprefix("corpus:"))
    if target.startswith("rust:"):
        return _verify_rust_target(target.removeprefix("rust:"))
    return f"Unknown target prefix in '{target}' (must start with 'corpus:' or 'rust:')"


def check_all_markers() -> list[str]:
    """Scan all test files and validate displacement markers."""
    errors: list[str] = []
    total_markers = 0

    for py_file in sorted(TESTS_DIR.rglob("*.py")):
        targets = _extract_marker_targets(py_file)
        for target, lineno in targets:
            total_markers += 1
            rel_file = py_file.relative_to(REPO_ROOT)
            err = _validate_target(target)
            if err:
                errors.append(f"{rel_file}:{lineno}: {err}")

    print(f"Validated {total_markers} displacement marker(s).")  # ruff:ignore[print]
    return errors


def main() -> int:
    """Run displacement marker verification and return exit code."""
    errors = check_all_markers()
    if errors:
        print(f"Found {len(errors)} invalid displacement marker(s):")  # ruff:ignore[print]
        for err in errors:
            print(f"  {err}")  # ruff:ignore[print]
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
