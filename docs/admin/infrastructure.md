# CI & Infrastructure

This page is for project maintainers and describes the repository's automation.

## Continuous Integration

`.github/workflows/build-and-test.yml` runs on every push and pull request to `master` and `next`:

- **rust-msrv**: builds the workspace on the toolchain selected for the
  `Cargo.toml` MSRV promise. **rust-lint** checks formatting, strict Clippy and
  Rust documentation with a pinned lint toolchain.
- **rust-tests**: runs locked Cargo tests using `LINT_TOOLCHAIN` on Linux
  x86_64/native ARM64 (`ubuntu-24.04-arm`), macOS and Windows.
  **rust-coverage** measures core line coverage with a separate 90% floor.
  **cargo-deny** checks advisories, licenses and dependency sources.
- **python-lint**: builds the release extension, then invokes the canonical
  `scripts/build.py lint` (Python linters/type checkers plus stub freshness,
  signature/return-type, corpus and displacement checks).
- **python-tests**: CPython 3.11–3.14 tests against the compiled extension,
  with Python coverage enforced at 95% on the default interpreter. Python
  coverage is not a measurement of native code.
- **packaging**: builds wheels and an sdist, rebuilds the sdist with its
  lockfile, and imports public modules from the exact wheel in a clean
  environment on Linux x86_64 and ARM64. Optional `[yaml]` loading is tested
  separately from the pydantic-only core dependency contract.
- **performance-gate**: runs the release-build regression benchmark. Its
  same-run Python calibration ratios reduce some machine noise, but are not
  architecture-independent proof: runner results must be checked, and no
  Linux/ARM calibration success is implied by local Apple Silicon measurements.
- **docs** job: installs `docs/requirements.txt` with pip (mirroring what Read the Docs installs) and runs `mkdocs build --strict`, so broken links or nav entries fail the PR instead of shipping silently.

These describe configured jobs, not proof that every target has passed.
macOS-local validation cannot verify Linux glibc/musl or Windows ARM64 wheel
execution; inspect the actual CI and release-job results before publishing.

`.github/workflows/prepare-release.yml` is an admin-only, manually-run workflow that bumps the version, rotates the changelog, opens the release PR, and creates a draft GitHub release; `.github/workflows/deploy-pypi.yml` publishes to PyPI when that release is published — see [Releases](releases.md).

The native build backend is maturin, not Poetry. Release preparation uses
`scripts/bump_version.py` to update `Cargo.toml` and workspace `Cargo.lock`
entries, refreshes `uv.lock`, and stages those files in the release PR.
Publishing merges per-platform wheel/sdist artifacts, smoke-tests an exact
local wheel, then uploads with maturin using `TWINE_API_KEY` as
`MATURIN_PYPI_TOKEN`. `uv build`/`uv publish` are not the release workflow.

`.github/workflows/notify-ecosystem.yml` also runs when a release is published: it sends a `repository_dispatch` (event `hier-config-release`, payload `version` + `prerelease`) to [netdevops/hier-config-ci](https://github.com/netdevops/hier-config-ci), whose orchestrator releases the downstream apps (hier-config-gpt, -api, -mcp, -cli) against the new version. It requires the `ECOSYSTEM_DISPATCH_TOKEN` secret — a PAT from an org admin that can dispatch to hier-config-ci.

## Dependency Automation

Dependency updates are managed by **Renovate** (`.github/renovate.json`), not Dependabot: weekly schedule, grouped non-major updates, semantic commit messages, and `security`-labelled vulnerability PRs that can open at any time.

## Documentation

Docs are built with MkDocs and published by **Read the Docs** (`.readthedocs.yml`) at [hier-config.readthedocs.io](https://hier-config.readthedocs.io/). RTD installs `docs/requirements.txt` and builds `mkdocs.yml`.

Preview locally:

```bash
uv sync --locked --extra yaml
uv run --no-sync maturin develop --release --locked
uv run --no-sync mkdocs serve
```

Checkout builds require Python 3.11+, a linker and the Rust MSRV declared in
`Cargo.toml` (currently 1.98). Rebuild the extension after native code changes.
The docs-only CI/RTD path uses committed source/stubs and
`docs/requirements.txt`, rather than installing a development checkout.

Validate the way CI does:

```bash
uv run --no-sync mkdocs build --strict
```

### Moving or Renaming Doc Pages

Never move a docs page without adding a `redirect_maps` entry to the `redirects` plugin in `mkdocs.yml` — published readthedocs.io URLs must keep working. Note that redirects cover pages, not `#fragment` anchors.

## Code Owners

Reviews are routed via `.github/CODEOWNERS`.
