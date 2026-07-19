# Installation

This page covers installing hier_config from PyPI or from source. It applies to anyone using the library.

> hier_config requires Python 3.10 or later.

## Install from PyPI

```bash
pip install hier-config
```

### Installing a prerelease (v4)

Version 4 is currently published as a prerelease (`4.0.0b1`). Pip skips prereleases by default, so pass `--pre` to install it:

```bash
pip install --pre hier-config
```

Or pin the exact version:

```bash
pip install hier-config==4.0.0b1
```

## Install from source

1. [Install Poetry](https://python-poetry.org/docs/#installation)
2. Clone the repository: `git clone git@github.com:netdevops/hier_config.git`
3. Install the project: `cd hier_config && poetry install`

## Next steps

- [Getting Started](getting-started.md) — walk through your first remediation.
- [Loading Configurations](loading-configs.md) — all the ways to build an `HConfig` tree.
