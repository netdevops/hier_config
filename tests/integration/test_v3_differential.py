"""Run the shared v3-API scenarios against a live v3 install and diff them.

Skipped by default: the `v3_output` fixture builds a virtual environment and
downloads a release from PyPI. Run these by hand, or in a nightly or
pre-release job:

    poetry run pytest -m v3_differential -v

`test_v3_baseline.py` covers the same ground against a committed recording on
every push. These tests exist for the case that recording cannot catch: when
`v3_scenarios.py` itself changes, the frozen values go stale, and only a live
v3 run proves the new scenarios still match.
"""

import json
from pathlib import Path

import pytest

from scripts.generate_v3_baseline import V3_VERSION
from tests.integration.v3_scenarios import run_all

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

pytestmark = pytest.mark.v3_differential


def test_the_scenario_sets_match(v3_output: dict[str, str]) -> None:
    assert set(run_all(FIXTURES)) == set(v3_output)


def test_v4_matches_live_v3(v3_output: dict[str, str]) -> None:
    current = run_all(FIXTURES)
    differing = {
        name: (expected, current.get(name))
        for name, expected in sorted(v3_output.items())
        if current.get(name) != expected
    }
    assert not differing, f"v{V3_VERSION} and this tree disagree: {differing}"


def test_the_committed_baseline_is_current(v3_output: dict[str, str]) -> None:
    """The committed recording must still match a live v3 run."""
    baseline: dict[str, str] = json.loads(
        (FIXTURES / "v3_baseline.json").read_text(encoding="utf8")
    )
    assert baseline == v3_output, (
        "tests/fixtures/v3_baseline.json is stale;"
        " regenerate it with ./scripts/generate_v3_baseline.py"
    )
