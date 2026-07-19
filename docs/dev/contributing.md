# Contributing

This page summarizes how to set up a development environment, run the checks that CI runs, and meet the project's expectations for pull requests. The authoritative reference is [CONTRIBUTING.md](https://github.com/netdevops/hier_config/blob/master/CONTRIBUTING.md) in the repository root.

## Development setup

The project uses **Poetry** (not pip) for dependency management:

```bash
# Fork on GitHub, then:
git clone git@github.com:YOUR-USERNAME/hier_config.git
cd hier_config
poetry install
git checkout -b YOUR-BRANCH
```

Python 3.10+ is required.

## Build and test commands

The single command that runs everything CI runs:

```bash
# Full lint + test suite
poetry run ./scripts/build.py lint-and-test

# Lint only (ruff, mypy, pyright, pylint, yamllint, flynt — run in parallel)
poetry run ./scripts/build.py lint

# Tests only (95% coverage required)
poetry run ./scripts/build.py pytest --coverage

# Auto-fix formatting
poetry run ruff format hier_config tests scripts
```

Useful pytest invocations:

```bash
# Run a single test
poetry run pytest tests/unit/platforms/test_cisco_xr.py::test_name -v

# Run only unit tests / integration tests
poetry run pytest tests/unit/ -v
poetry run pytest tests/integration/ -v
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
- **`tests/benchmarks/`** — performance benchmarks, skipped by default (run with `poetry run pytest -m benchmark -v -s`).

Coverage must stay at or above **95%**.

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
| New platform support | `hier_config/platforms/<name>/driver.py` (subclass `HConfigDriverBase`) |
| New rule type | `hier_config/models.py` (new `BaseModel` subclass) + `hier_config/platforms/driver_base.py` (`HConfigDriverRules` field) |
| New utility function | `hier_config/utils.py` |
| New view property | `hier_config/platforms/view_base.py` (abstract) + each platform's `view.py` |
| Core tree algorithm | `hier_config/tree_algorithms.py` (comparison algorithms) or `hier_config/base.py` / `hier_config/root.py` (tree structure) |

Read the [Architecture](architecture.md) page before making structural changes.

## Next steps

- [Architecture](architecture.md) — orientation before your first change.
- [Creating a Platform Driver](creating-drivers.md) — the most common kind of contribution.
- [API Reference](api-reference.md) — the public surface your change may affect.
