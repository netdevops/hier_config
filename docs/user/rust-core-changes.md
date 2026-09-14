# Rust core behavior changes

hier_config **4.0** replaces the pure-Python engine with Rust and PyO3 in the
existing repository and Python distribution. This is not a v5 release or a
separate project. The familiar tree/driver/workflow concepts remain, but the
rewrite is **not a drop-in replacement for every Python API**.

Read [Migrating from v3](migrating-from-v3.md) for the earlier v4 renames and
[v3 compatibility](v3-compatibility.md) for the explicitly retained aliases.
An alias commitment is not a promise that every undocumented helper or Python
object protocol remains identical. This page lists the additional migration
work required by the native implementation.

## Installation and packaging

The build backend is maturin. `Cargo.toml` supplies the package version.
Compatible CPython 3.10+ `abi3` wheels need no Rust toolchain; sdist and checkout
builds require Python 3.10+, a linker, and the Rust MSRV in `Cargo.toml`
(currently 1.98). There is no pure-Python fallback.
See [Installation](install.md) for wheel targets and source-build commands.

`pydantic` is the only required Python runtime dependency. YAML file helpers
require `pip install --pre 'hier-config[yaml]'`. Importing the library and
loading rule dictionaries do not require PyYAML; YAML calls without it raise
an `ImportError` with installation instructions.

## Custom drivers

### Hook support matrix

| Extension point | v4 behavior |
| --- | --- |
| `_instantiate_rules()` | Supported; returns `HConfigDriverRules` |
| `negation_prefix`, `declaration_prefix` | Supported properties |
| Mutable rule collections | Supported, including retained v3 negation lists |
| `post_load_callbacks` | Supported; built-in native callbacks are not applied twice |
| `remediation_transform_callbacks`, workflow plugins | Supported Python transforms |
| Custom `config_preprocessor()` | Removed override hook; defining one raises `TypeError` at class creation |
| `idempotent_for()`, `negate_with()`, `sectional_exit()`, `swap_negation()` | Removed; defining an override raises `TypeError` when the class is created |

The five removed override hooks are **not silently ignored**:
`HConfigDriverBase.__init_subclass__()` rejects them. The core resolves the four
negation/idempotency/exiting hooks from rule data and prefixes; custom text
preprocessing must happen explicitly before construction. Remove those
overrides before importing the custom driver. The private helpers
`_idempotent_for_helper()`, `_negation_negate_with_helper()`, and
`_idempotency_key()` are also removed.

### Selecting native platform operations

The public `platform` class attribute selects native vendor operations:

```python
from typing import ClassVar

from hier_config import HConfigDriverBase, HConfigDriverRules, Platform
from hier_config.platforms.driver_base import load_platform_rules


class CustomIOS(HConfigDriverBase):
    platform: ClassVar[Platform] = Platform.CISCO_IOS

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return load_platform_rules(Platform.CISCO_IOS)
```

Subclassing a built-in driver inherits its selector. Without a selector, a
custom driver uses Generic native operations, even if its registry name
resembles a vendor or its rules were loaded from a built-in platform. Explicit
rules, prefixes, and callbacks still apply; vendor-specific parsing and fixups
are not inferred from the class name. Use Generic for genuinely new syntax,
or select a built-in platform whose native behavior you intend to inherit.
An invalid explicit `platform` selector raises `ValueError`; it does not
silently fall back to Generic.

### Migrating removed hooks

Use `IdempotentCommandsRule` for `idempotent_for()`,
`SectionalExitingRule` for `sectional_exit()`, and negation rules for
`negate_with()`. For example:

```python
from hier_config.models import MatchRule, NegationDefaultWithRule

driver.rules.negate_with.append(
    NegationDefaultWithRule(
        match_rules=(MatchRule(re_search=r"^(tacacs-server host \S+) .*$"),),
        use=r"no \1",
    )
)
```

`swap_negation()` derives its behavior from the negation/declaration prefixes.
Regex compatibility depends on whether the rule needs captures or only a
boolean match. See the boundary below before migrating custom patterns.

