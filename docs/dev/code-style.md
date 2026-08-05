# Code Style & Standards

All standards below are enforced by `poetry run ./scripts/build.py lint`, which runs ruff (format + check), mypy, pyright, pylint, yamllint, and flynt in parallel. CI fails if any tool reports an issue.

## Lint & Type Checking Stack

| Tool | Configuration |
|------|---------------|
| ruff | `select = ["ALL"]` with preview rules, line length 88, formatting via `ruff format` |
| mypy | `strict = true` with the pydantic plugin |
| pyright | `typeCheckingMode = "strict"` |
| pylint | Extension plugins + `pylint_pydantic`; rules not already covered by ruff |
| yamllint | 2-space indentation, no document-start marker |
| flynt | f-string conversion checks |

The authoritative rule configuration lives in `pyproject.toml`. Do not add suppression comments (`# type: ignore`, `# noqa`) without a justifying reason, and never loosen the lint or coverage configuration to make a change pass.

## Pydantic Model Conventions

- **Always subclass the project-local `BaseModel`** defined in `hier_config/models.py` — never `pydantic.BaseModel` directly. The local base sets `ConfigDict(frozen=True, extra="forbid")`, making every model immutable and strict.
- **Immutable collections only** in model fields: `tuple[...]` for ordered data, `frozenset[...]` for sets. Never `list` or `set`. Deliberate exception: the rule-collection fields on `HConfigDriverRules` are `list[...]` on purpose, so built-in rules and callbacks can be removed by identity (e.g. `rules.post_load_callbacks.remove(...)`) — do not convert them to tuples.
- **Rule models** match configuration lineage with `match_rules: tuple[MatchRule, ...]`.
- Fields on `HConfigDriverRules` use **named module-level default factory functions** (e.g., `_ordering_rules_default`) rather than lambdas, for strict-mode type checking.

## General Conventions

- Python 3.10+ (`target-version = "py310"`); CI tests 3.10 through 3.14.
- Full type annotations everywhere, including tests.
- Docstrings required for new public classes, methods, and functions; use raw strings (`r"""..."""`) when they contain backslashes.
- Runtime dependencies are deliberately minimal (`pydantic` only) — do not add runtime dependencies without prior discussion in an issue.

## Changelog & Commits

- Every PR updates `CHANGELOG.md` under `## [Unreleased]` using [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) categories (`Added`, `Changed`, `Fixed`, `Removed`), referencing the issue/PR number, e.g. `(#209)`.
- Commit messages follow the style in [Contributing](contributing.md#commit-messages-and-prs): imperative mood, subject ≤72 characters, body explains *why*.
