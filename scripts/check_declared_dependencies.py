#!/usr/bin/env python3
"""Fail if any public ``hier_config`` module needs an undeclared dependency.

Every other CI job builds and imports the package in-tree, where the dev
environment happens to provide whatever the library reaches for. That hides the
case where library code imports a third-party package that never made it into
``[project.dependencies]`` -- the failure then surfaces for users after release
rather than in CI.

This script is meant to run inside a *clean* virtualenv that has the built wheel
installed and nothing else, so the only importable third-party packages are the
ones the distribution actually declares::

    python -m venv /tmp/wheel-env
    /tmp/wheel-env/bin/pip install dist/*.whl
    /tmp/wheel-env/bin/python scripts/check_declared_dependencies.py
"""

from __future__ import annotations

import importlib
import pkgutil
import sys

import hier_config


def undeclared_imports() -> list[str]:
    """Import every public submodule, returning one message per failure."""
    failures: list[str] = []
    for module in pkgutil.walk_packages(hier_config.__path__, "hier_config."):
        # Each module is probed independently so one missing dependency does not
        # hide the rest; the cost is irrelevant next to importing the package.
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # ruff:ignore[blind-except, try-except-in-loop] # pylint: disable=broad-exception-caught
            failures.append(f"  {module.name}: {exc!r}")
    return failures


def main() -> int:
    """Return a process exit status for the dependency check."""
    failures = undeclared_imports()
    if failures:
        sys.stderr.write(
            "Modules that failed to import with only declared dependencies:\n"
            + "\n".join(failures)
            + "\nAdd the missing package to [project.dependencies] in pyproject.toml.\n",
        )
        return 1

    sys.stdout.write("All public hier_config modules imported cleanly.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
