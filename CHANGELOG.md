# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

v4 design decisions, for the record:

- `HConfig.remediation()` stays public (#223): it was deliberately renamed
  from `config_to_get_to()` in #216 as the tree-level primitive;
  `WorkflowRemediation` remains the recommended workflow API and already
  validates driver compatibility (`IncompatibleDriverError`).
- Drivers remain declaratively-configured with sanctioned imperative
  extension points (#222): #220 removed the negation-related override needs.
  `config_preprocessor()` stays freely overridable. The Rust core now resolves
  `idempotent_for()`, `negate_with()`, `sectional_exit()`, and
  `swap_negation()` itself, so those four hooks no longer exist on
  `HConfigDriverBase` and defining one raises `TypeError`.
- Config trees stay mutable (#224): full immutability would break the
  callback/plugin mutation model for marginal benefit. The remediation
  algorithms are guaranteed (and now tested) not to mutate their input
  configs.

### Changed

- The config view layer is now implemented entirely in Rust and exposed through
  PyO3. `hier_config/platforms/view_base.py` and every platform `view.py` are
  facades over the native `HConfigView` / `ConfigViewInterface` classes,
  removing ~1,300 lines of duplicated Python and the `testdata/views/`
  anti-drift corpus that existed only to pin the two implementations together.
  `HConfigViewBase` and `ConfigViewInterfaceBase` remain as aliases, the
  per-platform view classes keep their names, and the capability-marker
  `isinstance()` protocol from #227 is preserved via `ViewMarkerMeta`, which
  answers from the native `capabilities` data.
- **Breaking:** three view properties that raised in v3 now return a value:
  `nac_max_dot1x_clients` / `nac_max_mab_clients` return `None` instead of
  raising `NotImplementedError` (Cisco IOS, Aruba AOS-CX); `module_number`
  returns `None` instead of raising `AttributeError` (Arista EOS, Cisco NX-OS,
  Cisco XR); and `bundle_member_interfaces` returns `()` instead of raising on a
  non-trunk interface (HP ProCurve). Replace `try`/`except` with a falsy check.
- Structured-format conversions are now implemented in Rust. `from_json()`,
  `to_json()`, `from_xml()`, `to_xml()`, `hconfig_to_netconf_xml()`, and
  `hconfig_to_gnmi_json()` moved from `hier_config/formats.py` into
  `hier_config_core::formats`; the Python module is now a thin, documented
  wrapper. This removes the last inverted dependency in which the Rust
  `WorkflowRemediation` bindings imported `hier_config.formats` back through
  the interpreter, so NETCONF/gNMI rendering is available to pure-Rust
  consumers. Behavior is pinned by a 385-case parity corpus
  (`testdata/formats/expected.json`) generated from the previous Python
  implementation.
- `InvalidConfigError` is now defined in the extension module and re-exported
  from `hier_config.exceptions`. Importing it from `hier_config.exceptions`
  (the documented path) is unchanged.
- `WorkflowRemediation` remediation and rollback trees are now lazily cached via
  `std::sync::OnceLock` in both `hier_config_core` and `hier_config_py`, converting
  query methods and properties to take `&self`. This allows lock-free immutable
  access across threads in Rust and eliminates runtime PyO3 `BorrowMutError`
  under concurrent property access from Python.
- Parser state accumulators are now encapsulated into `ParserState`,
  `ParserCursor`, and `IndentTracker` in `hier_config_core::parser`, eliminating
  mutable cross-function parameter threading. Pure transactional tree constructors
  (`parse_tree`, `parse_tree_with_callbacks`, `parse_fast`, `parse_fast_with_callbacks`)
  build and return complete trees without requiring caller-allocated mutable instances.
- Tree traversals in `hier_config_core` now provide zero-allocation, stack-based
  pre-order depth-first iterators (`Tree::descendants` and `Tree::descendants_sorted`),
  replacing recursive out-parameter vector accumulation (`collect_all_children`).
  `Tree::node_count` provides $O(1)$ sizing on root nodes and zero-allocation
  descendant counting on subtrees, which powers `HConfigBase.__len__()` without
  allocating intermediate vectors or Python object handles.
- Remediation and diffing engine internal state is now encapsulated in `RemediationContext`,
  `FutureContext`, and `DiffTrees` in `hier_config_core::remediation`, eliminating
  loose mutable parameters passed across recursive helpers.
- Vendor-specific platform logic (sectional exits, negation swapping, preprocessors,
  and post-load callbacks) has been refactored behind a unified `PlatformOps` trait
  and localized strictly within each platform's `platforms/<platform>/mod.rs` module.
- Core tree and workflow domain logic (`Tree::merge`, `Tree::with_tags`, `Tree::add_ancestor_copy_of`,
  `Tree::add_ancestor_copy_within`, `Tree::from_json`, `Tree::from_xml`,
  `WorkflowRemediation::remediation_netconf_xml`, and `WorkflowRemediation::remediation_gnmi`)
  is now natively implemented in `hier_config_core`, enabling full standalone use from Rust
  without Python or PyO3 dependencies.

### Fixed

- `from_json()` / `from_xml()` no longer silently de-duplicate repeated list
  entries. Duplicates raise `DuplicateChildError` as documented, and the error
  type survives the Rust boundary instead of being flattened to
  `InvalidConfigError`.
- Keyword arguments documented in the type stubs are accepted again.
  `tags_add()`, `tags_remove()`, `add_tags()` and `remove_tags()` took
  `tag_or_tags` at runtime while the stubs promised `tag`, and
  `get_child_deep()` / `get_children_deep()` took `rules` while the stubs
  promised `match_rules`. Calling them by keyword as documented raised
  `TypeError` despite type checking cleanly. The native signatures now match
  the published names.
- Two type stubs contradicted the objects they describe, found by the new
  return-type check. `HConfigBase.all_children_sorted()` was declared
  `Iterator[HConfigChild]` but returns an eager sequence, so the documented
  `next(...)` raised `TypeError: 'tuple' object is not an iterator`; it is now
  `Sequence[HConfigChild]`, matching its `all_children_sorted_by_tags`
  sibling. `ConfigViewInterface.poe` was declared `bool` but is
  `Option<bool>` in the core and returns `None` on EOS, NX-OS and XR; it is
  now `bool | None`.
- Idempotency checks in `future()` (`Tree::idempotent_for`, `Tree::base_idempotent_for`,
  `Tree::is_idempotent_command`, and FortiOS declaration checks) now fall back to the
  counterpart tree's driver rules when the delta/change tree is generic, preventing
  `future()` from ignoring source platform idempotency rules and retaining duplicate
  commands when applied against generically loaded configurations.
- `_hier_config_rust.pyi` is now provided at repository root and guarded by
  `scripts/gen_stubs.py --check` in sync with `stubs/_hier_config_rust.pyi`, enabling
  maturin to bundle `_hier_config_rust/__init__.pyi` directly into published wheels for
  consumer IDE and type checker resolution.

### Added

- The lint gate now fails on type-stub and corpus drift.
  `scripts/gen_stubs.py --check` additionally diffs the live
  `_hier_config_rust` surface against `stubs/_hier_config_rust.pyi`, so a new
  `#[pyfunction]` or `#[pyclass]` that is not declared in the stub — which
  would silently degrade every caller to `Unknown` under pyright strict — is
  caught in CI, as is a `#[getter]` or `#[pymethod]` added to an existing
  `#[pyclass]` without a matching stub member. `scripts/gen_formats_corpus.py
  --check` joins it to keep the formats parity corpus honest.
- `mypy.stubtest` now runs in the lint gate (`python scripts/build.py
  stubtest`), comparing every `.pyi` stub against the object it actually
  describes. The name-level guards above cannot see *signatures*, so a stub
  could promise a parameter the compiled extension rejects — code that type
  checks but raises `TypeError`. Audited, documented exemptions for pydantic,
  PyO3 enum and sentinel-default idioms live in
  `stubs/stubtest-allowlist.txt`; unused entries fail, so the list cannot rot.
  Return and parameter *type* annotations remain outside its reach — they are
  not introspectable from a compiled extension.
- `scripts/check_stub_types.py` now runs in the lint gate, closing the
  return-type half of that gap. Because annotations cannot be read back from a
  compiled extension, the stub is the type checkers' *premise* rather than
  something they verify: rewriting `vlan_ids -> frozenset[int]` as
  `dict[str, bytes]` changes the pyright strict error count by zero. The
  script instead exercises each declared member against a corpus of real
  configs and checks the observed value against its annotation, descending
  into container element types. Generating the stub from Rust would not help
  — 30% of exported methods return an opaque `PyObject`, so `vlans`,
  `stack_members` and `ipv4_default_gw` share one Rust signature and three
  Python types — and it found the two stub bugs above on its first run.
  Parameter types remain unverifiable by construction and stay the type
  checkers' responsibility. A member whose every observed value is empty is
  reported as unobserved rather than failed — an empty container cannot
  contradict an element type — so the set of unobserved members is pinned in
  `stubs/unobserved-allowlist.txt`. An unlisted gap and a stale entry both
  fail, which stops a newly added stub member from arriving with no
  verification at all and stops an entry outliving the gap it documents.

### Removed

- Dead driver algorithm. `HConfigDriverBase.idempotent_for()`,
  `negate_with()`, `sectional_exit()`, and `swap_negation()` — plus the private
  `_idempotency_key()` machinery and the `@core_owned` escape hatch for
  overriding them — are gone. The Rust core resolved all four from rule data
  and never called the Python implementations, so ~560 lines of unreachable
  code shadowed the real behavior. Defining any of the four on a subclass now
  raises `TypeError`. Rule data (`rules.negation`, `rules.negate_with`,
  `rules.idempotent_commands`, `rules.sectional_exiting`) and the
  `negation_prefix` / `declaration_prefix` properties are unchanged and remain
  the supported way to shape these behaviors.

### Added

- Stub-freshness gate. `python scripts/build.py check-stubs` (also wired into
  `lint` and `lint-and-test`) runs `scripts/gen_stubs.py --check` and fails when
  the committed `hier_config/{base,child,children,root}.pyi` stubs no longer
  match the compiled extension. The generator already supported `--check`, but
  nothing invoked it, so the type information mypy and pyright rely on could
  drift from the native surface without any test noticing.
- Rust core. Parsing, the tree, post-load fixups, and the remediation engine
  are implemented in Rust (`crates/`) and exposed through PyO3 as the
  `_hier_config_rust` extension. There is no pure-Python fallback, so
  hier_config now ships as a compiled wheel rather than a pure-Python one.
  Wheels are published for Linux (x86_64, aarch64), macOS, and Windows on
  CPython 3.10-3.14; other targets build from source and need a Rust
  toolchain. Behavior is covered by a shared JSON case corpus under
  `testdata/cases/` that both the Rust and Python suites execute, so the two
  implementations cannot silently diverge. See
  [Rust core behavior changes](docs/user/rust-core-changes.md) for the full
  list of differences and
  [Performance & Benchmarks](docs/dev/benchmarks.md) for measurements.
- Standalone Rust usage. `hier_config_core` is now usable as a plain Rust
  crate with no Python interpreter involved: the built-in drivers already
  embed their rules as JSON in Rust, and a native view layer
  (`crates/hier_config_core/src/view/`) plus one-call constructors
  (`config_from_text`, `config_view`) complete the surface. Views are ported
  for the six platforms that have a Python `view.py`
  (Arista EOS, Aruba AOS-CX, Cisco IOS, Cisco NX-OS, Cisco XR, HP ProCurve)
  using traits with default method bodies, so a platform implements only what
  its Python sibling overrides. **The Python view layer is unchanged.** The two
  are pinned together by a shared corpus under `testdata/views/` that is
  generated from Python and asserted from both sides, so neither can drift.
  See [Native view divergences](docs/user/rust-core-changes.md) for the
  handful of properties where Rust returns `None` instead of raising.
- `core_owned` decorator on `hier_config.platforms.driver_base`. It marks a
  driver member whose behavior the Rust core owns, in two places: a post-load
  callback the core already runs (so the Python copy is skipped rather than
  applied twice), and an override of one of the three engine-resolved hooks
  above (so the guard lets the definition through). The marker is a
  declaration, not a switch — it never causes the core to call the Python
  implementation.

- Permanent v3 API compatibility (#300). Every v3 name that v4 renamed or
  removed is restored as a thin delegation to its v4 counterpart, with no
  `DeprecationWarning` and no planned removal: the `get_hconfig*()`
  constructors, `config_to_get_to()`, `dump_simple()`, `cisco_style_text()`,
  `tags_add()`/`tags_remove()`, `use_default_for_negation()`,
  `load_hconfig_v2_options()`, `load_hconfig_v2_tags()`,
  `load_hconfig_v2_options_from_file()`, `HCONFIG_PLATFORM_V2_TO_V3_MAPPING`,
  `hconfig_v2_os_v3_platform_mapper()`, `hconfig_v3_platform_v2_os_mapper()`,
  and the `NegationDefaultWithRule` / `NegationDefaultWhenRule` /
  `NegationSubRule` models together with their `HConfigDriverRules` fields.
  Those fields stay live: passing them to the constructor and appending to them
  afterwards both take effect, so `driver.rules.negate_with.append(...)` — the
  idiom v3's custom-driver docs teach — behaves as it did in v3. Documented in
  `docs/user/v3-compatibility.md`. The `depth` property, the typed exceptions,
  and the completed EOS/NX-OS/XR views remain behavior changes.
- `HConfigDriverRules.all_negation_rules()` resolves the unified `negation`
  list together with the v3 negation fields on every lookup (#300). Nothing is
  folded in at validation, so re-validating a rules model never duplicates
  rules.
- v3-to-v4 integration tests (#300): `tests/integration/v3_scenarios.py`
  mirrors `nautobot_golden_config.models._get_hierconfig_remediation` and runs
  under both major versions. `tests/integration/test_v3_baseline.py` compares
  v4 against a committed v3.7.0 recording on every push, and
  `tests/integration/test_v3_differential.py` (marker `v3_differential`,
  deselected by default) diffs against a live v3 install. Regenerate the
  recording with `./scripts/generate_v3_baseline.py`.
- `notify ecosystem` workflow (`.github/workflows/notify-ecosystem.yml`): on
  release publish, sends a `repository_dispatch` to netdevops/hier-config-ci
  so the downstream app ecosystem (hier-config-gpt, -api, -mcp, -cli) is
  released against the new hier_config version automatically.
- Admin-only `prepare release` workflow (`.github/workflows/prepare-release.yml`):
  run from any branch with a major/minor/patch/prerelease bump choice, it bumps
  the version, rotates `CHANGELOG.md` (`scripts/rotate_changelog.py`, skipped
  for prereleases), opens a `chore(release): prepare X.Y.Z` PR, and creates a
  draft GitHub release. The PyPI deploy workflow now triggers on release
  `published` (not `created`) so publishing a draft deploys it.
- `HConfig.future_with_report()` returns the predicted future config together
  with a frozen `FutureReport` listing unresolved negations (negations that
  matched nothing in the running config) and idempotency-tracked negation
  replacements, so change-validation pipelines can assert
  `not report.unresolved_negations` instead of grepping the render for
  `no ` lines (#285).
- Migration guide for v3 → v4 upgrades (`docs/user/migrating-from-v3.md`):
  rename tables for constructors, methods, and utilities, the unified
  negation rule mapping, exception and config-view changes, and behavior
  changes to review.
- `HConfig.future(..., prune_empty_branches=True)` removes sections that a
  change emptied out — matching devices that prune empty stanzas on commit —
  while keeping sections that were already empty (#269).
- `.github/workflows/claude-review.yml`: a GitHub Actions workflow that runs
  the in-repo `hier-config-review` skill against every pull request through
  `anthropics/claude-code-action` and posts the findings as a PR comment. The
  job installs the poetry and docs environments first, so the skill's lint,
  test, and `mkdocs build --strict` gates run for real. It is skipped for draft
  and fork pull requests, where `CLAUDE_CODE_OAUTH_TOKEN` is unavailable.
- Aruba AOS-CX platform support (`Platform.ARUBA_AOSCX`): a new driver and
  config view covering AOS-CX's Cisco/EOS-like hierarchical CLI. Because
  `vlan trunk allowed` is additive on AOS-CX rather than declarative, collapsed
  unnamed VLAN headers (`vlan 1,10`) and comma/range trunk lists are split into
  one VLAN per line via `post_load_callbacks`, so remediation adds a missing
  VLAN with `vlan trunk allowed <id>` and removes an extra one with
  `no vlan trunk allowed <id>`. All other sections, including `evpn` and
  `interface vxlan`, are remediated with the standard rule framework. (#289)
- Guidance for AI-assisted contributions: `AGENTS.md` as the canonical
  statement of repo standards, a `hier-config-review` Claude Code skill
  (`.claude/skills/`) that self-reviews a change set against those standards,
  GitHub Copilot review instructions (`.github/copilot-instructions.md`), and
  a pull request template with a self-review checklist (#290).
- Two more Claude Code skills: `hier-config-new-driver` scaffolds in-tree
  platform driver support (characterization checklist, TDD test and driver
  templates, registration and documentation steps), and
  `hier-config-troubleshoot` diagnoses unexpected library behavior via a
  symptom-to-rule table covering negation, idempotency, indentation,
  `DuplicateChildError`, sectional rules, ordering, and `future()` limits
  (#290).
- New developer and maintainer documentation: testing conventions, code style
  and standards, the release process, and CI/infrastructure notes (#290).
- NETCONF `edit-config` remediation rendering (#232):
  `WorkflowRemediation.remediation_netconf_xml()` (and
  `hier_config.formats.hconfig_to_netconf_xml()`) render a remediation
  between `HConfig.from_xml()` trees as a NETCONF payload — deletions become
  `nc:operation="delete"` elements (keyed list entries delete by their key
  leaf, resolved against the running config), additions use the default merge
  operation, and attribute-level changes raise `InvalidConfigError`.
- gNMI-style JSON remediation rendering (#287):
  `WorkflowRemediation.remediation_json()` (and
  `hier_config.formats.hconfig_to_gnmi_json()`) render a remediation between
  `HConfig.from_json()` trees as a gNMI-SetRequest-style structure — added
  and changed values render into an `update` object (modified keyed list
  entries keep their identity leaf), negations become xpath-ish `delete`
  paths with `[key=value]` selectors resolved against the running config,
  and attribute-level changes raise `InvalidConfigError`.

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
- Custom exception hierarchy: `HierConfigError` base, `DriverNotFoundError`,
  `InvalidConfigError`, `IncompatibleDriverError` (#219). `DuplicateChildError`
  reparented under `HierConfigError`.

### Changed

- Build and release moved from poetry to maturin. `pyproject.toml` uses PEP
  621 metadata with a PEP 735 `dev` dependency group; `poetry.lock` is gone.
  Contributors need a Rust toolchain and must run `maturin develop --release`
  before the Python suite will see a change under `crates/`.
- `all_children_sorted()` returns a tuple rather than a generator, matching
  `all_children_sorted_by_tags()` and `HConfig.unused_objects()`. Sorting has to
  see the whole tree before it can yield anything, so the generator bought no
  laziness and cost a Python frame per node; a full walk is now about six times
  faster. `all_children()` is still a generator. Iteration and comprehension are
  unaffected; only code that called `.send()`/`.close()` on the result breaks.
- `HConfig.from_dump()` runs a driver's remediation-transform callbacks after
  the tree is fully built rather than incrementally during the load, so a
  callback observes the complete config. Callbacks that relied on seeing a
  partially-loaded tree will behave differently.

- Restructured the documentation into User, Administrator, and Developer
  guides (`docs/user/`, `docs/admin/`, `docs/dev/`) with a rewritten landing
  page, new pages for loading configurations and remediation workflows, and
  content refreshed for the v4 API.
- Old readthedocs.io URLs (both the original flat layout and the 3.7 `user/`
  layout) keep working via the mkdocs-redirects plugin; CLAUDE.md was slimmed
  to an overlay that imports `AGENTS.md` (#290).
- Built-in driver post-load callbacks are now public functions exported from
  their driver modules (e.g. `remove_ipv4_acl_remarks` in
  `hier_config.platforms.cisco_ios.driver`), so a built-in callback can be
  removed by identity with `rules.post_load_callbacks.remove(...)` (#286).
- The driver registry is keyed internally on canonical uppercase platform
  names; `Platform` members are converted via their names at the boundary, so
  a member and its name are fully interchangeable in `register_driver`,
  `unregister_driver`, and `get_hconfig_driver`. `get_registered_platforms()`
  returns `Platform` members for enum-known names and uppercase strings for
  custom names (#284).
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
  (#220). `load_driver_rules()` still accepts the v2 dict keys, and the three
  v3 fields remain live on `HConfigDriverRules` (#300).
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
- Renamed `load_hconfig_v2_options` to `load_driver_rules`; the v3 name is retained (#221).
- Renamed `load_hconfig_v2_tags` to `load_tag_rules`; the v3 name is retained (#221).
- Renamed `tags_add()`/`tags_remove()` to `add_tags()`/`remove_tags()`; the v3 names are retained (#216).
- Renamed `cisco_style_text()` to `indented_text()`; the v3 name is retained (#216).
- Renamed `dump_simple()` to `to_lines()`; the v3 name is retained (#216).
- Renamed `config_to_get_to()` to `remediation()`; the v3 name is retained (#216).
- Converted `depth()` method to `depth` property (#216). This is the one rename with no compatibility alias; call sites must drop the parentheses.

### Removed

- The Python config-text loader. `HConfig.from_text()` and `from_lines()` now
  parse in the core; the Python parsing path they replaced is gone. This is
  internal, but a subclass that overrode a loader helper no longer has an
  effect.
- The unfinished native view subsystem. Config views are Python-only, as they
  were in v3 — see `hier_config/platforms/*/view.py`.

Every name previously listed under this heading — `get_hconfig()`,
`get_hconfig_fast_load()`, `get_hconfig_from_dump()`,
`get_hconfig_fast_generic_load()`, `HConfigChild.use_default_for_negation()`,
the three v3 negation rule models and their `HConfigDriverRules` fields,
`HCONFIG_PLATFORM_V2_TO_V3_MAPPING`, `hconfig_v2_os_v3_platform_mapper()`,
`hconfig_v3_platform_v2_os_mapper()`, and `load_hconfig_v2_options_from_file()`
— is retained as a permanent, supported compatibility surface (#300). See the
`### Added` entry above.

### Fixed

- Documentation gap sweep: repaired doc examples that no longer ran or showed
  wrong output (getting-started fixture path, tags filtering, the custom ACL
  remediation `delete()` idiom, config-view and hierarchical-JunOS outputs);
  removed the stale prerelease pin from the install page and added `--pre` to
  the README install; propagated Aruba AOS-CX into the architecture and
  config-view docs; documented the built-in post-load callbacks, the formats
  module, `future_with_report()`, and the view data models in the API
  reference and glossary; corrected agent instruction files (branching
  strategy in `AGENTS.md`, the `HConfigDriverRules` mutable-list carve-out,
  review-skill diff base, registry key format, CI Python matrix) and the
  benchmarks per-file lint-ignore path (#297).
- Registering a driver under a `Platform` member's *value* string (e.g. `"3"`,
  the value of `Platform.CISCO_IOS`) no longer silently overwrites that
  platform's built-in registry entry, and value strings no longer resolve in
  platform lookups — platforms are identified by name (#284).
- `future()` negation edge cases (#269): a negation whose positive form exists
  in the running config now removes it without surviving as a literal `no ...`
  child (evaluated before the idempotency rules, which can match the negation
  line itself); shorthand negations (`no description`) remove the valued lines
  they match, as devices do. Negations matching nothing are still kept as a
  did-not-apply-cleanly signal, and idempotency-tracked negated forms (e.g.
  IOS `no logging console`) still replace their counterpart and persist.
- XML ingestion keys an element whenever an identifying `list_keys` child
  exists, not only when the tag repeats among siblings, so configs with
  different list-entry counts diff surgically instead of deleting and
  re-adding surviving entries (#232).
- `port_number` no longer raises `ValueError` on slash-less interface names
  such as `Port-channel10`, `port-channel10`, `Bundle-Ether10`, and `Trk1`;
  it now derives from the letter-stripped `number` property on all platform
  views (IOS, EOS, NX-OS, XR, ProCurve).
- Fortinet FortiOS: hardened `swap_negation()` and `idempotent_for()` against
  `IndexError` on degenerate single-word commands, and documented that dropping
  parameters when negating (`set description "Port 1"` → `unset description`) is
  intentional FortiOS semantics (#225).

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
