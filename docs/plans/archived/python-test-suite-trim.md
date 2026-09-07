# Python Test Suite Trim & Coverage Re-anchoring — Planning Doc

## Status

- **State:** ⏹️ Closed / Superseded by `upstream/next` migration & Python facade consolidation
- **Owner:** Network Engineering & Core Automation Team
- **Last updated:** 2026-09-07
- **Prerequisite:** all six phase plans of the Rust-native testing strategy complete (Phases 0–5)
- **Related:**
  - `docs/dev/testing.md` (conventions and coverage thresholds)
  - `docs/dev/architecture.md` (layer ownership boundaries)
- **Supersedes / Superseded by:** Supersedes Phase 6 of the Rust-native testing strategy; superseded by the `upstream/next` test reorganization and the v4 Python surface area collapse into Rust PyO3 facades.

## Progress

- ✅ **Phase 1 — Displacement Audit**: Completed prior to rebase; remaining markers down to 5 in `tests/integration/`.
- ✅ **Phase 2 — Elimination of Legacy Driver Tests**: Superseded by `upstream/next` restructuring, which retired `tests/test_driver_*.py` into `tests/integration/test_<platform>.py`.
- ⏹️ **Phase 3 — Corpus Runner Narrowing**: Closed / deferred. The Python corpus runner (`tests/native/test_corpus.py`) runs in ~0.5s with PyO3 and provides continuous full-matrix verification against native testdata.
- ✅ **Phase 4 — Dead Code Pruning**: Completed — Python view and format implementations were removed and replaced with PyO3 delegations to the Rust core.
- ✅ **Phase 5 — Coverage Re-anchoring**: Enforced at 88% minimum (currently achieving ~91% coverage across 1,026 tests).
- ✅ **Phase 6 — Final Verification**: Full dual-language test suites and strict linters (`ruff`, `mypy`, `pyright`, `pylint`, `yamllint`) passing cleanly.

---

## Problem Statement

When Phases 0–5 of `docs/plans/rust-native-testing-strategy.md` land, the
repository will have two parallel test suites exercising the same core logic:

1. **Rust native suite:** Corpus-driven round-trips, integration introspection
   tests, property-based invariants, and doctests directly covering
   `crates/hier_config_core/` under an enforced Rust coverage floor.
2. **Legacy Python driver suite:** 3,185 lines across 13 `tests/test_driver_*.py`
   files — **136 tests** (81 round-trip, 55 introspection) executing the same
   behavioral checks through PyO3 wrappers.

This temporary duplication was intentional during migration to make the Rust
test suite provable and ensure zero regressions. However, maintaining both
suites permanently incurs continuous developer overhead, slows down CI, and
obscures the boundary between native logic and binding glue.

This planning document governs the execution of that trim. Because every
displaced Python test was tagged with a verified `@pytest.mark.displaced_by(...)`
marker during the first plan, deletion is a deterministic query rather than an
archaeological guessing game.

---

## Prerequisites & Entry Gates

All entry conditions are met and verified as of Phase 5 completion:

1. ✅ **Rust Test Suite Complete:** Phases 0–5 of `docs/plans/rust-native-testing-strategy.md`
   are implemented and verified (corpus runner, per-platform tests, property-based invariants, and doctests).
2. ✅ **Rust Coverage Gate Active:** CI enforces `rust-coverage` job
   (`cargo llvm-cov --fail-under-lines 47`). Current line coverage is 48.22% (5,435 lines evaluated across `hier_config_core`).
3. ✅ **100% Displacement Tagging:** All 136 driver tests (81 round-trip, 55 introspection) across 13 `tests/test_driver_*.py` carry `@pytest.mark.displaced_by(...)`. Zero unmarked driver tests remain.
4. ✅ **Marker Validation Passes:** `python scripts/check_displacement_markers.py` validated 136 displacement markers and exited 0.
5. ✅ **Corpus Parity:** All 81 round-trip cases in `testdata/` pass cleanly in both
   Rust (`cargo test --test corpus`) and Python (`pytest tests/test_corpus.py`).
6. ✅ **Doctests Green:** 8 runnable documentation tests in `hier_config_core` compile and pass (`cargo test --doc --package hier_config_core`).

---

## Retained vs. Displaced Layer Inventory

The layer ownership contract established in `docs/plans/rust-native-testing-strategy.md`
strictly governs what is deleted and what is preserved:

| Layer | Component | Action | Destination / Rationale |
|---|---|---|---|
| **Layer 1** | Tree operations, parsing, post-load fixups, view queries | **DELETE from Python** | Fully covered by native Rust unit & integration tests |
| **Layer 2** | Per-platform behavioral round-trips (`test_driver_*.py`) | **DELETE from Python** | Covered by `testdata/` corpus in `crates/hier_config_core/tests/corpus.rs` |
| **Layer 3** | PyO3 boundary, handle interning, object protocols, `__eq__`, pickle | **RETAIN in Python** | `tests/test_hier_config.py`, `tests/parity/` (proves Python runtime integration) |
| **Layer 4** | Public Python API (`WorkflowRemediation`, constructors, models, stubs) | **RETAIN in Python** | `tests/test_constructors.py`, `tests/test_workflows.py`, stub checks |
| **Layer 5** | Extension surface (custom drivers, callbacks, injected rules) | **RETAIN in Python** | `tests/test_extension_surface.py`, `tests/test_import_surface.py` |
| **Layer 6** | Performance regression gate | **RETAIN in Python** | `tests/benchmarks/` (calibrated regression tripwires) |

