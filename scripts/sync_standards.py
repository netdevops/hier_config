#!/usr/bin/env python3
"""Sync shared development-standard files from the canonical netdevops repository.

The `.standards.yml` manifest at the repository root declares the canonical
source repository and the files it owns. `check` reports drift between the
local copies and the canonical versions; `apply` overwrites the local copies
with the canonical versions.

Package-name substitutions can push a canonical line past the formatter's
line-length limit, so Python files are re-formatted with `ruff format` after
substitution. Without this the synced file would never converge: `apply`
would write a file that `ruff format` immediately rewrites, and the next
`check` would report drift again.
"""

from __future__ import annotations

import difflib
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from http import HTTPStatus
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel, Field
from typer import Typer

app = Typer()

_REPO_ROOT = Path(__file__).parent.parent
_MANIFEST_PATH = _REPO_ROOT / ".standards.yml"


class Source(BaseModel):
    """Canonical repository holding the standard files."""

    repo: str
    ref: str


class Manifest(BaseModel):
    """Parsed representation of the `.standards.yml` manifest."""

    source: Source
    substitutions: dict[str, str] = Field(default_factory=dict)
    files: tuple[str, ...]


@app.callback()
def callback() -> None:
    """Sync shared development standards from the canonical repository."""


@app.command()
def check() -> None:
    """Report drift between local files and the canonical standards."""
    if _sync(write=False):
        sys.exit(1)


@app.command()
def apply() -> None:
    """Overwrite local files with the canonical standards."""
    _sync(write=True)


def _sync(*, write: bool) -> list[str]:
    manifest = _load_manifest()
    drifted: list[str] = []
    for file_path in manifest.files:
        canonical = _canonical_content(manifest, file_path)
        if canonical is None:
            source = manifest.source
            print(  # ruff: ignore[print]
                f"{file_path}: not published on {source.repo}@{source.ref} — "
                "the manifest lists a file the canonical source does not have yet",
            )
            drifted.append(file_path)
            continue
        local_path = _REPO_ROOT / file_path
        local = local_path.read_text(encoding="utf-8") if local_path.is_file() else None
        if local == canonical:
            print(f"{file_path}: in sync")  # ruff: ignore[print]
            continue
        drifted.append(file_path)
        if write:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(canonical, encoding="utf-8")
            print(f"{file_path}: updated from canonical")  # ruff: ignore[print]
        else:
            print(f"{file_path}: drifted from canonical")  # ruff: ignore[print]
            _print_diff(file_path, local or "", canonical)
    return drifted


def _load_manifest() -> Manifest:
    data = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return Manifest.model_validate(data)


def _fetch(source: Source, file_path: str) -> str | None:
    """Return the canonical file contents, or None when the source lacks the file."""
    url = f"https://raw.githubusercontent.com/{source.repo}/{source.ref}/{file_path}"
    response = httpx.get(url, timeout=30.0, follow_redirects=True)
    if response.status_code == HTTPStatus.NOT_FOUND:
        return None
    response.raise_for_status()
    return response.text


def _canonical_content(manifest: Manifest, file_path: str) -> str | None:
    fetched = _fetch(manifest.source, file_path)
    if fetched is None:
        return None
    content = _apply_substitutions(fetched, manifest.substitutions)
    if file_path.endswith(".py"):
        content = _ruff_format(content, file_path)
    return content


def _apply_substitutions(content: str, substitutions: dict[str, str]) -> str:
    for old, new in substitutions.items():
        content = re.sub(rf"\b{re.escape(old)}\b", new, content)
    return content


def _ruff_format(content: str, file_path: str) -> str:
    ruff = shutil.which("ruff")
    if ruff is None:
        message = "ruff is not installed; run this from the dev environment"
        raise RuntimeError(message)
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [ruff, "format", "--stdin-filename", file_path, "-"],
        check=True,
        capture_output=True,
        text=True,
        input=content,
    )
    return result.stdout


def _print_diff(file_path: str, local: str, canonical: str) -> None:
    diff = difflib.unified_diff(
        local.splitlines(keepends=True),
        canonical.splitlines(keepends=True),
        fromfile=f"local/{file_path}",
        tofile=f"canonical/{file_path}",
    )
    sys.stdout.writelines(diff)


if __name__ == "__main__":
    app()
