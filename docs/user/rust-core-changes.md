# Rust core behavior changes

hier_config 4.0 replaces the pure-Python core with a Rust implementation exposed
through PyO3. This page covers the behavior differences that fall out of that
engine swap. It is the companion to [Migrating from v3](migrating-from-v3.md),
which covers the v4 API renames; read that one first, then this one. For the
measured speedup figures and the architectural story behind the rewrite, see
[Performance & Benchmarks](../dev/benchmarks.md).

Module layout and import paths are unchanged, and every v3 name remains a
supported alias, so most projects upgrade by bumping the pin and re-running
their test suite.

The exceptions are concentrated in two areas. The larger one is **custom driver
subclasses**: four `HConfigDriverBase` hooks that worked in 3.x are no longer
consulted by the engine, and they fail *silently* — the driver still builds, the
remediation still runs, and the output is simply the stock platform behaviour.
The smaller one is **object identity**: handles returned from bulk traversals are
no longer interned, so `is` comparisons that held in 3.x now return `False`.

!!! warning "Read this section even if your tests pass"
    The driver hook changes, the `HConfigChildren.__eq__` change, and the
    traversal identity change do not raise. A green test suite does not prove
    your custom driver still customizes anything, nor that your `is` comparisons
    still mean what they did. Work through [Custom drivers](#custom-drivers) and
    [Handle identity across bulk
    traversals](#handle-identity-across-bulk-traversals) explicitly.

## At a glance

| Change | Impact | Silent? |
| --- | --- | --- |
| `idempotent_for()`, `negate_with()`, `sectional_exit()` overrides raise `TypeError` | Custom drivers fail at import | **Yes** |
| `config_preprocessor()`, `declaration_prefix` overrides only partially honored | Custom drivers emit stock output in some paths | **Yes** |
| `HConfigChildren.__eq__` compares child `text` in insertion order | Equality results can flip in either direction | **Yes** |
| Source installs need a Rust toolchain | Only affects `--no-binary` / unsupported platforms | No — build error |
| Invalid custom rule payloads now raise | Previously fell back to stock rules | No — exception |
| `HConfigBase.__contains__` does real membership | `"x" in config` was always `False` in 3.x | **Yes** |
| `str(HConfig)` no longer duplicates nested lines | Bug fix; output changes if you snapshotted the broken form | **Yes** |
| `future()` negation handling corrected | Bug fix; fewer stray `no ...` lines survive | **Yes** |
| `DuplicateChildError` now inherits `HierConfigError` | Broader `except` clauses now catch it | No |
| `all_children*()` / `unused_objects()` return a tuple, not a generator | `Iterator[...]` annotations fail type-checking | No — type error |
| Bulk traversals no longer intern handles | `child_a is child_b` across traversals is now `False` | **Yes** |
| `pydantic` and `pyyaml` now declared as runtime deps | Fixes an undeclared-import bug in 3.x | No |

Everything else — `hier_config.base`, `.child`, `.children`, `.root`,
`.platforms.*`, `.models`, `.constructors`, `.workflows`, `.utils`, the
`Platform` enum, and every config view — keeps its 3.x import path and signature.

## Installation and packaging

### Wheels

4.0 ships pre-built `abi3` wheels for Linux, macOS, and Windows on CPython 3.10
and newer. `pip install hier-config` needs no toolchain on those platforms.

Installing from an sdist — or on a platform without a published wheel — now
requires a **Rust toolchain** (`rustup`, stable). The build backend moved from
Poetry to [maturin](https://www.maturin.rs/), and the package version is derived
from `Cargo.toml`.

See [Install hier_config](install.md) for the full matrix.

### Python version

`requires-python` is `>=3.10`, unchanged from 3.7. CI covers 3.10 through 3.14.

### Runtime dependencies

```toml
dependencies = ["pydantic>=2.9,<3", "pyyaml>=6,<7"]
```

`pyyaml` is **not** a new import — `hier_config.utils` used it in 3.x too, but the
wheel never declared it. If you were relying on a transitive `pyyaml`, nothing
changes; if you had pinned it out, the dependency is now explicit and correct.

!!! tip "Pin defensively during the upgrade"
    Downstream packages that declare an unbounded `hier-config>=3.x` will pick up
    4.0 automatically. Cap those to `<4` until you have worked through this guide.

## Custom drivers

This is where real breakage lives.

### Why hooks stopped firing

In 4.0 the remediation engine runs entirely in Rust. The only bridge from a
Python driver into that engine serializes two things:

- the `negation_prefix` property, and
- `driver.rules`, as JSON (excluding `post_load_callbacks`, which are registered
  separately).

Anything expressed as **data on `rules`** crosses the boundary. Anything
expressed as **imperative Python on the driver class** does not — the engine
never calls back into Python during remediation, so an override is simply never
reached.

### Hook support matrix

| Hook | 4.0 status |
| --- | --- |
| `_instantiate_rules()` | ✅ Supported |
| `negation_prefix` property | ✅ Supported |
| Appending to `driver.rules.*` collections | ✅ Supported |
| `post_load_callbacks` | ✅ Supported (additive; project callbacks are built in) |
| `swap_negation()` | ⚠️ Direct calls work; not invoked by the engine |
| `idempotent_for()` | ⚠️ Override rejected unless marked `@core_owned` |
| `negate_with()` | ⚠️ Override rejected unless marked `@core_owned` |
| `sectional_exit()` | ⚠️ Override rejected unless marked `@core_owned` |
| `config_preprocessor()` | ⚠️ Runs in `HConfig.from_text()`; skipped by `from_lines()` |
| `declaration_prefix` property | ❌ **Silently ignored** |

`idempotent_for()`, `negate_with()`, and `sectional_exit()` still exist, but the
engine resolves all three inside the Rust core, so a plain Python override is
never consulted. Rather than let that fail silently, `__init_subclass__` raises
`TypeError` at class-creation time.

If your override intentionally duplicates what the core already does — the
in-tree platform drivers are in exactly this position — mark it with the
`@core_owned` decorator to acknowledge that the core owns the behavior and let
the definition through:

```python
from hier_config.platforms.driver_base import HConfigDriverBase, core_owned


class MyDriver(HConfigDriverBase):
    @core_owned
    def negate_with(self, config): ...
```

The marker is a declaration, not a switch: it suppresses the guard, it does not
make the engine call your override. If you need genuinely different negation
behavior, express it as rules (see [Negation
rules](migrating-from-v3.md#negation-rules)) rather than as a method.

The private helpers that existed only to serve these hooks —
`_idempotent_for_helper()` and `_negation_negate_with_helper()` — are removed.
`_idempotency_key()` is unaffected.

See [Key methods in `HConfigDriverBase`](../dev/creating-drivers.md#key-methods-in-hconfigdriverbase)
for the authoritative reference, which is pinned by
`tests/native/test_extension_surface.py`.

### Detecting the problem

You do not have to instrument anything for the three removed hooks — importing
the module raises:

```text
TypeError: MyDriver defines idempotent_for(), which the v4 engine never calls:
only rule data crosses into the Rust core. Express this as a rule on
HConfigDriverRules instead.
```

For `config_preprocessor()` and `declaration_prefix`, which are only partially
honored, instrument the subclass and confirm what actually runs:

```python
from hier_config import get_hconfig
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS


class Probe(HConfigDriverCiscoIOS):
    seen: list[str] = []

    @classmethod
    def config_preprocessor(cls, config_text: str) -> str:
        cls.seen.append("config_preprocessor")
        return config_text


get_hconfig(Probe(), "interface Eth1\n")  # runs the preprocessor
print(Probe.seen)
```

### Migrating `idempotent_for()`

Express the same intent as an `IdempotentCommandsRule` instead:

```python
from hier_config.models import IdempotentCommandsRule, MatchRule

driver.rules.idempotent_commands.append(
    IdempotentCommandsRule(
        match_rules=(MatchRule(re_search=r"^tacacs-server host (\S+) encrypted-key"),),
    )
)
```

### Migrating `negate_with()`

`negate_with()` maps to appending a `NegationDefaultWithRule` to
`driver.rules.negate_with`. New in 4.0, `use` accepts regex backreferences
against the last `match_rule` carrying a `re_search`, which replaces the v3
`_negation_negate_with_helper()` "rebuild from the first *N* words" idiom:

```python
from hier_config.models import MatchRule, NegationDefaultWithRule

driver.rules.negate_with.append(
    NegationDefaultWithRule(
        match_rules=(MatchRule(re_search=r"^(tacacs-server host \S+) .*$"),),
        use=r"no \1",
    )
)
```

`sectional_exit()` maps to appending a
`SectionalExitingRule` to `driver.rules.sectional_exiting`.
[Customizing Driver Rules](../admin/customizing-rules.md) has worked examples
for each rule type.

### Migrating `config_preprocessor()`

There is no rule equivalent for arbitrary text rewriting. Apply the
transformation to the config string **before** handing it to `get_hconfig`:

```python
config_text = my_preprocessor(raw_config_text)
config = get_hconfig(driver, config_text)
```

If the rewrite is line-shaped rather than text-shaped, a
`per_line_sub` rule or a `post_load_callback` is usually a better fit.

### `_instantiate_rules()` is concrete, not abstract

`HConfigDriverBase` remains an `ABC`, and `_instantiate_rules()` remains a
`staticmethod` — existing overrides need no change. What moved is the base
implementation: it is no longer decorated `@abstractmethod`, and instead raises
`NotImplementedError` when called.

The distinction matters for one case. In 3.x a subclass that forgot
`_instantiate_rules()` could not be instantiated at all; in 4.0 it constructs
successfully and fails at the point the rules are first needed. Subclasses that
do define the override behave identically.

Each in-tree driver now declares its own override rather than deriving the
platform from a class attribute:

```python
@staticmethod
def _instantiate_rules() -> HConfigDriverRules:
    return load_platform_rules(Platform.CISCO_IOS)
```

`load_platform_rules()` reads the canonical rules the Rust core compiles
against, so a custom driver that wants stock platform behavior plus additions
can call it and then append to the returned collections.

### Invalid rules now raise

If a custom driver's `rules` payload cannot be converted for the Rust engine,
4.0 raises. 3.x silently discarded the custom rules and ran with stock platform
behaviour. This is strictly better — but a driver that "worked" in 3.x only
because its broken rules were being dropped will now fail loudly.

## Behaviour changes

### `HConfigChildren.__eq__`

3.x compared children sorted by `order_weight`, recursing into `text`, `tags`,
and grandchildren. 4.0 compares child `text` in **insertion order**.

Results can differ in *both* directions: two configs with the same lines in a
different order now compare unequal, and children differing only in tags or
grandchildren now compare equal.

```python
# Compare the children objects, not the collection, to keep 3.x semantics
a.children["interface Eth1"] == b.children["interface Eth1"]  # full recursive ==
```

Individual `HConfigChild` comparison is unchanged and still recursive.

### `HConfigBase.__contains__`

3.x defined no `__contains__`, so `"hostname r1" in config` fell through to
iteration semantics and was effectively always `False`. 4.0 implements real
membership against child `text`:

```python
"hostname r1" in config  # True in 4.0 when that child exists
```

Any code that relied on the always-`False` behaviour — for example
`if line not in config:` guards that were unconditionally taken — changes
meaning.

### `str(HConfig)` no longer duplicates lines

The 3.7 Rust backend rendered nested structures repeatedly. A tree of `a/b/c`
plus a sibling `c` produced `a, b, c, exit, exit, b, c, exit, c`. 4.0 restores
the invariant:

```python
str(config) == "\n".join(str(c) for c in sorted(config.children))
```

If you snapshot-tested against the broken output, regenerate those fixtures.

### `future()` negation handling

Negations whose positive form is present now remove that line instead of
surviving as a literal `no ...`. Shorthand negations such as `no description`
remove the valued line they match. Negations with no corresponding positive line
are still retained.

```python
running = get_hconfig(Platform.CISCO_IOS, "interface Eth1\n  description old\n")
remediation = get_hconfig(Platform.CISCO_IOS, "interface Eth1\n  no description\n")
running.future(remediation).dump_simple()
# 4.0: ('interface Eth1',)   — 3.x left a stray 'no description'
```

### `DuplicateChildError`

Now inherits `HierConfigError`. Handlers written as `except HierConfigError:`
previously did **not** catch it and now do. It remains an `Exception` subclass,
so bare `except Exception` handlers are unaffected.

### `expand_range` bounds

`expand_range` and `hp_procurve_expand_range` cap expansion both per-segment and
in aggregate. Oversized ranges return an error and leave the line untouched
rather than attempting to materialize the range. `vlan 1-4000000000` no longer
exhausts memory.

### Config view identity

`interface_views`, `interface_view_by_name()`, and `bundle_interface_views()`
return interned `HConfigChild` handles, so identity checks hold:

```python
view.config is config.children["interface Eth1"]  # True
```

### Some traversal methods return tuples, not generators

`all_children()` is still a true generator, so `isinstance(x,
types.GeneratorType)`, `.send()`, `.throw()`, and `.close()` all still work.

`all_children_sorted()`, `all_children_sorted_by_tags()`, and
`HConfig.unused_objects()` return a **tuple** instead. The rule is whether the
method can be lazy at all: none of these three can produce a result before it
has seen the whole tree, so the 3.x generator was a wrapper around an
already-materialized list — it added a Python frame per item and bought no
laziness. Dropping it makes a full `all_children_sorted()` walk roughly six
times faster.

For those three, the change is mostly additive at runtime:

```python
children = config.all_children_sorted_by_tags(frozenset({"safe"}), frozenset())
len(children)          # now works
children[0]            # now works
list(children)         # now repeatable -- no longer exhausted after one pass
```

Two things break:

- **Static annotations.** `Sequence` is not an `Iterator`, so
  `x: Iterator[HConfigChild] = config.unused_objects()` is now a mypy/pyright
  error. Change the annotation to `Sequence[HConfigChild]`, or to
  `Iterable[HConfigChild]` if you want to accept both.
- **Generator-specific operations.** `isinstance(x, types.GeneratorType)` is now
  `False` for these two, and `.send()`, `.throw()`, and `.close()` no longer
  exist. If you need a true iterator, wrap the call: `iter(...)`.

Ordinary `for` loops, comprehensions, unpacking, and `tuple(...)` /
`list(...)` calls are unaffected.

### Handle identity across bulk traversals

`HConfigChild` handles are Python wrappers over nodes in a shared native tree.
In 4.0, **bulk traversals no longer intern their handles**, so two handles for
the same node obtained from *different* traversals are no longer the same
Python object:

```python
config.all_children()[0] is config.all_children()[0]  # False in 4.0, True in 3.x
```

Interning costs a lock, a hash, a weakref allocation, and a weakref upgrade per
node. On a whole-tree walk that dominates the cost — removing it is where the
61% `iteration` improvement comes from.

**Everything that depends on value semantics still works**, because `__eq__` and
`__hash__` are derived from the node rather than the wrapper:

```python
a, b = config.all_children()[0], config.all_children()[0]
a == b                    # True
hash(a) == hash(b)        # True
a in config.all_children()  # True
set(config.all_children()) # deduplicates correctly
```

Mutation visibility is also unaffected — tags, comments, and facts live in the
shared tree keyed by node, so a write through one handle is visible through any
other handle for the same node.

**Single-node lookups still intern**, and this is guaranteed, not incidental:

```python
child = config.add_child("interface Eth1")
config.add_child("interface Eth1", return_if_present=True) is child  # True
config.children.get("interface Eth1") is child                      # True
config.get_child(equals="interface Eth1") is child                   # True
view.config is config.children["interface Eth1"]                     # True
```

**What to check:** grep for `is` / `is not` / `id()` comparisons on
`HConfigChild` objects, and for code that uses handles as dict keys *expecting
identity semantics*. Replace `is` with `==`. Dict and set usage keyed on
`HConfigChild` needs no change, since those already use `__hash__`/`__eq__`.

Because this change is silent, grep is the reliable detector — a test suite that
happens to compare handles from the *same* traversal will keep passing:

```bash
# Candidate sites. Review each: only comparisons on handles from *different*
# traversals actually change behaviour.
grep -rnE '\bis (not )?[a-z_]+\b' --include='*.py' . | grep -i 'child\|node\|view'
grep -rn 'id(' --include='*.py' . | grep -i 'child\|node'
```

The mechanical fix is `is` → `==` and `id(x)` → `x` as a dict key. Both are
safe even where identity happens to still hold, so you do not need to work out
which call sites are affected — converting all of them is correct.

### Comments

Comments written by built-in post-load callbacks now surface through
`HConfigChild.comments`. In earlier builds they were stored but not visible from
Python.

### Native view divergences

The Python view layer is unchanged, so **none of these affect Python users.**
They apply only when you consume the native Rust view in `hier_config_core`,
which returns values where the Python property raises:

| Platform | Property | Python | Rust |
| --- | --- | --- | --- |
| Cisco IOS, Aruba AOS-CX | `nac_max_dot1x_clients`, `nac_max_mab_clients` | `NotImplementedError` | `None` |
| Arista EOS, Cisco NX-OS, Cisco XR | `module_number` | `AttributeError` | `None` |
| HP `ProCurve` | `bundle_member_interfaces` | `ValueError` on a non-trunk interface | empty list |

Rust favors a total function over a panic, because a panic in a getter is not a
usable error-handling contract for a library. The shared corpus records each
raising pair in its `raises` map and allow-lists it, so a *new* divergence is a
test failure rather than a silent drift.

Two Python behaviors are reproduced faithfully even though they look like bugs,
because changing them would be a behavior change rather than a port:

- HP `ProCurve` `speed` is always `None`. The Python implementation passes the
  whole `speed-duplex 1000-full` line into a parser that expects just the value,
  so no branch ever matches. `duplex` works only incidentally, by matching the
  line's `half`/`full` suffix.
- Cisco IOS `speed` raises `ValueError` in Python whenever the configured value
  is `auto`, because it calls `int()` on it. Rust returns `None`.

If either should change, it should change in Python first and flow into the port
through a regenerated corpus.

## Import surface

No import paths were removed or moved.

- `hier_config.base`, `.child`, `.children`, and `.root` are re-export shims over
  the extension. `tests/test_import_surface.py` pins them.
- `hier_config.platforms.view_base` and every
  `hier_config/platforms/<platform>/view.py` are unchanged pure Python. The
  Rust core carries a parallel native view for standalone Rust use; the two are
  pinned together by the shared corpus under `testdata/views/`.
- Type stubs (`hier_config/*.pyi`) are shipped, so downstream annotations resolve
  to real types instead of `Any`.
- Native classes report `__module__` correctly, which makes `HConfig` and
  `HConfigChild` **picklable**. They were not in 3.7.
- `HConfigBase.children` is a real property rather than a `__getattr__`
  fallback, so it now appears in `dir()`, IDE completion, and type checkers.
- `TextStyle` in `hier_config.models` is an explicit `TypeAlias`.

## Performance

`get_hconfig_fast_load` now has a native implementation. It was roughly 25x
slower than `get_hconfig` in 3.x; an 8,431-line config went from ~41.6 ms to
~1.5 ms. If you avoided `fast_load` for performance reasons, re-benchmark it.

4.0 also collected the optimizations that required a compatibility break.
Relative to the start of the 4.0 cycle:

| Operation | Change |
| --- | --- |
| Whole-tree iteration | **−61%** |
| `deepcopy` | **−32%** |
| Parsing | −11% |
| Remediation | −11% |
| `fast_load` | −7% |

The iteration gain comes from the two breaks documented above —
[sequence returns](#some-traversal-methods-return-tuples-not-generators) and
[bulk-traversal de-interning](#handle-identity-across-bulk-traversals). The
others come from a Rust-internal change with no Python-visible surface.

Remaining optimizations under consideration are tracked in the
[performance roadmap](../dev/performance-roadmap.md). Those are **not** part of
4.0.

## Upgrade checklist

1. Cap any unbounded `hier-config>=3.x` requirements at `<4` before upgrading, so
   the bump is deliberate.
2. Confirm your platforms have wheels; otherwise provision a Rust toolchain in
   the build image.
3. **Audit every `HConfigDriverBase` subclass.** For each override of
   `idempotent_for`, `negate_with`, `sectional_exit`, `config_preprocessor`, or
   `declaration_prefix`, re-express it as a rule or delete it. Use the probe in
   [Detecting the problem](#detecting-the-problem) to verify.
4. Grep for `.children ==` and `.children !=` comparisons and switch to
   comparing `HConfigChild` objects where recursive semantics matter.
5. Grep for `in config` / `not in config` membership tests.
6. Regenerate any snapshots taken from `str(HConfig)` or from `future()` output.
7. Review `except HierConfigError` blocks for newly-caught `DuplicateChildError`.
8. Grep for `Iterator[HConfigChild]` / `Generator[...]` annotations on
   `all_children*()` and `unused_objects()` results and change them to
   `Sequence[HConfigChild]`.
9. Grep for `is` / `is not` / `id()` comparisons on `HConfigChild` objects and
   switch them to `==` / `!=` unless the handle came from a single-node lookup.
10. Run your suite, then diff real remediation output for a representative device
    sample against 3.x rather than relying on unit tests alone.

## Getting help

If you hit a break that is not covered here, please
[open an issue](https://github.com/netdevops/hier_config/issues) with the
config snippets and driver code needed to reproduce it.
