# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- Structured config ingestion and rendering (#232): `HConfig.from_json()` /
  `HConfig.from_xml()` build config trees from JSON (e.g. OpenConfig) and XML
  (e.g. NETCONF payloads), with OpenConfig-style keyed lists identified via
  `list_keys` (default `("name", "id")`). `HConfig.to_json()` / `to_xml()`
  invert the mapping, so structured configs can be diffed, predicted with
  `future()`, and rendered back in their source format. The format-detection
  error now points at the new constructors. NETCONF `edit-config` operation
  attributes are not yet given remediation semantics.

- Interface view capability mixins (#227): `ConfigViewInterfaceBase` now
  carries only the core interface properties (`name`, `description`,
  `enabled`, `ipv4_interfaces`, `is_loopback`, `is_svi`, `number`,
  `port_number`, `vrf`, plus concrete helpers `ipv4_interface`,
  `is_subinterface`, `parent_name`, `subinterface_number`). Optional
  capabilities moved to new ABC mixins in
  `hier_config.platforms.view_base` — `InterfaceBundleViewMixin`,
  `InterfaceVlanViewMixin` (owns the concrete `dot1q_mode`),
  `InterfaceNACViewMixin`, and `InterfacePhysicalViewMixin` (owns a concrete
  `module_number`) — all exported from the package root. Platform views
  inherit only the mixins they support, and users check capability with
  `isinstance(view, InterfaceVlanViewMixin)` instead of catching
  `NotImplementedError`. `HConfigViewBase.bundle_interface_views` and
  `module_numbers` are now capability-aware.
- Completed the Arista EOS, Cisco NX-OS, and Cisco IOS XR config views (#230):
  all three now implement the full core interface property set plus the VLAN
  and bundle mixins (EOS/NX-OS switchport, trunk, and channel-group parsing;
  XR `encapsulation dot1q`, `ipv4 address x.x.x.x/nn | x.x.x.x y.y.y.y`, and
  `Bundle-Ether`/`bundle id <N>` parsing), along with the root view
  properties `interface_names_mentioned`, `ipv4_default_gw`, `location`,
  `stack_members`, and `vlans`.
- Cisco IOS `bundle_member_interfaces` and HP ProCurve `bundle_id` are now
  implemented (previously `NotImplementedError` stubs) (#230).

- Driver registration system (#226): `register_driver()`, `unregister_driver()`,
  and `get_registered_platforms()`. Custom platforms are registered by string
  name (case-insensitive) and work anywhere a `Platform` is accepted; built-in
  drivers can be overridden and later restored. `HConfigDriverBase` and
  `HConfigDriverRules` are now exported as public API.
- View registration follows driver registration (#187, #229): drivers declare
  their view via the `view_class` attribute, `get_hconfig_view()` resolves it
  from the driver, and registered custom drivers get views without extra
  wiring.
- `HConfig.from_text()`, `HConfig.from_lines()`, and `HConfig.from_dump()`
  classmethod constructors (#218).
- `remediation_transform_callbacks` on `HConfigDriverRules` (#180): drivers can
  transform the remediation config after diff computation, before it is
  returned by `WorkflowRemediation.remediation_config`.
- `RemediationPlugin` ABC (`hier_config.plugins`) and a `plugins` parameter on
  `WorkflowRemediation` (#181): users can package custom remediation
  transforms outside hier_config and apply them per workflow.
- Root-level duplicate children (#215): a `ParentAllowsDuplicateChildRule`
  with empty `match_rules` now applies to the root `HConfig`.
- `NegationRule` validates its per-strategy fields at construction time:
  `REPLACE` requires `use` and `REGEX_SUB` requires `search` (#220).
- Structured config format detection (#232): `HConfig.from_text()` rejects XML
  and JSON input with a clear `InvalidConfigError`; set-style configs remain
  natively supported via the JunOS, VyOS, and Nokia SRL driver preprocessors.
  Full XML/JSON ingestion is additive, post-4.0 roadmap work.
- Custom exception hierarchy: `HierConfigError` base, `DriverNotFoundError`,
  `InvalidConfigError`, `IncompatibleDriverError` (#219). `DuplicateChildError`
  reparented under `HierConfigError`.

### Changed

- Shared interface-view logic hoisted out of the five platform view files into
  concrete defaults on `ConfigViewInterfaceBase`, the capability mixins
  (parameterized by `_bundle_membership_prefix` / `_encapsulation_prefix`
  hooks), `HConfigViewBase`, and a new `parse_ipv4_interface()` helper in
  `hier_config.platforms.functions` — removing ~390 duplicated lines (#227).
- `WorkflowRemediation(plugins=...)` accepts any `Callable[[HConfig], None]`;
  `RemediationPlugin` instances are now callable (#181).
- The structured-format guard (#232) also covers the raw-`str` form of
  `HConfig.from_lines()`, inspects only a bounded prefix of the input, and
  `from_lines()`/`from_dump()` no longer route empty-tree construction through
  the full text-parsing pipeline.
- `HConfig` calls the `tree_algorithms` functions directly; the pass-through
  delegation shims on `HConfigBase` were removed (#217).
- Negation rules are unified into a single `NegationRule` model with a
  `NegationStrategy` enum — `REPLACE` (was `negate_with`), `DEFAULT` (was
  `negation_default_when`), and `REGEX_SUB` (was `negation_sub`) — in one
  ordered `negation` list on `HConfigDriverRules`; first matching rule wins
  (#220). `load_driver_rules()` still accepts the v2 dict keys.
- Tree algorithms (difference, remediation, future, with_tags) extracted from
  `HConfigBase` into `hier_config.tree_algorithms` as standalone functions;
  `HConfigBase` retains thin delegating methods (#217).
- `_load_from_string_lines()` refactored into a stateful `_ConfigTextLoader`
  parser class with focused banner/normalize/hierarchy methods (#186).
- Remediation right pass no longer allocates a probe `HConfigChild` for matched
  leaf lines, where the delta subtree is provably empty. Speeds up remediation
  of mostly-identical configs by ~30% and resolves the long-standing TODO in
  `_remediation_right()` (#191).
- `HConfigBase.__len__()` now counts descendants with a generator instead of
  materializing a tuple of every node, avoiding a large temporary allocation on
  big configuration trees (#188).
- `dot1q_mode_from_vlans()` is now a concrete static method on `HConfigViewBase`
  implementing the same semantics as `ConfigViewInterfaceBase.dot1q_mode`
  (`tagged_all` → `TAGGED_ALL`, tagged VLANs → `TAGGED`, untagged only →
  `ACCESS`); the per-platform `NotImplementedError` stubs were removed (#228).
- Changed `style` parameter on `indented_text()` and `RemediationReporter.to_text()` from `str` to `Literal["without_comments", "merged", "with_comments"]` via new `TextStyle` type alias (#189).
- Renamed `load_hconfig_v2_options` to `load_driver_rules` (#221).
- Renamed `load_hconfig_v2_tags` to `load_tag_rules` (#221).
- Renamed `tags_add()`/`tags_remove()` to `add_tags()`/`remove_tags()` (#216).
- Renamed `cisco_style_text()` to `indented_text()` (#216).
- Renamed `dump_simple()` to `to_lines()` (#216).
- Renamed `config_to_get_to()` to `remediation()` (#216).
- Converted `depth()` method to `depth` property (#216).

### Removed

- `get_hconfig()`, `get_hconfig_fast_load()`, `get_hconfig_from_dump()`, and
  `get_hconfig_fast_generic_load()` — replaced by the `HConfig.from_*`
  classmethods (#218). `get_hconfig_driver()` and `get_hconfig_view()` remain.
- `NegationDefaultWithRule`, `NegationDefaultWhenRule`, and `NegationSubRule`
  models and their `HConfigDriverRules` fields (#220).
- `HConfigChild.use_default_for_negation()` — subsumed by the unified
  negation rule evaluation (#220).
- Removed `HCONFIG_PLATFORM_V2_TO_V3_MAPPING` constant (#221).
- Removed `hconfig_v2_os_v3_platform_mapper()` function (#221).
- Removed `hconfig_v3_platform_v2_os_mapper()` function (#221).
- Removed `load_hconfig_v2_options_from_file()` function (#221).

### Fixed

- `port_number` no longer raises `ValueError` on slash-less interface names
  such as `Port-channel10`, `port-channel10`, `Bundle-Ether10`, and `Trk1`;
  it now derives from the letter-stripped `number` property on all platform
  views (IOS, EOS, NX-OS, XR, ProCurve).
- Fortinet FortiOS: hardened `swap_negation()` and `idempotent_for()` against
  `IndexError` on degenerate single-word commands, and documented that dropping
  parameters when negating (`set description "Port 1"` → `unset description`) is
  intentional FortiOS semantics (#225).

### v4 design decisions

- `HConfig.remediation()` stays public (#223): it was deliberately renamed
  from `config_to_get_to()` in #216 as the tree-level primitive;
  `WorkflowRemediation` remains the recommended workflow API and already
  validates driver compatibility (`IncompatibleDriverError`).
- Drivers remain declaratively-configured with sanctioned imperative
  extension points (#222): #220 removed the negation-related override needs;
  `idempotent_for()`, `negate_with()`, and `config_preprocessor()` stay
  overridable for logic that rules cannot express.
- Config trees stay mutable (#224): full immutability would break the
  callback/plugin mutation model for marginal benefit. The remediation
  algorithms are guaranteed (and now tested) not to mutate their input
  configs.

---

## [3.6.2] - 2026-07-13

### Fixed

- Cisco IOS-XR: the `indent_adjust` rule no longer misfires on the
  `template data timeout` and `template options timeout` leaves inside a
  `flow exporter-map` version block. Because no `end-template` follows these
  leaves, the parser previously nested every subsequent configuration line
  under them, silently collapsing the tree. Follow-up to #205 (#268).

---

## [3.6.1] - 2026-07-04

### Added

- Nokia SRL platform driver (`Platform.NOKIA_SRL`) (#245)

### Changed

- Renovate bot configuration (`.github/renovate.json`) to automate Poetry and
  GitHub Actions dependency updates, with weekly lock-file maintenance, grouped
  non-major updates, and immediate vulnerability alerts.

### Fixed

- Huawei VRP: parsing configs with multiple `peer-public-key` blocks no longer
  raises `DuplicateChildError`. The closing `peer-public-key end` line (printed
  at the same indent as the opening `rsa/dsa/ecc peer-public-key ...` line) is
  now nested under its opener via an `IndentAdjustRule` (#266).

- Collapsed VLAN lines can produce a destructive `no vlan x,y` remediation in Cisco IOS (#264, #265).

---

## [3.6.0] - 2026-03-26

### Added

- `TextStyle` type alias (`Literal["without_comments", "merged", "with_comments"]`) for
  the `style` parameter on `HConfigChild.cisco_style_text()` and
  `RemediationReporter.to_text()`, replacing the unconstrained `str` type (#189).

- Performance benchmarks for parsing, remediation, and iteration (#202).
  Skipped by default; run with `poetry run pytest -m benchmark -v -s`.

- Added support for Huawei VRP with a new driver and test suite (#238).

### Fixed

- `DuplicateChildError` raised when parsing IOS-XR configs with indented `!` section
  separators (e.g., ` !`, `  !`). The `per_line_sub` regex was changed from `^!\s*$`
  to `^\s*!\s*$` so bare `!` lines at any indentation level are stripped, restoring
  v3.4.2 behavior (#231).

- `__hash__` and `__eq__` inconsistency in `HConfigChild`: `__hash__` included
  `new_in_config` and `order_weight` but `__eq__` excluded them, and `__eq__` checked
  `tags` but `__hash__` did not, violating the Python invariant that `a == b` implies
  `hash(a) == hash(b)`. Both methods now use the same fields: `text`, `tags`, and
  `children` (#185).

---

## [3.5.0] - 2026-03-19

### Added

- Unused object detection framework: `UnusedObjectRule`, `ReferenceLocation` models,
  and `unused_objects()` method on `HConfig`. Not enabled in any driver by default —
  must be explicitly configured via driver extension or `load_hconfig_v2_options` (#15).
- IOS-XR comment preservation: `!` comment lines inside sections are now attached to
  the next sibling's `comments` set instead of being stripped. Top-level `!` delimiters
  and `#` comments are still removed (#30).
- Negation regex substitution: `NegationSubRule` model and `negation_sub` step in
  `negate()` for platform-specific negation transformations such as truncating
  SNMP user removal commands (#101).
- `unused_objects` and `negation_sub` processing in `load_hconfig_v2_options`.
- `post_load_callbacks` now run in `get_hconfig_fast_load` for consistency with
  `get_hconfig`.
- Idempotent command tests and improved `IdempotentCommandsRule` docstring (#61).
- `exit_text_parent_level` on `SectionalExitingRule` for IOS-XR `end-*` exit text
  rendered at parent indentation level (#130).
- `CLAUDE.md` for Claude Code guidance.

### Fixed

- IOS-XR: `DuplicateChildError` when parsing configs with multiple `group`
  blocks (#209).
- IOS-XR: Three tests updated for `exit_text_parent_level` indentation change.
- `pyproject.toml`: Closed author email brackets, removed duplicate pylint
  extension, fixed "Coverred" typos (#190).

---

## [3.4.3] - 2026-03-19

### Fixed

- IOS-XR: `DuplicateChildError` when parsing configs with multiple `group`
  blocks. Added `SectionalExitingRule` for `group` → `end-group` and a
  `PerLineSubRule` to indent `end-group` so it is treated as a section
  terminator rather than a standalone root-level child (issue #209).

---

## [3.4.2] - 2026-03-17

### Fixed

- IOS-XR: `DuplicateChildError` on nested `if/endif` blocks inside `route-policy`
  sections. Added a `parent_allows_duplicate_child` rule at depth 2
  (`route-policy` -> `if`) so duplicate `endif` children are permitted (issue #206).
- IOS-XR: `indent_adjust` rule for `template` incorrectly triggered on
  `template timeout` leaf parameters inside `flow exporter-map` blocks, corrupting
  indentation for all subsequent top-level sections. Narrowed the start expression
  with a negative lookahead (`(?!\s+timeout)`) to exclude leaf uses (issue #205).

---

## [3.4.1] - 2026-01-28

### Added

- `negation_negate_with` support in `load_hconfig_v2_options` utility, allowing
  v2-style option dictionaries to express custom negation strings when migrating
  to v3 drivers (issue #182).

### Changed

- Updated `poetry.lock` to resolve dependency version pins.

---

## [3.4.0] - 2026-01-10

### Added

- **Structural idempotency matching** — `_future()` now derives an identity key
  from a command's full lineage before comparing it against idempotency rules.
  This prevents unrelated lines that share a common prefix (e.g. distinct BGP
  neighbour descriptions) from being collapsed into a single entry during
  `future()` predictions.
- Fortinet FortiOS driver documentation.

### Fixed

- BGP neighbour descriptions with different peer addresses no longer merge into
  one entry when `future()` is called.
- Resolved issue #169.

### Changed

- Internal type annotations updated to PEP 604 union syntax (`X | Y`).

---

## [3.3.0] - 2025-11-05

### Added

- **Config view abstraction** — new `HConfigViewBase` and `ConfigViewInterfaceBase`
  abstract classes providing a structured, typed API over configuration trees
  without modifying the underlying `HConfig` objects.
- Platform-specific view implementations for Cisco IOS, Cisco NX-OS, Cisco IOS XR,
  Arista EOS, and HP ProCurve.

---

## [3.2.2] - 2025-01-14

### Changed

- Removed `snmp-server community` from built-in driver idempotency rules to
  avoid unintended matching across platforms.
- Linting and type annotation cleanup.

---

## [3.2.1] - 2024-12-19

### Fixed

- Corrected an incorrect parent assignment when building a delta subtree during
  `config_to_get_to()`, which could cause child nodes to appear under the wrong
  parent in the remediation output.

### Changed

- Updated `poetry.lock`.

---

## [3.2.0] - 2024-12-18

### Added

- **`RemediationReporter`** — aggregates remediation configs from multiple devices,
  exposing summary statistics, tag-based filtering, and JSON/CSV export (issue #34).

---

## [3.1.1] - 2024-12-11

### Added

- `py.typed` marker file, enabling downstream packages to perform PEP 561
  type-checking against hier_config without additional configuration.

---

## [3.1.0] - 2024-12-09

### Added

- `fast_load` utility for high-performance bulk config loading.
- `get_hconfig_from_dump` — reconstruct an `HConfig` tree from a serialised
  `Dump` object, enabling round-trip serialisation.
- HP ProCurve (Aruba AOSS) driver with post-load callbacks that normalise VLAN
  membership and port-access range expansion.
- HP Comware5 driver with `undo` negation prefix.

---

## [3.0.0] - 2024-11-18

### Breaking Changes

- **`Host` class removed.** The `Host` class that existed in v2 has been deleted.
  Use `get_hconfig(platform, config_text)` and `get_hconfig_driver(platform)`
  instead.
- **Driver system introduced.** OS-specific behaviour is now encoded in typed
  Pydantic driver classes (`HConfigDriverBase` subclasses) rather than plain
  dictionaries.  Each platform has a dedicated module under
  `hier_config/platforms/`.
- **Pydantic v2.** All internal models use Pydantic v2 (`model_config`,
  `ConfigDict`, etc.).  Third-party code that accessed internal model fields
  directly may need updating.
- **`options` / `hconfig_options` dictionaries removed.** Use driver classes
  with `HConfigDriverRules` instead.

### Added

- `get_hconfig(platform, text)` — primary constructor function.
- `get_hconfig_driver(platform)` — retrieve a standalone driver instance.
- `hier_config.utils` — migration helpers including `load_hconfig_v2_options`
  to convert v2 option dicts to v3 driver rule objects.
- `WorkflowRemediation` — replaces the old `Host`-level remediation API.
- Fortinet FortiOS driver.
- Juniper JunOS driver (experimental, set/delete syntax).
- VyOS driver (experimental, set/delete syntax).
- `Platform` enum for type-safe platform selection.

### Changed

- All rule definitions now use immutable Pydantic models (`MatchRule`,
  `SectionalExitingRule`, `IdempotentCommandsRule`, etc.).
- `HConfig` and `HConfigChild` now use `__slots__` for lower memory overhead.

---

[Unreleased]: https://github.com/netdevops/hier_config/compare/v3.6.0...HEAD
[3.6.0]: https://github.com/netdevops/hier_config/compare/v3.5.1...v3.6.0
[3.5.1]: https://github.com/netdevops/hier_config/compare/v3.5.0...v3.5.1
[3.5.0]: https://github.com/netdevops/hier_config/compare/v3.4.3...v3.5.0
[3.4.3]: https://github.com/netdevops/hier_config/compare/v3.4.2...v3.4.3
[3.4.2]: https://github.com/netdevops/hier_config/compare/v3.4.1...v3.4.2
[3.4.1]: https://github.com/netdevops/hier_config/compare/v3.4.0...v3.4.1
[3.4.0]: https://github.com/netdevops/hier_config/compare/v3.3.0...v3.4.0
[3.3.0]: https://github.com/netdevops/hier_config/compare/v3.2.2...v3.3.0
[3.2.2]: https://github.com/netdevops/hier_config/compare/v3.2.1...v3.2.2
[3.2.1]: https://github.com/netdevops/hier_config/compare/v3.2.0...v3.2.1
[3.2.0]: https://github.com/netdevops/hier_config/compare/v3.1.1...v3.2.0
[3.1.1]: https://github.com/netdevops/hier_config/compare/v3.1.0...v3.1.1
[3.1.0]: https://github.com/netdevops/hier_config/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/netdevops/hier_config/compare/v2.x.x...v3.0.0
