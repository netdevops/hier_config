# Performance & Benchmarks: The 3.x to 4.0 Story

hier_config 4.0 introduces an arena-backed Rust core engine (`hier_config_core`)
exposed to Python through native PyO3 bindings. This replaced the 3.x
pure-Python tree implementation to eliminate the performance and scaling
bottlenecks that network automation pipelines encountered when processing
thousands of large configurations.

This document tells the 3.x to 4.0 performance improvement story: the
architectural bottlenecks of the pure-Python engine, the empirical benchmark
measurements across configuration sizes, the structural reality of the CPython
object allocation boundary, the iterative optimization passes that tuned the hot
paths, and the automated calibration-unit regression guardrails protecting these
gains in CI.

---

## Executive Summary

On a 10,000-line Cisco IOS configuration (8,823 nodes), hier_config 4.0 achieves
**3x to 259x speedups** across core operations compared to the pure-Python 3.x
baseline:

| Operation | 4.0 (Rust Core) | 3.x (Pure Python) | Speedup | Result Category |
|---|---:|---:|---:|---|
| **`copy.deepcopy()`** | **0.52 ms** | 134.56 ms | **259x** | New tree / memory clone |
| **`get_hconfig` (50k lines)** | **10.04 ms** | 384.76 ms | **38x** | Scalar / tree creation |
| **`get_hconfig` (10k lines)** | **1.97 ms** | 61.28 ms | **31x** | Scalar / tree creation |
| **`get_hconfig` (1k lines)** | **0.25 ms** | 7.10 ms | **28x** | Scalar / tree creation |
| **`config_to_get_to` (remediation)** | **0.98 ms** | 11.55 ms | **12x** | New remediation tree |
| **`dump()`** | **2.43 ms** | 18.65 ms | **7.7x** | *N* Python objects |
| **`all_children_sorted()`** | **0.29 ms** | 2.35 ms | **8.1x** | *N* Python objects |

*Measured on Apple Silicon (Apple M2 Max), CPython 3.12, release build (`maturin develop --release`).*

### Real-World Operational Impact

In large-scale network automation pipelines evaluating fleets of edge routers,
data center switches, and route reflectors:

1. **Minutes become seconds**: Processing 1,000 devices with 10k-line
   configurations previously required over a minute of pure CPU time just for
   parsing and remediation diffing. In 4.0, the core computation finishes in
   under 3 seconds.
2. **Elimination of multiprocessing overhead**: In 3.x, CPU-bound tree diffing
   held the Python Global Interpreter Lock (GIL). Parallelizing workloads across
   cores required `multiprocessing`, incurring high memory overhead and
   inter-process serialization costs. The 4.0 Rust core releases the GIL during
   heavy native diffing and parsing, allowing standard Python thread pools
   (`concurrent.futures.ThreadPoolExecutor`) to saturate all CPU cores with a
   shared memory footprint.
3. **Sub-millisecond rollbacks and simulations**: Complex simulation workflows
   calling `future()` and computing inverse rollbacks frequently duplicate
   trees. The 259x speedup in `deepcopy` makes multi-stage state projections
   virtually instantaneous.

---

## Why Pure Python Hit a Wall (The 3.x Bottlenecks)

The pure-Python 3.x architecture organized configuration lines into a tree of
`HConfig` and `HConfigChild` objects, backed by `HConfigChildren` collections.
While flexible and idiomatic, this architecture faced fundamental CPython
overhead at scale:

### 1. Object Explosion and Allocator Pressure

A 10,000-line network configuration contains roughly 8,800 distinct hierarchical
nodes. In 3.x, every single node was an independent Python object instance:

- Each node allocated its own `__dict__`, a child list, sets for tags and
  comments, an integer order weight, and references to parent and driver objects.
- Parsing a single large configuration resulted in tens of thousands of heap
  allocations managed by the CPython memory allocator and garbage collector.
- Walking the tree meant chasing pointers across scattered memory, destroying
  CPU cache locality.

### 2. Recursive Lineage and Pattern Matching in Bytecode

Remediation calculation (`config_to_get_to`) requires comparing two trees node
by node. For every candidate difference, the engine must evaluate:

- Driver lineage matchers (`MatchRule` tuples) against the node's ancestor path.
- Regular expressions for idempotency, sectional exits, and ordering.
- Sorting child nodes by `order_weight` and insertion index.

In 3.x, all of this executed in Python bytecode. Ancestor paths were
constructed as temporary Python tuples, regex patterns were evaluated via the
`re` module, and sorting required allocating intermediate lists at every level of
the tree.

### 3. The `deepcopy` Nightmare

Network remediation often projects future configurations (`future()`) and
validates rollbacks by cloning the running or remediation tree.

