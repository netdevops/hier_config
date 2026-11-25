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

The tree lives in `crates/hier_config_core/src/`. Nodes are addressed by IDs in
an arena, with child ordering and text lookup maintained by the native tree.
`crates/hier_config_py/src/` exposes Python handles over that shared state.
`hier_config/base.py`, `root.py`, `child.py`, and `children.py` preserve import
paths as thin re-export facades; they do not implement a second tree.

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

`HConfigChildren` is a native-backed view of a parent's direct children.
The Rust tree preserves insertion order and indexes text for lookup. When
duplicate text is allowed (`ParentAllowsDuplicateChildRule`), iteration includes
every copy while lookup returns the first. Obtain a collection from
`config.children` or `child.children`; it has no public standalone constructor.

### `HConfigBase` (abstract base)

Both `HConfig` and `HConfigChild` inherit from `HConfigBase`, which provides:

- Child manipulation: `add_child`, `add_children`, `add_deep_copy_of`, `add_shallow_copy_of`.
- Searching: `get_child`, `get_children`, `get_child_deep`, `get_children_deep`.
- Traversal: `descendants`, `all_children_sorted`.
- Diffing: `unified_diff`.

### Native typing (`hier_config/_hier_config_rust.pyi`)

`HConfig`, `HConfigChild`, `HConfigChildren`, and `HConfigBase` are compiled
PyO3 classes, and neither mypy, pyright, nor griffe (mkdocstrings) can
introspect a compiled extension. The shipped `.pyi` stub gives those
tools — and downstream users' own annotations — real types instead of `Any`.

There is **one generated native stub**, beside the packaged extension in
`hier_config/`. Its source of truth is the PyO3 bindings in
`crates/hier_config_py`: `pyo3-stub-gen` records the classes, functions,
signatures, and documentation. Bindings whose Rust signatures erase Python
types carry explicit Python-facing type metadata, including overloads and
types from Python models. Never substitute `Any` for an erased return type.

Generation reads the current bindings, not Git history, old releases, or a
second set of Python class declarations. A shallow checkout or source
distribution has everything needed to regenerate:

```bash
uv run --no-sync ./scripts/build.py generate-stubs
uv run --no-sync ./scripts/build.py check-stubs
```

`check-stubs` compares generated output without rewriting the committed file.
It runs in `lint` and `lint-and-test`, together with independent native-export
coverage, `mypy.stubtest`, and observed return-type checks. Installed-wheel
contracts check both valid and invalid calls using mypy and pyright outside
the checkout, with no custom stub search paths. Keep these guards: generation
cannot prove the correctness of manually supplied metadata for erased types.
Change binding metadata and regenerate; do not edit the generated stub.

The public `base.py`, `root.py`, `child.py`, `children.py`, and `workflows.py`
modules remain thin re-exports; their types and docs resolve to the native
stub, rather than duplicate `.pyi` declarations. Other Python modules still own
models, drivers, registration, callbacks, reporting, and compatibility helpers.
They are necessary runtime code, not a second tree engine.

The old top-level `_hier_config_rust` import remains a compatibility package
re-exporting the same objects, so historical class references and pickles
still resolve. New code should use the public `hier_config` APIs. There is no
root `stubs/` directory; validation allowlists live in `tests/typing/`, and
the package's `py.typed` marker makes wheel-installed typing discoverable.

### Tree algorithms

Remediation, difference, future prediction, pruning, and tag filtering execute
in `crates/hier_config_core/src/`. The remediation left pass removes source
commands missing from the target; the right pass adds target commands, honoring
sectional overwrite, idempotency, and negation rules. Context structs carry each
operation's state. Python callers use `HConfig.remediation()`, `difference()`,
`future()`, `future_with_report()`, and `with_tags()` rather than the removed
standalone `compute_*` functions.

`hier_config/tree_algorithms.py` retains the Python `FutureReport` data carrier.
See [Predicting Future Configs](../user/future-config.md) for prediction limits.

---

## Driver system

The driver layer lives in `hier_config/platforms/`.

### `HConfigDriverBase`

Every platform driver subclasses `HConfigDriverBase` (`hier_config/platforms/driver_base.py`) and overrides:

