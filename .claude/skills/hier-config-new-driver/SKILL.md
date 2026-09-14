---
name: hier-config-new-driver
description: Use when adding hier_config support for a new network platform or operating system — creating a platform driver, registering a new Platform enum member, or scaffolding driver rules and tests for an unsupported vendor.
---

# Build a New hier_config Platform Driver

Scaffold an in-tree platform driver the way this repo expects. The authoritative recipe is `docs/dev/creating-drivers.md`; this skill adds the concrete templates. For a driver that lives *outside* this repo (in user code), follow `docs/admin/custom-drivers.md` instead.

## Step 1: Characterize the Platform

Answer these before writing code — they determine which overrides and rules the driver needs. Study real config samples from the platform:

| Question | Driver hook if non-default |
|----------|---------------------------|
| Negation prefix (`no `? `undo `? `delete `?) | `negation_prefix` property (default `"no "`) |
| Some commands reset with a different form? | `NegationRule` (REPLACE/DEFAULT/REGEX_SUB strategy) / override `swap_negation` |
| Sections closed with an exit token (`exit`, `quit`, `end-*`)? | `SectionalExitingRule` / override `sectional_exit` |
| Last-write-wins commands (`hostname`, `description`, …)? | `IdempotentCommandsRule` |
| Comment/banner lines to strip on load? | `PerLineSubRule` / `FullTextSubRule` |
| Blocks with irregular indentation? | `IndentAdjustRule` |
| Flat `set`/`delete` syntax (Junos-like)? | `config_preprocessor` + `declaration_prefix` (see `platforms/vyos/driver.py`) |
| Order-sensitive commands? | `OrderingRule` with weights |

Reference implementations: `platforms/huawei_vrp/driver.py` (small, rule-based), `platforms/vyos/driver.py` (preprocessor-based), `platforms/cisco_ios/driver.py` (comprehensive).

## Step 2: Write the Failing Test First (TDD)

Create `tests/integration/test_<platform>.py` before the driver exists — conventions in `docs/dev/testing.md`. Flat functions, full annotations, round-trip idiom:

```python
from hier_config import HConfig, Platform


def test_negation_prefix() -> None:
    running_config = HConfig.from_lines(
        Platform.ACME_OS, ("interface eth0", "  shutdown")
    )
    generated_config = HConfig.from_lines(
        Platform.ACME_OS, ("interface eth0",)
    )
    remediation = running_config.remediation(generated_config)
    assert remediation.to_lines() == ("interface eth0", "  no shutdown")

    running_after = running_config.future(remediation)
    rollback = running_after.remediation(running_config)
    running_after_rollback = running_after.future(rollback)
    assert not tuple(running_config.unified_diff(running_after_rollback))
```

Run it and confirm it fails for the right reason (unknown platform), not an import error. Add realistic config fixtures to `tests/integration/fixtures/` if tests need more than inline tuples.

## Step 3: Scaffold the Driver

Create `hier_config/platforms/<platform>/__init__.py` (empty) and `hier_config/platforms/<platform>/driver.py`:

```python
from hier_config.models import IdempotentCommandsRule, MatchRule, PerLineSubRule
from hier_config.platforms.driver_base import HConfigDriverBase, HConfigDriverRules


class HConfigDriverAcmeOS(HConfigDriverBase):
    """Driver for Acme OS.

    Platform enum: ``Platform.ACME_OS``.
    """

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            idempotent_commands=[
                IdempotentCommandsRule(match_rules=(MatchRule(startswith="hostname "),)),
            ],
            per_line_sub=[
                PerLineSubRule(search="^\\s*#.*", replace=""),
            ],
        )
```

Replace `#` in the `per_line_sub` regex with the platform's actual comment token, and keep the `^\s*` anchor so indented comments are stripped too. Rules take `match_rules: tuple[MatchRule, ...]` (immutable — never lists), while the `HConfigDriverRules` *collection fields themselves* are intentionally `list[...]` as shown above (so built-in rules/callbacks can be removed by identity). A minimal driver returning bare `HConfigDriverRules()` is valid; only add rules the platform needs. Public classes require docstrings.

## Step 4: Register the Platform

1. Add the member to the `Platform` enum in `hier_config/models.py` (alphabetical position). Note the enum uses `auto()`, so inserting a member renumbers everything after it — fine for in-repo use, but never rely on `Platform.value` for serialization.
2. Add the mapping to the `_BUILTIN_DRIVERS` dict in `hier_config/registry.py` and import the driver class there. The key must be the canonical uppercase name string — `Platform.ACME_OS.name` — not the enum member (`_normalize()` canonicalizes lookups to `.name`, so a `Platform`-member key would be silently unreachable). If the platform has a config view, set the `view_class` attribute on the driver.

## Step 5: Document and Log

- Add driver-level unit tests in `tests/unit/platforms/test_<platform>.py` (every recent driver has one; see `tests/unit/platforms/test_aruba_aoscx.py`). If the driver ships a config view, add `tests/unit/platforms/views/test_<platform>.py` too.
- Add a driver section (behavior summary) and a platform-table row to `docs/admin/platforms.md`. Mark the status `Experimental` for a new driver.
- If you introduced a new *rule type* (not just rule instances), document it in `docs/dev/rule-reference.md`.
- Add a `CHANGELOG.md` entry under `## [Unreleased]` → `### Added`.

## Step 6: Run the Gates

```bash
uv run pytest tests/integration/test_<platform>.py -v
uv run ./scripts/build.py lint-and-test
uv run mkdocs build --strict
```

All three must pass (mypy/pyright are strict; coverage floor is 95%). Then run the `hier-config-review` skill before opening the PR.
