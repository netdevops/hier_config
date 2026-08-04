# Migrating from v3 to v4

This page is for existing hier_config 3.x users upgrading to 4.x. Version 4 renames
most entry points, unifies the negation rule system, and removes the v2
compatibility utilities — but the concepts (trees, drivers, remediation) are
unchanged, and most migrations are mechanical find-and-replace.

If you are new to hier_config, skip this page and start with
[Getting Started](getting-started.md).

## Quick reference

### Constructors

| v3 | v4 |
|---|---|
| `get_hconfig(platform, text)` | `HConfig.from_text(platform, text)` |
| `get_hconfig_fast_load(platform, lines)` | `HConfig.from_lines(platform, lines)` |
| `get_hconfig_from_dump(platform, dump)` | `HConfig.from_dump(platform, dump)` |
| `get_hconfig_fast_generic_load(lines)` | `HConfig.from_lines(Platform.GENERIC, lines)` |
| `get_hconfig_driver(platform)` | unchanged (now also accepts platform name strings) |
| `get_hconfig_view(config)` | unchanged (now resolved from the driver's `view_class`) |

```python
# v3
from hier_config import get_hconfig
config = get_hconfig(Platform.CISCO_IOS, config_text)

# v4
from hier_config import HConfig
config = HConfig.from_text(Platform.CISCO_IOS, config_text)
```

### Methods and properties

| v3 | v4 |
|---|---|
| `config.config_to_get_to(target)` | `config.remediation(target)` |
| `config.dump_simple()` | `config.to_lines()` |
| `child.cisco_style_text()` | `child.indented_text()` |
| `child.tags_add(...)` / `child.tags_remove(...)` | `child.add_tags(...)` / `child.remove_tags(...)` |
| `child.depth()` (method) | `child.depth` (property) |

### Utility functions

| v3 | v4 |
|---|---|
| `load_hconfig_v2_options(options, platform)` | `load_driver_rules(options, platform)` |
| `load_hconfig_v2_tags(tags)` | `load_tag_rules(tags)` |
| `load_hconfig_v2_options_from_file(path, platform)` | removed — read the file yourself and call `load_driver_rules()` |
| `HCONFIG_PLATFORM_V2_TO_V3_MAPPING` | removed |
| `hconfig_v2_os_v3_platform_mapper(os)` | removed |
| `hconfig_v3_platform_v2_os_mapper(platform)` | removed |

The dict format accepted by `load_driver_rules()` is unchanged, including the
`negation_negate_with`, `negation_default_when`, and `negation_sub` keys — they
are mapped onto the unified rule model for you.

## Negation rules

The three v3 negation rule models collapse into a single `NegationRule` with a
strategy enum, held in one ordered `negation` list on `HConfigDriverRules`:

| v3 | v4 |
|---|---|
| `NegationDefaultWithRule(match_rules=..., use=...)` | `NegationRule(strategy=NegationStrategy.REPLACE, match_rules=..., use=...)` |
| `NegationDefaultWhenRule(match_rules=...)` | `NegationRule(strategy=NegationStrategy.DEFAULT, match_rules=...)` |
| `NegationSubRule(match_rules=..., search=..., replace=...)` | `NegationRule(strategy=NegationStrategy.REGEX_SUB, match_rules=..., search=..., replace=...)` |
| `rules.negate_with` / `rules.negation_default_when` / `rules.negation_sub` | `rules.negation` (single list) |

```python
# v3
driver.rules.negate_with.append(
    NegationDefaultWithRule(
        match_rules=(MatchRule(startswith="logging console "),),
        use="logging console debugging",
    )
)

# v4
from hier_config.models import NegationRule, NegationStrategy

driver.rules.negation.append(
    NegationRule(
        strategy=NegationStrategy.REPLACE,
        match_rules=(MatchRule(startswith="logging console "),),
        use="logging console debugging",
    )
)
```

`REPLACE` rules are consulted first (via `driver.negate_with()`, which
imperative driver overrides also hook into); remaining rules evaluate in list
order, first match wins. See the
[driver rule reference](../dev/rule-reference.md) for details.

## Exceptions

v3 raised generic `ValueError`/`TypeError` from constructors and workflows. v4
raises typed exceptions under a common base — update any `except` clauses:

| Condition | v4 exception |
|---|---|
| Unknown platform | `DriverNotFoundError` |
| Unparseable/rejected config input | `InvalidConfigError` |
| Running/generated driver mismatch | `IncompatibleDriverError` |
| Duplicate child where not allowed | `DuplicateChildError` (now under the base) |
| Any of the above | `HierConfigError` |

```python
from hier_config import HierConfigError

try:
    config = HConfig.from_text(platform, config_text)
except HierConfigError as exc:
    ...
```

## Config views

`ConfigViewInterfaceBase` no longer declares every property abstract with
per-platform `NotImplementedError` stubs. Core properties (`name`,
`description`, `enabled`, `ipv4_interfaces`, ...) are always available;
optional capabilities live on mixins, and you check support with
`isinstance()` instead of catching `NotImplementedError`:

```python
# v3
try:
    vlans = interface_view.tagged_vlans
except NotImplementedError:
    vlans = ()

# v4
from hier_config import InterfaceVlanViewMixin

if isinstance(interface_view, InterfaceVlanViewMixin):
    vlans = interface_view.tagged_vlans
```

See [Config Views](config-views.md) for the mixin catalog.

## Behavior changes to review

- **`future()` negation resolution** — negations that match an existing line
  (exactly or by shorthand prefix) now remove it instead of surviving as a
  literal `no ...` child; see
  [Predicting Future Configs](future-config.md) for the resolution order and
  the new `prune_empty_branches` option.
- **Structured input rejection** — `HConfig.from_text()` (and the string form
  of `from_lines()`) raises `InvalidConfigError` when given XML or JSON
  instead of silently building a garbage tree. Use `HConfig.from_xml()` /
  `HConfig.from_json()` for those formats
  ([Loading Configurations](loading-configs.md)).
- **Custom driver wiring** — subclassed drivers previously required a local
  constructor function; v4 registers them with
  [`register_driver()`](../admin/custom-drivers.md), which also makes them
  work with every constructor and carries their config view via `view_class`.

## New in v4 (worth adopting)

Not required for migration, but these are the headline additions:

- [Driver registry](../admin/custom-drivers.md) — `register_driver()`,
  `unregister_driver()`, `get_registered_platforms()`; override built-ins or
  add custom platforms by string name.
- [JSON and XML configs](loading-configs.md) — `HConfig.from_json()` /
  `from_xml()` / `to_json()` / `to_xml()`, plus
  [NETCONF remediation payloads](remediation-workflows.md).
- [Remediation plugins](remediation-workflows.md) —
  `WorkflowRemediation(plugins=...)` and driver-level
  `remediation_transform_callbacks`.
- [Root-level duplicate children](../dev/rule-reference.md) — a
  `ParentAllowsDuplicateChildRule` with empty `match_rules` applies to the
  root.
- `HConfigDriverBase` and `HConfigDriverRules` are public API for
  [custom drivers](../dev/creating-drivers.md).

## Next steps

- [Getting Started](getting-started.md) — the v4 workflow end to end.
- [Customizing Driver Rules](../admin/customizing-rules.md) — if you carried
  v3 driver customizations.
- Full change list: the 4.0.0 section of the
  [CHANGELOG](https://github.com/netdevops/hier_config/blob/next/CHANGELOG.md).
