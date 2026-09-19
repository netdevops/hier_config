#!/usr/bin/env python3
"""Check installed-wheel consumer typing without checkout import paths.

Install a non-editable wheel, mypy, pyright and typing_extensions in a venv, then
run ``python scripts/check_wheel_typing.py --python /venv/bin/python``.
Fixtures and strict Python 3.11 checker configurations are copied outside the
checkout. Neither checker receives a stub path or a source search path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed commands, no shell.
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast


@dataclass(frozen=True, order=True)
class Diagnostic:
    """One expected checker error, including its category and source line."""

    filename: str
    line: int
    rule: str


def expected_diagnostics(fixture: Path, checker: str) -> frozenset[Diagnostic]:
    """Read checker-specific error markers from a consumer fixture."""
    pattern = re.compile(rf"\b{re.escape(checker)}=([\w,-]+)")
    return frozenset(
        Diagnostic(fixture.name, number, rule)
        for number, line in enumerate(
            fixture.read_text(encoding="utf-8").splitlines(), start=1
        )
        if "# error:" in line
        if (match := pattern.search(line)) is not None
        for rule in match[1].split(",")
    )


def parse_mypy(output: str) -> frozenset[Diagnostic]:
    """Extract mypy error lines with stable diagnostic codes."""
    summary = (
        r"(?:checked [1-9]\d* source files?\)"
        r"|Success: no issues found in [1-9]\d* source files?)"
    )
    if re.search(summary, output) is None:
        message = "mypy did not analyze the consumer"
        raise ValueError(message)
    pattern = re.compile(r"^(.+):(\d+): error: .+\[([\w-]+)\]$")
    diagnostics: set[Diagnostic] = set()
    for line in output.splitlines():
        if match := pattern.match(line):
            diagnostics.add(Diagnostic(Path(match[1]).name, int(match[2]), match[3]))
        elif ": error:" in line:
            message = f"Unrecognized mypy diagnostic: {line}"
            raise ValueError(message)
    return frozenset(diagnostics)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        message = "Expected a JSON object in pyright results"
        raise TypeError(message)
    if not all(isinstance(key, str) for key in cast("dict[object, object]", value)):
        message = "Expected string keys in pyright results"
        raise TypeError(message)
    return cast("dict[str, object]", value)


def parse_pyright(output: str) -> frozenset[Diagnostic]:
    """Extract pyright JSON errors, rejecting malformed checker output."""
    value: object = json.loads(output)
    report = _object(value)
    entries = report.get("generalDiagnostics")
    if not isinstance(entries, list):
        message = "Missing pyright generalDiagnostics"
        raise TypeError(message)
    diagnostics: set[Diagnostic] = set()
    for entry in cast("list[object]", entries):
        diagnostic = _object(entry)
        if diagnostic.get("severity") not in {"error", "warning", "information"}:
            message = "Missing or invalid pyright severity"
            raise TypeError(message)
        if diagnostic["severity"] != "error":
            continue
        filename = diagnostic.get("file")
        rule = diagnostic.get("rule")
        line = _object(_object(diagnostic.get("range")).get("start")).get("line")
        if not isinstance(filename, str) or not isinstance(line, int):
            message = "Missing pyright diagnostic location"
            raise TypeError(message)
        # Syntax/import failures may lack a rule; they must not disappear.
        diagnostics.add(
            Diagnostic(
                Path(filename).name,
                line + 1,
                rule if isinstance(rule, str) else "unknown",
            )
        )
    count = _object(report.get("summary")).get("filesAnalyzed")
    if not isinstance(count, int) or count < 1:
        message = "pyright did not analyze the consumer"
        raise ValueError(message)
    return frozenset(diagnostics)


def validate_diagnostics(
    expected: frozenset[Diagnostic],
    actual: frozenset[Diagnostic],
    returncode: int,
) -> tuple[str, ...]:
    """Require every expected error and reject unrelated errors or tool crashes."""
    errors: list[str] = []
    wanted_status = 1 if expected else 0
    if returncode != wanted_status:
        errors.append(f"Checker exited {returncode}; expected {wanted_status}")
    errors.extend(f"Missing diagnostic: {item}" for item in sorted(expected - actual))
    errors.extend(
        f"Unexpected diagnostic: {item}" for item in sorted(actual - expected)
    )
    return tuple(errors)


def diagnose(
    checker: str,
    expected: frozenset[Diagnostic],
    result: subprocess.CompletedProcess[str],
) -> tuple[str, ...]:
    """Parse checker output and compare it against the fixture's expectations."""
    try:
        actual = (
            parse_mypy(result.stdout)
            if checker == "mypy"
            else parse_pyright(result.stdout)
        )
    except (TypeError, ValueError) as exc:
        return (str(exc),)
    return validate_diagnostics(expected, actual, result.returncode)


