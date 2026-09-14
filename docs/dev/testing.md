# Testing Conventions

hier_config follows **Test-Driven Development (TDD)**: write a failing test that validates the expected behavior, confirm it fails for the right reason, implement the minimal code to make it pass, then run the full suite for regressions.

## Commands

All commands use uv:

```bash
# Full lint + test suite (what CI runs)
uv run ./scripts/build.py lint-and-test

# Tests only (95% coverage required)
uv run ./scripts/build.py pytest --coverage

# A single test
uv run pytest tests/integration/test_cisco_ios.py::test_delete_sectional_exit_regression -v

# A single file
uv run pytest tests/integration/test_cisco_ios.py -v

# Only unit tests / only integration tests
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
```

Coverage must stay at or above **95%** (`--cov-fail-under=95`, enforced by `scripts/build.py` and CI).

## Conventions

- **Flat, function-based tests** — no test classes. (The only exceptions are the benchmark groupings in `tests/benchmarks/test_benchmarks.py` and the parametrized circular-workflow suite.)
- **Tests mirror the source layout**: unit tests for individual classes and functions live in `tests/unit/` (with driver unit tests in `tests/unit/platforms/` and config view tests in `tests/unit/platforms/views/`); end-to-end remediation scenarios live in `tests/integration/` with one file per platform (e.g., `test_cisco_xr.py`). Driver behavior changes belong in the matching file.
- **Fixtures** are module-scoped, defined in the relevant `conftest.py`, and read config text from the sibling `fixtures/` directory. Add new sample configs there rather than embedding large configs inline.
- **Full type annotations** — test functions are annotated (`def test_x() -> None:`) and pass the same strict type checking as library code.

## The Dominant Test Idiom

Most driver tests follow a round-trip assertion chain — build both configs, compute the remediation, assert its exact text, then prove the rollback restores the original:

```python
def test_example() -> None:
    running_config = HConfig.from_lines(platform, ("interface Ethernet1", "  shutdown"))
    generated_config = HConfig.from_lines(platform, ("interface Ethernet1", "  no shutdown"))

    remediation = running_config.remediation(generated_config)
    assert remediation.to_lines() == ("interface Ethernet1", "  no shutdown")

    running_after = running_config.future(remediation)
    rollback = running_after.remediation(running_config)
    running_after_rollback = running_after.future(rollback)
    assert not tuple(running_config.unified_diff(running_after_rollback))
```

When fixing a bug, add a regression test that would have caught it.

## Benchmarks

Performance benchmarks live in `tests/benchmarks/test_benchmarks.py` and are **skipped by default** via the `benchmark` pytest marker (`addopts = "-m 'not benchmark'"`). They generate ~10,000-line configs and assert upper time bounds.

```bash
# All benchmarks, with timing output
uv run pytest -m benchmark -v -s

# One benchmark
uv run pytest -m benchmark -k test_parse_large_ios_config -v -s
```

If a benchmark fails its time threshold, investigate the relevant code path for performance regressions.

## v3 compatibility tests

`tests/integration/v3_scenarios.py` holds scenarios that run under **both** hier_config v3 and v4. Its core mirrors `nautobot_golden_config.models._get_hierconfig_remediation`, the reference v3 consumer. Keep that module importable on both majors: no v4-only imports, no pytest fixtures, and no v4 behaviour that the [v3 compatibility surface](../user/v3-compatibility.md) does not cover.

Two tests consume it:

- `tests/integration/test_v3_baseline.py` compares `run_all()` against `tests/fixtures/v3_baseline.json`, a committed recording made on v3.7.0. It runs in the normal suite -- no network, no second environment.
- `tests/integration/test_v3_differential.py` diffs against a **live** v3 install. It is deselected by default via the `v3_differential` marker because it builds a virtual environment and downloads from PyPI.

```bash
# Diff against a live v3 install
uv run pytest -m v3_differential -v

# Re-record the baseline after changing v3_scenarios.py
uv run ./scripts/generate_v3_baseline.py
```

After changing `v3_scenarios.py`, regenerate the baseline and **review the diff**. A changed value for an existing scenario means v4 no longer matches v3 -- fix the compatibility surface, not the recording.
