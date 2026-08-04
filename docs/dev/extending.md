# Extending hier_config

This guide covers the three most common in-tree contributions: adding support for a new platform, adding a new driver rule type, and adding config view properties. For customizing drivers *outside* the library (in your own code), see [Customizing and Creating Drivers](../user/custom-drivers.md).

Every change described here follows [TDD](testing.md): write the failing test first, then implement.

---

## Adding an In-Tree Platform Driver

1. **Create the driver package**: `hier_config/platforms/<platform>/` containing `driver.py` with a class subclassing `HConfigDriverBase` (`hier_config/platforms/driver_base.py`). Override `_instantiate_rules()` to return an `HConfigDriverRules` model constructed with the platform's rules (see `platforms/huawei_vrp/driver.py` for a small example).
2. **Register the platform**: add a member to the `Platform` enum in `hier_config/models.py`.
3. **Wire the constructor**: map the new enum member to your driver class in the `platform_drivers` dict inside `get_hconfig_driver` (`hier_config/constructors.py`).
4. **Add tests**: create `tests/test_driver_<platform>.py` following the [testing conventions](testing.md). Add any config fixtures to `tests/fixtures/`.
5. **Document it**: add a driver section and a platform-table row to [Drivers](../user/drivers.md).
6. **Changelog**: add an entry under `## [Unreleased]` in `CHANGELOG.md`.

Rule behavior available to drivers (negation, sectional exiting, ordering, idempotency, substitutions, etc.) is catalogued in [Driver Rule Types](../user/custom-drivers.md#driver-rule-types).

## Adding a Driver Rule Type

1. **Model**: add a frozen Pydantic model in `hier_config/models.py`. Subclass the project-local `BaseModel` (never `pydantic.BaseModel` directly — the local base enforces `frozen=True, extra="forbid"`). Lineage matching uses `match_rules: tuple[MatchRule, ...]`; collections must be immutable (`tuple` / `frozenset`).
2. **Rules container**: add a named module-level default factory function and a field to `HConfigDriverRules` in `hier_config/platforms/driver_base.py`.
3. **Consume the rule**: implement the behavior in `hier_config/child.py` and/or `hier_config/root.py` (typically evaluated via `HConfigChild.is_lineage_match()`).
4. **Populate**: add instances of the rule to the relevant platform drivers' `_instantiate_rules()`.
5. **Test, document, changelog**: failing test first; document the rule type in [Driver Rule Types](../user/custom-drivers.md#driver-rule-types) and add a [glossary](../user/glossary.md) entry; update `CHANGELOG.md`.

## Adding Config View Properties

1. **Abstract property**: declare it on `HConfigViewBase` or `ConfigViewInterfaceBase` in `hier_config/platforms/view_base.py`.
2. **Platform implementations**: implement the property in each platform's `view.py` (e.g., `hier_config/platforms/cisco_ios/view.py`).
3. **Test**: add coverage in `tests/config_view/` (per-platform files such as `test_view_cisco_ios.py`).
4. **Document**: add the property to [Config View](../user/config-view.md).

---

## Where Changes Belong

| Change type | Location |
|-------------|----------|
| New platform support | `hier_config/platforms/<name>/driver.py` |
| New rule type | `hier_config/models.py` + `hier_config/platforms/driver_base.py` |
| New utility function | `hier_config/utils.py` |
| New view property | `hier_config/platforms/view_base.py` + each platform's `view.py` |
| Core tree algorithm | `hier_config/base.py` (shared) or `hier_config/root.py` (`HConfig`-only) |

Read the [Architecture Overview](architecture.md) before making structural changes.
