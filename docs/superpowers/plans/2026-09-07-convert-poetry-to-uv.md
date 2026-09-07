# Convert Poetry to uv Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `hier_config` repository packaging, dependency management, build backend, and CI/CD workflows from Poetry to `uv`.

**Architecture:** Replace Poetry with standard PEP 621 metadata and `uv_build` as PEP 517 backend in `pyproject.toml`. Define dev dependencies using PEP 735 dependency groups. Generate a universal `uv.lock`. Update all GitHub Actions workflows to use `astral-sh/setup-uv` and `uv` commands. Update developer scripts, documentation, and agent guidelines.

**Tech Stack:** `uv`, `uv_build`, PEP 621, PEP 735, GitHub Actions (`setup-uv`), Python 3.10–3.14.

**Spec:** `docs/superpowers/specs/2026-09-07-convert-poetry-to-uv-design.md`

## Global Constraints

- Python compatibility: 3.10–3.14 must remain fully supported across all matrix builds.
- Runtime dependencies: `pydantic` only (`>=2.9,<3.0`).
- Strict typing and linting: Mypy and pyright in strict mode, ruff `ALL` with line length 88.
- Test coverage floor: 95% minimum coverage maintained.
- All commands in dev workflow and CI use `uv` (no Poetry).

---

### Task 1: Migrate `pyproject.toml` to PEP 621, `uv_build` Backend, and Generate `uv.lock`

**Files:**
- Modify: `pyproject.toml`
- Delete: `poetry.lock`
- Create: `uv.lock`

**Interfaces:**
- Consumes: Existing dependency declarations from `pyproject.toml`.
- Produces: Standard PEP 621 `[project]`, `[build-system]` using `uv_build`, `[dependency-groups]` dev group, and valid `uv.lock`.

- [ ] **Step 1: Update `pyproject.toml` with PEP 621 metadata, `uv_build` backend, and PEP 735 dev group**

Replace `[tool.poetry]`, `[tool.poetry.dependencies]`, `[tool.poetry.group.dev.dependencies]`, and `[build-system]` in `pyproject.toml` with:

```toml
[project]
name = "hier-config"
version = "4.0.0b3"
description = "A network configuration query and comparison library, used to build remediation configurations."
readme = "README.md"
license = "MIT"
authors = [
    { name = "Andrew Edwards", email = "edwards.andrew@heb.com" },
    { name = "James Williams", email = "james.williams@networktocode.com" },
    { name = "Jan Brooks", email = "jan.brooks@rackspace.com" },
]
requires-python = ">=3.10.0,<4.0"
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Intended Audience :: Information Technology",
    "Intended Audience :: System Administrators",
    "Intended Audience :: Telecommunications Industry",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Natural Language :: English",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: System :: Networking",
]
dependencies = [
    "pydantic>=2.9,<3.0",
]

[build-system]
requires = ["uv_build>=0.11.11,<0.12.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-root = "."

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

- [ ] **Step 2: Remove `poetry.lock` and generate `uv.lock`**

Run:
```bash
rm -f poetry.lock
uv lock
```

- [ ] **Step 3: Verify lockfile and build outputs**

Run:
```bash
uv lock --check
uv build
```
Verify `dist/` contains valid sdist (`.tar.gz`) and wheel (`.whl`).
Clean up `dist/`:
```bash
rm -rf dist
```

- [ ] **Step 4: Commit changes**

```bash
git add pyproject.toml uv.lock poetry.lock
git commit -m "build: migrate packaging and dependencies from poetry to uv

Replace tool.poetry with standard PEP 621 metadata, PEP 735 dev
dependency group, and uv_build build backend. Replace poetry.lock
with uv.lock.

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Update GitHub Actions Workflows & Renovate Config

**Files:**
- Modify: `.github/workflows/build-and-test.yml`
- Modify: `.github/workflows/claude-review.yml`
- Modify: `.github/workflows/prepare-release.yml`
- Modify: `.github/workflows/deploy-pypi.yml`
- Modify: `.github/renovate.json`

**Interfaces:**
- Consumes: `uv.lock`, `pyproject.toml`.
- Produces: GitHub Actions workflows using `astral-sh/setup-uv@v5`, `uv sync`, `uv run`, `uv version`, `uv publish`, and Renovate configuration for `pep621`.

- [ ] **Step 1: Update `.github/workflows/build-and-test.yml`**

Replace `snok/install-poetry@v1` and `poetry install` with `astral-sh/setup-uv@v5` and `uv sync`:
```yaml
    - name: Install uv
      uses: astral-sh/setup-uv@v5
      with:
        enable-cache: true
    - name: Run tests
      run: |
        uv sync --frozen --no-install-project
        uv run python scripts/build.py lint
        uv run python scripts/build.py pytest --coverage
```

- [ ] **Step 2: Update `.github/workflows/claude-review.yml`**

Replace `snok/install-poetry@v1` and `poetry install` with `astral-sh/setup-uv@v5` and `uv sync`:
```yaml
    - name: Install uv
      uses: astral-sh/setup-uv@v5
      with:
        enable-cache: true

    - name: Install the project dependencies
      run: uv sync --frozen --no-install-project
```

- [ ] **Step 3: Update `.github/workflows/prepare-release.yml`**

Replace `snok/install-poetry@v1` with `astral-sh/setup-uv@v5`. Update bump input options and version step:
```yaml
      bump:
        description: Version bump type
        required: true
        type: choice
        options:
        - major
        - minor
        - patch
        - alpha
        - beta
        - rc
```
And:
```yaml
    - name: Install uv
      uses: astral-sh/setup-uv@v5
    - name: Bump version
      id: bump
      run: |
        uv version --bump "${{ inputs.bump }}"
        echo "version=$(uv version --short)" >> "$GITHUB_OUTPUT"
    - name: Rotate changelog
      if: "!contains(fromJSON('[\"alpha\", \"beta\", \"rc\"]'), inputs.bump)"
      run: |
        python scripts/rotate_changelog.py "${{ steps.bump.outputs.version }}" > release-notes.md
```

