# Shared Development Standards

The hier-config projects in the [netdevops](https://github.com/netdevops)
organization — the `hier_config` library and the applications built on it
(`hier-config-api`, `hier-config-cli`, `hier-config-mcp`, `hier-config-gpt`) —
share one development model: the same lint, typing, and test tooling, the same
YAML style, and the same containerized development environment.

This repository is the **canonical source** for those shared files. Downstream
projects pull them in rather than maintaining their own copies, so a change
made here propagates to every project.

## Docker Development Environment

Every hier-config project ships a Docker development environment driven by
[invoke](https://www.pyinvoke.org/) tasks in `tasks.py`, so the same commands
work in every repository:

```bash
invoke build             # build the development image
invoke docs              # docs with live reload at http://localhost:8001
invoke pytest            # tests (--coverage for the coverage gate)
invoke lint              # linters (--fix to apply auto-fixes)
invoke lint-and-test     # full suite, same as CI
invoke cli               # shell inside the container
invoke sync-standards    # check drift against the canonical standards
invoke destroy           # tear down containers
```

Projects that serve an application add a `serve` task for it; everything else
is expected to behave identically across repositories.

## Synced Files

The files below are owned by this repository and listed in each project's
`.standards.yml` manifest:

| File | Purpose |
|------|---------|
| `scripts/build.py` | Lint, type-check, and test driver used by every project and by CI |
| `scripts/sync_standards.py` | The sync tool itself |
| `.yamllint.yml` | YAML style rules |
| `.dockerignore` | Build-context exclusions for the development image |

`Dockerfile`, `docker-compose.yml`, and `tasks.py` are deliberately **not**
synced: each project's image and services differ (an application serves a
process, a library does not). They follow the conventions above, with this
repository's copies as the reference implementation.

## The Manifest

Each project declares where its standards come from in `.standards.yml`:

```yaml
source:
  repo: netdevops/hier_config
  ref: master

# Whole-word replacements so package references match the consuming project
substitutions:
  hier_config: hier_config_api

files:
  - scripts/build.py
  - scripts/sync_standards.py
  - .yamllint.yml
  - .dockerignore
```

Substitutions rewrite package names as files are fetched, which is what lets a
single `scripts/build.py` serve projects with different package names. Because
a substitution can push a line past the 88-character limit, Python files are
re-run through `ruff format` after substitution — without that step a synced
file would never converge, since `apply` would write content that the formatter
immediately rewrites.

## Syncing

```bash
# Report drift; exits non-zero when local files differ from canonical
invoke sync-standards

# Pull the canonical versions into the local files
invoke sync-standards --apply
```

Downstream projects also run a scheduled GitHub Actions workflow that applies
the sync weekly and opens a pull request when anything changed, so CI validates
the update before it merges.

Run in this repository, `sync-standards` compares the working tree against what
is published on the source ref. That previews what downstream projects will
receive on their next sync, and reports drift while a change to a shared file
is still unreleased on `master`.

## Changing a Shared File

1. Change the file here and open a pull request, as with any other change.
2. Once it merges to `master`, downstream projects pick it up on their next
   scheduled sync, or immediately via `invoke sync-standards --apply`.

Never edit a synced file directly in a downstream project: the next sync will
overwrite it. Keep tool version constraints compatible across projects too — a
downstream project pinned to an older linter may not accept canonical files
that rely on newer behavior.
