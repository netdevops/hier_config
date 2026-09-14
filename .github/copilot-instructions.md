<!-- Condensed from AGENTS.md — when standards change, update both files. -->

# GitHub Copilot Instructions for hier_config

hier_config is a Python library that compares network device configurations (running vs intended) and generates minimal remediation commands by parsing config text into hierarchical trees. Runtime dependencies are deliberately minimal (`pydantic` only).

## Branching

`master` is the stable v3.x branch; `next` is the v4 development branch. All v4 features and breaking changes must target `next`, not `master`.

## Build & Test

All commands use uv (not pip):

```bash
uv run ./scripts/build.py lint          # CI lint step
uv run ./scripts/build.py pytest --coverage   # CI test step, 95% coverage floor
uv run ./scripts/build.py lint-and-test # both in one command
```

CI also runs the test step across Python 3.10–3.14 (code must stay 3.10-compatible) and builds docs with `mkdocs build --strict` on every push/PR.

## Rules to Enforce in Review

- **Pydantic models must subclass the project-local `BaseModel`** from `hier_config/models.py` (it sets `frozen=True, extra="forbid"`). Direct use of `pydantic.BaseModel` is a defect.
- **Model fields use immutable collections only**: `tuple` and `frozenset`, never `list` or `set`. Rule models match config lineage with `match_rules: tuple[MatchRule, ...]`. Deliberate exception: the rule-collection fields on `HConfigDriverRules` are intentionally `list[...]` so built-in rules/callbacks can be removed by identity (#286) — do not flag them.
- **Strict typing**: flag `Any`, missing annotations (including in tests), and `# type: ignore` / `# noqa` comments without a justifying reason. mypy and pyright both run in strict mode.
- **Tests must accompany every code change** (the project follows TDD). Tests are flat functions — no test classes (benchmarks excepted). Driver behavior changes belong in `tests/integration/test_<platform>.py`; driver unit tests in `tests/unit/platforms/`; config view changes in `tests/unit/platforms/views/`.
- **Driver/rule changes need round-trip assertions**: build running + intended configs, assert the exact remediation output (`to_lines()`), and verify the rollback restores the original (no `unified_diff`).
- **Fields on `HConfigDriverRules`** (`hier_config/platforms/driver_base.py`) use named module-level default factory functions, not lambdas.
- **`CHANGELOG.md` must have an entry** under `## [Unreleased]` (Keep a Changelog categories: Added/Changed/Fixed/Removed, with an issue/PR reference like `(#209)`).
- **Docs must be updated** when public API or driver behavior changes; new doc pages must be added to `mkdocs.yml` nav; moved pages need a `redirect_maps` entry.
- **No loosening of quality gates**: reject changes that lower coverage thresholds, disable lint rules, or relax type-checking configuration to make a change pass.
- **No new runtime dependencies** without prior discussion in an issue.

## Full Standards

See `AGENTS.md` at the repo root, `CONTRIBUTING.md`, and the developer docs under `docs/dev/` (architecture, creating-drivers, rule-reference, testing, code-style).
