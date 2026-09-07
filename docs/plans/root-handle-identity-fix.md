# Plan: Fix the root-identity trap and gate stub accuracy in CI

**Audience:** an AI coding agent executing this end to end.
**Branch:** `rust-rewrite-plan` (this feature branch — do not create a new branch).

Follow the tasks in order. Each task has a verification gate. **Do not start a task
until the previous task's gate passes.** If a gate fails in a way this plan does not
describe, STOP and report — do not improvise a workaround.

---

## Background (read before editing)

`HConfigChild.parent` and `HConfigChild.root` must return *the same Python object*
the caller constructed:

```python
cfg = get_hconfig(Platform.CISCO_IOS, "interface Gi0/0\n description x\n")
kid = cfg.get_child(startswith="interface")
assert kid.parent is cfg   # must be True
```

This works because the Rust `SharedTree` stores a `root_handle` — a reference to the
root's Python object. `PyHConfig::__init__` (`crates/hier_config_py/src/root.rs`)
populates it.

**The bug:** PyO3 puts `__init__` in the native type's `__dict__` but never wires it
to CPython's `tp_init` slot. `type_call` uses the *slot*, so constructing the native
class directly never runs it:

```
rust.HConfig(drv) → add_child       : kid.parent is root -> False   # silently wrong
rust.HConfig(drv); obj.__init__(drv): kid.parent is root -> True
```

The only reason the library works is that `hier_config/root.py` defines a Python
subclass. Defining a Python subclass makes CPython run `fixup_slot_dispatchers`,
which wires that subclass's `__init__` into `tp_init`; it calls
`super().__init__(driver)`, which reaches the native `__init__`.

So `hier_config/root.py`'s `__init__` is **load-bearing**, not boilerplate.

When `root_handle` is `None`, `child.rs` currently *mints a brand-new `PyHConfig`*
and caches it. That is the silent failure: the caller gets a different object that
wraps the same tree, so `is` comparisons fail while everything else looks fine.

**The fix:** keep the Python subclass (it is the correct and only supported
constructor), document it so nobody "simplifies" it away, add regression tests, and
replace the duplicate-minting fallbacks with a loud error.

### Why we are not doing other things

- **Do not** try to make PyO3 wire `tp_init`. It cannot be done from `#[pymethods]`;
  `#[new]` returns a `PyClassInitializer` before the object exists.
- **Do not** touch the `.pyi` stubs. The missing comparison dunders on `HConfig` and
  `HConfigChildren` are **deliberate and correct** — those types genuinely raise
  `TypeError` on `<`, and `scripts/gen_stubs.py` documents this at `FORCE_EMIT`.

### Scope

Your entire change set is:

```
hier_config/root.py                        (Task 1)
tests/test_hier_config.py                  (Task 2)
crates/hier_config_py/src/child.rs         (Task 3)
scripts/gen_stubs.py                       (Task 4 — ALREADY DONE, verify only)
scripts/build.py                           (Task 5)
.github/workflows/build-and-test.yml       (Task 6)
CHANGELOG.md                               (Task 7)
docs/plans/root-handle-identity-fix.md     (delete at the end)
```

Do not modify any other file. In particular **do not edit the four generated stubs**
(`hier_config/{base,child,children,root}.pyi`) by hand — they are generated output,
and Task 4's gate proves they are already correct.

### Environment

### Environment

Bare `python`, `pytest`, `mkdocs`, `pylint` are **not** on `PATH`. Always use
`.venv/bin/<tool>`, or prefix `PATH="$PWD/.venv/bin:$PATH"`.

---

## Task 1 — Document the load-bearing `__init__`

**File:** `hier_config/root.py`

Add a comment to the `__init__` method explaining why it cannot be removed. Keep the
existing behavior byte-for-byte; this task adds a comment only.

The comment must state:

- `super().__init__(driver)` populates the Rust-side `root_handle`.
- Defining this subclass is what wires `__init__` into `tp_init`; the native class
  alone does not.
- Removing it makes `child.parent is config` and `child.root is config` return
  `False`.

### Gate 1

```bash
cd "$(git rev-parse --show-toplevel)"
git diff --stat hier_config/root.py
```

Expect: only `hier_config/root.py` changed, insertions only, no deletions of code.

---

## Task 2 — Add regression tests (TDD: write these before Task 3)

**File:** `tests/test_hier_config.py`

Add flat, fully annotated test functions (no classes — see `AGENTS.md`). Match the
existing style in that file.

Add two tests:

1. `test_child_parent_and_root_are_the_constructed_object` — build a config with
   `get_hconfig`, take a nested child, and assert **all** of:
   - `child.parent is config`
   - `child.root is config`
   - for a grandchild, `grandchild.root is config`

