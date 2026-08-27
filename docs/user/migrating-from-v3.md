# Migrating from v3 to v4

This page is for existing hier_config 3.x users upgrading to 4.x. Version 4 renames
most entry points and unifies the negation rule system — but the concepts (trees,
drivers, remediation) are unchanged.

!!! note "The renames are optional"
    Every v3 name below still works in v4, permanently and with no
    `DeprecationWarning`. See [v3 API Compatibility](v3-compatibility.md). Your v3
    code runs on v4 unchanged; adopt the v4 names when it suits you.

    Three v4 changes are **not** covered by that compatibility surface, so review
    them before you upgrade: the `depth` property, the new exception types, and the
    completed EOS/NX-OS/XR views. They are in
    [Behavior changes to review](#behavior-changes-to-review).

If you are new to hier_config, skip this page and start with
[Getting Started](getting-started.md).

## Quick reference

The left column is the v3 spelling and still works. The right column is the v4
spelling, which the rest of the documentation uses.

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
| `child.depth()` (method) | `child.depth` (property) — **you must change this**; see [Behavior changes to review](#behavior-changes-to-review) |

### Utility functions

| v3 | v4 |
|---|---|
| `load_hconfig_v2_options(options, platform)` | `load_driver_rules(options, platform)` |
| `load_hconfig_v2_tags(tags)` | `load_tag_rules(tags)` |
| `load_hconfig_v2_options_from_file(path, platform)` | no v4 rename; reads the file, then calls `load_driver_rules()` |
| `HCONFIG_PLATFORM_V2_TO_V3_MAPPING` | no v4 equivalent; keep using it |
| `hconfig_v2_os_v3_platform_mapper(os)` | no v4 equivalent; keep using it |
| `hconfig_v3_platform_v2_os_mapper(platform)` | no v4 equivalent; keep using it |

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
# v3 -- still works when passed to the constructor
HConfigDriverRules(
    negate_with=[
        NegationDefaultWithRule(
            match_rules=(MatchRule(startswith="logging console "),),
            use="logging console debugging",
        )
    ],
)

# v4
from hier_config.models import NegationRule, NegationStrategy

HConfigDriverRules(
    negation=[
        NegationRule(
            strategy=NegationStrategy.REPLACE,
            match_rules=(MatchRule(startswith="logging console "),),
            use="logging console debugging",
        )
    ],
)
```

!!! note "The v3 lists still work"
    `HConfigDriverRules` keeps `negate_with`, `negation_default_when`, and
    `negation_sub`. Pass them to the constructor or append to them afterwards —
    both take effect. `driver.rules.negate_with.append(...)`, the idiom the v3
    custom-driver docs teach, behaves exactly as it did in v3.

`REPLACE` rules are consulted first (via `driver.negate_with()`, which
imperative driver overrides also hook into); remaining rules evaluate in list
order, first match wins. See the
[driver rule reference](../dev/rule-reference.md) for details.

## Exceptions

v3 raised generic `ValueError`/`TypeError` from constructors and workflows. v4
raises typed exceptions under a common base. This is one of the three changes the
[v3 compatibility surface](v3-compatibility.md) does not cover, so update any
`except ValueError` clauses:

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

Everything else in this guide is optional. These are not.

### Gaps the v3 compatibility surface cannot cover

A name alias cannot absorb a changed signature, exception type, or return
value. These four apply even to code that keeps the v3 spellings:

- **`depth` is a property** — replace `child.depth()` with `child.depth`. This is
  the only required call-site edit.
- **Typed exceptions** — see [Exceptions](#exceptions) above.
- **Completed config views** — the Arista EOS, Cisco NX-OS, and Cisco IOS-XR views
  return real data where v3 raised `NotImplementedError`. Code that caught
  `NotImplementedError` now silently receives values.
- **Structured input rejection** — `HConfig.from_text()` and the restored
  `get_hconfig()` (and the string form of `from_lines()`) raise
  `InvalidConfigError` when given XML or JSON, instead of silently building a
  garbage tree. Use `HConfig.from_xml()` / `HConfig.from_json()` for those
  formats ([Loading Configurations](loading-configs.md)).

### Other v4 changes worth reviewing

These were never candidates for name-alias coverage. They are improvements to
how v4 works, listed here so an upgrade does not surprise you:

- **`future()` negation resolution** — negations that match an existing line
  (exactly or by shorthand prefix) now remove it instead of surviving as a
  literal `no ...` child; see
  [Predicting Future Configs](future-config.md) for the resolution order and
  the new `prune_empty_branches` option.
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
- Built-in post-load callbacks are public functions removable by identity —
  see [Customizing Driver Rules](../admin/customizing-rules.md#customizing-post-load-callbacks).
- `HConfig.future_with_report()` — predict a future config and get a
  `FutureReport` of [how the change's negations resolved](future-config.md#auditing-negation-resolution).

## Next steps

- [v3 API Compatibility](v3-compatibility.md) — the full list of v3 names that
  keep working in v4, and the two limits.
- [Getting Started](getting-started.md) — the v4 workflow end to end.
- [Customizing Driver Rules](../admin/customizing-rules.md) — if you carried
  v3 driver customizations.
- Full change list: the Unreleased section of the
  [CHANGELOG](https://github.com/netdevops/hier_config/blob/next/CHANGELOG.md)
  (it becomes the 4.0.0 section at release).