- [ ] **Step 4: Update `.github/workflows/deploy-pypi.yml`**

Replace `snok/install-poetry@v1` and `poetry publish` with `astral-sh/setup-uv@v5` and `uv publish`:
```yaml
    - name: Install uv
      uses: astral-sh/setup-uv@v5
    - name: Build and publish to PyPI
      env:
        UV_PUBLISH_TOKEN: ${{ secrets.TWINE_API_KEY }}
      run: |
        uv build
        uv publish
```

- [ ] **Step 5: Update `.github/renovate.json`**

Update `matchManagers` to `"pep621"` instead of `"poetry"`.

- [ ] **Step 6: Validate YAML syntax across workflows**

Run:
```bash
uv run python scripts/build.py yamllint
```

- [ ] **Step 7: Commit changes**

```bash
git add .github/workflows/ .github/renovate.json
git commit -m "ci: update github workflows and renovate config for uv

Replace poetry actions with astral-sh/setup-uv@v5 in test, review,
release, and deploy workflows. Update renovate package manager matchers.

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Update Developer Scripts and Test Docstrings

**Files:**
- Modify: `scripts/generate_v3_baseline.py`
- Modify: `tests/integration/test_v3_differential.py`
- Modify: `tests/benchmarks/test_benchmarks.py`

**Interfaces:**
- Consumes: None.
- Produces: Clear, accurate documentation and docstrings referring to `uv run`.

- [ ] **Step 1: Update `scripts/generate_v3_baseline.py`**

Update the usage example in the docstring:
Change `poetry run ./scripts/generate_v3_baseline.py` to `uv run ./scripts/generate_v3_baseline.py`.

- [ ] **Step 2: Update `tests/integration/test_v3_differential.py`**

Update docstring:
Change `poetry run pytest -m v3_differential -v` to `uv run pytest -m v3_differential -v`.

- [ ] **Step 3: Update `tests/benchmarks/test_benchmarks.py`**

Update docstring:
Change `poetry run pytest -m benchmark -v` to `uv run pytest -m benchmark -v`.

- [ ] **Step 4: Commit changes**

```bash
git add scripts/generate_v3_baseline.py tests/
git commit -m "chore: update script and test references to uv

Replace poetry commands in docstrings and usage instructions with uv.

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Update Documentation, Agent Instructions & Skills

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `.github/copilot-instructions.md`
- Modify: `CONTRIBUTING.md`
- Modify: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `docs/dev/contributing.md`
- Modify: `docs/dev/testing.md`
- Modify: `docs/dev/code-style.md`
- Modify: `docs/admin/releases.md`
- Modify: `docs/admin/infrastructure.md`
- Modify: `docs/user/install.md`
- Modify: `.claude/skills/hier-config-review/SKILL.md`
- Modify: `.claude/skills/hier-config-new-driver/SKILL.md`
- Modify: `.claude/skills/hier-config-troubleshoot/SKILL.md`

**Interfaces:**
- Consumes: uv workflow conventions.
- Produces: Consistent contributor documentation, agent prompts, and skills reflecting uv.

- [ ] **Step 1: Update `AGENTS.md` and `CLAUDE.md`**

Replace all `poetry run ...` commands with `uv run ...`. Update package management references from Poetry to `uv`.

- [ ] **Step 2: Update `.github/copilot-instructions.md` and `CONTRIBUTING.md`**

Replace `poetry` commands with `uv run` commands.

- [ ] **Step 3: Update docs under `docs/`**

Replace poetry commands in `docs/dev/contributing.md`, `docs/dev/testing.md`, `docs/dev/code-style.md`, `docs/admin/releases.md`, `docs/admin/infrastructure.md`, and `docs/user/install.md`.

- [ ] **Step 4: Update `.claude/skills/` and `.github/PULL_REQUEST_TEMPLATE.md`**

Replace `poetry run ...` in skills and PR template checklist with `uv run ...`.

- [ ] **Step 5: Verify docs build cleanly**

Run:
```bash
uv run mkdocs build --strict
```

- [ ] **Step 6: Commit changes**

```bash
git add AGENTS.md CLAUDE.md .github/ CONTRIBUTING.md docs/ .claude/
git commit -m "docs: update contributor docs, agent instructions, and skills for uv

Replace all Poetry command references with uv run and uv sync across
guides, documentation, PR templates, and assistant skills.

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Add Changelog Entry & Full Quality Gate Verification

**Files:**
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: All previous tasks.
- Produces: Updated CHANGELOG.md, 100% passing linters, tests, and coverage.

- [ ] **Step 1: Add entry to `CHANGELOG.md`**

Under `## [Unreleased]`, add under `### Changed`:
```markdown
- Migrated project packaging and dependency management from Poetry to `uv` with `uv_build` backend.
```

- [ ] **Step 2: Run full lint suite**

Run:
```bash
uv run ./scripts/build.py lint
```
Expected: All linters (ruff format, ruff check, mypy, pyright, pylint, yamllint, flynt) pass with 0 errors.

- [ ] **Step 3: Run full test suite with coverage**

Run:
```bash
uv run ./scripts/build.py pytest --coverage
```
Expected: All tests pass with >= 95% coverage floor.

- [ ] **Step 4: Verify strict docs build**

Run:
```bash
uv run mkdocs build --strict
```
Expected: Documentation builds without warnings or errors.

- [ ] **Step 5: Commit changes**

```bash
git add CHANGELOG.md
git commit -m "chore: record poetry to uv migration in changelog

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```
