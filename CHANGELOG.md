# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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

[Unreleased]: https://github.com/netdevops/hier_config/compare/v3.4.1...HEAD
[3.4.1]: https://github.com/netdevops/hier_config/compare/v3.4.0...v3.4.1
[3.4.0]: https://github.com/netdevops/hier_config/compare/v3.3.0...v3.4.0
[3.3.0]: https://github.com/netdevops/hier_config/compare/v3.2.2...v3.3.0
[3.2.2]: https://github.com/netdevops/hier_config/compare/v3.2.1...v3.2.2
[3.2.1]: https://github.com/netdevops/hier_config/compare/v3.2.0...v3.2.1
[3.2.0]: https://github.com/netdevops/hier_config/compare/v3.1.1...v3.2.0
[3.1.1]: https://github.com/netdevops/hier_config/compare/v3.1.0...v3.1.1
[3.1.0]: https://github.com/netdevops/hier_config/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/netdevops/hier_config/compare/v2.x.x...v3.0.0
