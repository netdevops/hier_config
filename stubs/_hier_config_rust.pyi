# Type stub for the compiled extension module.
#
# `_hier_config_rust` is a `.so` built by maturin, so type checkers cannot
# introspect it. Without this stub every `from _hier_config_rust import ...`
# in the re-export shims resolves to `Unknown`, which under pyright's strict
# mode cascades into dozens of errors across `hier_config/` and makes the
# package's own source unverifiable.
#
# The authoritative, documented signatures live in the `hier_config/*.pyi`
# stubs beside the shims -- those are what mkdocstrings renders and what
# downstream users see. This file deliberately re-exports from them rather
# than restating them, so there is exactly one copy of each signature and the
# two can never drift.
#
# This stub is repo-local (see `mypy_path` / `stubPath` in pyproject.toml) and
# is not shipped: `_hier_config_rust` is underscore-prefixed precisely because
# callers are meant to reach these types through `hier_config`, which is fully
# typed via `py.typed`.

from hier_config.base import HConfigBase as HConfigBase
from hier_config.child import HConfigChild as HConfigChild
from hier_config.children import HConfigChildren as HConfigChildren
from hier_config.exceptions import DuplicateChildError as DuplicateChildError
from hier_config.exceptions import HierConfigError as HierConfigError
from hier_config.root import HConfig as HConfig
from hier_config.workflows import WorkflowRemediation as WorkflowRemediation

# Declared here rather than re-exported: this iterator is returned by
# `HConfigChildren.__iter__` but has no stub of its own under `hier_config/`.
class HConfigChildrenIter:
    def __iter__(self) -> HConfigChildrenIter: ...
    def __next__(self) -> HConfigChild: ...

def get_platform_rules_json(platform_str: str) -> str: ...
def driver_swap_negation(platform_str: str, text: str) -> str: ...
def convert_to_set_commands(config_raw: str) -> str: ...
def config_preprocessor(platform_str: str, config_text: str) -> str: ...

__all__ = (
    "DuplicateChildError",
    "HConfig",
    "HConfigBase",
    "HConfigChild",
    "HConfigChildren",
    "HConfigChildrenIter",
    "HierConfigError",
    "WorkflowRemediation",
    "config_preprocessor",
    "convert_to_set_commands",
    "driver_swap_negation",
    "get_platform_rules_json",
)
