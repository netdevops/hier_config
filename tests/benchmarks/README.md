# Performance regression protection

Performance regressions in this project are *silent*. Every result stays
correct, every functional test keeps passing, and the library just gets slower.
Two real examples from the Rust migration:

* `_native_post_load_matches` guarded the native parse path on `driver.platform`
  — an attribute no driver has. It always returned `False`, so `get_hconfig`
  fell back to a per-line Python loop with ~10,000 FFI crossings. **The whole
  suite still passed.**
* 19 call sites compiled their regexes on every use. Compiling costs ~10–100µs;
  running a compiled regex costs ~25ns. Routing them through a cache took a
  10k-line parse from **7354ms to 16ms**. No functional test noticed either way.

Neither was caught by the test suite, and neither would have been caught by a
benchmark suite that nobody runs. Hence three layers, ordered by cost.

## Layer 1 — Fast-path guards (`tests/test_native_fast_paths.py`)

Deterministic assertions that the native paths are *reachable*. No timing, runs
in ~0.05s as part of the normal suite.

These catch the "fast path became dead code" class directly. Reintroducing the
`driver.platform` bug fails 15 of these tests while the rest of the suite still
passes — which is precisely the point.

## Layer 2 — Source guard (`crates/hier_config_core/tests/no_inline_regex.rs`)

Fails the build if a regex constructor appears outside `regex_cache.rs`. Crude,
but zero-maintenance and it catches the highest-severity bug class before it can
ship. It found one genuine miss (`TextMatch::re_search`) the moment it was added.

Runs as part of `cargo test --workspace`.

## Layer 3 — Ratio gate (`tests/benchmarks/test_perf_regression.py`)

Times each operation under the native backend and the pure-Python backend, in
the same run on the same machine, and asserts a minimum speedup ratio.

**Why a ratio, not a threshold.** Absolute timings cannot gate CI: shared
runners vary by an order of magnitude, so a fixed millisecond budget is either
too loose to catch anything or too tight to stay green. A ratio is
self-normalising — a slow runner slows both backends equally. Measured spread
across repeated local runs is under 15%, versus the multiples seen in raw
timings.

Floors sit at ~65% of the lowest observed ratio. They are calibrated, not
guessed: disabling the regex cache drops parse from ~28x to 14.2x, which trips
the 18x floor.

```bash
pytest -m benchmark tests/benchmarks/test_perf_regression.py -s
```

### What the ratio gate does *not* catch

If a regression slows the native backend and the pure-Python backend equally, or
if a fallback path is still much faster than pure Python, the ratio barely
moves. Disabling the native parse fast path only took parse from 27x to 23x —
comfortably inside any sane floor. That failure mode belongs to Layer 1, which
catches it deterministically. The layers are complementary, not redundant.

## `baseline.json` and `test_perf_benchmark.py`

Historical Phase 0 artifacts recording absolute pure-Python timings from one
developer machine. They document the "before" state and are **not** used as a
gate by anything. Do not wire CI to them.
