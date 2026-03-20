# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

hier_config is a Python library that compares network device configurations (running vs intended) and generates minimal remediation commands. It parses config text into hierarchical trees and computes diffs respecting vendor-specific syntax rules.

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
poetry run pytest tests/test_driver_cisco_xr.py::test_multiple_groups_no_duplicate_child_error -v

# Run a single test file
poetry run pytest tests/test_driver_cisco_xr.py -v

# Auto-fix formatting
poetry run ruff format hier_config tests scripts
```

## Architecture

Three-layer design: **Tree** (parse/represent config), **Driver** (platform-specific rules), **Workflow** (compute diffs/remediations).

### Tree Layer

- `HConfig` (root.py) — root node, owns the driver reference. Key methods: `config_to_get_to()`, `future()`, `difference()`, `dump_simple()`.
- `HConfigChild` (child.py) — tree node with `text`, `parent`, `children`, `tags`, `comments`. Provides `is_lineage_match()` for rule evaluation and `negate()` for negation logic.
- `HConfigBase` (base.py) — abstract base shared by both. Provides `add_child()`, `get_children_deep()`, `_config_to_get_to()` (left pass = negate missing, right pass = add new).
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

## Code Style

- Strict type checking: pyright strict mode + mypy strict + pylint with pydantic plugin.
- Ruff handles formatting (line length 88) and most lint rules.
- Docstrings use raw strings (`r"""..."""`) when containing backslashes.
- Test coverage minimum: 95%.
- Python 3.10+ required.
