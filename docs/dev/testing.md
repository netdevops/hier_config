# Testing Conventions

hier_config follows **Test-Driven Development (TDD)**: write a failing test that validates the expected behavior, confirm it fails for the right reason, implement the minimal code to make it pass, then run the full suite for regressions.

## Commands

Install Python dependencies with `uv sync --locked --extra yaml` and build the
extension with `uv run --no-sync maturin develop --release --locked` first.
Use `--no-sync` afterward: automatic synchronization can replace the fresh
extension with an older cached wheel. Rebuild after `uv sync` or Rust edits;
otherwise Python tests can exercise the old binary. Source builds need
Python 3.10+, a linker, and Rust meeting the MSRV in `Cargo.toml`.

```bash
# Python lint + test suite (native gates are separate)
uv run --no-sync ./scripts/build.py lint-and-test

# Tests only (95% coverage required)
uv run --no-sync ./scripts/build.py pytest --coverage

# A single test
uv run --no-sync pytest tests/integration/test_cisco_ios.py::test_delete_sectional_exit_regression -v

# A single file
uv run --no-sync pytest tests/integration/test_cisco_ios.py -v

# Only unit tests / only integration tests
uv run --no-sync pytest tests/unit/ -v
uv run --no-sync pytest tests/integration/ -v
```

Coverage must stay at or above **95%** (`--cov-fail-under=95`, enforced by `scripts/build.py` and CI).

## Native and boundary tests

The implementation is split between `crates/hier_config_core` (algorithms,
parsing, formats, views) and `crates/hier_config_py` (Python bindings).
Python coverage does not measure either crate. The separate Rust-core line
coverage gate has a **90% floor**, not the Python gate's 95%.
Do not lower either gate when moving behavior across the boundary.

```bash
cargo fmt --check
cargo clippy --locked --all-targets --all-features -- -D warnings
cargo test --locked --workspace --all-features
cargo llvm-cov --locked --package hier_config_core --fail-under-lines 90
uv run --no-sync pytest tests/native/ tests/parity/ -v
```

`cargo llvm-cov` requires the cargo-llvm-cov tool and `llvm-tools-preview`.
CI additionally checks the declared MSRV, Rust docs, dependency policy, clean
wheel installation, and supported Python/OS combinations.

- Rust unit/integration tests cover implementation behavior without Python.
- `tests/native/` covers extension imports, signatures, callbacks, handles,
  native fast paths, and the Python runner for the shared corpus.
- `tests/parity/` compares object protocols against the recorded upstream
  behavior. Intentional differences must be explicit, reviewed expectations,
  not blanket skips.
- Native stub freshness, export coverage, `stubtest`, and observed return-type
  checks complement runtime tests. Regenerate the canonical
  `hier_config/_hier_config_rust.pyi` after changing binding metadata with
  `uv run --no-sync ./scripts/build.py generate-stubs`. Generation needs no Git
  history; `check-stubs` must fail on drift without rewriting files.
- Packaging CI runs positive and negative consumer typing contracts with mypy
  and pyright against an installed wheel outside the checkout. The contracts
  and audited runtime allowlists live in `tests/typing/`; no repository-local
  `mypy_path` or `stubPath` is required.
  Pylint checks every runtime `.py` source; Ruff and the type checkers validate
  the `.pyi` declarations rather than treating their empty bodies as executable
  Python.

### Shared remediation corpus

Each `testdata/cases/<platform>/<case>/` contains `case.json`, `running.conf`,
`intended.conf`, and optional `remediation.conf`. Both
`crates/hier_config_core/tests/corpus.rs` and `tests/native/test_corpus.py`
consume these cases. Missing `remediation.conf` means the expected remediation
is empty. Indentation in the expected output is significant.

Keep `assert_rollback` enabled: assert exact remediation, apply it, compute and
apply rollback, and assert no diff from the original. Disable rollback only
for a documented prediction limitation, never to hide a regression. Add
Python-boundary tests too when a fix involves wrapper identity, exceptions,
constructors, or callback dispatch.

