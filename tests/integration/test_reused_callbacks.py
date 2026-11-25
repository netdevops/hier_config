"""Public callback reuse must match native normalization, including rollback."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hier_config import HConfig, Platform, get_hconfig_driver
from hier_config.platforms.aruba_aoscx.driver import split_interface_vlan_trunk_allowed
from hier_config.platforms.cisco_ios.driver import (
    add_acl_sequence_numbers,
    remove_ipv4_acl_remarks,
    remove_ipv6_acl_sequence_numbers,
)
from hier_config.platforms.cisco_xr.driver import fixup_xr_comments
from hier_config.platforms.hp_procurve.driver import (
    fixup_hp_procurve_aaa_port_access,
    fixup_hp_procurve_device_profile,
    fixup_hp_procurve_vlan,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.parametrize(
    ("callback", "lines", "expected"),
    (
        (
            remove_ipv6_acl_sequence_numbers,
            (
                "ipv6 access-list V6",
                " sequence 10 permit ipv6 any any",
                " deny ipv6 any any",
            ),
            ("ipv6 access-list V6", "  permit ipv6 any any", "  deny ipv6 any any"),
        ),
        (
            remove_ipv4_acl_remarks,
            ("ip access-list extended V4", " remark old", " permit ip any any"),
            ("ip access-list extended V4", "  permit ip any any"),
        ),
        (
            add_acl_sequence_numbers,
            (
                "hostname r1",
                "ip access-list extended V4",
                " permit ip any any",
                " deny ip any any",
                " remark kept",
            ),
            (
                "hostname r1",
                "ip access-list extended V4",
                "  10 permit ip any any",
                "  20 deny ip any any",
                "  remark kept",
            ),
        ),
        (
            split_interface_vlan_trunk_allowed,
            (
                "interface 1/1/1",
                " vlan trunk allowed 10,20-21",
                "interface 1/1/2",
                " vlan trunk allowed all",
            ),
            (
                "interface 1/1/1",
                "  vlan trunk allowed 10",
                "  vlan trunk allowed 20",
                "  vlan trunk allowed 21",
                "interface 1/1/2",
                "  vlan trunk allowed all",
            ),
        ),
        (
            split_interface_vlan_trunk_allowed,
            ("interface 1/1/1", " vlan trunk allowed 1-2-3", " vlan trunk allowed 5"),
            ("interface 1/1/1", "  vlan trunk allowed 1-2-3", "  vlan trunk allowed 5"),
        ),
        (
            fixup_hp_procurve_aaa_port_access,
            (
                "aaa port-access authenticator 1-2",
                "aaa port-access mac-based 3",
                "aaa port-access mac-based 4,5",
            ),
            (
                "aaa port-access mac-based 3",
                "aaa port-access authenticator 1",
                "aaa port-access authenticator 2",
                "aaa port-access mac-based 4",
                "aaa port-access mac-based 5",
            ),
        ),
        (
            fixup_hp_procurve_device_profile,
            (
                "device-profile name phone",
                " tagged-vlan 10,20",
                "device-profile name ap",
                " tagged-vlan 30",
                "device-profile name bare",
            ),
            (
                "device-profile name phone",
                "  tagged-vlan 10",
                "  tagged-vlan 20",
                "device-profile name ap",
                "  tagged-vlan 30",
                "device-profile name bare",
            ),
        ),
        (
            fixup_hp_procurve_vlan,
            ("vlan 10", " untagged 1-2", " tagged 3,4", " no untagged 5", "vlan 20"),
            (
                "vlan 10",
                "vlan 20",
                "interface 1",
                "  untagged vlan 10",
                "interface 2",
                "  untagged vlan 10",
                "interface 3",
                "  tagged vlan 10",
                "interface 4",
                "  tagged vlan 10",
            ),
        ),
        (
            fixup_xr_comments,
            (
                "! headline",
                "interface Eth1",
                " ! nested",
                " description uplink",
                "! trailing",
            ),
            ("interface Eth1", "  description uplink"),
        ),
    ),
)
def test_callback_reused_by_generic_driver_round_trip(
    callback: Callable[[HConfig], None],
    lines: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    driver = get_hconfig_driver(Platform.GENERIC)
    driver.rules.post_load_callbacks.append(callback)
    intended = HConfig.from_lines(driver, lines)
    assert intended.to_lines() == expected

    running = HConfig.from_lines(driver, ())
    remediation = running.remediation(intended)
    assert remediation.to_lines() == expected
    future = running.future(remediation)
    assert not tuple(future.unified_diff(intended))
    restored = future.future(future.remediation(running))
    assert not tuple(restored.unified_diff(running))


def test_reused_xr_callback_preserves_comment_attachment() -> None:
    driver = get_hconfig_driver(Platform.GENERIC)
    driver.rules.post_load_callbacks.append(fixup_xr_comments)
    config = HConfig.from_lines(
        driver, ("! heading", "interface Eth1", " ! nested", " description uplink")
    )
    interface = config.get_child(equals="interface Eth1")
    assert interface is not None
    assert interface.comments == {"heading"}
    description = interface.get_child(equals="description uplink")
    assert description is not None
    assert description.comments == {"nested"}
