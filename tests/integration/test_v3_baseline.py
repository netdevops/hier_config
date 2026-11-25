"""Assert v4 reproduces v3's output for the shared v3-API scenarios.

The baseline in `tests/fixtures/v3_baseline.json` was recorded by running
`tests/integration/v3_scenarios.py` under hier-config 3.7.0; regenerate it with
`uv run ./scripts/generate_v3_baseline.py`. Comparing against a committed
recording keeps this check in the normal suite -- no second environment and no
network. `test_v3_differential.py` runs the same scenarios against a live v3
install for the cases the frozen recording cannot catch.

A failure here means the v3 compatibility surface has drifted. Fix the surface,
not the baseline, unless the scenario module itself changed on purpose.
"""

import json
from pathlib import Path

import pytest

from tests.integration.v3_scenarios import run_all

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
BASELINE: dict[str, str] = json.loads(
    (FIXTURES / "v3_baseline.json").read_text(encoding="utf8")
)
CURRENT: dict[str, str] = run_all(FIXTURES)


def test_the_baseline_covers_every_scenario() -> None:
    assert set(CURRENT) == set(BASELINE)


@pytest.mark.parametrize("scenario", tuple(sorted(BASELINE)))
def test_v4_matches_the_v3_baseline(scenario: str) -> None:
    assert CURRENT[scenario] == BASELINE[scenario]
