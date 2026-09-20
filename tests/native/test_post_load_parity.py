"""Tests verifying native post-load transformations and additive callback support.

Built-in platform post-load callbacks run natively in the Rust core during parsing.
Any custom callbacks added to `driver.rules.post_load_callbacks` execute additively.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hier_config import Platform, get_hconfig
from hier_config.constructors import get_hconfig_driver

if TYPE_CHECKING:
    from hier_config.root import HConfig


def test_cisco_ios_native_post_load() -> None:
    sample = """\
ip access-list extended TEST
 remark this remark is removed
 permit ip any any
 deny ip any any
ipv6 access-list V6TEST
 sequence 10 permit ipv6 any any
"""
    config = get_hconfig(Platform.CISCO_IOS, sample)
    v4 = config.get_child(equals="ip access-list extended TEST")
    assert v4 is not None
    # Remarks stripped
    assert not any(c.text.startswith("remark") for c in v4.children)
    # Sequence numbers added
    assert any(c.text.startswith("10 permit") for c in v4.children)
    assert any(c.text.startswith("20 deny") for c in v4.children)

    v6 = config.get_child(equals="ipv6 access-list V6TEST")
    assert v6 is not None
    # Sequence numbers removed
    assert any(c.text == "permit ipv6 any any" for c in v6.children)


def test_cisco_xr_native_post_load() -> None:
    sample = """\
! a leading comment
interface GigabitEthernet0/0/0/0
 description core link
!
router bgp 65000
 bgp router-id 10.0.0.1
"""
    config = get_hconfig(Platform.CISCO_XR, sample)
    assert config.get_child(equals="interface GigabitEthernet0/0/0/0") is not None
    assert config.get_child(equals="router bgp 65000") is not None


def test_hp_procurve_native_post_load() -> None:
    sample = """\
vlan 10
 name VLAN10
 untagged 1-3
 tagged 6,7
device-profile name PROFILE
 tagged-vlan 10,20
aaa port-access authenticator 1-2
"""
    config = get_hconfig(Platform.HP_PROCURVE, sample)
    profile = config.get_child(equals="device-profile name PROFILE")
    assert profile is not None
    # tagged-vlan 10,20 should be split
    assert profile.get_child(equals="tagged-vlan 10") is not None
    assert profile.get_child(equals="tagged-vlan 20") is not None

    # aaa port-access 1-2 should be expanded
    assert config.get_child(equals="aaa port-access authenticator 1") is not None
    assert config.get_child(equals="aaa port-access authenticator 2") is not None


def test_aruba_aoscx_native_post_load() -> None:
    sample = """\
interface 1/1/1
 vlan trunk allowed 10,20
"""
    config = get_hconfig(Platform.ARUBA_AOSCX, sample)
    intf = config.get_child(equals="interface 1/1/1")
    assert intf is not None
    assert intf.get_child(equals="vlan trunk allowed 10") is not None
    assert intf.get_child(equals="vlan trunk allowed 20") is not None


@pytest.mark.parametrize("platform", list(Platform))
def test_all_platforms_support_additive_callbacks(platform: Platform) -> None:
    driver = get_hconfig_driver(platform)
    call_log: list[str] = []

    def _custom_cb(config: HConfig) -> None:
        call_log.append("custom_invoked")
        config.add_child("tag-additive-test")

    driver.rules.post_load_callbacks.append(_custom_cb)
    try:  # pylint: disable=too-many-try-statements
        sample = "interface Eth1\n description test\n"
        cfg = get_hconfig(driver, sample)
        assert "custom_invoked" in call_log
        assert cfg.get_child(equals="tag-additive-test") is not None
    finally:
        driver.rules.post_load_callbacks.remove(_custom_cb)