### Regex compatibility boundary

Python replacement-template semantics are preserved for per-line/full-text
substitutions and negation `REGEX_SUB`: numbered/named captures, literal dollar
signs, escaped backslashes, common escapes and octal escapes. Invalid or
malformed group references raise errors even if the pattern finds no match.
`REGEX_SUB` replaces all occurrences, as `re.sub`
does by default, rather than just the first match.

This is **not complete Python regex-pattern compatibility**. Capture-producing
patterns used in substitutions, negation templates, idempotency keys and
unused-object name/reference extraction must use the Rust `regex` syntax subset.
Lookarounds, pattern backreferences and Python's `\Z` are unsupported there
and raise contextual errors rather than being silently ignored. Python API
callers receive `ValueError` for these invalid/unsupported rule patterns.
Move unsupported text transformations into explicit preprocessing or rewrite
the affected rule without changing its intended matching behavior.

Matching-only `MatchRule` and indentation checks can use a bounded
`fancy-regex` fallback for richer patterns; its execution-limit failures are
also errors, not false matches. A pattern accepted for boolean matching can
therefore still be rejected when a rule needs its captured groups.

Standalone Rust consumers loading dynamic rules should use fallible APIs:
`Driver::try_compute_negation()`, `Driver::try_idempotency_key()`,
`try_negate_with()`, `try_unused_objects()`, and `try_is_object_referenced()`.
Their infallible convenience counterparts may panic on invalid rule regexes.

### Text preprocessing and callbacks

Move a custom `config_preprocessor()` out of the driver and call it explicitly
before `HConfig.from_text()`:

```python
from hier_config import HConfig, Platform


def preprocess_config(config_text: str) -> str:
    return config_text.replace("hostname old-router", "hostname new-router")


config = HConfig.from_text(
    Platform.CISCO_IOS, preprocess_config("hostname old-router")
)
```

This explicit step runs **before** the constructor's full-text substitutions,
unlike the former override hook. Review order-dependent transformations.
Built-in platform preprocessing still runs natively for text constructors;
stock `config_preprocessor()` methods remain callable helpers, explicitly
marked `core_owned`, not Python override dispatch points. The marker is not a
supported way to make a custom override execute. Fast line loading bypasses
full-text/native platform preprocessing. A `per_line_sub` rule or post-load
callback may be more appropriate for line/tree edits.

`core_owned` also marks built-in post-load callback implementations already
executed natively so they are not applied twice. It does not enable the four
other removed hooks or cause the engine to call arbitrary Python overrides.

**Callback ordering differs from the pure-Python implementation.** Enabled
stock platform callbacks run natively before additive Python post-load
callbacks. Custom Python callbacks retain their relative list order, but
inserting one at index zero does not make it run before stock normalization.
If a transformation must precede native parsing or normalization, apply it
explicitly to the input text before calling the constructor.

### Rule construction and errors

`_instantiate_rules()` remains a static method, but is concrete rather than
abstract; the base implementation raises `NotImplementedError` when a driver
without an implementation is initialized. Invalid rule serialization raises
instead of silently selecting stock rules.

## Python API migration

### Descendants and removed helpers

`all_children()` was renamed to **`descendants()`**, with no `all_children`
alias. Update recursive walks:

```python
for child in config.descendants():
    print(child.text)
```

`config.children` still means direct children. `len(config)` counts all
descendants; `len(config.children)` counts only direct children.

The following construction and implementation helpers were removed:

| Removed surface | Replacement |
| --- | --- |
| `HConfigChildren()` direct construction | Use `config.children` or `child.children` |
| `HConfigChild.instantiate_child()` | Use a parent's `add_child()` |
| `tree_algorithms.compute_remediation()` | `source.remediation(target)` |
| `tree_algorithms.compute_difference()` | `source.difference(target)` |
| `tree_algorithms.compute_future()` | `source.future(changes)` |
| `tree_algorithms.compute_future_with_report()` | `source.future_with_report(changes)` |
| `tree_algorithms.compute_with_tags()` | `source.with_tags(tags)` |
| `tree_algorithms.prune_emptied_branches()` | `source.future(changes, prune_empty_branches=True)` |

