"""Bump the project version in the workspace ``Cargo.toml``.

The build moved from poetry to maturin, so ``[project.version]`` in
``pyproject.toml`` is dynamic and Cargo owns the real number. ``poetry version``
no longer has anything to edit, and this replaces it in the release workflow.

Cargo demands SemVer, so a pre-release is stored as ``4.0.0-beta.4``; maturin
normalizes that to the PEP 440 ``4.0.0b4`` when it builds the wheel. Both forms
are printed so the workflow can tag with one and match the wheel with the other.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The version lives on `[workspace.package]`; every crate inherits it with
# `version.workspace = true`, so this is the only place to edit.
CARGO_TOML = Path(__file__).resolve().parents[1] / "Cargo.toml"

# Cargo SemVer with an optional dotted pre-release, e.g. `4.0.0-beta.4`.
_VERSION = re.compile(
    r'^version\s*=\s*"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)'
    r'(?:-(?P<pre_label>[A-Za-z]+)\.(?P<pre_num>\d+))?"',
    re.MULTILINE,
)

BUMPS = ("major", "minor", "patch", "premajor", "preminor", "prepatch", "prerelease")

# Cargo pre-release label -> PEP 440 suffix.
_PEP440_LABELS = {"alpha": "a", "beta": "b", "rc": "rc"}


def _pep440(version: str) -> str:
    """Render a Cargo version string the way maturin will name the wheel."""
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-([A-Za-z]+)\.(\d+))?", version)
    if match is None or match.group(2) is None:
        return version
    base, label, number = match.group(1), match.group(2), match.group(3)
    return f"{base}{_PEP440_LABELS.get(label, label)}{number}"


def bump(current: re.Match[str], kind: str) -> str:
    """Apply ``kind`` to the parsed ``current`` version and return the new one."""
    major = int(current["major"])
    minor = int(current["minor"])
    patch = int(current["patch"])
    label = current["pre_label"]
    number = int(current["pre_num"]) if current["pre_num"] else 0

    if kind == "prerelease":
        if label is None:
            message = (
                f"cannot bump prerelease: {major}.{minor}.{patch} is a final "
                f"release, use premajor/preminor/prepatch instead"
            )
            raise ValueError(message)
        return f"{major}.{minor}.{patch}-{label}.{number + 1}"

    if kind.startswith("pre"):
        # A pre-release of an unreleased version bumps the pre-release counter
        # rather than the base, matching poetry's behaviour.
        base = {
            "premajor": (major + 1, 0, 0),
            "preminor": (major, minor + 1, 0),
            "prepatch": (major, minor, patch + 1),
        }[kind]
        if label is not None and (major, minor, patch) == base:
            return f"{major}.{minor}.{patch}-{label}.{number + 1}"
        next_major, next_minor, next_patch = base
        return f"{next_major}.{next_minor}.{next_patch}-beta.1"

    if label is not None:
        # Finalizing a pre-release drops the suffix without moving the base.
        return f"{major}.{minor}.{patch}"
    return {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
    }[kind]


def main() -> int:
    """Rewrite the Cargo version and print the new Cargo and PEP 440 forms."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bump", choices=BUMPS)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the new version without writing it",
    )
    args = parser.parse_args()

    text = CARGO_TOML.read_text(encoding="utf-8")
    match = _VERSION.search(text)
    if match is None:
        sys.stderr.write(f"no version field found in {CARGO_TOML}\n")
        return 1

    try:
        new_version = bump(match, args.bump)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    if not args.dry_run:
        updated = (
            f'{text[: match.start()]}version = "{new_version}"{text[match.end() :]}'
        )
        CARGO_TOML.write_text(updated, encoding="utf-8")

    sys.stdout.write(f"{new_version}\n{_pep440(new_version)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
