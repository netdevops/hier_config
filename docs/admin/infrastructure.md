# CI & Infrastructure

This page is for project maintainers and describes the repository's automation.

## Continuous Integration

`.github/workflows/build-and-test.yml` runs on every push and pull request to `master`:

- **build** job: a Python 3.10–3.14 matrix that installs dependencies with uv, then runs `scripts/build.py lint` (ruff, mypy, pyright, pylint, yamllint, flynt in parallel) and `scripts/build.py pytest --coverage` (95% coverage floor).
- **docs** job: installs `docs/requirements.txt` with pip (mirroring what Read the Docs installs) and runs `mkdocs build --strict`, so broken links or nav entries fail the PR instead of shipping silently.

`.github/workflows/prepare-release.yml` is an admin-only, manually-run workflow that bumps the version, rotates the changelog, opens the release PR, and creates a draft GitHub release; `.github/workflows/deploy-pypi.yml` publishes to PyPI when that release is published — see [Releases](releases.md).

`.github/workflows/notify-ecosystem.yml` also runs when a release is published: it sends a `repository_dispatch` (event `hier-config-release`, payload `version` + `prerelease`) to [netdevops/hier-config-ci](https://github.com/netdevops/hier-config-ci), whose orchestrator releases the downstream apps (hier-config-gpt, -api, -mcp, -cli) against the new version. It requires the `ECOSYSTEM_DISPATCH_TOKEN` secret — a PAT from an org admin that can dispatch to hier-config-ci.

## Dependency Automation

Dependency updates are managed by **Renovate** (`.github/renovate.json`), not Dependabot: weekly schedule, grouped non-major updates, semantic commit messages, and `security`-labelled vulnerability PRs that can open at any time.

## Documentation

Docs are built with MkDocs and published by **Read the Docs** (`.readthedocs.yml`) at [hier-config.readthedocs.io](https://hier-config.readthedocs.io/). RTD installs `docs/requirements.txt` and builds `mkdocs.yml`.

Preview locally:

```bash
uv sync
uv run mkdocs serve
```

Validate the way CI does:

```bash
uv run mkdocs build --strict
```

### Moving or Renaming Doc Pages

Never move a docs page without adding a `redirect_maps` entry to the `redirects` plugin in `mkdocs.yml` — published readthedocs.io URLs must keep working. Note that redirects cover pages, not `#fragment` anchors.

## Code Owners

Reviews are routed via `.github/CODEOWNERS`.
