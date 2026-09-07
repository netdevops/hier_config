"""Guard the Python object protocol against the frozen legacy snapshot.

`probe_object_protocol.expected` was recorded from the original pure-Python
implementation before it was deleted. It captures the observable object
protocol that downstream code depends on but which ordinary unit tests do not
assert: `__slots__` enforcement, identity of re-fetched children, deepcopy and
pickle round-trips, subclassability, `tags` being a `frozenset`, comment
handling and `repr` shape.

With the pure-Python implementation gone this file is the only remaining oracle
for those semantics, so it is wired into the suite rather than left as a
standalone script.

A diff here means the Rust core changed observable Python behaviour. That is
occasionally intentional -- if so, re-record the snapshot deliberately and note
the change in the changelog -- but it is never something to update casually.
"""

from __future__ import annotations

from pathlib import Path

from tests.parity.probe_object_protocol import probe

EXPECTED = Path(__file__).with_name("probe_object_protocol.expected")


def test_object_protocol_matches_legacy_snapshot() -> None:
    actual = probe().strip()
    expected = EXPECTED.read_text(encoding="utf-8").strip()

    if actual != expected:
        actual_lines = actual.splitlines()
        expected_lines = expected.splitlines()
        diffs = [
            f"  line {i + 1}: expected {e!r}, got {a!r}"
            for i, (e, a) in enumerate(zip(expected_lines, actual_lines, strict=False))
            if e != a
        ]
        if len(actual_lines) != len(expected_lines):
            diffs.append(
                f"  line count: expected {len(expected_lines)}, got {len(actual_lines)}"
            )
        detail = "\n".join(diffs) or "  (whitespace-only difference)"
        msg = (
            "Python object protocol drifted from the frozen legacy snapshot.\n"
            f"{detail}\n"
            "This snapshot is the last remaining record of pure-Python "
            "semantics. Only re-record it for a deliberate, documented "
            "behaviour change."
        )
        raise AssertionError(msg)