`hier_config.tree_algorithms` retains `FutureReport`, not the six algorithm
functions. Code importing those functions must migrate even though the module
itself still imports.

### Traversal return types

Consult the shipped stubs for the precise iterator versus collection contract
of each method. The native boundary preserves these method-specific contracts:

| Surface | v4 return contract |
| --- | --- |
| `get_children()`, `get_children_deep()`, `lineage()` | Iterator; supports `next(...)` |
| `path` | Iterator; supports `next(...)` |
| `unified_diff()` | Iterator; supports `next(...)` |
| `all_children_sorted()`, `all_children_sorted_by_tags()` | Tuple; use `iter(...)` before `next(...)` |

An iterator need not be a Python generator or a live view of later mutations.
An eager list/tuple is iterable but is **not** an iterator:
`next(values)` fails; `next(iter(values))` works. Likewise, `Iterator[T]`
annotations do not accept a `Sequence[T]`. Prefer `Iterable[T]` for code that
only loops, and use `iter(...)` when consuming incrementally. Generator-only
operations (`send`, `throw`, `close`) are not a general iterable contract.

### Handle identity across bulk traversals

Native nodes live in a shared tree. Bulk traversal can return distinct Python
wrappers for the same node; do not use `is` or `id()` to compare those wrappers.
Single-node lookups and view-backed node access retain interning.

```python
a = next(iter(config.descendants()))
b = next(iter(config.descendants()))
a == b  # node comparison, not Python wrapper identity
```

Metadata changes through one live handle are visible through another handle
for that node. A handle does not keep a removed node attached: reacquire nodes
after destructive edits rather than accessing a stale handle.

Node methods/properties and child containers whose owner has been deleted raise
`ValueError("configuration node has been deleted")`. Catch this ordinary
exception at the edit boundary if stale references are expected; do not rely
on a native panic or an empty success-shaped result.

Retained native interface views are stale too when their interface node is
deleted. Their node-backed accessors, including `config`, raise
`ValueError` rather than panicking or returning an empty name. Code holding
both nodes and views across edits can catch `ValueError` and
reacquire the appropriate object from the updated tree.

### Copying trees and metadata

`copy.deepcopy()` creates an independent native tree and uses Python's memo
dictionary when copying metadata. Cycles and repeated references in a copied
object graph are preserved rather than recursively copying forever or
duplicating shared objects. Native tree locks are released before invoking
Python metadata copy hooks.

`remove_tags("tag")` raises `KeyError` if that tag is absent from any affected
leaf; earlier leaves may already have been changed, so the operation is not
transactional. In contrast, `remove_tags(iterable_of_tags)` uses set-difference
semantics and ignores absent tags. These preserve the Python contracts.

### Child collection equality

`HConfigChildren.__eq__` compares direct child text in insertion order, not the
previous sorted recursive comparison of tags and descendants. This is a silent
semantic change. Compare child nodes or use `unified_diff()` when recursive
configuration equality is intended.

### Workflow inputs are read-only

`WorkflowRemediation.running_config` and `.generated_config` cannot be
reassigned. Construct a new workflow when replacing either input; assignment
raises `AttributeError`. The input and returned config trees remain mutable.
Remediation and rollback are computed lazily and cached. Caching does not make
the entire mutable tree API lock-free or safe to mutate concurrently.

### Native config views

The six supported platform views now use **one native implementation**, not an
unchanged Python implementation beside a Rust copy. `HConfigViewBase` and
`ConfigViewInterfaceBase` are aliases for native classes. Capability mixins
are markers for `isinstance()` checks, not Python implementations to inherit
for their default property bodies. See [Config Views](config-views.md).

