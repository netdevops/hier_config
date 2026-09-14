Contributing
============

Fork, then clone the repo:

```
git@github.com:YOUR-USERNAME/hier_config.git
```

Install uv:

```
https://docs.astral.sh/uv/getting-started/installation/
```

Set up your environment:

Install Python 3.10+ and Rust meeting `workspace.package.rust-version` in
`Cargo.toml` (currently 1.98), including a working C/C++ linker. The v4 engine
is Rust with PyO3 bindings; source development has no pure-Python fallback.
uv manages Python dependencies; maturin builds the extension.

```bash
cd hier_config
uv sync --locked --extra yaml
uv run --no-sync maturin develop --release --locked
```

Rebuild after Rust changes before running Python checks. `--no-sync` prevents
uv from replacing the rebuilt extension with an older cached wheel; rebuild
again after any subsequent `uv sync`. Commit both
`uv.lock` and `Cargo.lock` when their dependency manifests change.
Create a branch from the right base: v4 features and breaking changes branch from **`next`**; v3.x maintenance fixes branch from **`master`**.

```
git checkout next
git checkout -b YOUR-BRANCH
```

Open your pull request against the same branch you based on (`next` for v4 work).

Make sure linters, type-checkers, and tests pass:

```
uv run --no-sync python scripts/build.py lint-and-test
```

Make your change. Add tests for your change. Make the linters, type-checkers, and tests pass:

```
uv run --no-sync python scripts/build.py lint-and-test
```

Push to your fork and submit a pull request.

At this point, you're waiting on us. We'll at least comment. We may suggest changes, improvements, or alternatives.

Some things that will increase the chance that your pull request is accepted:

* Write to the python style-guide (https://www.python.org/dev/peps/pep-0008/).
* Write tests.
* Write docstrings (https://www.python.org/dev/peps/pep-0257/).
* Write a good commit message.

---

## Running Tests

Run the full test suite:

```bash
uv run --no-sync pytest
```

Run a single test file:

```bash
uv run --no-sync pytest tests/integration/test_cisco_ios.py
```

Stop on the first failure:

```bash
uv run --no-sync pytest -x
```

Run tests in parallel (requires `pytest-xdist`):

```bash
uv run --no-sync pytest -n auto
```

Run with coverage:

```bash
uv run --no-sync ./scripts/build.py pytest --coverage
```

The Python coverage floor remains **95%**; moving implementation into Rust is
not permission to lower quality gates. Python coverage does not measure native
code. Run the native gates as well:

```bash
cargo fmt --check
cargo clippy --locked --all-targets --all-features -- -D warnings
cargo test --locked --workspace --all-features
cargo llvm-cov --locked --package hier_config_core --fail-under-lines 47
```

Use `tests/native/` for Python/native-boundary contracts, `tests/parity/` for
upstream behavior comparisons, and `testdata/cases/` for shared Rust/Python
round-trip scenarios. See [Testing](docs/dev/testing.md) for corpus maintenance.
---

## Running Linters Individually

The build script runs all of these over `hier_config`, `tests`, and `scripts`:

```bash
uv run --no-sync ruff check .                  # style + lint
uv run --no-sync ruff format --check .         # formatting (no changes)
uv run --no-sync mypy hier_config/ tests/ scripts/     # type checking
uv run --no-sync pyright hier_config/ tests/ scripts/  # additional type checking
uv run --no-sync pylint hier_config/ tests/ scripts/   # extended lint rules
uv run --no-sync yamllint .                    # YAML files
uv run --no-sync flynt -d -tc -f hier_config tests scripts  # f-string conversion check
```

To auto-fix ruff issues:

```bash
uv run --no-sync ruff check --fix .
uv run --no-sync ruff format .
```

---

## Commit Message Style

- Use the **imperative mood** in the subject line: "Add feature" not "Added feature".
- Keep the subject line to **72 characters or fewer**.
- Leave a **blank line** between the subject and the body.
- The body should explain *why*, not *what* (the diff shows what).

Example:

```
Add negation_negate_with support to load_driver_rules

When loading driver rules from a dict, users may need to express custom
negation strings. This change forwards that value into the
NegationDefaultWithRule model so that the behaviour is preserved.
```

---

## PR Expectations

- **Tests required** — all new behaviour must be covered by tests: unit tests in
  `tests/unit/`, end-to-end driver scenarios in `tests/integration/test_<platform>.py`.
- **Linting must pass** — `uv run --no-sync python scripts/build.py lint-and-test` must exit 0.
- **Changelog entry required** — every PR adds an entry to `CHANGELOG.md` under
  `## [Unreleased]` (Keep a Changelog categories, with a `(#NNN)` reference).
- **Docstrings for new public API** — any new public class, method, or function
  must have a docstring.
- **No breaking changes without discussion** — open an issue first if you plan to
  change a public interface.

---

## Architecture Orientation

Where do changes belong?

| Change type | Location |
|-------------|----------|
| New platform support | `crates/hier_config_core/src/platforms/` (native operations/rules), Python driver facade, enums and registry |
| New rule type | Python rule model/container plus Rust rule decoding and evaluation |
| New utility function | `hier_config/utils.py` |
| New view property | `crates/hier_config_core/src/view/`, `crates/hier_config_py/src/view.rs`, and type stubs; Python view files are facades |
| Core tree algorithm | `crates/hier_config_core/src/`; expose Python contracts in `crates/hier_config_py/src/` |

Read the [Architecture Overview](docs/dev/architecture.md) before making structural changes.

---

## IDE Tips

**VS Code**

- Install the [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) extension and enable strict mode in `settings.json`:

  ```json
  "python.analysis.typeCheckingMode": "strict"
  ```

- Install the [Ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) extension for inline lint feedback.

**PyCharm**

- Enable the **mypy** plugin (Settings → Plugins → mypy) and point it at `uv run --no-sync mypy`.
- Configure ruff as an external tool for on-save formatting.
