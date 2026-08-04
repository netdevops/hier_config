# hier_config — Agent & Contributor Guide

This file is the canonical quick reference for AI coding agents (and humans) working in this repository. The deep documentation lives in `docs/` and on [Read the Docs](https://hier-config.readthedocs.io/); this file is the index.

## Project Overview

hier_config is a Python library that compares network device configurations (running vs intended) and generates minimal remediation commands. It parses config text into hierarchical trees and computes diffs respecting vendor-specific syntax rules. Runtime dependencies are deliberately minimal (`pydantic` only).

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
poetry run pytest tests/test_driver_cisco_xr.py::test_name -v

# Run a single test file
poetry run pytest tests/test_driver_cisco_xr.py -v

# Auto-fix formatting
poetry run ruff format hier_config tests scripts

# Validate docs (required if docs/ or mkdocs.yml changed)
poetry run mkdocs build --strict
```

## Architecture in Brief

Three-layer design — full detail in [docs/dev/architecture.md](docs/dev/architecture.md):

- **Tree** (`base.py`, `root.py`, `child.py`, `children.py`): `HConfig` root and `HConfigChild` nodes; key operations `config_to_get_to()`, `future()`, `unified_diff()`, `dump_simple()`.
- **Driver** (`platforms/`): each platform subclasses `HConfigDriverBase` and overrides `_instantiate_rules()` returning `HConfigDriverRules` — typed, frozen Pydantic rule models matched against config lineage via `MatchRule` tuples.
- **Workflow** (`workflows.py`, `reporting.py`): `WorkflowRemediation` exposes `remediation_config` / `rollback_config`; constructors live in `constructors.py` (`get_hconfig()`, `get_hconfig_fast_load()`, `get_hconfig_driver()`).

Supported platforms (`Platform` enum in `models.py`): ARISTA_EOS, CISCO_IOS, CISCO_NXOS, CISCO_XR, FORTINET_FORTIOS, GENERIC, HP_COMWARE5, HP_PROCURVE, HUAWEI_VRP, JUNIPER_JUNOS, NOKIA_SRL, VYOS.

## Hard Rules

These are enforced by CI and by reviewers; violations block merges:

1. **Models**: always subclass the project-local `BaseModel` in `hier_config/models.py` (it sets `frozen=True, extra="forbid"`) — never `pydantic.BaseModel` directly. Model fields use immutable collections only (`tuple`, `frozenset`). Rule models match lineage with `match_rules: tuple[MatchRule, ...]`.
2. **Typing**: mypy strict + pyright strict. Full annotations everywhere, including tests. No `Any`, no unjustified `# type: ignore` or `# noqa`.
3. **Lint**: ruff `select = ["ALL"]` with preview, line length 88. Never loosen lint or coverage configuration to make a change pass.
4. **TDD**: write a failing test first, confirm it fails for the right reason, implement minimally, run the full suite. 95% coverage floor.
5. **Tests**: flat function-based (no classes except benchmarks); driver changes go in `tests/test_driver_<platform>.py`; fixtures are module-scoped in `tests/conftest.py` reading `tests/fixtures/`; the dominant idiom is fast_load → `config_to_get_to` → assert `dump_simple()` tuple → `future()` → rollback → assert no `unified_diff`.
6. **Rules containers**: fields on `HConfigDriverRules` use named module-level default factory functions, not lambdas.
7. **Changelog**: every PR adds an entry to `CHANGELOG.md` under `## [Unreleased]` (Keep a Changelog categories, `(#NNN)` reference).
8. **Commits**: imperative mood, subject ≤72 characters, body explains *why* (see [CONTRIBUTING.md](CONTRIBUTING.md)).
9. **Docs**: public API or driver behavior changes must update `docs/`; new pages must be added to `mkdocs.yml` nav; never move a page without a redirect entry.
10. **Dependencies**: no new runtime dependencies without prior discussion in an issue.

## Task → Documentation Map

| Task | Read first |
|------|-----------|
| Add a platform driver, rule type, or view property | [docs/dev/extending.md](docs/dev/extending.md) |
| Write or fix tests | [docs/dev/testing.md](docs/dev/testing.md) |
| Understand lint/typing/model standards | [docs/dev/code-style.md](docs/dev/code-style.md) |
| Understand the internals | [docs/dev/architecture.md](docs/dev/architecture.md) |
| Dev environment setup, commit style, PR expectations | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Driver behavior reference | [docs/user/drivers.md](docs/user/drivers.md), [docs/user/custom-drivers.md](docs/user/custom-drivers.md) |

## Before Opening a PR

- [ ] `poetry run ./scripts/build.py lint-and-test` exits 0.
- [ ] Tests written first (TDD) and cover the change.
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`.
- [ ] Docs updated if public API or driver behavior changed; `mkdocs build --strict` passes if docs touched.
- [ ] Commit messages follow CONTRIBUTING.md style.

Claude Code users: run the `hier-config-review` skill (in `.claude/skills/`) to check all of the above automatically. Two more repo skills cover common workflows: `hier-config-new-driver` (scaffold support for a new platform) and `hier-config-troubleshoot` (diagnose wrong remediation/parsing output). Other agents can follow the same workflows via the docs those skills reference (`docs/dev/extending.md` and the troubleshooting symptom table in the skill files, which are plain markdown).