def run_isolated(
    python: Path, arguments: tuple[str, ...], workspace: Path
) -> subprocess.CompletedProcess[str]:
    """Run a consumer command without inherited source import overrides."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "MYPYPATH", "PYTHONHOME"}
    }
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed commands, explicit interpreter.
        (str(python), "-I", *arguments),
        cwd=workspace,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def check_consumer(python: Path, workspace: Path, fixtures: Path) -> tuple[str, ...]:
    """Run wheel provenance, legacy identity, and positive/negative contracts."""
    for fixture in fixtures.glob("*.py.txt"):
        shutil.copyfile(fixture, workspace / fixture.stem)
    (workspace / "mypy.ini").write_text(
        "[mypy]\n"
        "strict = True\n"
        "python_version = 3.11\n"
        "show_error_codes = True\n"
        "pretty = False\n"
        "show_column_numbers = False\n"
        "show_error_context = False\n"
        "color_output = False\n",
        encoding="utf-8",
    )
    (workspace / "pyrightconfig.json").write_text(
        json.dumps(
            {
                "typeCheckingMode": "strict",
                "pythonVersion": "3.11",
                "autoSearchPaths": False,
                "extraPaths": [],
                "useLibraryCodeForTypes": False,
            }
        ),
        encoding="utf-8",
    )
    runtime = run_isolated(python, ("runtime.py",), workspace)
    if runtime.returncode:
        return (
            f"Installed-wheel runtime check failed:\n{runtime.stdout}{runtime.stderr}",
        )

    errors: list[str] = []
    for checker in ("mypy", "pyright"):
        for filename in ("positive.py", "negative.py"):
            expected = expected_diagnostics(workspace / filename, checker)
            if filename == "negative.py" and not expected:
                errors.append(
                    f"{checker}: negative fixture has no expected diagnostics"
                )
                continue
            arguments = (
                (
                    "-m",
                    "mypy",
                    "--config-file",
                    "mypy.ini",
                    "--python-executable",
                    str(python),
                    "--no-incremental",
                    filename,
                )
                if checker == "mypy"
                else (
                    "-m",
                    "pyright",
                    "--project",
                    "pyrightconfig.json",
                    "--pythonpath",
                    str(python),
                    "--outputjson",
                    filename,
                )
            )
            result = run_isolated(python, arguments, workspace)
            failures = diagnose(checker, expected, result)
            if failures:
                errors.append(
                    f"{checker} {filename}:\n"
                    + "\n".join(failures)
                    + f"\n{result.stdout}{result.stderr}"
                )
            else:
                sys.stdout.write(
                    f"{checker} {filename}: {len(expected)} expected errors verified\n"
                )
    return tuple(errors)


def main() -> int:
    """Check an installed wheel and return a nonzero status for any regression."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path.home() / ".cache" / "hier-config-wheel-typing",
        help="parent of the disposable consumer directory; must be outside checkout",
    )
    args = parser.parse_args()
    # Keep the venv executable path: resolving its symlink selects system Python.
    python = args.python.absolute()
    work_dir = args.work_dir.resolve()
    repository = Path(__file__).resolve().parents[1]
    if work_dir.is_relative_to(repository):
        parser.error("--work-dir must be outside the repository")
    work_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="consumer-", dir=work_dir) as directory:
        failures = check_consumer(
            python, Path(directory), repository / "tests" / "typing"
        )
    if failures:
        joined_failures = "\n".join(failures)
        sys.stderr.write(f"{joined_failures}\n")
        return 1
    sys.stdout.write("Installed-wheel runtime and strict typing contracts passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