Preserve the source test's setup, not just its text and expected output:
`cisco_nxos/line_console_terminal_settings_negation_negate_with` carries its
upstream injected negation rules in case metadata, rather than changing stock
NX-OS defaults. Both that case and `cisco_xr/template_block_indent_adjust`
select `loader: "lines"` to match the source tests' `from_lines()` calls instead
of text preprocessing. Their manifest `source` entries identify the exact
upstream test at `upstream/next@0866dc2`.
The expected outputs are unchanged; the correction is to loader/custom-rule
setup and provenance, **not an intentional divergence**. See
`testdata/README.md` for the manifest schema. Corpus coverage alone still does
not prove universal upstream parity.

When moving a Python assertion into Rust, retain equivalent assertions and
identify the target with a `displaced_by` marker (`corpus:<path>` or a native
test target). `scripts/check_displacement_markers.py` validates targets.
A marker alone does not prove equivalent coverage; review the assertions.

### Structured-format reference provenance

The format fixtures distinguish an independent reference from native regression
snapshots:

- `testdata/formats/expected.json` contains IOS/EOS and error expectations
  captured from the fingerprinted pure-Python source at
  `upstream/next@0866dc2316443909edea2d629117b44a3a9ed472`.
- `testdata/formats/native-v1.json` retains historical Junos expectations
  from `fa49af6fffd1a529807c0e14aeb5e6ff9dc83a6c`. These are native regression
  snapshots, **not independent upstream parity evidence**: the Python
  reference rejects that unflattened JSON/XML remediation input because it
  expects set/delete syntax.

`scripts/gen_formats_corpus.py --check` compares the current backend to both
frozen sets; the Rust harness likewise preserves their disjoint cases. Only
the stable `InvalidConfigError` prefixes for malformed JSON/XML are normalized,
not semantic outputs. Default invocation refuses to overwrite references.
`--capture-reference` requires the exact fingerprinted pure-Python archive on
`PYTHONPATH`; it must not capture the implementation under test as its own
oracle. The script cannot regenerate the native snapshots.

### Preserved upstream limitations

The native regression audit also records behavior inherited from the pure-Python
reference at `0866dc2316443909edea2d629117b44a3a9ed472`, rather than silently
changing it:

- XML mixed-content tail text is not represented by the config-tree mapping
  (`hier_config/formats.py`); see [Loading configs](../user/loading-configs.md).
- The HP ProCurve interface view passes the complete `speed-duplex` command
  to helpers that expect only its value, so configured speed is not reported
  (`hier_config/platforms/hp_procurve/view.py`). Native view tests retain this
  behavior pending a separate compatibility decision.
- Python child moves can leave stale parent references and allow cyclic
  attachment (`hier_config/child.py`). These inherited mutation semantics were
  not redesigned by the coverage audit; callers should avoid cyclic moves.
- Idempotency capture keys normalize both absent and empty groups to empty
  strings and join captures with `|` (`hier_config/platforms/driver_base.py`).
  This can conflate capture tuples containing that delimiter. The audit restores
  capture positions lost by Rust but preserves the upstream encoding.
- Junos, VyOS and SRL future/rollback prediction can retain both a deletion and
  the original `set` command. Python `child.py` strips only the negation prefix;
  `tree_algorithms.py` then cannot match the remaining text to the original
  `set` command. For example, changing `set system host-name old-router` to
  `set system host-name new-router` can project the delete, new and old commands.
  SRL has the same behavior with `system name host-name`.
- With `sectional_overwrite_no_negate`, projecting a replacement section can
  raise `DuplicateChild` because Python `tree_algorithms.py` copies both the
  replacement and the original section. The regression suite characterizes
  this separately from the metadata-equality fix.

### Deferred native parity gap

