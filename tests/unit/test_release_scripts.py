from __future__ import annotations

import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - invokes local Cargo on fixture manifests
from typing import TYPE_CHECKING

import pytest

from scripts import bump_version

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("dry_run", (False, True))
def test_bump_updates_workspace_lock_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, dry_run: bool
) -> None:
    manifest = tmp_path / "Cargo.toml"
    lock = tmp_path / "Cargo.lock"
    original = '[workspace.package]\nversion = "4.0.0-beta.4"\n'
    locked = (
        'version = 4\n\n[[package]]\nname = "hier_config"\n'
        'version = "4.0.0-beta.4"\n\n'
        '[[package]]\nname = "hier_config_core"\nversion = "4.0.0-beta.4"\n\n'
        '[[package]]\nname = "external"\nversion = "4.0.0-beta.4"\n'
        'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
    )
    manifest.write_text(original, encoding="utf-8")
    lock.write_text(locked, encoding="utf-8")
    monkeypatch.setattr(bump_version, "CARGO_TOML", manifest)
    arguments = ["bump_version.py", "prerelease"]
    if dry_run:
        arguments.append("--dry-run")
    monkeypatch.setattr("sys.argv", arguments)

    assert bump_version.main() == 0
    expected = "4.0.0-beta.4" if dry_run else "4.0.0-beta.5"
    assert manifest.read_text(encoding="utf-8") == original.replace(
        "4.0.0-beta.4", expected
    )
    assert lock.read_text(encoding="utf-8") == locked.replace(
        "4.0.0-beta.4", expected, 2
    )


@pytest.mark.parametrize(
    ("current", "kind", "expected"),
    (
        ("4.0.0", "alpha", "4.0.1-alpha.1"),
        ("4.0.0-alpha.2", "alpha", "4.0.0-alpha.3"),
        ("4.0.0-alpha.2", "beta", "4.0.0-beta.1"),
        ("4.0.0-beta.4", "rc", "4.0.0-rc.1"),
    ),
)
def test_workflow_prerelease_choices(current: str, kind: str, expected: str) -> None:
    match = re.fullmatch(
        r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
        r"(?:-(?P<pre_label>[A-Za-z]+)\.(?P<pre_num>\d+))?",
        current,
    )
    assert match is not None
    assert kind in bump_version.BUMPS
    assert bump_version.bump(match, kind) == expected


def test_bumped_workspace_accepts_cargo_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("Cargo is needed to verify the release lockfile")
    manifest = tmp_path / "Cargo.toml"
    manifest.write_text(
        '[workspace]\nmembers = ["core", "bindings"]\nresolver = "2"\n'
        '[workspace.package]\nversion = "4.0.0-beta.4"\n',
        encoding="utf-8",
    )
    for member in ("core", "bindings"):
        directory = tmp_path / member
        (directory / "src").mkdir(parents=True)
        (directory / "src" / "lib.rs").write_text("", encoding="utf-8")
        (directory / "Cargo.toml").write_text(
            f'[package]\nname = "release_fixture_{member}"\n'
            'version.workspace = true\nedition = "2021"\n',
            encoding="utf-8",
        )
    lock = tmp_path / "Cargo.lock"
    lock.write_text(
        'version = 4\n\n[[package]]\nname = "release_fixture_bindings"\n'
        'version = "4.0.0-beta.4"\n\n[[package]]\n'
        'name = "release_fixture_core"\nversion = "4.0.0-beta.4"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(bump_version, "CARGO_TOML", manifest)
    monkeypatch.setattr("sys.argv", ["bump_version.py", "prerelease"])

    assert bump_version.main() == 0
    # Literal arguments; offline metadata resolution never builds the extension.
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [cargo, "metadata", "--locked", "--offline", "--format-version=1"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"version":"4.0.0-beta.5"' in result.stdout
