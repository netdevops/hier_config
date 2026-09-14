<!-- Condensed from AGENTS.md — when standards change, update both files. -->

# GitHub Copilot Instructions for hier_config

hier_config is a Python library that compares network device configurations (running vs intended) and generates minimal remediation commands by parsing config text into hierarchical trees. Runtime dependencies are deliberately minimal (`pydantic` only).

The Rust rewrite ships as v4 in this repository, not v5 or a separate repository.
`crates/hier_config_core` owns trees, algorithms, formats and views;
`crates/hier_config_py` supplies PyO3 bindings. Python tree/view modules are thin
facades, not alternate implementations. PyYAML is optional via `[yaml]`.

## Branching

`master` is the stable v3.x branch; `next` is the v4 development branch. All v4 features and breaking changes must target `next`, not `master`.

## Build & Test

Use uv for Python dependencies and maturin for builds. Source development
requires Python 3.10+, a linker, and Rust meeting `Cargo.toml`'s MSRV (1.98).
Rebuild after Rust changes:

```bash
uv sync --locked --extra yaml
uv run --no-sync maturin develop --release --locked
uv run --no-sync ./scripts/build.py lint          # CI lint step
uv run --no-sync ./scripts/build.py pytest --coverage   # CI test step, 95% coverage floor
uv run --no-sync ./scripts/build.py lint-and-test # both in one command
cargo fmt --check
cargo clippy --locked --all-targets --all-features -- -D warnings
cargo test --locked --workspace --all-features
cargo llvm-cov --locked --package hier_config_core --fail-under-lines 47
```

CI also runs the test step across Python 3.10–3.14 (code must stay 3.10-compatible) and builds docs with `mkdocs build --strict` on every push/PR.

Use `--no-sync` after a manual maturin rebuild: automatic uv synchronization
can replace the fresh extension with a cached wheel. Rebuild after any later
`uv sync`.

## Rules to Enforce in Review

Native migration contracts: custom `config_preprocessor()` is rejected along
with `idempotent_for()`, `negate_with()`, `sectional_exit()`, and `swap_negation()`.
Preprocess custom text explicitly before `HConfig.from_text()`; marked stock
preprocessors remain callable helpers. Built-in device-view subclasses remain
supported, but Generic native views, direct interface-view construction, and
old capability-mixin `issubclass()` relationships do not.

- **Pydantic models must subclass the project-local `BaseModel`** from `hier_config/models.py` (it sets `frozen=True, extra="forbid"`). Direct use of `pydantic.BaseModel` is a defect.
- **Model fields use immutable collections only**: `tuple` and `frozenset`, never `list` or `set`. Rule models match config lineage with `match_rules: tuple[MatchRule, ...]`. Deliberate exception: the rule-collection fields on `HConfigDriverRules` are intentionally `list[...]` so built-in rules/callbacks can be removed by identity (#286) — do not flag them.
- **Strict typing**: flag `Any`, missing annotations (including in tests), and `# type: ignore` / `# noqa` comments without a justifying reason. mypy and pyright both run in strict mode.
- **Tests must accompany every code change** (the project follows TDD). Tests are flat functions — no test classes (benchmarks excepted). Driver behavior changes belong in `tests/integration/test_<platform>.py`; driver unit tests in `tests/unit/platforms/`; config view changes in `tests/unit/platforms/views/`.
- **Driver/rule changes need round-trip assertions**: build running + intended configs, assert the exact remediation output (`to_lines()`), and verify the rollback restores the original (no `unified_diff`).
- **Native coverage**: use Rust tests plus `tests/native/` boundary tests,
  `tests/parity/` upstream comparisons and shared `testdata/cases/` round-trips.
  Python coverage has a 95% floor; the separate Rust-core gate has a 47% floor.
  Never lower either gate. Displaced Python assertions
  require equivalent identified native tests. Keep generated/shipped stubs in sync.
- **Fields on `HConfigDriverRules`** (`hier_config/platforms/driver_base.py`) use named module-level default factory functions, not lambdas.
- **`CHANGELOG.md` must have an entry** under `## [Unreleased]` (Keep a Changelog categories: Added/Changed/Fixed/Removed, with an issue/PR reference like `(#209)`).
- **Docs must be updated** when public API or driver behavior changes; new doc pages must be added to `mkdocs.yml` nav; moved pages need a `redirect_maps` entry.
- **No loosening of quality gates**: reject changes that lower coverage thresholds, disable lint rules, or relax type-checking configuration to make a change pass.
- **No new runtime dependencies** without prior discussion in an issue.

## Full Standards

See `AGENTS.md` at the repo root, `CONTRIBUTING.md`, and the developer docs under `docs/dev/` (architecture, creating-drivers, rule-reference, testing, code-style).