Junos `try_swap_negation()` rejects commands without a set/delete/activate/
deactivate prefix, as the original Python driver does. Native
`try_compute_negation()` retains a permissive fallback for the same text.
This is a native divergence, not an upstream Python bug.

Making the latter strict also breaks the frozen Junos NETCONF/gNMI cases:
their structured trees contain unflattened data nodes rather than CLI commands.
The audit therefore characterizes and preserves this fallback without rewriting
`testdata/formats/native-v1.json`. Resolving the gap requires distinguishing
structured-data negation from set-style command validation.

## Conventions

- **Flat, function-based tests** — no test classes. (The only exceptions are the benchmark groupings in `tests/benchmarks/test_benchmarks.py` and the parametrized circular-workflow suite.)
- **Tests mirror the source layout**: unit tests for individual classes and functions live in `tests/unit/` (with driver unit tests in `tests/unit/platforms/` and config view tests in `tests/unit/platforms/views/`); end-to-end remediation scenarios live in `tests/integration/` with one file per platform (e.g., `test_cisco_xr.py`). Driver behavior changes belong in the matching file.
- **Fixtures** are module-scoped, defined in the relevant `conftest.py`, and read config text from the sibling `fixtures/` directory. Add new sample configs there rather than embedding large configs inline.
- **Full type annotations** — test functions are annotated (`def test_x() -> None:`) and pass the same strict type checking as library code.

## The Dominant Test Idiom

Most driver tests follow a round-trip assertion chain — build both configs, compute the remediation, assert its exact text, then prove the rollback restores the original:

```python
def test_example() -> None:
    running_config = HConfig.from_lines(platform, ("interface Ethernet1", "  shutdown"))
    generated_config = HConfig.from_lines(platform, ("interface Ethernet1", "  no shutdown"))

    remediation = running_config.remediation(generated_config)
    assert remediation.to_lines() == ("interface Ethernet1", "  no shutdown")

    running_after = running_config.future(remediation)
    rollback = running_after.remediation(running_config)
    running_after_rollback = running_after.future(rollback)
    assert not tuple(running_config.unified_diff(running_after_rollback))
```

When fixing a bug, add a regression test that would have caught it.

## Benchmarks

Performance benchmarks live in `tests/benchmarks/test_benchmarks.py` and are **skipped by default** via the `benchmark` pytest marker (`addopts = "-m 'not benchmark'"`). They generate ~10,000-line configs and assert upper time bounds.

```bash
# All benchmarks, with timing output
uv run --no-sync pytest -m benchmark -v -s

# One benchmark
uv run --no-sync pytest -m benchmark -k test_parse_large_ios_config -v -s
```

If a benchmark fails its time threshold, investigate the relevant code path for performance regressions.

## v3 compatibility tests

`tests/integration/v3_scenarios.py` holds scenarios that run under **both** hier_config v3 and v4. Its core mirrors `nautobot_golden_config.models._get_hierconfig_remediation`, the reference v3 consumer. Keep that module importable on both majors: no v4-only imports, no pytest fixtures, and no v4 behaviour that the [v3 compatibility surface](../user/v3-compatibility.md) does not cover.

Two tests consume it:

- `tests/integration/test_v3_baseline.py` compares `run_all()` against `tests/fixtures/v3_baseline.json`, a committed recording made on v3.7.0. It runs in the normal suite -- no network, no second environment.
- `tests/integration/test_v3_differential.py` diffs against a **live** v3 install. It is deselected by default via the `v3_differential` marker because it builds a virtual environment and downloads from PyPI.

```bash
# Diff against a live v3 install
uv run --no-sync pytest -m v3_differential -v

# Re-record the baseline after changing v3_scenarios.py
uv run --no-sync ./scripts/generate_v3_baseline.py
```

After changing `v3_scenarios.py`, regenerate the baseline and **review the diff**. A changed value for an existing scenario means v4 no longer matches v3 -- fix the compatibility surface, not the recording.
