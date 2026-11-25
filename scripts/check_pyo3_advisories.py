#!/usr/bin/env python3
"""Guard the ``deny.toml`` ignore of RUSTSEC-2026-0176.

That ignore rests on the assertion that this workspace never calls ``nth``,
``nth_back``, or ``skip`` on a PyO3 ``PyList``/``PyTuple`` iterator. The advisory
is an out-of-bounds read reachable only through those entry points.

``clippy.toml`` cannot express this half: ``.nth(n)``/``.nth_back(n)``/``.skip(n)``
dispatch through ``Iterator``/``DoubleEndedIterator``, and ``disallowed_methods``
only matches inherent associated functions. A rule naming them resolves to nothing
and silently never fires, so this textual guard stands in for it.

The check is deliberately conservative: it flags the call whenever it appears on
the same expression as a ``PyList``/``PyTuple`` iterator, and asks for an explicit
``# pyo3-advisory-ok: <reason>`` waiver rather than trying to type-check Rust.

Fails with exit status 1 if any unwaived call is found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CRATES_DIR = REPO_ROOT / "crates"

WAIVER = "pyo3-advisory-ok:"

# A call to one of the advisory entry points, chained off something that produced
# a PyList/PyTuple iterator on the same expression. `iter_borrowed` and plain
# `iter` are the only ways to reach `BoundListIterator`/`BoundTupleIterator`.
_RISKY_CALL = re.compile(
    r"""
    (?P<source>
        \b(?:PyList|PyTuple)\b [^;\n]*? \. (?:iter|iter_borrowed) \s* \(\s*\)
        |
        \. (?:iter|iter_borrowed) \s* \(\s*\) [^;\n]*?
    )
    \s* \. \s* (?P<method>nth|nth_back|skip) \s* \(
    """,
    re.VERBOSE,
)

# Narrow the second, looser alternative above to expressions that actually name a
# PyList/PyTuple somewhere on the line, so ordinary Rust iterators are not flagged.
_PY_SEQ = re.compile(r"\b(?:PyList|PyTuple|py_list|py_tuple|args|tuple|list)\b")


def _iter_rust_files() -> list[Path]:
    return sorted(CRATES_DIR.rglob("*.rs"))


def _check_file(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, method) for each unwaived risky call."""
    findings: list[tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if WAIVER in line:
            continue
        match = _RISKY_CALL.search(line)
        if match is None:
            continue
        if not _PY_SEQ.search(line):
            continue
        findings.append((lineno, match.group("method")))
    return findings


def main() -> int:
    failures: list[str] = []
    for path in _iter_rust_files():
        for lineno, method in _check_file(path):
            rel = path.relative_to(REPO_ROOT)
            failures.append(
                f"{rel}:{lineno}: `.{method}()` on a PyO3 sequence iterator is "
                f"forbidden by RUSTSEC-2026-0176 (ignored in deny.toml on the "
                f"basis that we never call it). Index the sequence directly, or "
                f"add `// {WAIVER} <reason>` if this is provably safe.",
            )

    if failures:
        print("pyo3 advisory guard failed:", file=sys.stderr)  # ruff: ignore[print]
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)  # ruff: ignore[print]
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
