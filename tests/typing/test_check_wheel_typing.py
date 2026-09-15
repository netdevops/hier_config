"""Regression tests for the installed-wheel diagnostic validator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.check_wheel_typing import (
    Diagnostic,
    expected_diagnostics,
    parse_mypy,
    parse_pyright,
    run_isolated,
    validate_diagnostics,
)


def test_negative_contract_requires_each_line_and_rule() -> None:
    """A checker error elsewhere cannot hide an accidentally untyped API."""
    expected = frozenset(
        (
            Diagnostic("negative.py", 4, "arg-type"),
            Diagnostic("negative.py", 8, "assignment"),
        )
    )
    assert not validate_diagnostics(expected, expected, 1)
    assert validate_diagnostics(expected, frozenset(), 1)
    assert validate_diagnostics(expected, expected, 0)
    assert validate_diagnostics(expected, expected, 2)
    assert validate_diagnostics(
        expected,
        frozenset(
            (
                Diagnostic("negative.py", 4, "arg-type"),
                Diagnostic("negative.py", 8, "import-not-found"),
            )
        ),
        1,
    )
    assert validate_diagnostics(
        expected,
        expected | {Diagnostic("positive.py", 3, "assignment")},
        1,
    )


def test_positive_contract_requires_success_and_no_diagnostics() -> None:
    """Even a crash without parseable errors must fail the positive contract."""
    assert not validate_diagnostics(frozenset(), frozenset(), 0)
    assert validate_diagnostics(frozenset(), frozenset(), 1)
    assert validate_diagnostics(
        frozenset(), frozenset((Diagnostic("positive.py", 3, "assignment"),)), 0
    )


def test_mypy_parser_preserves_line_and_diagnostic_code() -> None:
    output = (
        "/consumer/negative.py:4: error: Argument 1 has incompatible type  [arg-type]\n"
        "/consumer/negative.py:4: note: See documentation\n"
        "Found 1 error in 1 file (checked 1 source file)\n"
    )
    assert parse_mypy(output) == frozenset((Diagnostic("negative.py", 4, "arg-type"),))


def test_pyright_parser_converts_zero_based_lines() -> None:
    output = json.dumps(
        {
            "generalDiagnostics": [
                {
                    "file": "/consumer/negative.py",
                    "severity": "error",
                    "range": {"start": {"line": 7, "character": 0}},
                    "rule": "reportAssignmentType",
                }
            ],
            "summary": {"filesAnalyzed": 1},
        }
    )
    assert parse_pyright(output) == frozenset(
        (Diagnostic("negative.py", 8, "reportAssignmentType"),)
    )


@pytest.mark.parametrize("output", ("not json", "{}", '{"generalDiagnostics":[{}]}'))
def test_pyright_parser_rejects_malformed_results(output: str) -> None:
    with pytest.raises((TypeError, ValueError), match=r"Expecting|Missing"):
        parse_pyright(output)


def test_pyright_parser_rejects_skipped_consumer() -> None:
    output = '{"generalDiagnostics": [], "summary": {"filesAnalyzed": 0}}'
    with pytest.raises(ValueError, match="did not analyze"):
        parse_pyright(output)


def test_mypy_parser_rejects_missing_consumer_summary() -> None:
    with pytest.raises(ValueError, match="did not analyze"):
        parse_mypy("")


def test_mypy_parser_accepts_success_summary() -> None:
    assert not parse_mypy("Success: no issues found in 1 source file\n")


def test_contract_markers_track_source_lines(tmp_path: Path) -> None:
    fixture = tmp_path / "negative.py"
    fixture.write_text(
        "first\nbad()  # error: mypy=arg-type pyright=reportArgumentType\n",
        encoding="utf-8",
    )
    assert expected_diagnostics(fixture, "mypy") == frozenset(
        (Diagnostic("negative.py", 2, "arg-type"),)
    )
    assert expected_diagnostics(fixture, "pyright") == frozenset(
        (Diagnostic("negative.py", 2, "reportArgumentType"),)
    )


def test_overload_markers_can_require_multiple_diagnostic_categories(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "negative.py"
    fixture.write_text(
        "bad()  # error: mypy=call-overload "
        "pyright=reportCallIssue,reportArgumentType\n",
        encoding="utf-8",
    )
    assert expected_diagnostics(fixture, "pyright") == frozenset(
        (
            Diagnostic("negative.py", 1, "reportCallIssue"),
            Diagnostic("negative.py", 1, "reportArgumentType"),
        )
    )


def test_consumer_process_excludes_source_search_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inherited development overrides cannot leak into a wheel consumer."""
    for variable in ("PYTHONPATH", "MYPYPATH", "PYTHONHOME"):
        monkeypatch.setenv(variable, str(Path.cwd()))
    result = run_isolated(
        Path(sys.executable),
        (
            "-c",
            (
                "import os, sys; "
                "assert sys.flags.isolated == 1; "
                "assert not {'PYTHONPATH', 'MYPYPATH', 'PYTHONHOME'} & os.environ.keys(); "
                "print(os.getcwd())"
            ),
        ),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).resolve() == tmp_path.resolve()
