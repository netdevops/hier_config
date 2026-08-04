---
name: hier-config-new-driver
description: Use when adding hier_config support for a new network platform or operating system — creating a platform driver, registering a new Platform enum member, or scaffolding driver rules and tests for an unsupported vendor.
---

# Build a New hier_config Platform Driver

Scaffold an in-tree platform driver the way this repo expects. The authoritative recipe is `docs/dev/extending.md`; this skill adds the concrete templates. For a driver that lives *outside* this repo (in user code), follow `docs/user/custom-drivers.md#creating-a-custom-driver` instead.

## Step 1: Characterize the Platform

Answer these before writing code — they determine which overrides and rules the driver needs. Study real config samples from the platform:

| Question | Driver hook if non-default |
|----------|---------------------------|
| Negation prefix (`no `? `undo `? `delete `?) | `negation_prefix` property (default `"no "`) |
| Some commands reset with a different form? | `NegationDefaultWithRule` / override `swap_negation` |
| Sections closed with an exit token (`exit`, `quit`, `end-*`)? | `SectionalExitingRule` / override `sectional_exit` |
| Last-write-wins commands (`hostname`, `description`, …)? | `IdempotentCommandsRule` |
| Comment/banner lines to strip on load? | `PerLineSubRule` / `FullTextSubRule` |
| Blocks with irregular indentation? | `IndentAdjustRule` |
| Flat `set`/`delete` syntax (Junos-like)? | `config_preprocessor` + `declaration_prefix` (see `platforms/vyos/driver.py`) |
| Order-sensitive commands? | `OrderingRule` with weights |

Reference implementations: `platforms/huawei_vrp/driver.py` (small, rule-based), `platforms/vyos/driver.py` (preprocessor-based), `platforms/cisco_ios/driver.py` (comprehensive).

## Step 2: Write the Failing Test First (TDD)

Create `tests/test_driver_<platform>.py` before the driver exists — conventions in `docs/dev/testing.md`. Flat functions, full annotations, round-trip idiom:

```python
from hier_config import Platform, get_hconfig_fast_load


def test_negation_prefix() -> None:
    running_config = get_hconfig_fast_load(
        Platform.ACME_OS, ("interface eth0", "  shutdown")
    )
    generated_config = get_hconfig_fast_load(
        Platform.ACME_OS, ("interface eth0",)
    )
    remediation = running_config.config_to_get_to(generated_config)
    assert remediation.dump_simple() == ("interface eth0", "  no shutdown")

    running_after = running_config.future(remediation)
    rollback = running_after.config_to_get_to(running_config)
    running_after_rollback = running_after.future(rollback)
    assert not tuple(running_config.unified_diff(running_after_rollback))
```

Run it and confirm it fails for the right reason (unknown platform), not an import error. Add realistic config fixtures to `tests/fixtures/` if tests need more than inline tuples.

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

Replace `#` in the `per_line_sub` regex with the platform's actual comment token, and keep the `^\s*` anchor so indented comments are stripped too. Rules take `match_rules: tuple[MatchRule, ...]` (immutable — never lists). A minimal driver returning bare `HConfigDriverRules()` is valid; only add rules the platform needs. Public classes require docstrings.

## Step 4: Register the Platform

1. Add the member to the `Platform` enum in `hier_config/models.py` (alphabetical position). Note the enum uses `auto()`, so inserting a member renumbers everything after it — fine for in-repo use, but never rely on `Platform.value` for serialization.
2. Add the mapping to the `platform_drivers` dict in `get_hconfig_driver` (`hier_config/constructors.py`) and import the driver class there.

## Step 5: Document and Log

- Add a driver section (behavior summary + activation snippet) and a platform-table row to `docs/user/drivers.md`. Mark the status `Experimental` for a new driver.
- Add a `CHANGELOG.md` entry under `## [Unreleased]` → `### Added`.

## Step 6: Run the Gates

```bash
poetry run pytest tests/test_driver_<platform>.py -v
poetry run ./scripts/build.py lint-and-test
poetry run mkdocs build --strict
```

All three must pass (mypy/pyright are strict; coverage floor is 95%). Then run the `hier-config-review` skill before opening the PR.