Device-level subclasses of a built-in view remain supported through the
driver's `view_class`, provided the config selects a platform with native view
operations. Keep the inherited constructor accepting an `HConfig`. A Generic
config cannot acquire native view support by assigning a Python `view_class`;
constructing that native-backed view is unsupported.

Direct construction of `ConfigViewInterfaceBase` (or a Python interface-view
subclass) is no longer supported: obtain interface views from a device view's
`interface_views` or `interface_view_by_name()`. Adding a Python `__init__`
does not restore the native base constructor.

Capability and platform marker membership is instance-based.
`issubclass(ConfigViewInterfaceCiscoIOS, InterfaceVlanViewMixin)` no longer
describes IOS capabilities; use `isinstance(interface_view, InterfaceVlanViewMixin)`
or `interface_view.capabilities`. Multiple-inheritance mixin recipes do not
install new native behaviors. For a genuinely new platform, implement native
view ops or use a separate application-owned wrapper over `HConfig`.

| Value/property | Before | v4 |
| --- | --- | --- |
| `InterfaceDuplex.value` | `"1"`, `"2"`, `"3"` | `"auto"`, `"full"`, `"half"` |
| IOS/AOS-CX `nac_max_dot1x_clients`, `nac_max_mab_clients` | `NotImplementedError` | `None` |
| EOS/NX-OS/XR `module_number` | `AttributeError` | `None` |
| ProCurve `bundle_member_interfaces` on non-trunk interfaces | `ValueError` | `()` |
| IOS speed configured as `auto` | `ValueError` | `None` |
| IOS unrecognized `authentication host-mode` | `ValueError` | `None` |

Serialize duplex member names or migrate stored numeric-string values
explicitly; `InterfaceDuplex("1")` no longer reconstructs a value.
Treat an unknown NAC mode as absent/unsupported; inspect the original config if
your application must distinguish an unknown token from a missing command.
Replace exception-based tests of unsupported properties with explicit
`None`/empty-value checks. ProCurve `speed` still returns `None`.

## Correctness changes and parity

- `HConfigBase.__contains__` now tests direct child text. Membership guards that
  relied on the old always-false result change behavior.
- Nested text rendering no longer repeats descendants.
- `future()` correctly resolves matching negations and platform idempotency.
  Unresolved negations can still remain; inspect `future_with_report()`.
- `DuplicateChildError` derives from `HierConfigError`. JSON/XML duplicate
  list identities preserve that exception across the native boundary.
- Native range expansion is bounded rather than allocating arbitrarily large
  ranges from input.

Shared `testdata/cases/` exercises exact remediation and rollback in Rust and
Python. It is not an assertion of universal upstream equivalence. Two initially
mismatched cases now preserve their original source setup and expectations:
`cisco_nxos/line_console_terminal_settings_negation_negate_with` supplies its
test-specific negation rules explicitly; both it and
`cisco_xr/template_block_indent_adjust` select the lines loader to match
`from_lines()`. Manifest provenance names the source tests at
`upstream/next@0866dc2`. Expected outputs are unchanged: these are corrections
to the test setup, not intentional platform-behavior divergences.

Review representative real configurations before deploying v4. Object-protocol
parity, retained v3 scenarios, formats, and native boundary tests provide
complementary checks; see [Testing](../dev/testing.md).

## Upgrade checklist

1. Pin `<4` until this migration has been reviewed; opt into v4 deliberately.
2. Provision a compatible wheel or source-build toolchain, and `[yaml]` if needed.
3. Replace `all_children()` and removed constructors/algorithm helpers.
4. Audit every custom driver, its platform selector, and the five removed hooks.
5. Review traversal return types, wrapper identity, collection equality, and
   any code retaining handles after deletion.
6. Replace workflow input reassignment with a new workflow.
7. Audit custom views and serialized duplex/NAC values.
8. Compare real remediation/rollback output against upstream as well as running
   application tests.

See [Performance & Benchmarks](../dev/benchmarks.md) for recorded measurements,
not a guarantee for a particular device or CI runner.
