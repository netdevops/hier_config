# Architecture

This page describes the internal design of hier_config for contributors and integrators: the hierarchical tree model, the tree algorithms, the driver system and registry, the structured-format layer, and the workflow / view / reporting layers. Users who only *consume* the library can usually stay in the [User Guide](../user/getting-started.md).

## Overview

hier_config is built around a three-layer model:

| Layer | Purpose |
|-------|---------|
| **Tree** | Parse and represent configuration text as a rooted tree of nodes |
| **Driver** | Encode all platform-specific behavior (negation, ordering, idempotency, …) |
| **Workflow** | Compute diffs, remediations, rollbacks, and reports against the tree |

---

## Core tree model

The tree layer lives in `hier_config/base.py`, `hier_config/root.py`, `hier_config/child.py`, and `hier_config/children.py`.

### `HConfig` (root node)

`HConfig` is the entry point of every configuration tree. It owns:

- A reference to the **driver** for the platform.
- An `HConfigChildren` collection of top-level `HConfigChild` nodes.
- Constructors: `from_text()`, `from_lines()`, `from_dump()`, `from_json()`, `from_xml()`.
- High-level operations: `future()`, `remediation()`, `merge()`, `difference()`, `dump()`, `to_lines()`, `to_json()`, `to_xml()`, `unused_objects()`.

```python
from hier_config import HConfig, Platform

hconfig = HConfig.from_text(Platform.CISCO_IOS, config_text)
```

### `HConfigChild` (tree node)

Each non-root node holds:

- `text` — the raw configuration line (stripped).
- `parent` — a reference to the parent `HConfig` or `HConfigChild`.
- `children` — an `HConfigChildren` collection of its own children.
- Metadata: `tags`, `comments`, `order_weight`, `new_in_config`, `instances`, `facts`.

