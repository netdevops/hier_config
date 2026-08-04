# Release Process

This page is for project maintainers. Releases are published to PyPI automatically when a GitHub release is created.

## Steps

1. **Prepare the release PR** (conventionally titled `chore(release): prepare X.Y.Z`):
    - Bump `version` in `pyproject.toml` following [Semantic Versioning](https://semver.org/spec/v2.0.0.html) — major for breaking changes, minor for features, patch for fixes.
    - In `CHANGELOG.md`, move the `## [Unreleased]` entries under a new `## [X.Y.Z] - YYYY-MM-DD` heading and start a fresh empty `## [Unreleased]` section.
2. **Merge to `master`** and confirm the [build-and-test workflow](infrastructure.md) passes.
3. **Create a GitHub release** targeting `master` with tag `vX.Y.Z`, pasting the changelog section as the release notes.
4. **Publishing happens automatically**: the `deploy to pypi` workflow (`.github/workflows/deploy-pypi.yml`) triggers on release creation and runs `poetry publish --build` using the `TWINE_API_KEY` repository secret.

## Post-Release Checks

- Verify the new version appears on [PyPI](https://pypi.org/project/hier-config/).
- Verify the [Read the Docs build](https://readthedocs.org/projects/hier-config/) succeeded for the new tag.
