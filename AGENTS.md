# hier_config — Agent & Contributor Guide

This file is the canonical quick reference for AI coding agents (and humans) working in this repository. The deep documentation lives in `docs/` and on [Read the Docs](https://hier-config.readthedocs.io/); this file is the index.

## Project Overview

hier_config is a Python library that compares network device configurations (running vs intended) and generates minimal remediation commands. It parses config text into hierarchical trees and computes diffs respecting vendor-specific syntax rules. Runtime dependencies are deliberately minimal (`pydantic` only).

## Branching Strategy

- `master` — stable branch for v3.x releases and maintenance.
- `next` — long-lived development branch for v4 work. All v4 features and breaking changes target this branch; base v4 branches on `next` and open PRs against `next`.
- `2.3-lts` — legacy LTS maintenance branch; only targeted fixes for 2.3.x land there.

## Build & Test Commands

All commands use **uv** (not pip):

```bash
# Full lint + test suite (equivalent to CI's lint + pytest --coverage steps)
uv run ./scripts/build.py lint-and-test

# Lint only (ruff, mypy, pyright, pylint, yamllint, flynt — run in parallel)
uv run ./scripts/build.py lint

# Tests only (95% coverage required)
uv run ./scripts/build.py pytest --coverage

# Run a single test
uv run pytest tests/integration/test_cisco_xr.py::test_name -v

# Run a single test file
uv run pytest tests/integration/test_cisco_xr.py -v

# Run only unit tests / only integration tests
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v

# Auto-fix formatting
uv run ruff format hier_config tests scripts

# Validate docs (CI runs this unconditionally on every push/PR)
uv run mkdocs build --strict

# Benchmarks (deselected by default via the `benchmark` marker)
uv run pytest -m benchmark -v -s

# Diff this tree against a live hier-config v3 install
# (deselected by default via the `v3_differential` marker; builds a venv)
uv run pytest -m v3_differential -v
```

CI facts that matter for changes:

- **Python matrix**: CI tests on Python 3.10–3.14 and ruff targets `py310` — write 3.10-compatible syntax even though your local interpreter may be newer.
- **Docs job**: CI builds docs with `mkdocs build --strict` on every push/PR using `docs/requirements.txt` (pip, not uv). Adding an mkdocs plugin requires updating **both** `pyproject.toml` and `docs/requirements.txt`.

## Architecture in Brief

Three-layer design — full detail in [docs/dev/architecture.md](docs/dev/architecture.md):

- **Tree** (`base.py`, `root.py`, `child.py`, `children.py`, `tree_algorithms.py`, `constructors.py`): `HConfig` root and `HConfigChild` nodes; key operations `remediation()`, `future()`, `future_with_report()`, `unified_diff()`, `to_lines()`. Constructors are classmethods: `HConfig.from_text()`, `HConfig.from_lines()`, `HConfig.from_dump()`, `HConfig.from_json()`, `HConfig.from_xml()`. Supporting modules: `formats.py` (JSON/XML ingestion and rendering, NETCONF `edit-config` XML, gNMI-style JSON via `GnmiRemediation`), `plugins.py` (`RemediationPlugin` extension point), `exceptions.py` (exception hierarchy under `HierConfigError`), `utils.py` (file/YAML rule loaders).
- **Driver** (`platforms/`): each platform subclasses `HConfigDriverBase` and overrides `_instantiate_rules()` returning `HConfigDriverRules` — typed, frozen Pydantic rule models matched against config lineage via `MatchRule` tuples. Drivers register in `registry.py` (`get_hconfig_driver()`, `register_driver()`, `unregister_driver()`, `get_registered_platforms()`) and expose their config view via the `view_class` attribute. Registry keys are canonicalized to uppercase platform names (`Platform.X.name`); string lookups are case-insensitive (#284/#295).
- **Workflow** (`workflows.py`, `reporting.py`): `WorkflowRemediation` exposes `remediation_config` / `rollback_config` plus structured renderings `remediation_netconf_xml()` / `remediation_json()`; `RemediationReporter` aggregates changes across devices.

Supported platforms (`Platform` enum in `models.py`): ARISTA_EOS, ARUBA_AOSCX, CISCO_IOS, CISCO_NXOS, CISCO_XR, FORTINET_FORTIOS, GENERIC, HP_COMWARE5, HP_PROCURVE, HUAWEI_VRP, JUNIPER_JUNOS, NOKIA_SRL, VYOS.

## Hard Rules

These are enforced by CI and by reviewers; violations block merges:

1. **Models**: always subclass the project-local `BaseModel` in `hier_config/models.py` (it sets `frozen=True, extra="forbid"`) — never `pydantic.BaseModel` directly. Model fields use immutable collections only (`tuple`, `frozenset`). Rule models match lineage with `match_rules: tuple[MatchRule, ...]`. **Deliberate exception**: the rule-collection fields on `HConfigDriverRules` (`platforms/driver_base.py`) are intentionally `list[...]` so built-in rules and callbacks can be removed by identity (e.g. `rules.post_load_callbacks.remove(...)`, #286) — do not convert them to tuples.
2. **Typing**: mypy strict + pyright strict. Full annotations everywhere, including tests. No `Any`, no unjustified `# type: ignore` or `# noqa`.
3. **Lint**: ruff `select = ["ALL"]` with preview, line length 88. Never loosen lint or coverage configuration to make a change pass.
4. **TDD**: write a failing test first, confirm it fails for the right reason, implement minimally, run the full suite. 95% coverage floor.
5. **Tests**: flat function-based (no classes except benchmarks); unit tests mirror the source in `tests/unit/` (config views in `tests/unit/platforms/views/`), end-to-end driver scenarios go in `tests/integration/test_<platform>.py`; fixtures are module-scoped in the relevant `conftest.py` reading the sibling `fixtures/` directory; the dominant idiom is `HConfig.from_lines()` → `remediation()` → assert `to_lines()` tuple → `future()` → rollback → assert no `unified_diff()`.
6. **Rules containers**: fields on `HConfigDriverRules` use named module-level default factory functions, not lambdas.
7. **v3 compatibility**: the v3 names restored in `hier_config/constructors.py`,
   `utils.py`, `models.py`, `root.py`, and `child.py` are a permanent supported
   API. Never add a `DeprecationWarning` to them and never remove them. Each one
   must stay a thin delegation to its v4 counterpart -- never a second
   implementation. See [docs/user/v3-compatibility.md](docs/user/v3-compatibility.md).
8. **Changelog**: every PR adds an entry to `CHANGELOG.md` under `## [Unreleased]` (Keep a Changelog categories, `(#NNN)` reference).
9. **Commits**: imperative mood, subject ≤72 characters, body explains *why* (see [CONTRIBUTING.md](CONTRIBUTING.md)).
10. **Docs**: public API or driver behavior changes must update `docs/`; new pages must be added to `mkdocs.yml` nav; never move a page without a redirect entry.
11. **Dependencies**: no new runtime dependencies without prior discussion in an issue.

## Task → Documentation Map

| Task | Read first |
|------|-----------|
| Add a platform driver or rule type | [docs/dev/creating-drivers.md](docs/dev/creating-drivers.md), [docs/dev/rule-reference.md](docs/dev/rule-reference.md) |
| Write or fix tests | [docs/dev/testing.md](docs/dev/testing.md) |
| Understand lint/typing/model standards | [docs/dev/code-style.md](docs/dev/code-style.md) |
| Understand the internals | [docs/dev/architecture.md](docs/dev/architecture.md) |
| Dev environment setup, commit style, PR expectations | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Driver behavior reference | [docs/admin/platforms.md](docs/admin/platforms.md), [docs/admin/custom-drivers.md](docs/admin/custom-drivers.md), [docs/admin/customizing-rules.md](docs/admin/customizing-rules.md) |
| Load rules/tags from YAML or JSON files | [docs/admin/rules-from-files.md](docs/admin/rules-from-files.md) |
| Release process, prerelease versioning | [docs/admin/releases.md](docs/admin/releases.md) |
| CI, Read the Docs, Renovate, redirect policy | [docs/admin/infrastructure.md](docs/admin/infrastructure.md) |

## Before Opening a PR

- [ ] `uv run ./scripts/build.py lint-and-test` exits 0.
- [ ] Tests written first (TDD) and cover the change.
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`.
- [ ] Docs updated if public API or driver behavior changed; `mkdocs build --strict` passes if docs touched.
- [ ] Commit messages follow CONTRIBUTING.md style.

Claude Code users: run the `hier-config-review` skill (in `.claude/skills/`) to check all of the above automatically. Two more repo skills cover common workflows: `hier-config-new-driver` (scaffold support for a new platform) and `hier-config-troubleshoot` (diagnose wrong remediation/parsing output). Other agents can follow the same workflows via the docs those skills reference ([docs/dev/creating-drivers.md](docs/dev/creating-drivers.md) and the troubleshooting symptom table in the skill files, which are plain markdown).
