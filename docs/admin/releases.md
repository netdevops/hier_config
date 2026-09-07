# Release Process

This page is for project maintainers. Releases are prepared by an admin-run
workflow and published to PyPI automatically when the GitHub release is
published.

## Steps

1. **Run the prepare-release workflow**: Actions → *prepare release* → *Run
   workflow*. Pick the branch to release from (`master` for stable releases,
   `next` for v4 prereleases) and the bump type — `major`, `minor`, `patch`,
   `alpha`, `beta`, or `rc`. The workflow is restricted to repository admins. It:
    - Bumps `version` in `pyproject.toml` and updates `uv.lock` with `uv version --bump <bump>`.
      `uv version` refuses a bump that would not increase the version, so from a
      prerelease you can only move forward along `alpha` → `beta` → `rc`: from
      `4.0.0b3`, `beta` gives `4.0.0b4` and `rc` gives `4.0.0rc1`, while `alpha`
      fails. From a *stable* version a bare `alpha`/`beta`/`rc` bump also fails —
      start a new prerelease line by running `uv version --bump minor --bump beta`
      locally and opening the release PR by hand.
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
4. **Publishing happens automatically**: the `deploy to pypi` workflow
   (`.github/workflows/deploy-pypi.yml`) triggers when the release is
   published and runs `uv build` and `uv publish` using the `TWINE_API_KEY`
   repository secret (mapped to `UV_PUBLISH_TOKEN`).

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
