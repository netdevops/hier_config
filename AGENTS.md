# hier_config — Agent & Contributor Guide

This file is the canonical quick reference for AI coding agents (and humans) working in this repository. The deep documentation lives in `docs/` and on [Read the Docs](https://hier-config.readthedocs.io/); this file is the index.

## Project Overview

hier_config is a Python library that compares network device configurations (running vs intended) and generates minimal remediation commands. It parses config text into hierarchical trees and computes diffs respecting vendor-specific syntax rules. Runtime dependencies are deliberately minimal (`pydantic` only).

The Rust rewrite ships as **v4 in this repository**. Rust owns the engine and
views; PyO3 exposes them through thin Python facades. PyYAML is optional via
`hier-config[yaml]`. There is no pure-Python engine fallback.

## Branching Strategy

- `master` — stable branch for v3.x releases and maintenance.
- `next` — long-lived development branch for v4 work. All v4 features and breaking changes target this branch; base v4 branches on `next` and open PRs against `next`.
- `2.3-lts` — legacy LTS maintenance branch; only targeted fixes for 2.3.x land there.

## Build & Test Commands

Use **uv** for Python dependencies and **maturin** for extension builds.
Source builds require Python 3.10+, a linker, and Rust meeting the MSRV in
`Cargo.toml` (currently 1.98). Before Python checks, and after Rust edits:

```bash
uv sync --locked --extra yaml
uv run --no-sync maturin develop --release --locked

# Python lint + test suite (native gates are separate)
uv run --no-sync ./scripts/build.py lint-and-test

# Lint only (ruff, mypy, pyright, pylint, yamllint, flynt — run in parallel)
uv run --no-sync ./scripts/build.py lint

# Tests only (95% coverage required)
uv run --no-sync ./scripts/build.py pytest --coverage

# Run a single test
uv run --no-sync pytest tests/integration/test_cisco_xr.py::test_name -v

# Run a single test file
uv run --no-sync pytest tests/integration/test_cisco_xr.py -v

# Run only unit tests / only integration tests
uv run --no-sync pytest tests/unit/ -v
uv run --no-sync pytest tests/integration/ -v

# Auto-fix formatting
uv run --no-sync ruff format hier_config tests scripts

# Validate docs (CI runs this unconditionally on every push/PR)
uv run --no-sync mkdocs build --strict

# Benchmarks (deselected by default via the `benchmark` marker)
uv run --no-sync pytest -m benchmark -v -s

# Diff this tree against a live hier-config v3 install
# (deselected by default via the `v3_differential` marker; builds a venv)
uv run --no-sync pytest -m v3_differential -v

# Native gates
cargo fmt --check
cargo clippy --locked --all-targets --all-features -- -D warnings
cargo test --locked --workspace --all-features
cargo llvm-cov --locked --package hier_config_core --fail-under-lines 90
```

CI facts that matter for changes:

- **Python matrix**: CI tests on Python 3.10–3.14 and ruff targets `py310` — write 3.10-compatible syntax even though your local interpreter may be newer.
- **Docs job**: CI builds docs with `mkdocs build --strict` on every push/PR using `docs/requirements.txt` (pip, not uv). Adding an mkdocs plugin requires updating **both** `pyproject.toml` and `docs/requirements.txt`.
- **Lockfiles**: dependency changes must update `uv.lock` and/or `Cargo.lock`. Use `uv add` / `uv add --dev` (or `uv lock` after editing `pyproject.toml`); native gates use `--locked`.

Use `--no-sync` after a manual maturin rebuild: automatic uv synchronization
can replace the fresh extension with a cached wheel. Rebuild after any later
`uv sync`.

## Architecture in Brief

Three-layer design — full detail in [docs/dev/architecture.md](docs/dev/architecture.md):

- **Native core** (`crates/hier_config_core/src/`): arena-backed trees, parser, remediation/future/diff algorithms, platform operations, structured formats and views. The crate works without Python.
- **Python boundary** (`crates/hier_config_py/src/`): PyO3 handles, exception translation, Python callbacks, and native views/workflows. `hier_config/{base,root,child,children,workflows}.py` and platform view files are thin facades; `tree_algorithms.py` retains only `FutureReport`. Keep the compiled extension and shipped `.pyi` stubs synchronized.
- **Driver** (`platforms/`): each platform subclasses `HConfigDriverBase` and overrides `_instantiate_rules()` returning `HConfigDriverRules` — typed, frozen Pydantic rule models matched against config lineage via `MatchRule` tuples. Drivers register in `registry.py` (`get_hconfig_driver()`, `register_driver()`, `unregister_driver()`, `get_registered_platforms()`) and expose their config view via the `view_class` attribute. Registry keys are canonicalized to uppercase platform names (`Platform.X.name`); string lookups are case-insensitive (#284/#295).
- **Workflow** (`workflows.py`, `reporting.py`): `WorkflowRemediation` exposes `remediation_config` / `rollback_config` plus structured renderings `remediation_netconf_xml()` / `remediation_json()`; `RemediationReporter` aggregates changes across devices.

Supported platforms (`Platform` enum in `models.py`): ARISTA_EOS, ARUBA_AOSCX, CISCO_IOS, CISCO_NXOS, CISCO_XR, FORTINET_FORTIOS, GENERIC, HP_COMWARE5, HP_PROCURVE, HUAWEI_VRP, JUNIPER_JUNOS, NOKIA_SRL, VYOS.

## Hard Rules

Native typing has one generated artifact,
`hier_config/_hier_config_rust.pyi`. Update `pyo3-stub-gen` metadata and
documentation beside the PyO3 bindings, then run
`uv run --no-sync ./scripts/build.py generate-stubs`. Never recover signatures
from Git history or maintain duplicate facade stubs. `check-stubs` is
read-only; runtime/export checks and wheel-consumer typing checks remain
independent gates. Validation allowlists belong in `tests/typing/`.

Native migration contracts: custom `config_preprocessor()` is rejected along
with `idempotent_for()`, `negate_with()`, `sectional_exit()`, and `swap_negation()`.
Preprocess custom text explicitly before `HConfig.from_text()`; marked stock
preprocessors remain callable helpers. Built-in device-view subclasses remain
supported, but Generic native views, direct interface-view construction, and
old capability-mixin `issubclass()` relationships do not.

These are enforced by CI and by reviewers; violations block merges:

1. **Models**: always subclass the project-local `BaseModel` in `hier_config/models.py` (it sets `frozen=True, extra="forbid"`) — never `pydantic.BaseModel` directly. Model fields use immutable collections only (`tuple`, `frozenset`). Rule models match lineage with `match_rules: tuple[MatchRule, ...]`. **Deliberate exception**: the rule-collection fields on `HConfigDriverRules` (`platforms/driver_base.py`) are intentionally `list[...]` so built-in rules and callbacks can be removed by identity (e.g. `rules.post_load_callbacks.remove(...)`, #286) — do not convert them to tuples.
2. **Typing**: mypy strict + pyright strict. Full annotations everywhere, including tests. No `Any`, no unjustified `# type: ignore` or `# noqa`.
3. **Lint**: ruff `select = ["ALL"]` with preview, line length 88. Never loosen lint or coverage configuration to make a change pass.
4. **TDD**: write a failing test first, confirm it fails for the right reason, implement minimally, run the full suite. 95% coverage floor.
5. **Tests**: flat function-based (no classes except benchmarks); unit tests mirror the source in `tests/unit/` (config views in `tests/unit/platforms/views/`), end-to-end driver scenarios go in `tests/integration/test_<platform>.py`; fixtures are module-scoped in the relevant `conftest.py` reading the sibling `fixtures/` directory; the dominant idiom is `HConfig.from_lines()` → `remediation()` → assert `to_lines()` tuple → `future()` → rollback → assert no `unified_diff()`.
   Native-boundary contracts belong in `tests/native/`, upstream comparisons in
   `tests/parity/`, and shared Rust/Python round-trips in `testdata/cases/`.
   Moving a test to Rust requires identified equivalent assertions, not just a
   skip marker. Python coverage has a 95% floor; the separate Rust-core gate
   currently has a 90% floor. Never lower either gate.
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

- [ ] `uv run --no-sync ./scripts/build.py lint-and-test` exits 0.
- [ ] Release extension rebuilt; Cargo formatting, Clippy, tests, and coverage pass.
- [ ] Tests written first (TDD) and cover the change.
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`.
- [ ] Docs updated if public API or driver behavior changed; `mkdocs build --strict` passes if docs touched.
- [ ] Commit messages follow CONTRIBUTING.md style.

Claude Code users: run the `hier-config-review` skill (in `.claude/skills/`) to check all of the above automatically. Two more repo skills cover common workflows: `hier-config-new-driver` (scaffold support for a new platform) and `hier-config-troubleshoot` (diagnose wrong remediation/parsing output). Other agents can follow the same workflows via the docs those skills reference ([docs/dev/creating-drivers.md](docs/dev/creating-drivers.md) and the troubleshooting symptom table in the skill files, which are plain markdown).
