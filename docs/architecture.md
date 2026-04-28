# Architecture Overview

This document describes the internal design of hier_config v3, covering the three main layers: the hierarchical tree model, the driver system, and the workflow / reporting layer.

---

## Overview

hier_config is built around a three-layer model:

| Layer | Purpose |
|-------|---------|
| **Tree** | Parse and represent configuration text as a rooted tree of nodes |
| **Driver** | Encode all platform-specific behaviour (negation, ordering, idempotency, …) |
| **Workflow** | Compute diffs, remediations, rollbacks, and reports against the tree |

---

## Core Tree Model

The tree layer lives in `hier_config/base.py`, `hier_config/root.py`, `hier_config/child.py`, and `hier_config/children.py`.

### `HConfig` (root node)

`HConfig` is the entry point of every configuration tree.  It owns:

- A reference to the **driver** for the platform.
- An `HConfigChildren` collection of top-level `HConfigChild` nodes.
- High-level operations: `future()`, `config_to_get_to()`, `merge()`, `difference()`, `dump()`.

Create an `HConfig` object via the constructor function:

```python
from hier_config import get_hconfig, Platform

hconfig = get_hconfig(Platform.CISCO_IOS, config_text)
```

### `HConfigChild` (tree node)

Each non-root node holds:

- `text` — the raw configuration line (stripped).
- `parent` — a reference to the parent `HConfig` or `HConfigChild`.
- `children` — an `HConfigChildren` collection of its own children.
- Metadata: `tags`, `comments`, `order_weight`, `new_in_config`, `instances`, `facts`.

`HConfigChild` inherits all tree-manipulation methods from `HConfigBase`.

### `HConfigChildren` (ordered collection)

`HConfigChildren` maintains two data structures in parallel:

- `_data: list[HConfigChild]` — preserves insertion order.
- `_mapping: dict[str, HConfigChild]` — maps `child.text` → first child for O(1) look-up.

When duplicate text is allowed (via `ParentAllowsDuplicateChildRule`), the list holds all copies while the mapping points to only the first.

### `HConfigBase` (abstract base)

Both `HConfig` and `HConfigChild` inherit from `HConfigBase`, which provides:

- Child manipulation: `add_child`, `add_children`, `add_deep_copy_of`, `add_shallow_copy_of`.
- Searching: `get_child`, `get_children`, `get_child_deep`, `get_children_deep`.
- Diffing: `unified_diff`, `_config_to_get_to`, `_difference`.
- Future prediction: `_future`, `_future_pre`.

---

## Driver System

The driver layer lives in `hier_config/platforms/`.

### `HConfigDriverBase`

Every platform driver subclasses `HConfigDriverBase` (`hier_config/platforms/driver_base.py`) and overrides:

- `_instantiate_rules()` — returns an `HConfigDriverRules` Pydantic model populated with the platform's rule sets.
- Optionally `negation_prefix`, `declaration_prefix`, `swap_negation`, `idempotent_for`, `negate_with`, `config_preprocessor`.

### `HConfigDriverRules`

A frozen Pydantic model holding lists of typed rule objects:

| Field | Rule type | Effect |
|-------|-----------|--------|
| `negate_with` | `NegationDefaultWithRule` | Replace negation with a fixed command |
| `negation_default_when` | `NegationDefaultWhenRule` | Use `default` form instead of `no` |
| `sectional_exiting` | `SectionalExitingRule` | Emit an exit token at end of section (optionally at parent indent level) |
| `sectional_overwrite` | `SectionalOverwriteRule` | Negate + re-create whole section |
| `sectional_overwrite_no_negate` | `SectionalOverwriteNoNegateRule` | Re-create without prior negation |
| `ordering` | `OrderingRule` | Assign integer weights for apply order |
| `idempotent_commands` | `IdempotentCommandsRule` | Last-value-wins commands |
| `idempotent_commands_avoid` | `IdempotentCommandsAvoidRule` | Exclude from idempotency matching |
| `per_line_sub` | `PerLineSubRule` | Line-level regex substitution on load |
| `full_text_sub` | `FullTextSubRule` | Full-text regex substitution on load |
| `indent_adjust` | `IndentAdjustRule` | Shift indentation at start/end markers |
| `parent_allows_duplicate_child` | `ParentAllowsDuplicateChildRule` | Permit duplicate child text |
| `post_load_callbacks` | `Callable[[HConfig], None]` | Run Python callbacks after parsing |

### Built-in Platform Drivers

