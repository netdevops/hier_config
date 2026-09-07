"""Guards that native fast paths and additive post-load callbacks function correctly.

Stock post-load callbacks are executed directly in the native Rust core. User-defined
callbacks on `driver.rules.post_load_callbacks` run additively on top of the native result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hier_config import get_hconfig, get_hconfig_fast_load
from hier_config.constructors import get_hconfig_driver
from hier_config.models import Platform

if TYPE_CHECKING:
    from hier_config.root import HConfig


def _stock_platforms() -> list[Platform]:
    supported: list[Platform] = []
    for platform in Platform:
        try:
            get_hconfig_driver(platform)
        except ValueError:
            continue
        supported.append(platform)
    return supported


@pytest.mark.parametrize("platform", _stock_platforms(), ids=lambda p: p.value)
def test_stock_driver_runs_native_post_load(platform: Platform) -> None:
    """Every stock driver parses and executes stock post-load transformations natively."""
    sample = "interface Eth1\n  description x\n"
    config = get_hconfig(platform, sample)
    assert any("interface Eth1" in c.text for c in config.children)


def test_custom_post_load_callbacks_are_additive() -> None:
    """A driver with custom callbacks runs them additively on top of native transformations."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    executed: list[str] = []

    def _custom(config: HConfig) -> None:
        executed.append("custom_ran")
        config.add_child("interface Loopback99")

    driver.rules.post_load_callbacks.append(_custom)
    try:  # pylint: disable=too-many-try-statements
        # Cisco IOS stock callback strips sequence numbers from IPv6 ACLs natively
        raw = "ipv6 access-list V6\n sequence 10 permit ipv6 any any\n"
        config = get_hconfig(driver, raw)
        # Verify native stock callback ran
        v6_acl = config.get_child(equals="ipv6 access-list V6")
        assert v6_acl is not None
        assert v6_acl.get_child(equals="permit ipv6 any any") is not None
        # Verify additive custom callback ran
        assert "custom_ran" in executed
        assert config.get_child(equals="interface Loopback99") is not None
    finally:
        driver.rules.post_load_callbacks.remove(_custom)


def test_subclassed_driver_runs_additive_callbacks() -> None:
    """A subclass can add callbacks additively without duplicating stock callbacks."""

    class CustomIos(type(get_hconfig_driver(Platform.CISCO_IOS))):  # type: ignore[misc] # pylint: disable=too-few-public-methods
        """Custom driver subclass for additive callback testing."""

    driver = CustomIos()
    custom_flag = False

    def _custom(_config: HConfig) -> None:
        nonlocal custom_flag
        custom_flag = True

    driver.rules.post_load_callbacks.append(_custom)

    raw = "ipv6 access-list V6\n sequence 10 permit ipv6 any any\n"
    config = get_hconfig(driver, raw)
    assert custom_flag is True
    # Stock callback ran natively
    v6_acl = config.get_child(equals="ipv6 access-list V6")
    assert v6_acl is not None
    assert v6_acl.get_child(equals="permit ipv6 any any") is not None


def test_get_hconfig_fast_load_runs_additive_callbacks() -> None:
    """`get_hconfig_fast_load` runs native fast loading and executes additive callbacks."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    executed: list[str] = []

    def _custom(_config: HConfig) -> None:
        executed.append("fast_custom_ran")

    driver.rules.post_load_callbacks.append(_custom)
    try:  # pylint: disable=too-many-try-statements
        config = get_hconfig_fast_load(driver, ["interface Eth1", "  description x"])
        assert config.get_child(equals="interface Eth1") is not None
        assert "fast_custom_ran" in executed
    finally:
        driver.rules.post_load_callbacks.remove(_custom)