In Python, `copy.deepcopy` is notoriously slow: it recursively inspects each
object, looks up its class, checks for `__deepcopy__`, allocates a new instance,
and maintains a memo dictionary of already-copied references to guard against
cycles. For an 8,823-node tree, `copy.deepcopy` spent **134.56 ms** just
duplicating Python objects.

---

## The 4.0 Architecture Shift

hier_config 4.0 re-architected the entire tree, parsing, and diffing pipeline
around native Rust primitives:

```
┌────────────────────────────────────────────────────────┐
│                   Python Consumer                      │
│      (WorkflowRemediation, get_hconfig, Views)         │
└───────────────────────────┬────────────────────────────┘
                            │ PyO3 Native FFI
┌───────────────────────────▼────────────────────────────┐
│                    hier_config_py                      │
│   (PyHConfig, PyHConfigChild, Handle Lifecycle)        │
└───────────────────────────┬────────────────────────────┘
                            │ Native Rust Calls
┌───────────────────────────▼────────────────────────────┐
│                   hier_config_core                     │
│  ├── Arena<Node> (Contiguous node vector)              │
│  ├── NodeId (Generational indices, 0-cost handles)     │
│  ├── Arc<str> (Zero-copy shared string slices)         │
│  ├── Native Parser (Fast indentation & banner parser)  │
│  ├── Compiled Regex Sets (Pre-compiled driver rules)   │
│  └── Remediation Diff Engine (Single-pass tree diff)   │
└────────────────────────────────────────────────────────┘
```

### Key Architectural Invariants

1. **Generational Arena Allocation (`Arena<Node>`, `NodeId`)**:
   Instead of allocating thousands of individual heap objects, trees are stored
   in contiguous arrays. A `NodeId` is a lightweight generational index (index +
   generation counter) that guarantees safe, constant-time O(1) lookups with
   perfect cache locality.
2. **Zero-Copy String Sharing (`Arc<str>`)**:
   Configuration lines, tags, and comment strings are stored as immutable
   atomic reference-counted string slices (`Arc<str>`). Node operations,
   traversals, and tree clones do not re-allocate strings.
3. **Instantaneous Tree Duplication**:
   Because nodes live in an arena and strings are immutable `Arc<str>`
   references, `deepcopy` in 4.0 simply clones the arena's underlying vector and
   increments string reference counts in native code. What took 134.56 ms in
   Python takes **0.52 ms** in Rust (down to **0.06 ms** in the hot-path
   microbenchmark).
4. **Pre-Compiled Rule Engines**:
   Driver rules, lineage patterns, and sectional overwrite rules are compiled
   into optimized native matchers and regex sets at driver initialization,
   removing regex overhead from per-line diff loops.
5. **Whole-Program Optimization (`[profile.release]`)**:
   The workspace is configured with `lto = "fat"` and `codegen-units = 1`. This
   enables link-time optimization and cross-crate inlining across the
   `hier_config_core` and `hier_config_py` boundary, allowing native methods to
   inline directly into PyO3 binding wrappers.

---

## Detailed Benchmark Suite

### 1. Scaling Across Configuration Sizes

To measure scaling characteristics across small, medium, and massive router
configurations, the test harness measured Cisco IOS configurations of varying
sizes:

| Benchmark Target | Line Count | Node Count | 4.0 Time | 3.x Time | Speedup |
|---|---:|---:|---:|---:|---:|
| **Parse (1k lines)** | ~1,000 | ~880 | **0.25 ms** | 7.10 ms | **28.4x** |
| **Parse (10k lines)** | ~10,000 | 8,823 | **1.97 ms** | 61.28 ms | **31.1x** |
| **Parse (50k lines)** | ~50,000 | ~44,100 | **10.04 ms** | 384.76 ms | **38.3x** |
| **Remediation (10k lines)** | ~10,000 | 8,823 | **0.98 ms** | 11.55 ms | **11.8x** |
| **Remediation (50k lines)** | ~50,000 | ~44,100 | **4.85 ms** | 58.18 ms | **12.0x** |

As configuration size increases from 1k to 50k lines, pure Python's parsing
slows down quadratically under memory pressure and garbage collection overhead,
while the Rust arena scales linearly with line count.

### 2. Operational Breakdown on 10k-Line Benchmark

Min-of-25 wall clock timings on a generated 10,000-line Cisco IOS configuration
(8,823 nodes) comparing the 4.0 release build against the 3.x baseline:

