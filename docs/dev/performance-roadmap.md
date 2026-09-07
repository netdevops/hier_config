# Performance Roadmap: API Changes That Unlock Further Gains

The Rust rewrite deliberately preserved the pure-Python package's public API. That constraint has been pushed to its limit: the remaining hot paths are bounded by **CPython object construction**, not by Rust.

This document records what is *left* to do. It lists the two remaining optimisations, what each would cost to unlock, and the measurements that justify them. Work that has already shipped is not tracked here — see `CHANGELOG.md` for history, [Performance & Benchmarks](benchmarks.md) for the 3.x to 4.0 benchmark story, [Architecture](architecture.md#core-tree-model) for the data-layout decisions and invariants that came out of it, and the [3.x → 4.0 migration guide](../user/rust-core-changes.md) for consumer-facing consequences.

---

## Current baseline

Reference figures on an Apple M2 Max, release build (`maturin develop --release`), against the generated 400-interface Cisco IOS config used by the gate. Costs are in **calibration units**, which self-normalise across machines (1 unit ≈ 3.0 ms on this machine).

| Operation | Cost (units) | Wall clock | Gate ceiling | Remaining headroom |
|---|---:|---:|---:|---|
| `deepcopy` | 0.020 | 0.06 ms | 0.03 | None — Rust-bound |
| `iteration` | 0.037 | 0.11 ms | 0.06 | ~0.011 units, via [item 2](#2-expose-a-bulkcolumnar-accessor) |
| `remediation` | 0.123 | 0.37 ms | 0.19 | None — Rust-bound |
| `fast_load` | 0.162 | 0.48 ms | 0.24 | None — Rust-bound |
| `parse` | 0.184 | 0.55 ms | 0.27 | None — Rust-bound |
| `dump` | 0.266 | 0.80 ms | 0.37 | ~45%, via [item 1](#1-change-dumpline-from-a-pydantic-model-to-a-__slots__-class) |

Re-derive these with `pytest -m benchmark tests/benchmarks/test_perf_regression.py -v -s` rather than trusting any number written down here.

**Only two operations have headroom left, and both are gated on the object model.** `parse`, `fast_load`, `deepcopy`, and `remediation` are Rust-bound and their compatible headroom has been collected; the split below is why.

### Why the rest is finished

Measured against a native Rust harness running the same logical operation with no interpreter involved:

| Operation | Python-visible | Rust core | Spent crossing into CPython |
|---|---:|---:|---:|
| `dump` | 0.941 ms | 0.106 ms | **89%** |
| `iteration` | 0.294 ms | 0.025 ms | **93%** |
| `parse` | 0.672 ms | 0.587 ms | 15% |
| `fast_load` | 0.604 ms | 0.553 ms | 13% |
| `remediation` | 0.392 ms | 0.297 ms | 27% |

!!! note
    These absolute timings predate the optimisation passes and are **not** current; the table is kept for its proportions, which still hold. Use the calibration table above for absolute figures.

The two expensive operations are almost entirely CPython-bound. No amount of Rust optimisation moves them — they are limited by how many Python objects must be allocated and how those objects are shaped, both fixed by the public API. Everything else is dominated by core work, where the headroom has already been taken.

For calibration, `dump` is already **~2.2x faster than the fastest pure-Python equivalent** (2.103 ms building the same 3223 `DumpLine` objects in a tight Python loop). This is not Rust performance left on the table; it is the cost of the object model.

---

## 1. Change `DumpLine` from a pydantic model to a `__slots__` class

**Gain:** ~45% of `dump` — the largest absolute win available, and the **only** remaining lever on `dump`.
**Cost:** a major version. Breaks every consumer relying on pydantic behaviour.
**Status:** not taken in 4.0 because its decision gate (below) was never run. It now waits for 5.0.

`dump` builds 3223 `DumpLine` instances. The MRO is `['DumpLine', 'BaseModel', 'BaseModel', 'object']` with four real slot descriptors: `__dict__`, `__pydantic_fields_set__`, `__pydantic_extra__`, `__pydantic_private__`. Three of those exist only to satisfy pydantic's internals.

The binding already bypasses pydantic's `__init__` entirely — `object.__new__` followed by direct slot population (`crates/hier_config_py/src/root.rs`). **That is already the fast path**, and the floor was measured directly:

| Construction strategy (×3223) | Cost |
|---|---:|
| `object.__new__(DumpLine)` alone | 0.283 ms |
| `__new__` + dict + 4 × `setattr` (pure Python) | 2.103 ms |
| plain `dict` per row | 0.668 ms |
| **current Rust implementation** | **0.941 ms** |

At ~246 ns per line against a measured floor of ~250 ns for constructing objects of this shape at all, **there is no Rust-side headroom left in `dump`.** A plain `__slots__` class carrying `depth`, `text`, `tags`, `comments`, `new_in_config` needs one allocation and no `__dict__`, which is where the ~45% comes from. Changing the class is the only thing that can move this number.

### What it breaks

`DumpLine` is exported from `hier_config.models`, rendered in [the API reference](api-reference.md), and reachable as `Dump.lines[n]`. On the class itself:

- `.model_dump()`, `.model_dump_json()`, `.model_validate()`, `.model_validate_json()`, `.model_copy()`, `.model_json_schema()`, `.model_fields`, `.model_config`;
- `TypeAdapter(DumpLine)` and `TypeAdapter(Dump)`;
- using `Dump` or `DumpLine` as a field on another pydantic model — which includes FastAPI request/response bodies and `@validate_call` signatures;
- validation on construction: `DumpLine(depth="not an int", ...)` raises `ValidationError` today and would be accepted silently;
- the project-local `BaseModel` behaviours — `frozen=True` (assignment raises) and `extra="forbid"` (unknown kwargs raise).

It does **not** break attribute reads, `config.dump()`, or `get_hconfig_from_dump()`, and the wire shape of a dump is unchanged.

!!! tip "Run this decision gate before committing to the full break"
    A `__slots__` class implementing `__get_pydantic_core_schema__` keeps `TypeAdapter`, nested-model use, and FastAPI interop working while still shedding the four `BaseModel` slots — which is where the ~45% actually comes from. It does not restore the `.model_*` *methods*, so it is still a break, but a far narrower one.

    **Prototype and measure this first.** If it retains most of the gain it is strictly the better trade. This measurement has not been made, and not making it in time is why the item missed 4.0.

---

## 2. Expose a bulk/columnar accessor

**Gain:** workload-dependent; large for analytics-style consumers. Also closes the gap between `iteration`'s measured 0.037 units and the 0.026 that was projected for it.
**Cost:** none — purely additive, so it can ship in any release, including a patch.
**Status:** not taken; nothing is blocking it.

Reading one attribute from every node costs one Python-level call per node, and every traversal constructs one `HConfigChild` per node whether or not the caller reads anything from it. A method returning parallel lists (or a single list of tuples) for a whole subtree would amortise the boundary crossing across the entire tree instead of paying it per node per attribute — and would skip wrapper construction entirely.

This is the natural escape hatch for callers who currently write `[c.text for c in config.all_children()]`.

### Why this is what remains in `iteration`

Traversal used to cost a hash probe, a failed weakref upgrade, a `Py::new`, a `PyWeakrefReference` allocation, and a cache insert per node. Measured split when the cold cost was 0.335 ms — treat these as proportions, not current absolutes:

| Component | Cost | Status |
|---|---:|---|
| `Py::new` + weakref alloc + cache insert | 0.205 ms (~61%) | Weakref and cache removed; **`Py::new` remains** |
| generator wrapper | 0.041 ms (~12%) | Removed |
| `list(iter(objs))` floor | 0.010 ms | Irreducible |

What is left is the `Py::new` per node itself. That is only avoidable by not constructing a Python object per node at all — which is exactly this item.

---

## What is not worth attempting

- **More Rust-side work on `dump`.** It is at ~246 ns/line against a ~250 ns CPython floor. Item 1 or nothing.
- **More work on `remediation`, `parse`, `fast_load`, or `deepcopy`.** All Rust-bound with the compatible headroom already collected. Confirm against a native harness before assuming otherwise.
- **Dropping node interning wholesale** rather than the current conservative split. The extra gain over keeping single-node identity is small, and it breaks the one identity case the suite pins. See [Architecture](architecture.md#core-tree-model).
- **Removing `Dump` / `DumpLine` from the public surface.** Serialising a config is a legitimate documented use case; changing the class shape is justified, deleting the API is not.

---

## Rules for anyone acting on this

1. **Measure before and after, in release mode.** A debug extension is roughly an order of magnitude slower and will mislead you. Always `maturin develop --release` first.
2. **Confirm the build actually succeeded** before trusting numbers. A failed `maturin develop` leaves the *previous* extension installed and produces convincing, wrong results.
3. **Separate Rust cost from boundary cost** before optimising. A native Rust harness exercising the same core operation tells you immediately whether the interpreter or the algorithm is the constraint — both items above only became obvious once that split was measured.
4. **Profile the Python glue too, not just the core.** The largest single win in the pre-4.0 pass (50x on driver construction) was a `model_copy(deep=True)` in `hier_config/platforms/driver_base.py`, found only after the Rust core had already been optimised twice. A native core makes it easy to stop looking at Python.
5. **Re-baseline the gate.** `MAX_COST_UNITS` in `tests/benchmarks/test_perf_regression.py` is set at ~1.5x observed cost. Tighten it after a win so the gain cannot silently regress; see [Testing Conventions](testing.md#benchmarks).
6. **Delete temporary harnesses.** Profiling examples under `crates/hier_config_core/examples/` are build-time cost for every contributor; remove them once the numbers are recorded here.
7. **Check whether an "API break" has actually shipped** before pricing it in. An unreleased interface costs nothing to change, and treating it as expensive has already caused one item to be deferred for no reason.

## Realistic ceiling

Taking both items would land `iteration` at ~0.026 units and `dump` at ~0.15. Nothing else moves.

A blanket "2x across the board" is **not** achievable while the current API holds — that is a measured result, not a prediction. The work already done cleared 1.35–1.86x on the Rust-bound operations and 2.6x on `iteration`, and moved `dump` almost not at all. The remaining gains are concentrated in exactly two operations, and both are paid for in compatibility or in new API surface.