- `_instantiate_rules()` — returns an `HConfigDriverRules` Pydantic model populated with the platform's rule sets.
- Optionally `negation_prefix`, `declaration_prefix`, and the `view_class` class attribute.

The driver's `platform: ClassVar[Platform]` selects native platform operations.
Subclassing a built-in inherits this selector; a custom driver without one uses
Generic native operations. A registry name or loaded rule set does not itself
select a vendor's imperative behavior. Pure-Python custom rules, prefixes,
and callbacks remain boundary extension points. Custom `config_preprocessor()`
overrides are rejected at class creation; preprocess text explicitly before
calling `HConfig.from_text()`. Built-in preprocessing executes in Rust, while
the stock `core_owned` Python methods remain callable helpers.

Negation, idempotency, and sectional exiting are resolved in the Rust core from the driver's rule data; the corresponding Python hooks do not exist and defining them raises `TypeError`. Idempotency matching derives a structural *idempotency key* from each command's lineage and its matching rule, so commands that differ only in attribute values (e.g. two BGP neighbor descriptions) are not conflated.

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

Built-in drivers are registered at import time in a module-level registry keyed on canonical uppercase platform names — `Platform` members are converted via their `.name`, string names are uppercased, so a member and its name address the same entry (#284):

- `register_driver(platform, driver_class)` — add a custom platform (string names, case-insensitive) or override a built-in.
- `unregister_driver(platform)` — remove a custom platform or restore an overridden built-in.
- `get_registered_platforms()` — list everything registered: `Platform` members for enum-known names, uppercase strings for custom names.
- `get_hconfig_driver(platform)` — instantiate the registered driver.
- `resolve_driver(platform_or_driver)` — accept a `Platform`, string, or driver instance (used by every constructor).

### Built-in platform drivers

| Platform enum | Driver class | Module |
|--------------|-------------|--------|
| `ARISTA_EOS` | `HConfigDriverAristaEOS` | `platforms/arista_eos/driver.py` |
| `ARUBA_AOSCX` | `HConfigDriverArubaAOSCX` | `platforms/aruba_aoscx/driver.py` |
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
| `RUCKUS_FASTIRON` | `HConfigDriverRuckusFastIron` | `platforms/ruckus_fastiron/driver.py` |
| `VYOS` | `HConfigDriverVYOS` | `platforms/vyos/driver.py` |

See [Supported Platforms](../admin/platforms.md) for behavior details and [Creating a Platform Driver](creating-drivers.md) for building new ones.

---

## Structured formats (`hier_config/formats.py`)

The Python formats module delegates to `hier_config_core::formats`, which maps
JSON and XML onto the same tree as CLI text. The core owns ingestion, rendering,
and structured remediation; standalone Rust callers need no Python interpreter.

Format tests combine an independent IOS/EOS/error reference with historical
native Junos regression snapshots. The latter are not upstream equivalence
evidence; see [reference provenance](testing.md#structured-format-reference-provenance).

- `hconfig_from_json` / `hconfig_to_json` — invertible JSON mapping (keyed lists identified via `list_keys`).
- `hconfig_from_xml` / `hconfig_to_xml` — invertible XML mapping (attributes and text content become specially-encoded leaves).
- `hconfig_to_netconf_xml` — renders a remediation between `from_xml` trees as a NETCONF `edit-config` payload (deletions become `nc:operation="delete"` elements).
- `hconfig_to_gnmi_json` — renders a remediation between `from_json` trees as a gNMI-SetRequest-style dict (additions render into an `update` object, deletions become xpath-ish paths with `[key=value]` selectors).

These are exposed on `HConfig` as `from_json` / `from_xml` / `to_json` / `to_xml`, and on `WorkflowRemediation` as `remediation_netconf_xml()` / `remediation_json()`. See [Loading Configurations](../user/loading-configs.md) for the mapping rules.

---

## Workflow layer

### `WorkflowRemediation`

`WorkflowRemediation` (`hier_config/workflows.py`) is the primary user-facing API for computing changes between two configurations:

```python
workflow = WorkflowRemediation(running_config, generated_config)
remediation = workflow.remediation_config   # what to apply
rollback    = workflow.rollback_config      # how to revert
```

The native workflow computes and caches remediation/rollback trees. The Python
binding applies ordering and the transform pipeline: driver
`rules.remediation_transform_callbacks` first, then user `plugins`. Construction
validates matching driver classes (`IncompatibleDriverError`).
`running_config` and `generated_config` are read-only properties; create a new
workflow to replace either input. The trees themselves remain mutable.

### Plugins (`hier_config/plugins.py`)

`RemediationPlugin` is an abstract base class for user-defined remediation transforms — organization policies, safety sequences, provisioning workflows — packaged outside the hier_config codebase and applied via `WorkflowRemediation(plugins=...)`. Instances are callable, so any `Callable[[HConfig], None]` position accepts them. Driver authors should prefer `remediation_transform_callbacks` on `HConfigDriverRules` for platform-level transforms.

---

## View layer

The view layer provides structured, typed access to configuration elements without modifying the underlying tree. Since v4 it is **implemented entirely in Rust**; `hier_config/platforms/view_base.py` and the platform-specific `view.py` files are thin facades over the native classes.

- `HConfigView` (aliased `HConfigViewBase`) — device-level view exposing `hostname`, `interface_views`, `interfaces`, `ipv4_default_gw`, `vlans`, `stack_members`, and the `dot1q_mode_from_vlans` static helper.
- `ConfigViewInterface` (aliased `ConfigViewInterfaceBase`) — per-interface view exposing core properties like `name`, `description`, `enabled`, `ipv4_interfaces`, and `vrf`.
- Optional capability mixins — `InterfaceBundleViewMixin` (`bundle_id`, `bundle_member_interfaces`, ...), `InterfaceVlanViewMixin` (`native_vlan`, `tagged_vlans`, `dot1q_mode`, ...), `InterfaceNACViewMixin` (`has_nac`, `nac_host_mode`, ...), and `InterfacePhysicalViewMixin` (`duplex`, `speed`, `poe`, `module_number`). The mixins are now *marker* classes: the native view carries a `capabilities` frozenset, and `ViewMarkerMeta.__instancecheck__` answers `isinstance(view, InterfaceVlanViewMixin)` from that data. The user-facing capability protocol is unchanged.

Views are resolved through the driver's `view_class` attribute:

```python
from hier_config import get_hconfig_view

view = get_hconfig_view(hconfig)
for iface in view.interface_views:
    print(iface.description)
```

### Native views

`crates/hier_config_core/src/view/` is the single view implementation, usable
from Rust without an interpreter and exposed to Python through PyO3:

- `ConfigOps` / `InterfaceOps` — common defaults with platform overrides. Optional capabilities are gated by `supports_vlan()`, `supports_nac()`, `supports_physical()`, and `bundle_prefix()`.
- `ConfigView<'a>` / `InterfaceView<'a>` — borrow a `Tree` and delegate each property to the platform's ops, falling back to the `default_*` implementation.
- `view_ops_for_platform(Platform)` — returns `None` for the platforms that deliberately have no Python `view.py`. The match is exhaustive, so adding a `Platform` variant is a compile error until a decision is recorded.

```rust
use hier_config_core::{Platform, config_from_text, config_view};

let tree = config_from_text(Platform::CiscoIos, config_text)?;
if let Some(view) = config_view(&tree) {
    for iface in view.interface_views() {
        println!("{}", iface.description());
    }
}
```

`hier_config.platforms.*.view` exposes the bindings in
`crates/hier_config_py/src/view.rs`. The old `testdata/views/` dual-implementation
corpus was removed, but native view tests and Python boundary tests remain
necessary: shared algorithms do not guarantee correct bindings or return types.

A small number of properties raised in Python v3 rather than returning a value; the native view returns `None` or an empty tuple instead. See [Rust core behavior changes](../user/rust-core-changes.md).

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
native platform preprocessing     (e.g. JunOS → set commands; no custom Python hook)
    │
    ▼
HConfig tree                      (HConfigBase / HConfigChild nodes)
    │                              + post_load_callbacks
    │
    ├──► HConfig.future()         → predicted post-change HConfig
    │
    ├──► HConfig.remediation()    (native remediation engine)
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
