"""Exception hierarchy for hier_config.

`HierConfigError` and `DuplicateChildError` are defined in the Rust extension
because the core raises them directly; re-exporting rather than redefining them
keeps `except DuplicateChildError:` matching errors raised from native code.
The remaining errors are raised only from Python and subclass the native base.
"""

from __future__ import annotations

from _hier_config_rust import DuplicateChildError, HierConfigError


class DriverNotFoundError(HierConfigError):
    """Raised when a platform driver cannot be found."""


class InvalidConfigError(HierConfigError):
    """Raised for malformed configuration text."""


class IncompatibleDriverError(HierConfigError):
    """Raised when configs with mismatched drivers are used together."""


__all__ = (
    "DriverNotFoundError",
    "DuplicateChildError",
    "HierConfigError",
    "IncompatibleDriverError",
    "InvalidConfigError",
)
