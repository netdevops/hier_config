"""Language-neutral corpus test runner.

Executes all test cases defined under testdata/cases/ against the Python
public API (get_hconfig, config_to_get_to, future, unified_diff).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hier_config import get_hconfig
from hier_config.models import Platform

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = REPO_ROOT / "testdata" / "cases"


def _discover_cases() -> list[tuple[str, Path, dict[str, Any]]]:
    """Discover all valid case directories containing case.json."""
    if not CASES_DIR.is_dir():
        msg = f"Corpus directory not found: {CASES_DIR}"
        raise RuntimeError(msg)

    found_cases: list[tuple[str, Path, dict[str, Any]]] = []
    for platform_dir in sorted(CASES_DIR.iterdir()):
        if not platform_dir.is_dir():
            continue
        for case_dir in sorted(platform_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            manifest_file = case_dir / "case.json"
            if not manifest_file.is_file():
                continue
            manifest: dict[str, Any] = json.loads(
                manifest_file.read_text(encoding="utf-8")
            )
            case_id = f"{platform_dir.name}/{case_dir.name}"
            found_cases.append((case_id, case_dir, manifest))

    if not found_cases:
        msg = "corpus is empty — testdata/cases/ contains no case.json"
        raise RuntimeError(msg)

    return found_cases


_CASES = _discover_cases()


def _read_config_files(case_dir: Path) -> tuple[str, str, tuple[str, ...]]:
    """Read running, intended, and optional remediation files for a case."""
    running_text = (case_dir / "running.conf").read_text(encoding="utf-8")
    intended_text = (case_dir / "intended.conf").read_text(encoding="utf-8")
    remediation_file = case_dir / "remediation.conf"
    expected_lines: tuple[str, ...] = ()
    if remediation_file.is_file():
        expected_lines = tuple(
            remediation_file.read_text(encoding="utf-8").splitlines()
        )
    return running_text, intended_text, expected_lines


@pytest.mark.parametrize(
    ("case_id", "case_dir", "manifest"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_corpus_case(
    case_id: str,
    case_dir: Path,
    manifest: dict[str, Any],
) -> None:
    """Run a single corpus round-trip and rollback test case."""
    del case_id
    platform = Platform[manifest["platform"]]
    running_text, intended_text, expected_lines = _read_config_files(case_dir)

    running = get_hconfig(platform, running_text)
    intended = get_hconfig(platform, intended_text)
    remediation = running.config_to_get_to(intended)

    assert remediation.dump_simple() == expected_lines

    if manifest.get("assert_rollback", True):
        future = running.future(remediation)
        rollback = future.config_to_get_to(running)
        restored = future.future(rollback)
        assert not list(restored.unified_diff(running))
