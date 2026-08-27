# v3 API Compatibility

Every v3 name that v4 renamed or removed still works in v4. The old names raise no
`DeprecationWarning`, and they are supported permanently. v3 code runs on v4
unchanged.

Each old name is a thin wrapper that calls its v4 counterpart, so the two spellings
can never drift apart. A committed recording of the v3 output
(`tests/fixtures/v3_baseline.json`) is compared against v4 on every CI run.

If you are writing new code, prefer the v4 names in
[Migrating from v3](migrating-from-v3.md). They are the ones the documentation and
examples use. Nothing forces you to change existing code.

## Supported v3 names

### Constructors

| v3 name | Calls |
|---|---|
| `get_hconfig(platform, text)` | `HConfig.from_text()` |
| `get_hconfig_fast_load(platform, lines)` | `HConfig.from_lines()` |
| `get_hconfig_from_dump(platform, dump)` | `HConfig.from_dump()` |
| `get_hconfig_fast_generic_load(lines)` | `HConfig.from_lines(Platform.GENERIC, lines)` |

All four are importable from `hier_config` and from `hier_config.constructors`.
`get_hconfig_driver` moved to `hier_config.registry` in v4 and is re-exported from
`hier_config.constructors`, so the v3 import path still resolves.

### Methods

| v3 name | Calls |
|---|---|
| `HConfig.config_to_get_to(target, delta=None)` | `HConfig.remediation()` |
| `HConfig.dump_simple(sectional_exiting=False)` | `HConfig.to_lines()` |
| `HConfigChild.cisco_style_text(style, tag)` | `HConfigChild.indented_text()` |
| `HConfigChild.tags_add(tag)` | `HConfigChild.add_tags()` |
| `HConfigChild.tags_remove(tag)` | `HConfigChild.remove_tags()` |

### Utility functions

| v3 name | Calls |
|---|---|
| `load_hconfig_v2_options(v2_options, platform)` | `load_driver_rules()` |
| `load_hconfig_v2_tags(v2_tags)` | `load_tag_rules()` |
| `load_hconfig_v2_options_from_file(path, platform)` | `load_driver_rules()` after reading the file |
| `hconfig_v2_os_v3_platform_mapper(os_name)` | no v4 equivalent; restored as-is |
| `hconfig_v3_platform_v2_os_mapper(platform)` | no v4 equivalent; restored as-is |
| `HCONFIG_PLATFORM_V2_TO_V3_MAPPING` | no v4 equivalent; restored as-is |

The wrappers keep the v3 parameter names (`v2_options`, `v2_tags`), so calls that
pass them as keywords still work.

### Negation rule models

| v3 model | Equivalent v4 rule |
|---|---|
| `NegationDefaultWithRule(match_rules, use)` | `NegationRule(match_rules, strategy=NegationStrategy.REPLACE, use=...)` |
| `NegationDefaultWhenRule(match_rules)` | `NegationRule(match_rules, strategy=NegationStrategy.DEFAULT)` |
| `NegationSubRule(match_rules, search, replace)` | `NegationRule(match_rules, strategy=NegationStrategy.REGEX_SUB, search=..., replace=...)` |

`HConfigDriverRules` still accepts the three v3 fields. It folds their contents into
the unified `negation` list at construction, in the order DEFAULT, REPLACE,
REGEX_SUB — the same order `load_driver_rules()` uses, which reproduces the v3
resolution priority.

```python
from hier_config import HConfigDriverBase, HConfigDriverRules, MatchRule
from hier_config.models import NegationDefaultWithRule


class MyDriver(HConfigDriverBase):
    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        # This v3 driver still works in v4.
        return HConfigDriverRules(
            negate_with=[
                NegationDefaultWithRule(
                    match_rules=(MatchRule(startswith="ip route"),),
                    use="no ip route",
                )
            ],
        )
```

Each v3 model also has `to_negation_rule()`, which returns the equivalent
`NegationRule` if you want to convert your driver by hand.

## A worked example

This is `nautobot_golden_config.models._get_hierconfig_remediation`, unchanged. It
runs on v4 as written:

```python
from hier_config import WorkflowRemediation, get_hconfig
from hier_config.utils import hconfig_v2_os_v3_platform_mapper, load_hconfig_v2_options

hierconfig_os = hconfig_v2_os_v3_platform_mapper(network_driver)
if remediation_options:
    hierconfig_os = load_hconfig_v2_options(remediation_options, hierconfig_os)

running = get_hconfig(hierconfig_os, actual)
intended = get_hconfig(hierconfig_os, generated)
workflow = WorkflowRemediation(running, intended)
remediation = workflow.remediation_config_filtered_text(
    include_tags={}, exclude_tags={}
)
```

## Two limits

The compatibility surface covers **names**. Two things are outside it.

**The v3 negation fields are constructor arguments only.** Pass them to
`HConfigDriverRules(...)` and they are folded into `negation`. Appending to
`rules.negate_with` *after* construction has no effect — append to `rules.negation`
instead. `load_driver_rules()` already does this, so rules loaded from a file or a
dict are unaffected.

**Some v4 behaviour changed even where the name did not.** Review these:

- `child.depth()` became the `child.depth` property. Drop the parentheses.
- `DriverNotFoundError`, `InvalidConfigError`, and `IncompatibleDriverError` replace
  the `ValueError` that v3 raised in the same places. All three subclass
  `HierConfigError`.
- The Arista EOS, Cisco NX-OS, and Cisco IOS-XR views are complete in v4. Properties
  that raised `NotImplementedError` in v3 now return real data.
- `HConfig.from_text()` and `get_hconfig()` reject XML and JSON input with
  `InvalidConfigError`. v3 accepted it and built a meaningless tree. Use
  `HConfig.from_xml()` or `HConfig.from_json()` for structured formats.

[Migrating from v3](migrating-from-v3.md) covers all of these in more detail.
