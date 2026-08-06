# Release Process

This page is for project maintainers. Releases are prepared by an admin-run
workflow and published to PyPI automatically when the GitHub release is
published.

## Steps

1. **Run the prepare-release workflow**: Actions → *prepare release* → *Run
   workflow*. Pick the branch to release from (`master` for stable releases,
   `next` for v4 prereleases) and the bump type — `major`, `minor`, `patch`,
   or `prerelease`. The workflow is restricted to repository admins. It:
    - Bumps `version` in `pyproject.toml` with `poetry version <bump>`.
    - For non-prerelease bumps, moves the `## [Unreleased]` entries in
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
   published and runs `poetry publish --build` using the `TWINE_API_KEY`
   repository secret.

## Post-Release Checks

- Verify the new version appears on [PyPI](https://pypi.org/project/hier-config/).
- Verify the [Read the Docs build](https://readthedocs.org/projects/hier-config/) succeeded for the new tag.
