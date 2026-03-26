"""Tests for the custom exception hierarchy (#219)."""

import pytest

from hier_config import Platform, WorkflowRemediation, get_hconfig, get_hconfig_driver
from hier_config.exceptions import (
    DriverNotFoundError,
    DuplicateChildError,
    HierConfigError,
    IncompatibleDriverError,
    InvalidConfigError,
)


def test_hier_config_error_is_base_exception() -> None:
    """All custom exceptions inherit from HierConfigError."""
    assert issubclass(DuplicateChildError, HierConfigError)
    assert issubclass(DriverNotFoundError, HierConfigError)
    assert issubclass(InvalidConfigError, HierConfigError)
    assert issubclass(IncompatibleDriverError, HierConfigError)


def test_hier_config_error_is_catchable_as_exception() -> None:
    """HierConfigError itself inherits from Exception."""
    assert issubclass(HierConfigError, Exception)


def test_duplicate_child_error_on_duplicate_section() -> None:
    config = get_hconfig(Platform.CISCO_IOS, "interface Loopback0")
    with pytest.raises(DuplicateChildError, match="Found a duplicate section"):
        config.add_child("interface Loopback0")


def test_driver_not_found_error_invalid_platform() -> None:
    """get_hconfig_driver raises DriverNotFoundError for unsupported platforms."""
    with pytest.raises(DriverNotFoundError, match="Unsupported platform"):
        get_hconfig_driver("bogus_platform")  # type: ignore[arg-type]


def test_incompatible_driver_error_mismatched_drivers() -> None:
    """WorkflowRemediation raises IncompatibleDriverError for mismatched drivers."""
    running = get_hconfig(Platform.CISCO_IOS)
    generated = get_hconfig(Platform.ARISTA_EOS)
    with pytest.raises(IncompatibleDriverError, match="same driver"):
        WorkflowRemediation(running, generated)


def test_invalid_config_error_banner_parsing() -> None:
    """Malformed banner config raises InvalidConfigError."""
    config_text = "banner motd ^C\nthis banner never ends"
    with pytest.raises(InvalidConfigError, match="banner"):
        get_hconfig(Platform.CISCO_IOS, config_text)
