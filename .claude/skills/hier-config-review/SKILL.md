---
name: hier-config-review
description: Use when asked to review changes, self-review work, or prepare a pull request in the hier_config repository — especially before opening or updating a PR, or when checking AI-generated code against this repo's standards.
---

# hier_config Change Review

Review the current change set against this repository's standards and report findings. **Do not fix anything unless explicitly asked** — the deliverable is the review report.

## Step 1: Establish the Diff

```bash
git diff master...HEAD --stat   # on a branch
git diff HEAD --stat            # fall back: uncommitted work
git diff --staged --stat        # fall back: staged only
```

List every changed file and classify it: library code (`hier_config/`), tests (`tests/`), docs (`docs/`, `mkdocs.yml`), CI/config, or `CHANGELOG.md`. Read the full diff for each classified file before judging it.

## Step 2: Run the Gates

Run these and report exact failures (tool, file, line, message):

```bash
poetry run ./scripts/build.py lint
poetry run ./scripts/build.py pytest --coverage
```

If docs/ or mkdocs.yml changed, also run:

```bash
poetry run mkdocs build --strict
```

## Step 3: Review by Category

Read the referenced doc before judging that category — the docs are the standard, not your intuition.

### Models & Typing — read `docs/dev/code-style.md`

- New Pydantic models subclass the local `BaseModel` (`hier_config/models.py`), never `pydantic.BaseModel` directly.
- Model fields use `tuple`/`frozenset`, never `list`/`set`. Rule models use `match_rules: tuple[MatchRule, ...]`.
- No `Any`, no missing annotations, no unjustified `# type: ignore` / `# noqa`.
- Lint/coverage/type-checking configuration was not loosened.

### Tests & TDD — read `docs/dev/testing.md`

- Every library code change has corresponding tests.
- Tests are flat functions with full annotations; no test classes (benchmarks excepted).
- Driver changes are tested in `tests/test_driver_<platform>.py`; view changes in `tests/config_view/`.
- Driver/rule behavior changes include the round-trip idiom: remediation asserted via `dump_simple()` tuple, rollback verified via no `unified_diff`.
- New fixtures live in `tests/fixtures/` with module-scoped accessors in `tests/conftest.py`.

### Driver & Rule Changes — read `docs/dev/extending.md`

- New rule types: frozen model in `models.py` → named default factory + field on `HConfigDriverRules` → consumed in `child.py`/`root.py` → populated in drivers.
- New platforms: `Platform` enum member, `get_hconfig_driver` wiring, per-platform test file, and a driver section + table row in `docs/user/drivers.md`.

### Changelog

- `CHANGELOG.md` has an entry under `## [Unreleased]`, in the right category (`Added`/`Changed`/`Fixed`/`Removed`), referencing the issue/PR (`(#NNN)`).

### Docs

- Public API or driver behavior changes are reflected in `docs/user/` (and `docs/user/api-reference.md` where relevant).
- New doc pages are in the `mkdocs.yml` nav; moved pages have a `redirect_maps` entry.

### Commits — read `CONTRIBUTING.md` (Commit Message Style)

- Imperative mood, subject ≤72 characters, body explains *why*.

## Step 4: Report

Group findings by severity, most severe first:

- **Blockers** — violates a hard rule or a gate fails (CI would reject this).
- **Should fix** — deviates from documented conventions; a reviewer would push back.
- **Nits** — minor style or wording.

Each finding: `file:line`, what is wrong, and which standard it violates (with the doc path). End with a pass/fail verdict against the "Before Opening a PR" checklist in `AGENTS.md`.
