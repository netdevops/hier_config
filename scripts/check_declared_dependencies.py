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

    python -m venv .wheel-env
    .wheel-env/bin/pip install dist/*.whl
    .wheel-env/bin/python scripts/check_declared_dependencies.py --wheel dist/*.whl
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys
from email.parser import Parser
from importlib import machinery, metadata
from pathlib import Path
from zipfile import ZipFile

import hier_config


def installed_wheel_errors(wheel: Path) -> list[str]:
    """Check the installed version and native backend against the built artifact."""
    with ZipFile(wheel) as archive:
        metadata_file = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        fields = Parser().parsestr(archive.read(metadata_file).decode("utf-8"))
    expected = fields["Version"]
    installed = metadata.version("hier-config")
    errors: list[str] = []
    if installed != expected:
        errors.append(
            f"installed hier-config {installed} does not match built wheel {expected}"
        )
    native = importlib.import_module("hier_config._hier_config_rust")
    binary = native
    if (
        binary.__file__ is None
        or not binary.__file__.endswith(tuple(machinery.EXTENSION_SUFFIXES))
        or native.HConfig is not hier_config.HConfig
    ):
        errors.append("hier_config is not using the compiled native backend")
    return errors


def undeclared_imports() -> list[str]:
    """Import every public submodule, returning one message per failure."""
    failures: list[str] = []
    for module in pkgutil.walk_packages(hier_config.__path__, "hier_config."):
        # Each module is probed independently so one missing dependency does not
        # hide the rest; the cost is irrelevant next to importing the package.
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # ruff:ignore[blind-except] # pylint: disable=broad-exception-caught
            failures.append(f"  {module.name}: {exc!r}")
    return failures


def main() -> int:
    """Return a process exit status for the dependency check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument(
        "--yaml-file",
        type=Path,
        help="also exercise the optional YAML loader using a tags file containing []",
    )
    args = parser.parse_args()
    failures = undeclared_imports()
    if args.wheel is not None:
        failures.extend(installed_wheel_errors(args.wheel))
    if args.yaml_file is not None:
        # Import remains lazy in the library, so core-only wheel checks above
        # still import every public module without requiring the YAML extra.
        from hier_config.utils import load_hier_config_tags  # ruff: ignore[import-outside-top-level]

        if load_hier_config_tags(str(args.yaml_file)) != ():
            failures.append("the optional YAML loader did not load an empty tags list")
    if failures:
        sys.stderr.write(
            "Installed package validation failures:\n"
            + "\n".join(failures)
            + "\nCore imports must not require optional extras; optional loaders "
            "must import their dependencies lazily.\n",
        )
        return 1

    sys.stdout.write(
        "All public hier_config modules and requested wheel checks passed.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