```
Operation          4.0 (Rust)        3.x (Python)     Speedup
─────────────────────────────────────────────────────────────
deepcopy              0.52 ms          134.56 ms       259.0x  ████████████████████
get_hconfig (50k)    10.04 ms          384.76 ms        38.3x  ███
get_hconfig (10k)     1.97 ms           61.28 ms        31.1x  ██
config_to_get_to      0.98 ms           11.55 ms        11.8x  █
all_children_sorted   0.29 ms            2.35 ms         8.1x  ▋
dump()                2.43 ms           18.65 ms         7.7x  ▌
```

---

## The CPython Allocation Boundary

Notice that the speedups range from **7.7x** to **259x**. Why is the spread not
uniform?

The answer lies in **what an operation returns** and whether it crosses the
CPython allocation boundary.

### Rust-Bound vs. CPython-Bound Operations

| Category | Operations | What Returns to Python | Primary Cost Driver | Speedup Range |
|---|---|---|---|---|
| **Rust-Bound** | `parse`, `fast_load`, `deepcopy`, `remediation` | A single scalar, string, or root handle | Native Rust execution | **12x – 259x** |
| **CPython-Bound** | `dump()`, `all_children_sorted()` | *N* individual Python objects (one per node) | CPython object allocation & GC | **7x – 8x** |

### The Math of Object Materialization

In an 8,823-node configuration:

- In 3.x, the `HConfigChild` objects were *already* in Python memory. An
  operation like `all_children_sorted()` merely yielded references to objects
  that had already been allocated during parsing.
- In 4.0, nodes live in the Rust arena. When Python calls
  `all_children_sorted()`, the Rust engine must allocate 8,823 `HConfigChild`
  Python handle objects to give Python code access to each node.

How fast can CPython allocate 8,823 objects?

Direct micro-benchmarks measuring pure CPython allocation show:
- Allocating 8,823 *empty* Python `__slots__` objects (`object.__new__`) costs
  **0.537 ms**.
- The entire pure-Python 3.x traversal took 2.348 ms.

$$\text{Theoretical Speedup Ceiling} = \frac{2.348\text{ ms}}{0.537\text{ ms}} \approx 4.4\text{x}$$

Even if the native Rust traversal and sorting took **0.000 ms** (infinitely
fast), the end-to-end Python call could not exceed ~4.4x if it interned full
Python objects, purely because CPython must allocate memory for 8,823 handles!

### Profiling the Python FFI Split

Profiling the 4.0 hot paths with native probes revealed where time is spent:

| Operation | Python-Visible Wall Clock | Pure Rust Core Time | Spent Crossing into CPython |
|---|---:|---:|---:|
| **`dump()`** | 0.941 ms | 0.106 ms | **89%** |
| **`all_children_sorted()`** | 0.294 ms | 0.025 ms | **93%** |
| **`remediation`** | 0.392 ms | 0.297 ms | 24% |
| **`get_hconfig` (parse)** | 0.672 ms | 0.587 ms | 13% |
| **`fast_load`** | 0.604 ms | 0.553 ms | 8% |

For `dump()` and iteration, **89% to 93% of the execution time is spent inside
the CPython runtime** allocating objects, setting dictionary keys, and creating
tuples. The Rust computation is virtually instant (25 microseconds for
iteration; 106 microseconds for dump serialization).

### Beating the Python Construction Floor in `dump()`

`HConfig.dump()` produces a collection of `DumpLine` objects representing the
entire configuration tree as structured records.

In pure Python:
- Constructing 8,823 `DumpLine` models via standard Pydantic validation took
  **12.45 ms**.
- Pydantic v2's `model_construct()` was actually slower (**12.93 ms**).
- The fastest possible pure-Python construction (`object.__new__` plus slot
  assignment, sharing an empty frozenset) took **3.86 ms**.

In 4.0, Rust populates the underlying Python instance dictionaries directly
via the Python C-API without executing Python bytecode. As a result, 4.0
achieves **2.43 ms** for `dump()` — **faster than the theoretical pure-Python
allocation floor**.

---

## Iterative Optimization Passes

The headline numbers were not achieved in a single pass. Achieving them required
systematic profiling and tuning across five distinct phases:

### Pass 1: The Initial Rust Core & Binding
The initial migration implemented the arena allocator, regex matching, and
remediation diff in Rust. This established the baseline 10x–30x speedups for
parsing and diffing, but revealed that `dump()` was initially slower than pure
Python due to per-node Pydantic validation crossing the FFI boundary.

### Pass 2: Compiler Flags & Cross-Crate LTO
Cargo's stock release profile disables Link-Time Optimization (LTO) and compiles
16 separate codegen units. Because `hier_config_core` and `hier_config_py` are
distinct crates, hot-path functions could not be inlined across the crate
boundary.
Enabling `[profile.release]` with `lto = "fat"`, `codegen-units = 1`, and
`opt-level = 3` yielded an immediate **15% to 25% throughput gain** across all
operations.

