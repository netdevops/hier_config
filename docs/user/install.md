# Installation

This page covers installing hier_config from PyPI or from source. It applies to anyone using the library.

> hier_config requires Python 3.10 or later.

Version 4 ships the Rust rewrite in **this repository and this Python package**.
There is no pure-Python fallback. Published `abi3` wheels support CPython 3.10+
on Linux glibc/musl (x86_64, aarch64), macOS (x86_64, aarch64), and Windows
(x64). Windows ARM64 wheels require CPython 3.11+.
Installing a compatible wheel does not require Rust.

## Install from PyPI

```bash
pip install hier-config
```

### Installing a prerelease (v4)

Version 4 is currently published as a prerelease. Pip skips prereleases by default, so pass `--pre` to install it:

```bash
pip install --pre hier-config
```

Or pin an exact version (see the [release history on PyPI](https://pypi.org/project/hier-config/#history) for the current prerelease):

```bash
pip install hier-config==<version>
```

## Install from source

An sdist install (`pip install --no-binary hier-config hier-config`), a checkout,
or a platform without a compatible wheel requires Python 3.10+, a C/C++ linker,
and a Rust toolchain meeting `workspace.package.rust-version` in `Cargo.toml`
(currently **Rust 1.98**). Install Rust with [rustup](https://rustup.rs/).
The build backend is [maturin](https://www.maturin.rs/), not Poetry.

For a development checkout:

```bash
git clone git@github.com:netdevops/hier_config.git
cd hier_config
git checkout next
uv sync --locked --extra yaml
uv run --no-sync maturin develop --release --locked
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first.
Rebuild the extension after editing Rust; Python imports the compiled artifact,
not the Rust source.

After a manual native rebuild, use `uv run --no-sync` for tests and other
commands. Automatic synchronization can reinstall an older cached project
wheel over the extension just built by maturin. If you run `uv sync` again,
rebuild the extension afterward. For example:

```bash
uv run --no-sync pytest tests/native/
```

## Optional YAML support

`pydantic` is the only required Python runtime dependency. File-based YAML
loaders in `hier_config.utils` require the optional `yaml` extra:

```bash
pip install --pre 'hier-config[yaml]'
```

Without the extra, importing the library, loading text configs, and passing
rule dictionaries still work. Calling a YAML loader raises an `ImportError`
with installation instructions. See [Loading Rules from Files](../admin/rules-from-files.md).

## Next steps

- [Getting Started](getting-started.md) — walk through your first remediation.
- [Loading Configurations](loading-configs.md) — all the ways to build an `HConfig` tree.
