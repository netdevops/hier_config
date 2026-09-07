---
name: hier-config-review
description: Use when asked to review changes, self-review work, or prepare a pull request in the hier_config repository — especially before opening or updating a PR, or when checking AI-generated code against this repo's standards.
---

# hier_config Change Review

Review the current change set against this repository's standards and report findings. **Do not fix anything unless explicitly asked** — the deliverable is the review report.

## Step 1: Establish the Diff

Pick the base branch first: v4 work branches from `next`; only v3.x maintenance work branches from `master`. Diffing a `next`-based branch against `master` would include all of v4 and make the review meaningless.

```bash
git diff "$(git merge-base origin/next HEAD)"...HEAD --stat   # v4 branch (the usual case)
git diff "$(git merge-base origin/master HEAD)"...HEAD --stat # v3.x maintenance branch
git diff HEAD --stat            # fall back: uncommitted work
git diff --staged --stat        # fall back: staged only
```

List every changed file and classify it: library code (`hier_config/`), tests (`tests/`), docs (`docs/`, `mkdocs.yml`), CI/config, or `CHANGELOG.md`. Read the full diff for each classified file before judging it.

## Step 2: Run the Gates

Run these and report exact failures (tool, file, line, message):

```bash
uv run ./scripts/build.py lint
uv run ./scripts/build.py pytest --coverage
```

Also run the docs build — CI runs it unconditionally on every push/PR, not just when docs change:

```bash
uv run mkdocs build --strict
```

Remember CI's test matrix covers Python 3.10–3.14: flag syntax or stdlib usage newer than 3.10 even if local checks pass.

## Step 3: Review by Category

Read the referenced doc before judging that category — the docs are the standard, not your intuition.

### Models & Typing — read `docs/dev/code-style.md`

- New Pydantic models subclass the local `BaseModel` (`hier_config/models.py`), never `pydantic.BaseModel` directly.
- Model fields use `tuple`/`frozenset`, never `list`/`set`. Rule models use `match_rules: tuple[MatchRule, ...]`. Exception: the rule-collection fields on `HConfigDriverRules` are intentionally `list[...]` (removal-by-identity, #286) — do not flag them.
- No `Any`, no missing annotations, no unjustified `# type: ignore` / `# noqa`.
- Lint/coverage/type-checking configuration was not loosened.

### Tests & TDD — read `docs/dev/testing.md`

- Every library code change has corresponding tests.
- Tests are flat functions with full annotations; no test classes (benchmarks excepted).
- Driver changes are tested in `tests/integration/test_<platform>.py` (unit-level driver tests in `tests/unit/platforms/`); view changes in `tests/unit/platforms/views/`.
- Driver/rule behavior changes include the round-trip idiom: remediation asserted via `to_lines()` tuple, rollback verified via no `unified_diff`.
- New fixtures live in the sibling `fixtures/` directory with module-scoped accessors in the relevant `conftest.py`.

### Driver & Rule Changes — read `docs/dev/creating-drivers.md` and `docs/dev/rule-reference.md`

- New rule types: frozen model in `models.py` → named default factory + field on `HConfigDriverRules` → consumed in `child.py`/`root.py` → populated in drivers → documented in `docs/dev/rule-reference.md`.
- New platforms: `Platform` enum member, `_BUILTIN_DRIVERS` wiring in `hier_config/registry.py` **keyed on `Platform.X.name`** (a `Platform`-member key is silently unreachable — `_normalize()` canonicalizes to uppercase name strings), `view_class` on the driver if it has a config view, per-platform test file, and a driver section + table row in `docs/admin/platforms.md`.

### Changelog

- `CHANGELOG.md` has an entry under `## [Unreleased]`, in the right category (`Added`/`Changed`/`Fixed`/`Removed`), referencing the issue/PR (`(#NNN)`).

### Docs

- Public API or driver behavior changes are reflected in `docs/user/` or `docs/admin/` (and `docs/dev/api-reference.md` where relevant).
- New doc pages are in the `mkdocs.yml` nav; moved pages have a `redirect_maps` entry.

### Commits — read `CONTRIBUTING.md` (Commit Message Style)

- Imperative mood, subject ≤72 characters, body explains *why*.

## Step 4: Report

Group findings by severity, most severe first:

- **Blockers** — violates a hard rule or a gate fails (CI would reject this).
- **Should fix** — deviates from documented conventions; a reviewer would push back.
- **Nits** — minor style or wording.

Each finding: `file:line`, what is wrong, and which standard it violates (with the doc path). End with a pass/fail verdict against the "Before Opening a PR" checklist in `AGENTS.md`.