### Pass 3: Memory Sizing & Hot-Path Allocation Pruning
Profiling with native allocation profilers exposed hidden vector re-allocations:
- **Arena capacity reservation**: `load_fast` was modified to call
  `tree.arena.reserve(lines.len())` upfront. Previously, large parses grew the
  arena repeatedly, copying 208-byte node structs on each expansion.
- **Ordered child optimization**: `collect_all_children_sorted` previously
  allocated and sorted a temporary `Vec` at every level of the tree. Because
  `order_weight` is left at default (0) on over 99% of nodes, a fast-path
  `children_already_ordered()` check was added. When children are already in
  order, the walk iterates the existing slice directly, eliminating thousands of
  heap allocations per traversal.
- **Sized traversal hints**: Traversal algorithms were updated to reserve
  capacity based on exact tree size hints, preventing repeated reallocations
  during whole-tree walks.

### Pass 4: Entry API Caching
The PyO3 handle interning cache initially used `cache.get()` followed by
`cache.insert()`, hashing every `NodeId` twice on cache misses. Switching to
the standard library `Entry` API eliminated the redundant hash lookup for every
child handle created.

### Pass 5: Non-Interning Bulk Traversals & Eager Tuples
In 4.0, bulk tree traversals (`all_children()`, `all_children_sorted()`,
`unused_objects()`) were migrated from lazy Python generators to eager native
tuples (`tuple[HConfigChild, ...]`).
Furthermore, handles created during bulk traversals bypass the persistent
interning cache, eliminating weakref tracking overhead and allowing CPython to
reclaim handle memory immediately after use. This reduced iteration time by
another **61%**.

---

## Performance Guardrails in CI

Performance gains can easily regress if a future PR introduces accidental
allocations, disables compiler inlining, or adds redundant FFI crossings.

To protect these gains, hier_config enforces an automated performance gate in
CI (`tests/benchmarks/test_perf_regression.py`).

### The Problem with Millisecond Thresholds

Absolute wall-clock timers cannot gate CI: shared virtualized GitHub Actions
runners vary in CPU speed by over 300% from run to run. A millisecond ceiling
calibrated for a developer workstation will either fail constantly on slow CI
nodes or be so loose that it catches no real regressions.

### The Calibration Unit Solution

Instead of measuring milliseconds, the regression test measures operations in
**calibration units**:

1. In the same test process, a fixed lump of pure-Python interpreter work
   (dictionary churn, string manipulation, and list joins) is timed. This
   establishes the machine's current execution speed as 1 unit:

   $$\text{1 Unit} = \text{Time to execute standardized Python calibration workload}$$

   *(On an Apple M2 Max, 1 unit $\approx$ 3.0 ms; on a standard GitHub Actions runner,
   1 unit $\approx$ 8.5 ms).*

2. Each hier_config operation is timed and divided by the calibration unit:

   $$\text{Cost in Units} = \frac{\text{Operation Elapsed Time (ms)}}{\text{Calibration Unit (ms)}}$$

If a CI runner is running twice as slow, both the calibration workload and the
hier_config operation slow down proportionally. The cost in calibration units
remains constant across different machines.

### Enforced CI Ceilings

The CI regression suite asserts strict upper bounds (`MAX_COST_UNITS`) against
a 400-interface configuration:

| Operation | Observed 4.0 Cost | CI Ceiling (`MAX_COST_UNITS`) | Safety Margin |
|---|---:|---:|---|
| **`deepcopy`** | **0.020 units** (0.06 ms) | 0.030 units | 1.5x |
| **`iteration`** | **0.037 units** (0.11 ms) | 0.060 units | 1.6x |
| **`remediation`** | **0.123 units** (0.37 ms) | 0.190 units | 1.5x |
| **`fast_load`** | **0.162 units** (0.48 ms) | 0.240 units | 1.5x |
| **`parse`** | **0.184 units** (0.55 ms) | 0.270 units | 1.5x |
| **`dump`** | **0.266 units** (0.80 ms) | 0.370 units | 1.4x |

Any PR that accidentally doubles an operation's cost (for instance, by disabling
regex caching or re-introducing temporary Python allocations) trips the gate and
fails CI before merging.

---

## Where to Look Next

- [Performance Roadmap](performance-roadmap.md) — The theoretical headroom
  remaining, and the future API changes (such as converting `DumpLine` to a
  `__slots__` class) planned for 5.0.
- [Architecture Overview](architecture.md) — The internal design of the Rust
  core, memory layout, and PyO3 handle lifecycle.
- [3.x to 4.0 Migration Guide](../user/rust-core-changes.md) — Guide for
  upgrading existing codebases to hier_config 4.0.
