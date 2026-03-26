# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

hier_config is a Python library that compares network device configurations (running vs intended) and generates minimal remediation commands. It parses config text into hierarchical trees and computes diffs respecting vendor-specific syntax rules.

## Branching Strategy

- `master` — stable branch for v3.x releases and maintenance.
- `next` — long-lived development branch for v4 work. All v4 features and breaking changes target this branch. PRs for v4 work should be opened against `next`.

## Build & Test Commands

All commands use **poetry** (not pip):

```bash
# Full lint + test suite (what CI runs)
poetry run ./scripts/build.py lint-and-test

# Lint only (ruff, mypy, pyright, pylint, yamllint, flynt — run in parallel)
poetry run ./scripts/build.py lint

# Tests only (95% coverage required)
poetry run ./scripts/build.py pytest --coverage

# Run a single test
poetry run pytest tests/unit/platforms/test_cisco_xr.py::test_multiple_groups_no_duplicate_child_error -v

# Run a single test file
poetry run pytest tests/unit/platforms/test_cisco_xr.py -v

# Run only unit tests
poetry run pytest tests/unit/ -v

# Run only integration tests
poetry run pytest tests/integration/ -v

# Auto-fix formatting
poetry run ruff format hier_config tests scripts
```

## Benchmarks

Performance benchmarks are in `tests/test_benchmarks.py` and are **skipped by default** via the `benchmark` pytest marker. They generate ~10,000-line configs and measure parsing, remediation, and iteration performance.

```bash
# Run all benchmarks with timing output
poetry run pytest -m benchmark -v -s

# Run a specific benchmark
poetry run pytest -m benchmark -k test_parse_large_ios_config -v -s
```

Use `-s` to see printed timing results. Each benchmark reports the best time over 3 iterations and asserts an upper bound (e.g., `< 5s` for parsing, `< 10s` for remediation). If a benchmark fails its time threshold, investigate the relevant code path for performance regressions.

After running benchmarks, always display the results to the user in a table format summarizing each benchmark's config size and elapsed time.

## Architecture

Three-layer design: **Tree** (parse/represent config), **Driver** (platform-specific rules), **Workflow** (compute diffs/remediations).

### Tree Layer

- `HConfig` (root.py) — root node, owns the driver reference. Key methods: `remediation()`, `future()`, `difference()`, `to_lines()`.
- `HConfigChild` (child.py) — tree node with `text`, `parent`, `children`, `tags`, `comments`. Provides `is_lineage_match()` for rule evaluation and `negate()` for negation logic.
- `HConfigBase` (base.py) — abstract base shared by both. Provides `add_child()`, `get_children_deep()`, `_remediation()` (left pass = negate missing, right pass = add new).
- `HConfigChildren` (children.py) — ordered collection with O(1) dict lookup by text.

### Driver Layer (`platforms/`)

Each platform driver subclasses `HConfigDriverBase` (driver_base.py) and overrides `_instantiate_rules()` to return `HConfigDriverRules` — a Pydantic model holding lists of typed rule objects:

- **Rule models** are frozen Pydantic BaseModels defined in `models.py`. Each uses `match_rules: tuple[MatchRule, ...]` for lineage-based matching.
- **MatchRule** supports: `equals`, `startswith`, `endswith`, `contains`, `re_search`. Multiple fields = AND logic.
- `is_lineage_match()` on `HConfigChild` compares the full ancestry path against a tuple of MatchRules.

Key rule types: `SectionalExitingRule`, `IdempotentCommandsRule`, `PerLineSubRule`, `NegationDefaultWithRule`, `OrderingRule`, `ParentAllowsDuplicateChildRule`, `IndentAdjustRule`.

Platform drivers: `CISCO_IOS`, `CISCO_XR`, `CISCO_NXOS`, `ARISTA_EOS`, `FORTINET_FORTIOS`, `HP_PROCURVE`, `HP_COMWARE5`, `JUNIPER_JUNOS`, `VYOS`, `GENERIC`.

### Workflow Layer

- `WorkflowRemediation` (workflows.py) — primary API: `remediation_config` and `rollback_config` properties.
- Constructor functions in `constructors.py`: `get_hconfig()`, `get_hconfig_fast_load()`, `get_hconfig_driver()`.

### Adding a New Driver Rule Type

Pattern: add frozen Pydantic model in `models.py` → add default factory + field in `HConfigDriverRules` (driver_base.py) → consume in `child.py` or `root.py` → populate in platform driver's `_instantiate_rules()`.

## Development Approach

This project follows **Test-Driven Development (TDD)**:

1. **Write a failing test first** that validates the expected behavior.
2. **Run the test to confirm it fails** for the right reason.
3. **Implement the minimal code** to make the test pass.
4. **Run the full test suite** to ensure no regressions.
5. **Refactor** if needed, keeping tests green.

All new features and bug fixes must have corresponding tests. Write tests before or alongside implementation, not after.

### Test Organization

Tests mirror the source code structure and are split into categories:

- **`tests/unit/`** — Unit tests for individual classes and functions.
  - `test_root.py`, `test_child.py`, `test_children.py` — Tree layer tests.
  - `test_constructors.py`, `test_utils.py`, `test_workflows.py`, `test_reporting.py` — Core module tests.
  - `platforms/` — Driver unit tests (post-load callbacks, swap_negation, etc.).
  - `platforms/views/` — Config view tests.
- **`tests/integration/`** — Tests that exercise driver remediation scenarios (running config → generated config → remediation).
  - Per-platform files (`test_cisco_ios.py`, `test_cisco_xr.py`, etc.).
  - `test_remediation.py` — Cross-platform remediation, future, and difference tests.
  - `test_circular_workflows.py` — Roundtrip workflow validation across all platforms.
- **`tests/benchmarks/`** — Performance benchmarks (skipped by default).

## Changelog

When creating a PR, always update `CHANGELOG.md` with a summary of the changes under the `## [Unreleased]` section. Use the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format with categories: `Added`, `Changed`, `Fixed`, `Removed`. Reference the GitHub issue number when applicable (e.g., `(#209)`). When a version is released, move unreleased entries under a new version heading with the release date.

## Code Style

- Strict type checking: pyright strict mode + mypy strict + pylint with pydantic plugin.
- Ruff handles formatting (line length 88) and most lint rules.
- Docstrings use raw strings (`r"""..."""`) when containing backslashes.
- Test coverage minimum: 95%.
- Python 3.10+ required.
