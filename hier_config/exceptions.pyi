# Type stubs for the Rust-backed implementation in `_hier_config_rust`.
#
# griffe (mkdocstrings) and mypy cannot introspect a compiled extension,
# so this stub is the documented, typed view of the native exceptions;
# see docs/dev/architecture.md.

class HierConfigError(Exception):
    """Base exception for all errors raised by hier_config."""

class DuplicateChildError(HierConfigError):
    """Raised when adding a child whose text already exists under the parent."""

__all__ = ("DuplicateChildError", "HierConfigError")
