# Design: Convert Project Packaging and Dependency Management from Poetry to uv

## Context & Objectives

`hier_config` currently uses Poetry for dependency management, packaging, and virtual environment orchestration. While functional, Poetry has heavier overhead and slower resolution compared to modern tooling.

`uv` is an extremely fast Python package manager and resolver developed by Astral. Migrating to `uv` provides:
- Near-instantaneous dependency resolution and lockfile operations.
- Native PEP 621 project metadata and PEP 735 dependency groups.
- Fast-path builds via the native `uv_build` backend.
- Faster, simplified CI/CD runs with `astral-sh/setup-uv`.
- Streamlined local developer workflows using `uv run`.

## Packaging & Build Backend (`pyproject.toml`)

### Standard PEP 621 Metadata

Replace `[tool.poetry]` tables with standard `[project]`:
- `name = "hier-config"`
- `version = "4.0.0b3"`
- `description = "A network configuration query and comparison library, used to build remediation configurations."`
- `readme = "README.md"`
- `license = "MIT"`
- `authors = [...]`
- `requires-python = ">=3.10.0,<4.0"`
- `classifiers = [...]`
- `dependencies = ["pydantic>=2.9,<3.0"]`

### Build System & Backend Configuration

Configure `uv_build` as the PEP 517 build backend:
```toml
[build-system]
requires = ["uv_build>=0.11.11,<0.12.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-root = "."
```
`module-root = "."` instructs `uv_build` to package the top-level `hier_config` package (flat layout), automatically excluding `tests`, `docs`, and `scripts`.

### Dependency Groups (PEP 735)

Replace `[tool.poetry.group.dev.dependencies]` with PEP 735 `[dependency-groups]`:
```toml
[dependency-groups]
dev = [
    "flynt",
    "mkdocs",
    "mkdocs-include-markdown-plugin",
    "mkdocs-redirects",
    "mkdocstrings[python]",
    "mypy",
    "pylint",
    "pylint-pydantic",
    "pyright",
    "pytest",
    "pytest-cov",
    "pytest-profiling",
    "pytest-runner",
    "pytest-xdist",
    "ruff",
    "typer",
    "types-pyyaml",
    "yamllint",
]
```

### Lockfile Migration

- Delete `poetry.lock`.
- Generate cross-platform, universal `uv.lock` supporting Python 3.10–3.14 via `uv lock`.

## CI & Automation Workflows

### 1. `.github/workflows/build-and-test.yml`
- Replace `snok/install-poetry@v1` with `astral-sh/setup-uv@v5` (with `enable-cache: true`).
- Sync dependencies with `uv sync --frozen --no-install-project`.
- Execute test/lint commands:
  - `uv run python scripts/build.py lint`
  - `uv run python scripts/build.py pytest --coverage`

### 2. `.github/workflows/claude-review.yml`
- Replace `snok/install-poetry@v1` with `astral-sh/setup-uv@v5` (`enable-cache: true`).
- Install dependencies with `uv sync --frozen --no-install-project`.

### 3. `.github/workflows/prepare-release.yml`
- Replace `snok/install-poetry@v1` with `astral-sh/setup-uv@v5`.
- Expand workflow dispatch bump options to: `major`, `minor`, `patch`, `alpha`, `beta`, `rc`.
- Use `uv version --bump "${{ inputs.bump }}"` to bump project version.
- Use `uv version --short` to capture output version for `$GITHUB_OUTPUT`.
- Update changelog rotation condition: `if: "!contains(fromJSON('[\"alpha\", \"beta\", \"rc\"]'), inputs.bump)"`.

### 4. `.github/workflows/deploy-pypi.yml`
- Replace `snok/install-poetry@v1` with `astral-sh/setup-uv@v5`.
- Replace `poetry publish --build` with:
  ```yaml
  env:
    UV_PUBLISH_TOKEN: ${{ secrets.TWINE_API_KEY }}
  run: |
    uv build
    uv publish
  ```

### 5. `.github/renovate.json`
- Update `matchManagers` to replace `"poetry"` with `"pep621"` for dependency management and Python constraint rules.

## Developer Tooling & Scripts

- `scripts/build.py`: Retains subprocess execution; all developer and CI calls use `uv run ./scripts/build.py <command>`.
- `scripts/generate_v3_baseline.py`: Update header documentation and CLI instructions to `uv run ./scripts/generate_v3_baseline.py`.
- Tests (`test_v3_differential.py`, `test_benchmarks.py`): Update docstrings to reference `uv run pytest ...`.

## Documentation, Skills, and Guidelines Updates

Replace all references to Poetry with `uv`:
- Repository instructions: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `CONTRIBUTING.md`.
- Documentation site: `docs/dev/contributing.md`, `docs/dev/testing.md`, `docs/dev/code-style.md`, `docs/admin/releases.md`, `docs/admin/infrastructure.md`, `docs/user/install.md`.
- PR template: `.github/PULL_REQUEST_TEMPLATE.md`.
- Repo skills: `.claude/skills/hier-config-review/SKILL.md`, `.claude/skills/hier-config-new-driver/SKILL.md`, `.claude/skills/hier-config-troubleshoot/SKILL.md`.
- Changelog: Add entry to `CHANGELOG.md` under `## [Unreleased]` -> `### Changed`.

## Verification & Quality Gates

Run full test and lint suites using `uv`:
1. `uv lock --check`
2. `uv build` (validate sdist and wheel generation and contents)
3. `uv run ./scripts/build.py lint` (ruff format check, ruff check, mypy, pyright, pylint, yamllint, flynt)
4. `uv run ./scripts/build.py pytest --coverage` (95%+ coverage requirement)
5. `uv run mkdocs build --strict`
