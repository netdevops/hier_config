# Loading Rules from Files

This page covers the helpers in `hier_config.utils` that load driver rules and tag rules from YAML files (or plain dictionaries). Use them when you want rule definitions to live in configuration files — versioned and edited without touching Python code.

> **Note:** post-load callbacks and remediation transform callbacks are Python code and are deliberately *not* loadable from YAML. Anything imperative belongs in a [driver subclass](customizing-rules.md) or a [plugin](../user/remediation-workflows.md#the-remediation-transform-pipeline).

## `read_text_from_file`

Reads the contents of a file into memory — a convenience for loading device configurations:

```python
from hier_config.utils import read_text_from_file

device_config = read_text_from_file("path/to/device_config.txt")
print(device_config)
```

## `load_driver_rules`

Loads driver rules from a dictionary or a YAML file and returns a driver instance for the given platform with those rules appended to the platform defaults.

**From a dictionary:**

```python
from hier_config import Platform
from hier_config.utils import load_driver_rules

options = {
    "ordering": [{"lineage": [{"startswith": "ntp"}], "order": 700}],
    "per_line_sub": [{"search": "^!.*Generated.*$", "replace": ""}],
    "sectional_exiting": [
        {"lineage": [{"startswith": "router bgp"}], "exit_text": "exit"}
    ],
    "idempotent_commands": [{"lineage": [{"startswith": "interface"}]}],
    "negation_negate_with": [
        {
            "lineage": [
                {"startswith": "interface Ethernet"},
                {"startswith": "spanning-tree port type"},
            ],
            "use": "no spanning-tree port type",
        }
    ],
}
driver = load_driver_rules(options, Platform.CISCO_IOS)
```

**From a YAML file:**

```python
from hier_config import Platform
from hier_config.utils import load_driver_rules

driver = load_driver_rules("/path/to/options.yml", Platform.CISCO_IOS)
```

Use the returned driver instance directly: `HConfig.from_text(driver, config_text)`.

### Supported option keys

Each entry uses a `lineage` list of match criteria (`startswith`, `endswith`, `contains`, `equals`, `re_search`) that maps onto [`MatchRule`](../glossary.md#match-rule) tuples:

| YAML key | Resulting rule |
|----------|----------------|
| `ordering` | `OrderingRule` (`order` value is offset by −500 to a weight) |
| `per_line_sub` | `PerLineSubRule` (`search` / `replace`) |
| `full_text_sub` | `FullTextSubRule` (`search` / `replace`) |
| `sectional_exiting` | `SectionalExitingRule` (`exit_text`) |
| `sectional_overwrite` | `SectionalOverwriteRule` |
| `sectional_overwrite_no_negate` | `SectionalOverwriteNoNegateRule` |
| `idempotent_commands` | `IdempotentCommandsRule` |
| `idempotent_commands_blacklist` | `IdempotentCommandsAvoidRule` |
| `parent_allows_duplicate_child` | `ParentAllowsDuplicateChildRule` |
| `indent_adjust` | `IndentAdjustRule` (`start_expression` / `end_expression`) |
| `negation_negate_with` | `NegationRule` with `strategy=REPLACE` (`use`) |
| `negation_default_when` | `NegationRule` with `strategy=DEFAULT` |
| `negation_sub` | `NegationRule` with `strategy=REGEX_SUB` (`search` / `replace`) |
| `unused_objects` | `UnusedObjectRule` (`name_re`, `reference_locations`) |

The three `negation_*` keys all produce the unified [`NegationRule`](../glossary.md#negation-rule) model with the corresponding `NegationStrategy`.

## `load_tag_rules`

Loads [tag rules](../user/tags.md) from a list of dictionaries or a YAML file into `TagRule` objects. Each entry needs a `lineage` list and an `add_tags` string:

```python
from hier_config.utils import load_tag_rules

tags = load_tag_rules([
    {
        "lineage": [{"startswith": ["ip name-server", "ntp"]}],
        "add_tags": "ntp"
    }
])

print(tags)
```

**From a YAML file:**

```python
from hier_config.utils import load_tag_rules

tags = load_tag_rules("path/to/tags.yml")
```

## `load_hier_config_tags`

Parses a YAML file whose entries are already in the native `TagRule` shape (`match_rules` + `apply_tags`) and validates them into `TagRule` objects:

```python
from hier_config.utils import load_hier_config_tags

tag_rules = load_hier_config_tags("path/to/tag_rules.yml")
```

Example YAML for this format:

```yaml
- match_rules:
  - startswith:
    - ip name-server
    - ntp
  apply_tags: [ntp]
```

Use `load_hier_config_tags` for the native `match_rules`/`apply_tags` format and `load_tag_rules` for the legacy `lineage`/`add_tags` format.

## Next steps

- [Working with Tags](../user/tags.md) — applying the loaded tag rules to a remediation.
- [Customizing Driver Rules](customizing-rules.md) — the same rules, expressed in Python.
