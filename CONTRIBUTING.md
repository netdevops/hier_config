Contributing
============

Fork, then clone the repo:

```
git@github.com:YOUR-USERNAME/hier_config.git
```

Install Poetry:

```
https://python-poetry.org/docs/#installation
```

Set up your environment:

```
cd hier_config
poetry install
poetry shell   # Poetry 2.x: requires the shell plugin, or use `poetry run <cmd>` / `poetry env activate`
```

Create a branch from the right base: v4 features and breaking changes branch from **`next`**; v3.x maintenance fixes branch from **`master`**.

```
git checkout next
git checkout -b YOUR-BRANCH
```

Open your pull request against the same branch you based on (`next` for v4 work).

Make sure linters, type-checkers, and tests pass:

```
python scripts/build.py lint-and-test
```

Make your change. Add tests for your change. Make the linters, type-checkers, and tests pass:

```
python scripts/build.py lint-and-test
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
pytest
```

Run a single test file:

```bash
pytest tests/integration/test_cisco_ios.py
```

Stop on the first failure:

```bash
pytest -x
```

Run tests in parallel (requires `pytest-xdist`):

```bash
pytest -n auto
```

Run with coverage:

```bash
pytest --cov=hier_config
```

---

## Running Linters Individually

The build script runs all of these over `hier_config`, `tests`, and `scripts`:

```bash
ruff check .                  # style + lint
ruff format --check .         # formatting (no changes)
mypy hier_config/ tests/ scripts/     # type checking
pyright hier_config/ tests/ scripts/  # additional type checking
pylint hier_config/ tests/ scripts/   # extended lint rules
yamllint .                    # YAML files
flynt -d -tc -f hier_config tests scripts  # f-string conversion check
```

To auto-fix ruff issues:

```bash
ruff check --fix .
ruff format .
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
- **Linting must pass** — `python scripts/build.py lint-and-test` must exit 0.
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
| New platform support | `hier_config/platforms/<name>/driver.py` (subclass `HConfigDriverBase`) |
| New rule type | `hier_config/models.py` (new `BaseModel` subclass) + `hier_config/platforms/driver_base.py` (`HConfigDriverRules` field) |
| New utility function | `hier_config/utils.py` |
| New view property | `hier_config/platforms/view_base.py` (abstract) + the `view.py` of each platform that ships a view (currently 6 of 13 platforms) |
| Core tree algorithm | `hier_config/base.py` (shared) or `hier_config/root.py` (`HConfig`-only) |

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

- Enable the **mypy** plugin (Settings → Plugins → mypy) and point it at `poetry run mypy`.
- Configure ruff as an external tool for on-save formatting.
