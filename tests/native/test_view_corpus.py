"""Guard the shared view corpus against Python-side drift.

The snapshots under ``testdata/views`` are the reference that the native Rust
view implementation is asserted against by
``crates/hier_config_core/tests/view_corpus.rs``. They are generated from the
Python view layer by ``scripts/gen_view_corpus.py``.

This test re-runs that generator in ``--check`` mode, so a change to the Python
views cannot silently invalidate the Rust comparison: the snapshots have to be
regenerated, which in turn makes the Rust side fail until it is updated too.
"""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from pathlib import Path

from hier_config.models import Platform

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "testdata" / "views"
GENERATOR = REPO_ROOT / "scripts" / "gen_view_corpus.py"


def _case_names() -> list[str]:
    return sorted(
        case_dir.name for case_dir in CORPUS_DIR.iterdir() if case_dir.is_dir()
    )


def test_view_snapshots_match_python() -> None:
    """The committed snapshots still match what the Python views produce."""
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"The Python views no longer produce the committed snapshots.\n"
        f"{result.stdout}{result.stderr}"
        f"After regenerating, update the native Rust view so "
        f"`cargo test -p hier_config_core --test view_corpus` passes again."
    )


def test_corpus_is_not_empty() -> None:
    """The corpus has cases; an empty directory would silently pass."""
    assert _case_names(), f"no view corpus cases found under {CORPUS_DIR}"


def test_every_corpus_case_names_a_known_platform() -> None:
    """Each corpus directory maps to a real platform."""
    for case_name in _case_names():
        assert case_name.upper() in Platform.__members__, (
            f"{case_name} is not a known platform"
        )
