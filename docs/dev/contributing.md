# Contributing

This page summarizes how to set up a development environment, run the checks that CI runs, and meet the project's expectations for pull requests. The authoritative reference is [CONTRIBUTING.md](https://github.com/netdevops/hier_config/blob/next/CONTRIBUTING.md) in the repository root.

## Development setup

The project uses **uv** (not pip) for dependency management:

```bash
# Fork on GitHub, then:
git clone git@github.com:YOUR-USERNAME/hier_config.git
cd hier_config
uv sync --locked --extra yaml
uv run --no-sync maturin develop --release --locked
git checkout -b YOUR-BRANCH
```

Dependencies are locked in `uv.lock`, and CI installs with `uv sync --locked`.
If you change dependencies, use `uv add` / `uv add --dev` (or run `uv lock`
after editing `pyproject.toml`) and commit the updated `uv.lock`.

Python 3.10+, a linker, and Rust meeting the MSRV in `Cargo.toml` (currently
1.98) are required. This is the v4 Rust rewrite in the existing repository,
not a separate package. maturin builds the PyO3 extension; rebuild after Rust
changes so tests do not exercise an older installed binary.
Rust dependencies are locked in `Cargo.lock`.

## Build and test commands

Python lint and test commands (native and packaging jobs run separately in CI):

```bash
# Full lint + test suite
uv run --no-sync ./scripts/build.py lint-and-test

# Lint only (ruff, mypy, pyright, pylint, yamllint, flynt — run in parallel)
uv run --no-sync ./scripts/build.py lint

# Tests only (95% coverage required)
uv run --no-sync ./scripts/build.py pytest --coverage

# Auto-fix formatting
uv run --no-sync ruff format hier_config tests scripts
```

Useful pytest invocations:

```bash
# Run a single test
uv run --no-sync pytest tests/unit/platforms/test_cisco_xr.py::test_name -v

# Run only unit tests / integration tests
uv run --no-sync pytest tests/unit/ -v
uv run --no-sync pytest tests/integration/ -v
```

## Test-driven development

The project follows TDD — all new features and bug fixes must have corresponding tests, written before or alongside the implementation:

1. **Write a failing test first** that validates the expected behavior.
2. **Run the test to confirm it fails** for the right reason.
3. **Implement the minimal code** to make the test pass.
4. **Run the full test suite** to ensure no regressions.
5. **Refactor** if needed, keeping tests green.

### Test layout

Tests mirror the source structure and are split into categories:

- **`tests/unit/`** — unit tests for individual classes and functions (tree layer, constructors, workflows, reporting, per-platform driver behavior under `platforms/`, config views under `platforms/views/`).
- **`tests/integration/`** — driver remediation scenarios (running config → generated config → remediation), cross-platform remediation/future/difference tests, and roundtrip workflow validation.
- **`tests/benchmarks/`** — performance benchmarks, skipped by default (run with `uv run --no-sync pytest -m benchmark -v -s`).

Coverage must stay at or above **95%**.

Also run `cargo fmt --check`,
`cargo clippy --locked --all-targets --all-features -- -D warnings`,
`cargo test --locked --workspace --all-features`, and
`cargo llvm-cov --locked --package hier_config_core --fail-under-lines 90`.
See [Testing](testing.md) for native, parity, and shared-corpus coverage.

## Code quality expectations

- **Strict type checking** — pyright strict mode, mypy strict, and pylint (with the pydantic plugin) all must pass.
- **Ruff** handles formatting (line length 88) and most lint rules.
- **Docstrings for new public API** — any new public class, method, or function must have a docstring.
- **No breaking changes without discussion** — open an issue first if you plan to change a public interface.

## Changelog

Update `CHANGELOG.md` under the `## [Unreleased]` section with every PR, using the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) categories (`Added`, `Changed`, `Fixed`, `Removed`) and referencing the GitHub issue number when applicable (e.g., `(#209)`).

## Commit messages and PRs

- Use the **imperative mood** in the subject line ("Add feature", not "Added feature"), 72 characters or fewer.
- Leave a blank line between subject and body; the body should explain *why*.
- v4 features and breaking changes target the `next` branch; v3.x maintenance targets `master`.
- Push to your fork and open a pull request — maintainers will review and may suggest changes.

## Where do changes belong?

| Change type | Location |
|-------------|----------|
| New platform support | Native platform operations/rules in `crates/hier_config_core/src/platforms/`, Python driver facade, enums, registry |
| New rule type | Python model/container plus Rust rule decoding and evaluation |
| New utility function | `hier_config/utils.py` |
| New view property | `crates/hier_config_core/src/view/`, PyO3 view bindings, and stubs |
| Core tree algorithm | `crates/hier_config_core/src/`; Python files are thin facades |

Read the [Architecture](architecture.md) page before making structural changes.

## Next steps

- [Architecture](architecture.md) — orientation before your first change.
- [Creating a Platform Driver](creating-drivers.md) — the most common kind of contribution.
- [API Reference](api-reference.md) — the public surface your change may affect.