2. `test_native_hconfig_without_init_raises_on_parent` — construct the native class
   directly and assert the trap now fails loudly:

   ```python
   import _hier_config_rust

   native = _hier_config_rust.HConfig(get_hconfig_driver(Platform.CISCO_IOS))
   child = native.add_child("interface Gi0/0")
   with pytest.raises(RuntimeError, match="root_handle"):
       _ = child.parent
   ```

   Adjust the `match=` string to whatever message you use in Task 3 — but pick the
   message in Task 3 *first* and keep them consistent.

### Gate 2

```bash
.venv/bin/pytest tests/test_hier_config.py -q
```

Expect: test 1 **passes** (current behavior is already correct via the subclass),
test 2 **fails** (the fallback still mints a duplicate instead of raising).

If test 1 fails, STOP — something else is broken. If test 2 passes, STOP — re-read
the test, it is not exercising the native path.

---

## Task 3 — Replace the duplicate-minting fallbacks

**File:** `crates/hier_config_py/src/child.rs` (only this file)

There are two blocks that construct a fresh `PyHConfig` when
`base.tree.root_handle` is `None`:

- inside the `parent` getter, in the `if is_root { ... }` branch (~lines 84–110)
- inside the `root` getter (~lines 124–155)

Each currently reads the handle, and on `None` builds a new `PyHConfig` via
`Py::new(...)`, stores it in `root_handle`, and returns it.

Replace **both** fallbacks so that when the handle is `None` they return a
`PyRuntimeError` instead of minting an object. Factor the shared logic into one
private helper in this file rather than duplicating it.

The error message must be actionable and must contain the literal substring
`root_handle` (so the Task 2 test can match it). It should tell the caller to
construct via `hier_config.HConfig` / `get_hconfig()` rather than
`_hier_config_rust.HConfig` directly.

After this change, `PyHConfig::get_default_driver` and the `driver_obj` read may
become unused *in this file*. Remove now-dead imports/locals — `clippy` runs with
`-D warnings` and will fail the build otherwise. Do **not** delete anything from
`root.rs`.

### Gate 3a — Rust

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --workspace
```

All three must pass. `cargo` may block briefly if another session holds the build
lock — wait and retry rather than killing it.

### Gate 3b — rebuild and run the Python suite

```bash
maturin develop --release
.venv/bin/pytest -q
```

Expect: **both** Task 2 tests pass, and the rest of the suite is green.

**If other tests now fail with your new `RuntimeError`,** that means some legitimate
code path reaches a tree whose `root_handle` was never registered — the assumption
behind this task is wrong. STOP and report which tests failed and the traceback. Do
not weaken the test or revert to minting a duplicate to make it pass.

---

## Task 4 — Verify the stub generator fix (already applied)

**File:** `scripts/gen_stubs.py` — **this change is already in your working tree.
Do not rewrite it. Your job here is only to verify it.**

Context you need: the four stubs `hier_config/{base,child,children,root}.pyi` are
generated by `scripts/gen_stubs.py`, which recovers type annotations from the
v3.7.0 pure-Python sources. Several methods were generators back then but return
eager `tuple`/`list` in the Rust port, so the generator emitted `Iterator[...]`
where the truth is `Sequence[...]`. Someone hand-corrected the committed stubs and
never fixed the generator, so regeneration produced ~127 lines of drift.

The applied fix adds a `RETURN_OVERRIDES` table (replaces only the return
annotation, so recovered docstrings survive), adds `Sequence` to two `HEADERS`
entries, makes the script run its own `ruff` passes, and adds a non-mutating
`--check` mode.

### Gate 4

Run each command and confirm the stated result. **If any differs, STOP and report.**

```bash
# a. write mode regenerates the committed stubs byte-for-byte
.venv/bin/python scripts/gen_stubs.py
git diff --exit-code -- hier_config/base.pyi hier_config/child.pyi \
    hier_config/children.pyi hier_config/root.pyi
```
Expected: exit 0, no diff.

```bash
# b. --check passes silently on a clean tree
.venv/bin/python scripts/gen_stubs.py --check ; echo "EXIT=$?"
```
Expected: `EXIT=0`, no output.

```bash
# c. --check detects drift and does NOT repair it
printf '\n# drift\n' >> hier_config/root.pyi
.venv/bin/python scripts/gen_stubs.py --check ; echo "EXIT=$?"
git checkout -- hier_config/root.pyi
```
Expected: `EXIT=1` and a "Committed stubs are out of date" message naming
`hier_config/root.pyi`. The `git checkout` cleans up.

```bash
# d. the script itself lints clean
.venv/bin/python -m ruff check scripts/gen_stubs.py
.venv/bin/python -m ruff format --check scripts/gen_stubs.py
```
Expected: both exit 0.

---

## Task 5 — Expose the gate locally via `scripts/build.py`

**File:** `scripts/build.py`

Add a standalone command mirroring the existing `check_displacement_markers`
pattern. Insert it immediately **after** the `_check_displacement_markers_command`
function:

```python
@app.command()
def check_stubs() -> None:
    """Fail if the committed .pyi stubs differ from freshly generated ones."""
    _run(_check_stubs_command())


