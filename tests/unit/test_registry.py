"""Tests for the driver registration system (#226, #229)."""

import pytest

from hier_config import (
    HConfig,
    HConfigDriverBase,
    HConfigDriverRules,
    Platform,
    get_hconfig_driver,
    get_hconfig_view,
    get_registered_platforms,
    register_driver,
    unregister_driver,
)
from hier_config.exceptions import DriverNotFoundError
from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS
from hier_config.platforms.cisco_ios.view import HConfigViewCiscoIOS


class _CustomDriver(HConfigDriverBase):
    """A user-defined driver for a custom platform."""

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules()


# The member's value string ("3"): a str-Enum artifact, not a platform name.
_CISCO_IOS_VALUE = str(Platform.CISCO_IOS.value)


def _assert_custom_platform_works() -> None:
    driver = get_hconfig_driver("MY_NOS")
    assert isinstance(driver, _CustomDriver)

    config = HConfig.from_text("MY_NOS", "hostname test\n")
    assert config.get_child(equals="hostname test") is not None


def test_register_custom_platform() -> None:
    """A registered string platform works with driver lookup and constructors."""
    register_driver("MY_NOS", _CustomDriver)
    try:
        _assert_custom_platform_works()
    finally:
        unregister_driver("MY_NOS")


def _assert_case_insensitive_lookup() -> None:
    assert isinstance(get_hconfig_driver("MY_NOS"), _CustomDriver)
    assert isinstance(get_hconfig_driver("my_nos"), _CustomDriver)


def test_register_custom_platform_is_case_insensitive() -> None:
    """Custom platform names are normalized to uppercase."""
    register_driver("my_nos", _CustomDriver)
    try:
        _assert_case_insensitive_lookup()
    finally:
        unregister_driver("MY_NOS")


def test_override_builtin_driver() -> None:
    """Registering an existing Platform overrides the built-in driver."""

    class CustomIOSDriver(HConfigDriverCiscoIOS):
        """Override of the built-in IOS driver."""

    register_driver(Platform.CISCO_IOS, CustomIOSDriver)
    try:
        assert isinstance(get_hconfig_driver(Platform.CISCO_IOS), CustomIOSDriver)
    finally:
        unregister_driver(Platform.CISCO_IOS)

    # Unregistering an overridden built-in restores the default driver.
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    assert driver.__class__ is HConfigDriverCiscoIOS


def _assert_custom_view_resolves() -> None:
    config = HConfig.from_text("CUSTOM_IOS", "hostname test\n")
    view = get_hconfig_view(config)
    assert isinstance(view, HConfigViewCiscoIOS)


def test_registered_driver_view_follows_driver() -> None:
    """A custom driver's view_class works through get_hconfig_view (#229)."""

    class CustomIOSDriver(HConfigDriverCiscoIOS):
        """Override with the inherited IOS view."""

    register_driver("CUSTOM_IOS", CustomIOSDriver)
    try:
        _assert_custom_view_resolves()
    finally:
        unregister_driver("CUSTOM_IOS")


def test_get_registered_platforms_contains_builtins() -> None:
    """All built-in platforms are registered at import time."""
    registered = get_registered_platforms()
    for platform in Platform:
        assert platform in registered


def test_unknown_platform_raises() -> None:
    """Looking up an unregistered platform raises DriverNotFoundError."""
    with pytest.raises(DriverNotFoundError, match="Unsupported platform"):
        get_hconfig_driver("NOT_REGISTERED")


def test_unregister_unknown_platform_raises() -> None:
    """Unregistering a platform that is not registered raises."""
    with pytest.raises(DriverNotFoundError, match="Unsupported platform"):
        unregister_driver("NOT_REGISTERED")


def test_unregister_builtin_without_override_raises() -> None:
    """A built-in platform without an override cannot be unregistered."""
    with pytest.raises(DriverNotFoundError, match="not overridden"):
        unregister_driver(Platform.CISCO_XR)


def test_register_platform_value_does_not_collide_with_builtin() -> None:
    """A Platform member's value string is a distinct custom key (#284)."""
    register_driver(_CISCO_IOS_VALUE, _CustomDriver)
    try:
        driver = get_hconfig_driver(Platform.CISCO_IOS)
    finally:
        unregister_driver(_CISCO_IOS_VALUE)
    assert driver.__class__ is HConfigDriverCiscoIOS


def test_platform_value_lookup_raises() -> None:
    """Platform member value strings are not platform names (#284)."""
    with pytest.raises(DriverNotFoundError, match="Unsupported platform"):
        get_hconfig_driver(_CISCO_IOS_VALUE)


def test_get_registered_platforms_includes_custom_names() -> None:
    """Custom platforms are listed by their canonical uppercase name (#284)."""
    register_driver("my_nos", _CustomDriver)
    try:
        assert [
            platform
            for platform in get_registered_platforms()
            if not isinstance(platform, Platform)
        ] == ["MY_NOS"]
    finally:
        unregister_driver("my_nos")


def test_get_registered_platforms_returns_enum_members_for_builtins() -> None:
    """Enum-known names are listed as Platform members, not strings (#284)."""
    members = {
        platform
        for platform in get_registered_platforms()
        if isinstance(platform, Platform)
    }
    assert members == set(Platform)


def test_platform_name_string_interchangeable_with_member() -> None:
    """A Platform member and its name address the same registry entry (#284)."""
    register_driver("cisco_ios", _CustomDriver)
    try:
        assert isinstance(get_hconfig_driver(Platform.CISCO_IOS), _CustomDriver)
    finally:
        unregister_driver(Platform.CISCO_IOS)

    driver = get_hconfig_driver(Platform.CISCO_IOS)
    assert driver.__class__ is HConfigDriverCiscoIOS