Notable methods: `is_lineage_match()` (evaluate a tuple of `MatchRule`s against the node's ancestry, used by all rule evaluation), `negate()` (apply driver negation logic), `add_tags()` / `remove_tags()`, and `indented_text()`. `HConfigChild` inherits all tree-manipulation methods from `HConfigBase`.

### `HConfigChildren` (ordered collection)

`HConfigChildren` maintains two data structures in parallel:

- `_data: list[HConfigChild]` — preserves insertion order.
- `_mapping: dict[str, HConfigChild]` — maps `child.text` → first child for O(1) look-up.

When duplicate text is allowed (via `ParentAllowsDuplicateChildRule`), the list holds all copies while the mapping points to only the first.

### `HConfigBase` (abstract base)

Both `HConfig` and `HConfigChild` inherit from `HConfigBase`, which provides:

- Child manipulation: `add_child`, `add_children`, `add_deep_copy_of`, `add_shallow_copy_of`.
- Searching: `get_child`, `get_children`, `get_child_deep`, `get_children_deep`.
- Traversal: `all_children`, `all_children_sorted`.
- Diffing: `unified_diff`.

### Tree algorithms (`hier_config/tree_algorithms.py`)

The comparison algorithms are extracted into a standalone module operating on nodes through their public tree API:

- `compute_remediation(source, target, delta)` — the remediation algorithm: a *left pass* (`_remediation_left`) negates children of `source` absent from `target`, then a *right pass* (`_remediation_right`) adds children of `target` absent from (or different in) `source`, applying sectional-overwrite and idempotency rules.
- `compute_difference(source, target, delta)` — config in `source` that is not in `target` (with ACL sequence-number awareness).
- `compute_future(source, config, future_config)` — recursively merges `config` on top of `source`, honoring sectional overwrites, idempotency, and negation resolution (see [Predicting Future Configs](../user/future-config.md)).
- `prune_emptied_branches(source, future_node)` — removes sections a change emptied out, for `future(..., prune_empty_branches=True)`.
- `compute_with_tags(source, tags, delta)` — tag-filtered deep copy.

---

## Driver system

The driver layer lives in `hier_config/platforms/`.

### `HConfigDriverBase`

Every platform driver subclasses `HConfigDriverBase` (`hier_config/platforms/driver_base.py`) and overrides:

- `_instantiate_rules()` — returns an `HConfigDriverRules` Pydantic model populated with the platform's rule sets.
- Optionally `negation_prefix`, `declaration_prefix`, `swap_negation`, `idempotent_for`, `negate_with`, `config_preprocessor`, and the `view_class` class attribute.

Idempotency matching derives a structural *idempotency key* from each command's lineage and its matching rule (`_idempotency_key`), so commands that differ only in attribute values (e.g. two BGP neighbor descriptions) are not conflated.

### `HConfigDriverRules`

A frozen Pydantic model holding mutable lists of typed rule objects:

| Field | Rule type | Effect |
|-------|-----------|--------|
| `negation` | `NegationRule` | Unified negation: REPLACE a fixed command, use the DEFAULT form, or REGEX_SUB the negated text |
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
| `unused_objects` | `UnusedObjectRule` | Detect defined-but-unreferenced objects |
| `post_load_callbacks` | `Callable[[HConfig], None]` | Run Python callbacks after parsing |
| `remediation_transform_callbacks` | `Callable[[HConfig], None]` | Run Python callbacks over computed remediations |
| `indentation` | `PositiveInt` | Spaces per indent level when rendering (default 2) |

See the [Driver Rule Reference](rule-reference.md) for every model's fields.

### Registry (`hier_config/registry.py`)

Built-in drivers are registered at import time in a module-level registry mapping `Platform | str` → driver class:

- `register_driver(platform, driver_class)` — add a custom platform (string names, case-insensitive) or override a built-in.
- `unregister_driver(platform)` — remove a custom platform or restore an overridden built-in.
- `get_registered_platforms()` — list everything registered.
- `get_hconfig_driver(platform)` — instantiate the registered driver.
- `resolve_driver(platform_or_driver)` — accept a `Platform`, string, or driver instance (used by every constructor).

### Built-in platform drivers

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
| `HUAWEI_VRP` | `HConfigDriverHuaweiVrp` | `platforms/huawei_vrp/driver.py` |
| `JUNIPER_JUNOS` | `HConfigDriverJuniperJUNOS` | `platforms/juniper_junos/driver.py` |
| `NOKIA_SRL` | `HConfigDriverNokiaSRL` | `platforms/nokia_srl/driver.py` |
| `VYOS` | `HConfigDriverVYOS` | `platforms/vyos/driver.py` |

See [Supported Platforms](../admin/platforms.md) for behavior details and [Creating a Platform Driver](creating-drivers.md) for building new ones.

---

## Structured formats (`hier_config/formats.py`)

The formats module maps JSON (e.g. OpenConfig) and XML (e.g. NETCONF payloads) onto the same `HConfig` tree used by the rest of the library, so structured configs can be diffed and predicted like CLI text:

- `hconfig_from_json` / `hconfig_to_json` — invertible JSON mapping (keyed lists identified via `list_keys`).
- `hconfig_from_xml` / `hconfig_to_xml` — invertible XML mapping (attributes and text content become specially-encoded leaves).
- `hconfig_to_netconf_xml` — renders a remediation between `from_xml` trees as a NETCONF `edit-config` payload (deletions become `nc:operation="delete"` elements).

These are exposed on `HConfig` as `from_json` / `from_xml` / `to_json` / `to_xml`, and on `WorkflowRemediation` as `remediation_netconf_xml()`. See [Loading Configurations](../user/loading-configs.md) for the mapping rules.

---

## Workflow layer

### `WorkflowRemediation`

`WorkflowRemediation` (`hier_config/workflows.py`) is the primary user-facing API for computing changes between two configurations:

```python
workflow = WorkflowRemediation(running_config, generated_config)
remediation = workflow.remediation_config   # what to apply
rollback    = workflow.rollback_config      # how to revert
```

Internally it calls `running_config.remediation(generated_config)` (which delegates to `compute_remediation`), then `set_order_weight()`, then runs the transform pipeline: the driver's `rules.remediation_transform_callbacks` first, followed by the user-supplied `plugins`. It validates at construction that both configs use the same driver class (`IncompatibleDriverError`).

### Plugins (`hier_config/plugins.py`)

`RemediationPlugin` is an abstract base class for user-defined remediation transforms — organization policies, safety sequences, provisioning workflows — packaged outside the hier_config codebase and applied via `WorkflowRemediation(plugins=...)`. Instances are callable, so any `Callable[[HConfig], None]` position accepts them. Driver authors should prefer `remediation_transform_callbacks` on `HConfigDriverRules` for platform-level transforms.

---

## View layer

The view layer (`hier_config/platforms/view_base.py` and platform-specific `view.py` files) provides structured, typed access to configuration elements without modifying the underlying tree.

- `HConfigViewBase` — abstract device-level base; subclasses implement `interface_views` and `dot1q_mode_from_vlans`.
- `ConfigViewInterfaceBase` — abstract per-interface base; exposes core properties like `name`, `description`, `enabled`, `ipv4_interfaces`, and `vrf`.
- Optional capability mixins — `InterfaceBundleViewMixin` (`bundle_id`, `bundle_member_interfaces`, ...), `InterfaceVlanViewMixin` (`native_vlan`, `tagged_vlans`, `dot1q_mode`, ...), `InterfaceNACViewMixin` (`has_nac`, `nac_host_mode`, ...), and `InterfacePhysicalViewMixin` (`duplex`, `speed`, `poe`, `module_number`). Platform views inherit only the mixins they support; users check capability with `isinstance(view, InterfaceVlanViewMixin)`.

Views are resolved through the driver's `view_class` attribute:

```python
from hier_config import get_hconfig_view

view = get_hconfig_view(hconfig)
for iface in view.interface_views:
    print(iface.description)
```

---

## Reporting layer

`RemediationReporter` (`hier_config/reporting.py`) aggregates remediation configs from multiple devices:

```python
from hier_config import RemediationReporter

reporter = RemediationReporter()
reporter.add_remediations([device1_remediation, device2_remediation])
summary = reporter.summary()
reporter.to_json("report.json")
```

See [Remediation Reporting](../user/remediation-reporting.md) for full documentation.

---

## Exceptions (`hier_config/exceptions.py`)

All library errors derive from `HierConfigError`:

- `DriverNotFoundError` — unknown platform or missing view.
- `DuplicateChildError` — strict `merge()` conflict or duplicate list identities in structured formats.
- `IncompatibleDriverError` — `WorkflowRemediation` given configs with different driver classes.
- `InvalidConfigError` — malformed or wrong-format input (JSON/XML detection, mapping violations).

---

## Data flow

```text
config text (or JSON / XML document)
    │
    ▼
full_text_sub / per_line_sub      (driver preprocessing)
    │
    ▼
config_preprocessor()             (optional platform transform, e.g. JunOS → set commands)
    │
    ▼
HConfig tree                      (HConfigBase / HConfigChild nodes)
    │                              + post_load_callbacks
    │
    ├──► HConfig.future()         → predicted post-change HConfig
    │
    ├──► HConfig.remediation()    (tree_algorithms.compute_remediation)
    │         │
    │         ▼
    │     delta HConfig           (remediation commands)
    │         │
    │         ▼
    │     remediation_transform_callbacks → plugins
    │         │
    │         ▼
    │     WorkflowRemediation.remediation_config
    │     WorkflowRemediation.rollback_config
    │
    └──► RemediationReporter      (multi-device aggregation)
```

## Next steps

- [Driver Rule Reference](rule-reference.md) — every rule model in detail.
- [Creating a Platform Driver](creating-drivers.md) — apply this architecture to a new platform.
- [Contributing](contributing.md) — build, test, and submit changes.
