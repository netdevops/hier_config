# CI & Infrastructure

This page is for project maintainers and describes the repository's automation.

## Continuous Integration

`.github/workflows/build-and-test.yml` runs on every push and pull request to `master`:

- **build** job: a Python 3.10–3.14 matrix that installs dependencies with poetry, then runs `scripts/build.py lint` (ruff, mypy, pyright, pylint, yamllint, flynt in parallel) and `scripts/build.py pytest --coverage` (95% coverage floor).
- **docs** job: installs `docs/requirements.txt` with pip (mirroring what Read the Docs installs) and runs `mkdocs build --strict`, so broken links or nav entries fail the PR instead of shipping silently.

`.github/workflows/deploy-pypi.yml` publishes to PyPI when a GitHub release is created — see [Releases](releases.md).

## Dependency Automation

Dependency updates are managed by **Renovate** (`.github/renovate.json`), not Dependabot: weekly schedule, grouped non-major updates, semantic commit messages, and `security`-labelled vulnerability PRs that can open at any time.

## Documentation

Docs are built with MkDocs and published by **Read the Docs** (`.readthedocs.yml`) at [hier-config.readthedocs.io](https://hier-config.readthedocs.io/). RTD installs `docs/requirements.txt` and builds `mkdocs.yml`.

Preview locally:

```bash
poetry install
poetry run mkdocs serve
```

Validate the way CI does:

```bash
poetry run mkdocs build --strict
```

### Moving or Renaming Doc Pages

Never move a docs page without adding a `redirect_maps` entry to the `redirects` plugin in `mkdocs.yml` — published readthedocs.io URLs must keep working. Note that redirects cover pages, not `#fragment` anchors.

## Code Owners

Reviews are routed via `.github/CODEOWNERS`.
