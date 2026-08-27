#!/usr/bin/env python3
"""Record the v3 output of tests/integration/v3_scenarios.py as a fixture.

Builds a throwaway virtual environment, installs the pinned v3 release into
it, runs the shared scenario module there, and writes the result to
tests/fixtures/v3_baseline.json. Commit that file: it lets
tests/integration/test_v3_baseline.py assert v4 parity on every CI run without
a second environment or network access.

Re-run this after changing v3_scenarios.py, and review the diff -- a changed
value means v4 no longer matches v3 for that scenario.

Usage:
    poetry run ./scripts/generate_v3_baseline.py
"""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
import venv
from pathlib import Path
from tempfile import TemporaryDirectory

#: The v3 release the committed baseline is recorded against. Bumping this
#: single constant moves both this script and the v3_differential tests.
V3_VERSION = "3.7.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = REPO_ROOT / "tests" / "integration" / "v3_scenarios.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
BASELINE = FIXTURES / "v3_baseline.json"


def record(destination: Path = BASELINE) -> Path:
    """Run the scenarios under v3 and write their output to `destination`."""
    with TemporaryDirectory(prefix="hier-config-v3-") as tmp:
        env_dir = Path(tmp) / "venv"
        venv.create(env_dir, with_pip=True)
        python = env_dir / "bin" / "python"
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--quiet",
                f"hier-config=={V3_VERSION}",
                # hier_config.utils imports yaml, but PyYAML is not a runtime
                # dependency of hier-config, so install it explicitly.
                "PyYAML",
            ],
            check=True,
        )
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [str(python), str(SCENARIOS), str(FIXTURES)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            message = f"v3 scenarios failed:\n{result.stderr}"
            raise RuntimeError(message)

    destination.write_text(result.stdout, encoding="utf8")
    return destination


def main() -> int:
    written = record()
    sys.stdout.write(f"wrote {written.relative_to(REPO_ROOT)} from v{V3_VERSION}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
