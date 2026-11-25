# Release Process

This page is for project maintainers. Releases are prepared by an admin-run
workflow and published to PyPI automatically when the GitHub release is
published.

## Steps

1. **Run the prepare-release workflow**: Actions → *prepare release* → *Run
   workflow*. Pick the branch to release from (`master` for stable releases,
   `next` for v4 prereleases) and the bump type — `major`, `minor`, `patch`,
   `alpha`, `beta`, or `rc`. The workflow is restricted to repository admins. It:
    - Runs `python scripts/bump_version.py <bump>`. The source of truth is
      `[workspace.package].version` in `Cargo.toml`, not `pyproject.toml`:
      maturin reads the dynamic Python version from Cargo.
    - Updates local workspace versions in `Cargo.lock` and refreshes `uv.lock`
      with `uv lock`. The release commit stages `Cargo.toml`, `Cargo.lock`,
      `pyproject.toml`, `uv.lock`, and `CHANGELOG.md`; review that both lockfiles
      and the Cargo manifest actually accompany the bump.
    - Stores Cargo prereleases as SemVer (`4.0.0-beta.4`) and uses the normalized
      PEP 440 value (`4.0.0b4`) for the Python distribution, tag and changelog.
      Preview the exact next version with
      `python scripts/bump_version.py beta --dry-run`. Do not use `uv version`
      or `poetry version`: neither owns this project's version.
    - For non-prerelease bumps (i.e. `major`, `minor`, or `patch`), moves the `## [Unreleased]` entries in
      `CHANGELOG.md` under a new `## [X.Y.Z] - YYYY-MM-DD` heading
      (`scripts/rotate_changelog.py`) and starts a fresh empty
      `## [Unreleased]` section.
    - Opens a PR (`chore(release): prepare X.Y.Z`) against the chosen branch.
    - Creates a **draft** GitHub release `vX.Y.Z` targeting the chosen
      branch, with the rotated changelog section as the notes (generated
      notes for prereleases), marked as a prerelease when the version is one.
2. **Merge the release PR** and confirm the
   [build-and-test workflow](infrastructure.md) passes. Note: CI does not
   start automatically on the bot-created PR — close and reopen it (or push
   to the branch) to trigger checks.
3. **Publish the draft release**. The tag is created at the tip of the target
   branch when the draft is published, so always merge the PR first.
4. **Publishing happens automatically**: `deploy to pypi`
   (`.github/workflows/deploy-pypi.yml`) builds release wheels with
   `PyO3/maturin-action` for Linux, macOS and Windows, plus a source distribution.
   The release job downloads all wheel/sdist artifacts into `dist/`, installs
   the exact locally built Linux wheel and smoke-tests its metadata/imports,
   then runs maturin `upload --non-interactive --skip-existing dist/*`.
   The existing `TWINE_API_KEY` secret is mapped to `MATURIN_PYPI_TOKEN`.

## Native build checks before publishing

The rewrite is the **v4 release of this repository**, not v5 or a separate
distribution. Verify the prepared version matches the intended release line.
The workflow's wheel jobs cover Linux glibc and musl (x86_64/aarch64),
macOS (x86_64/aarch64), and Windows (x64/ARM64), using CPython `abi3`.
The musl target is `musllinux_1_2`. Windows ARM64 builds on `windows-11-arm`
with Python 3.11; the other wheels use a Python 3.11 baseline. Confirm these
jobs on their actual runners; local macOS checks do not verify those artifacts.

Source builds require Python 3.11+, a linker and Rust meeting
`workspace.package.rust-version` in `Cargo.toml` (currently 1.98).
CI must build the sdist with its included lockfile, not just build a wheel
from the checkout. A release smoke test must install the exact artifact path:
`pip install --find-links dist hier-config` could select an older index release
and is not evidence that the newly built wheel works.

PyYAML is optional via `[yaml]`; clean-wheel checks cover core imports without
it and YAML loading after the extra is installed. Check the workflow result,
not just the existence of files under `dist/`.

## Ecosystem Fan-Out

Publishing a hier_config release also triggers
`.github/workflows/notify-ecosystem.yml`, which dispatches to
[netdevops/hier-config-ci](https://github.com/netdevops/hier-config-ci). Its
orchestrator then releases the downstream apps (hier-config-gpt, -api, -mcp,
-cli): prerelease hier_config versions produce app prereleases from each
app's `next` branch; stable versions produce patch releases from each app's
default branch. See the hier-config-ci README for the required secrets and
manual-run instructions.

## Post-Release Checks

- Verify the new version appears on [PyPI](https://pypi.org/project/hier-config/).
- Verify the [Read the Docs build](https://readthedocs.org/projects/hier-config/) succeeded for the new tag.
