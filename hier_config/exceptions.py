"""Exception hierarchy for hier_config.

`HierConfigError`, `DuplicateChildError` and `InvalidConfigError` are defined in
the Rust extension because the core raises them directly; re-exporting rather
than redefining them keeps `except InvalidConfigError:` matching errors raised
from native code. The remaining errors are raised only from Python and subclass
the native base.
"""

from __future__ import annotations

from _hier_config_rust import (
    DuplicateChildError,
    HierConfigError,
    InvalidConfigError,
)

# Exception classes are message carriers; they have no methods by design.
# pylint: disable=too-few-public-methods


class DriverNotFoundError(HierConfigError):
    """Raised when a platform driver cannot be found."""


class IncompatibleDriverError(HierConfigError):
    """Raised when configs with mismatched drivers are used together."""


__all__ = (
    "DriverNotFoundError",
    "DuplicateChildError",
    "HierConfigError",
    "IncompatibleDriverError",
    "InvalidConfigError",
)
