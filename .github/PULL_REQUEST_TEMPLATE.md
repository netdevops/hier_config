# Summary

<!-- What does this PR change, and why? Link the related issue, e.g. "Closes #123". -->

## Self-Review Checklist

<!-- The full standards live in AGENTS.md and https://hier-config.readthedocs.io/en/latest/dev/contributing/ -->

- [ ] `poetry run ./scripts/build.py lint-and-test` passes locally (lint + 95% test coverage).
- [ ] Tests were written first (TDD) and cover the change, following the [testing conventions](https://hier-config.readthedocs.io/en/latest/dev/testing/).
- [ ] `CHANGELOG.md` has an entry under `## [Unreleased]` referencing this issue/PR (`(#NNN)`).
- [ ] Documentation is updated if public API or driver behavior changed (and `mkdocs build --strict` passes if docs were touched).
- [ ] Commit messages follow the [contributing guide](https://github.com/netdevops/hier_config/blob/master/CONTRIBUTING.md): imperative mood, subject ≤72 characters, body explains *why*.

## AI-Assisted Contributions

If this PR was written with an AI coding tool, review it against the repo standards before requesting review: Claude Code users can run the `hier-config-review` skill; other tools should be pointed at `AGENTS.md` and the [developer docs](https://hier-config.readthedocs.io/en/latest/dev/contributing/).
