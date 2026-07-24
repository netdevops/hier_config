from hier_config import WorkflowRemediation, get_hconfig
from hier_config.models import Platform


def _remediation_text(running: str, intended: str) -> str:
    workflow = WorkflowRemediation(
        get_hconfig(Platform.ARUBA_AOSCX, running),
        get_hconfig(Platform.ARUBA_AOSCX, intended),
    )
    return "\n".join(
        line.cisco_style_text()
        for line in workflow.remediation_config.all_children_sorted()
    )


def test_interface_vlan_trunk_allowed_is_additive() -> None:
    running = """
interface 1/1/1
    vlan trunk allowed 20,21,26
"""
    intended = """
interface 1/1/1
    vlan trunk allowed 25,26
"""

    assert _remediation_text(running, intended).strip() == (
        "interface 1/1/1\n"
        "  no vlan trunk allowed 20\n"
        "  no vlan trunk allowed 21\n"
        "  vlan trunk allowed 25-26"
    )


def test_interface_vlan_trunk_allowed_expands_ranges() -> None:
    running = """
interface 1/1/1
    vlan trunk allowed 20-21,26
"""
    intended = """
interface 1/1/1
    vlan trunk allowed 25-26
"""

    assert _remediation_text(running, intended).strip() == (
        "interface 1/1/1\n"
        "  no vlan trunk allowed 20\n"
        "  no vlan trunk allowed 21\n"
        "  vlan trunk allowed 25-26"
    )


def test_interface_vlan_trunk_allowed_collapses_remediation() -> None:
    running = """
interface 1/1/1
    vlan trunk allowed 500,502
"""
    intended = """
interface 1/1/1
    vlan trunk allowed 500-504,550-554
"""

    assert _remediation_text(running, intended).strip() == (
        "interface 1/1/1\n  vlan trunk allowed 500-504,550-554"
    )


def test_interface_vlan_trunk_allowed_filtered_text_is_collapsed() -> None:
    workflow = WorkflowRemediation(
        get_hconfig(
            Platform.ARUBA_AOSCX,
            """
interface 1/1/1
    vlan trunk allowed 500,502
""",
        ),
        get_hconfig(
            Platform.ARUBA_AOSCX,
            """
interface 1/1/1
    vlan trunk allowed 500-504,550-554
""",
        ),
    )

    assert workflow.remediation_config_filtered_text().strip() == (
        "interface 1/1/1\n  vlan trunk allowed 500-504,550-554"
    )


def test_aruba_aoscx_splits_top_level_vlan_lists() -> None:
    config = get_hconfig(
        Platform.ARUBA_AOSCX,
        """
vlan 1,10
vlan 100-102
""",
    )

    assert tuple(line.cisco_style_text() for line in config.all_children_sorted()) == (
        "vlan 1",
        "vlan 10",
        "vlan 100",
        "vlan 101",
        "vlan 102",
    )


def test_aruba_aoscx_top_level_vlan_lists_match_individual_vlans() -> None:
    running = """
vlan 1,10
"""
    intended = """
vlan 1
vlan 10
"""

    assert not _remediation_text(running, intended).strip()


def test_aruba_aoscx_top_level_vlan_lists_remove_only_extra_vlans() -> None:
    running = """
vlan 1,10,20
"""
    intended = """
vlan 1
vlan 10
"""

    assert _remediation_text(running, intended).strip() == "no vlan 20"


def test_aruba_aoscx_strips_terminal_prompt_lines() -> None:
    config = get_hconfig(
        Platform.ARUBA_AOSCX,
        """
cx-switch# show run
hostname cx-switch
cx-switch(config)# interface 1/1/1
interface 1/1/1
    description #P3# Test
cx-switch(config-if)# vlan trunk allowed 500
""",
    )

    assert tuple(line.cisco_style_text() for line in config.all_children_sorted()) == (
        "hostname cx-switch",
        "interface 1/1/1",
        "  description #P3# Test",
    )


def test_aruba_aoscx_replaces_single_value_interface_commands() -> None:
    running = """
interface 1/1/1
    description OLD
    vlan access 10
interface vlan 10
    ip address 10.0.0.2/24
"""
    intended = """
interface 1/1/1
    description USER-PORT
    vlan access 20
interface vlan 10
    ip address 10.0.0.3/24
"""

    assert _remediation_text(running, intended).strip() == (
        "interface 1/1/1\n"
        "  description USER-PORT\n"
        "  vlan access 20\n"
        "interface vlan 10\n"
        "  ip address 10.0.0.3/24"
    )


def test_aruba_aoscx_evpn_vxlan_sections_are_partial() -> None:
    running = """
evpn
    arp-suppression
    vlan 10
        rd auto
        route-target export 65100:10
        route-target import 65100:10
        redistribute host-route
interface vxlan 1
    source ip 192.168.10.1
    vxlan-counters aggregate
    no shutdown
    vni 100010
        vlan 10
"""
    intended = """
evpn
    vlan 30
        rd auto
        route-target export 65100:30
        route-target import 65100:30
        redistribute host-route
interface vxlan 1
    vni 100030
        vlan 30
"""

    assert _remediation_text(running, intended).strip() == (
        "evpn\n"
        "  vlan 30\n"
        "    rd auto\n"
        "    route-target export 65100:30\n"
        "    route-target import 65100:30\n"
        "    redistribute host-route\n"
        "interface vxlan 1\n"
        "  vni 100030\n"
        "    vlan 30"
    )


def test_aruba_aoscx_evpn_vxlan_explicit_no_commands_are_kept() -> None:
    running = """
evpn
    vlan 20
        rd auto
interface vxlan 1
    vni 100020
        vlan 20
"""
    intended = """
evpn
    no vlan 20
interface vxlan 1
    no vni 100020
"""

    assert _remediation_text(running, intended).strip() == (
        "evpn\n  no vlan 20\ninterface vxlan 1\n  no vni 100020"
    )
