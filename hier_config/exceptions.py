class HierConfigError(Exception):
    """Base exception for all hier_config errors."""


class DuplicateChildError(HierConfigError):
    """Raised when attempting to add a duplicate child."""


class DriverNotFoundError(HierConfigError):
    """Raised when a platform driver cannot be found."""


class InvalidConfigError(HierConfigError):
    """Raised for malformed configuration text."""


class IncompatibleDriverError(HierConfigError):
    """Raised when configs with mismatched drivers are used together."""