def _check_stubs_command() -> str:
    return f"{sys.executable} scripts/gen_stubs.py --check"
```

> **Do NOT add `_check_stubs_command()` to the tuples inside `lint()` or
> `lint_and_test()`.** Those run commands *in parallel* via
> `_run_commands_threaded`. The stub check temporarily rewrites the `.pyi` files
> before restoring them, so running it concurrently with `mypy`, `pyright`, or
> `ruff` would race and produce flaky failures. It must stay a serial,
> standalone command.

### Gate 5

```bash
PATH="$PWD/.venv/bin:$PATH" python scripts/build.py check-stubs ; echo "EXIT=$?"
```
Expected: `EXIT=0`.

```bash
.venv/bin/python -m ruff check scripts/build.py
```
Expected: exit 0.

---

## Task 6 — Add the fail-only CI gate

**File:** `.github/workflows/build-and-test.yml`

In the **`python-lint`** job only, append one step after the existing
`Check displacement markers` step, keeping the same indentation as its siblings:

```yaml
    - name: Check stubs are up to date
      run: python scripts/gen_stubs.py --check
```

Why this job: `python-lint` already runs `maturin develop --release --locked`, and
`gen_stubs.py` imports the compiled `_hier_config_rust`, so the extension is
present. Steps in a job run sequentially, so there is no race with the linters.

The gate is **fail-only**. It must never commit, push, or open a PR. `--check`
restores the original files before exiting, so the checkout is left untouched; the
job simply reports a non-zero exit when the stubs are stale.

### Gate 6

```bash
.venv/bin/python -m yamllint .github/workflows/build-and-test.yml
```
Expected: exit 0.

Confirm by reading the file that the new step is inside `python-lint` (not
`python-tests` or `rust-tests`) and that you added no other step.

---

## Task 7 — Changelog

**File:** `CHANGELOG.md`

Add **two** entries under `## [Unreleased]` in the `### Fixed` category (create the
category if it is missing).

1. Constructing `_hier_config_rust.HConfig` directly used to yield children whose
   `.parent` / `.root` returned a *different* object; it now raises instead of
   failing silently.
2. `scripts/gen_stubs.py` emitted `Iterator[...]` for methods that actually return
   eager sequences, so regenerating the stubs produced spurious drift. The
   generator now matches the committed stubs, and CI fails if they diverge.

Do **not** invent a `(#NNN)` reference — there is no issue for this, and the PR
number is being handled separately. Omit the reference entirely.

---

## Task 8 — Final verification

```bash
PATH="$PWD/.venv/bin:$PATH" python scripts/build.py lint-and-test
PATH="$PWD/.venv/bin:$PATH" python scripts/build.py check-stubs
```

Both must exit 0.

Docs: no public API or driver behavior changed, so `docs/` needs no update and you
do **not** need to run `mkdocs build --strict`.

Then delete this plan file (it is untracked, so use `rm`, not `git rm`):

```bash
rm docs/plans/root-handle-identity-fix.md
```

---

## Task 9 — Commit

Use the `commit-by-feature` skill. Expect **two** commits — the runtime fix and the
tooling/CI gate are unrelated concerns:

| # | Subject | Files |
|---|---------|-------|
| 1 | `fix: raise instead of minting a divergent root handle` | `hier_config/root.py`, `crates/hier_config_py/src/child.rs`, `tests/test_hier_config.py` |
| 2 | `build: gate generated stub accuracy in CI` | `scripts/gen_stubs.py`, `scripts/build.py`, `.github/workflows/build-and-test.yml` |

Put the `CHANGELOG.md` entry for each fix in its matching commit (stage the file
twice, once per hunk, using `git add -p` if needed; if that proves awkward, include
the whole changelog in commit 2).

Stage **only** the files listed in "Scope". Verify before each commit:

```bash
git status --short
```

Other files are already modified in this branch by earlier work — leave them
unstaged. Do not use `git add -A` or `git commit -a`.

Commit subjects: imperative mood, ≤72 characters. Bodies explain *why* (commit 1:
the `tp_init` slot is never wired, so the Python subclass is required; commit 2:
stub accuracy cannot depend on a human remembering to run a script). Include the
`Co-authored-by` trailer on both.

---

## Definition of done

- [ ] `hier_config/root.py` documents why `super().__init__()` cannot be removed
- [ ] Two regression tests added and passing
- [ ] Both `child.rs` fallbacks raise instead of minting a divergent root
- [ ] `cargo fmt --check`, `clippy -D warnings`, `cargo test --workspace` pass
- [ ] `gen_stubs.py` round-trips the committed stubs with zero drift (Gate 4)
- [ ] `scripts/build.py check-stubs` exists and exits 0
- [ ] `python-lint` CI job runs `gen_stubs.py --check`
- [ ] `python scripts/build.py lint-and-test` exits 0
- [ ] `CHANGELOG.md` updated under `## [Unreleased]` with both entries
- [ ] This plan file deleted
- [ ] Two commits, containing only the listed files