| Platform enum | Driver class | Module |
|--------------|-------------|--------|
| `ARISTA_EOS` | `HConfigDriverAristaEOS` | `platforms/arista_eos/driver.py` |
| `CISCO_IOS` | `HConfigDriverCiscoIOS` | `platforms/cisco_ios/driver.py` |
| `CISCO_NXOS` | `HConfigDriverCiscoNXOS` | `platforms/cisco_nxos/driver.py` |
| `CISCO_XR` | `HConfigDriverCiscoIOSXR` | `platforms/cisco_xr/driver.py` |
| `FORTINET_FORTIOS` | `HConfigDriverFortinetFortiOS` | `platforms/fortinet_fortios/driver.py` |
| `GENERIC` | `HConfigDriverGeneric` | `platforms/generic/driver.py` |
| `HP_COMWARE5` | `HConfigDriverHPComware5` | `platforms/hp_comware5/driver.py` |
| `HP_PROCURVE` | `HConfigDriverHPProcurve` | `platforms/hp_procurve/driver.py` |
| `JUNIPER_JUNOS` | `HConfigDriverJuniperJUNOS` | `platforms/juniper_junos/driver.py` |
| `NOKIA_SRL` | `HConfigDriverNokiaSRL` | `platforms/nokia_srl/driver.py` |
| `VYOS` | `HConfigDriverVYOS` | `platforms/vyos/driver.py` |

See [Drivers](drivers.md) for full documentation on customising or creating drivers.

---

## Workflow Layer

### `WorkflowRemediation`

`WorkflowRemediation` (`hier_config/workflows.py`) is the primary user-facing API for computing changes between two configurations:

```python
workflow = WorkflowRemediation(running_config, generated_config)
remediation = workflow.remediation_config   # what to apply
rollback    = workflow.rollback_config      # how to revert
```

Internally it calls `running_config.config_to_get_to(generated_config)` which traverses the tree and calls `_config_to_get_to_left` (what to negate) and `_config_to_get_to_right` (what to add).

### `config_to_get_to()`

This method computes the **minimal delta** between two configs:

1. **Left pass** — find children in `self` that are absent from `target` and emit their negation.
2. **Right pass** — find children in `target` that are absent from or different in `self` and emit them as additions.

Sectional-overwrite and idempotency rules are applied during the right pass.

### `future()`

`HConfig.future(config)` predicts the device state after `config` is applied on top of the current running config.  It recursively merges the two trees, honouring:

- Sectional overwrite / no-negate rules
- Idempotency rules (last value wins)
- Negation commands (`no ...` removes the corresponding positive command)

See [Future Config](future-config.md) for known limitations.

---

## View Layer

The view layer (`hier_config/platforms/view_base.py` and platform-specific `view.py` files) provides structured, typed access to configuration elements without modifying the underlying tree.

- `HConfigViewBase` — abstract base; subclasses implement `interface_views` and `dot1q_mode_from_vlans`.
- `ConfigViewInterfaceBase` — abstract base for per-interface views; exposes properties like `ip_address`, `native_vlan`, `tagged_vlans`, `description`, `duplex`, `bundle_id`.

Instantiate a view with:

```python
from hier_config.platforms.cisco_ios.view import HConfigViewCiscoIOS

view = HConfigViewCiscoIOS(hconfig)
for iface in view.interface_views:
    print(iface.description, iface.native_vlan)
```

---

## Reporting Layer

`RemediationReporter` (`hier_config/reporting.py`) aggregates remediation configs from multiple devices:

```python
from hier_config import RemediationReporter

reporter = RemediationReporter()
reporter.add_remediations([device1_remediation, device2_remediation])
summary = reporter.summary()
reporter.to_json("report.json")
```

See [Remediation Reporting](remediation-reporting.md) for full API documentation.

---

## Data Flow

```
config text
    │
    ▼
per_line_sub / full_text_sub  (driver preprocessing)
    │
    ▼
config_preprocessor()         (optional platform transform, e.g. JunOS → set commands)
    │
    ▼
HConfig tree                  (HConfigBase / HConfigChild nodes)
    │
    ├──► HConfig.future()     → predicted post-change HConfig
    │
    ├──► HConfig.config_to_get_to()
    │         │
    │         ▼
    │     delta HConfig       (remediation commands)
    │         │
    │         ▼
    │     WorkflowRemediation.remediation_config
    │     WorkflowRemediation.rollback_config
    │
    └──► RemediationReporter  (multi-device aggregation)
```