**Roughly 1,600 lines of Python tests in Layers 3–6 will never be deleted.**
Only the 3,185 lines of duplicated driver tests in Layers 1 & 2 are removed.

---

## Detailed Execution Phases

### Phase 1 — Displacement Audit & Verification

Before modifying any test files, execute an automated audit of the displacement
ledger:

1. Collect all marked tests via pytest and confirm the count is **136**:
   ```bash
   .venv/bin/python -m pytest tests/test_driver_*.py -m displaced_by --collect-only -q | tail -1
   .venv/bin/python -m pytest tests/test_driver_*.py --collect-only -q | tail -1
   ```
2. Run the displacement validator script (it takes no flags):
   ```bash
   .venv/bin/python scripts/check_displacement_markers.py
   ```
3. Audit any unmarked tests in `tests/test_driver_*.py`:
   ```bash
   .venv/bin/python -m pytest tests/test_driver_*.py -m "not displaced_by" --collect-only -q
   ```
   This must report zero tests. If an unmarked test remains:
   - Determine if it covers a Layer 1/2 feature (must be ported to Rust/corpus
     first before proceeding), or
   - Determine if it covers Layer 3/5 Python binding behavior (move to
     `tests/test_extension_surface.py` or `tests/test_hier_config.py`).

### Phase 2 — Mechanical Deletion of Driver Tests

With the audit green, delete the displaced tests:

1. For each `tests/test_driver_<platform>.py`:
   - Delete all functions decorated with `@pytest.mark.displaced_by`.
   - Remove unused imports, fixtures, and constants.
2. If all tests in a `tests/test_driver_<platform>.py` file were displaced:
   - Delete the empty test file entirely.
   - Any driver file with remaining Python-specific tests (e.g. testing
     subclassing errors or Python-specific overrides) is retained with only those
     tests.

### Phase 3 — Corpus Runner Narrowing

In `tests/test_corpus.py`:

1. Change the parametrization from `testdata/cases/*/*` (all 81 cases) to a curated
   smoke subset:
   - Exactly 1 representative case per platform (13 cases total).
2. The role of `tests/test_corpus.py` transforms from a behavioral test suite to
   an end-to-end PyO3 integration smoke test.
3. This cuts Python test execution time significantly while still validating that
   the Python bindings load, parse, remediate, and rollback configurations via
   the native engine.

### Phase 4 — Dead Code Pruning

With the legacy driver tests removed:

1. Inspect `hier_config/platforms/` for dead helper functions or transitional
   fixup code that was only kept alive to satisfy legacy test assertions.
2. Confirm no external callers or remaining tests reference them.
3. Remove dead functions cleanly.

### Phase 5 — Coverage Re-anchoring

The removal of dead code and duplicated tests changes the Python test coverage
profile:

1. Run the test suite with coverage:
   ```bash
   python scripts/build.py pytest --coverage
   ```
2. The Python coverage baseline will no longer be artificially depressed by
   unused transitional code.
3. Update `pyproject.toml` and CI workflows (`.github/workflows/build-and-test.yml`):
   - Ratchet the `--cov-fail-under` floor upward from 88% back toward 95%.
4. Verify strict type checking (`mypy`, `pyright`) and linter checks pass.

### Phase 6 — Final Verification & Documentation

1. Run the full verification pipeline:
   ```bash
   cargo fmt --check && cargo clippy --all-targets --all-features -- -D warnings
   cargo test --workspace
   python scripts/build.py lint-and-test
   mkdocs build --strict
   ```
2. Update `docs/dev/testing.md` to reflect the final state:
   - Driver behavioral testing is 100% Rust / `testdata/`.
   - Python tests cover bindings, workflows, extensions, and packaging.
   - Python coverage floor is re-anchored.
3. Add a `[Removed]` and `[Changed]` entry to `CHANGELOG.md` under `## [Unreleased]`.

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Accidental deletion of a Layer 3–5 Python binding test | High | Strict enforcement of the displacement marker validator in Phase 1. Only tests explicitly decorated with `@pytest.mark.displaced_by` that map to verified Rust tests may be deleted. |
| Python coverage drops unexpectedly after test removal | Medium | Phase 4 removes the corresponding dead Python code before Phase 5 recalculates the floor. The remaining codebase consists primarily of thin shims and workflows with near-100% coverage. |
| Latent regression in a specific platform's Python binding | Low | Phase 3 retains a 13-platform smoke test in `tests/test_corpus.py`, ensuring every platform driver still instantiates and runs round-trips via Python. |

---

## Success Criteria

1. All ~3,000 lines of redundant Layer 1 & 2 Python driver tests are cleanly deleted.
2. All 13 platforms retain end-to-end verification via Rust corpus tests and integration tests.
3. `tests/test_corpus.py` runs a lean 13-case smoke suite in Python CI.
4. Python coverage floor is raised back to ≥ 95% in `pyproject.toml`.
5. CI execution time for the Python test suite is noticeably reduced.
6. Zero regressions in the public Python API or PyO3 extension surface.
