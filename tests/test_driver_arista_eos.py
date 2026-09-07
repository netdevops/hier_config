"""Tests for Arista EOS driver functionality."""

import pytest

from hier_config import WorkflowRemediation, get_hconfig, get_hconfig_fast_load
from hier_config.models import Platform


@pytest.mark.displaced_by(
    "rust:tests/driver_arista_eos.rs::test_arista_eos_per_line_sub_strips_metadata"
)
def test_arista_eos_per_line_sub_strips_metadata() -> None:
    """Test that Arista EOS per-line substitutions strip banners and metadata."""
    raw_config = (
        "! Last configuration change at Mon Jan 1 00:00:00 2024\n"
        "Building configuration...\n"
        "Current configuration : 1234 bytes\n"
        "! NVRAM config last updated at Mon Jan 1 00:00:00 2024\n"
        "version 4.28.0F\n"
        "interface Ethernet1\n"
        " description uplink\n"
        "end\n"
    )
    config = get_hconfig(Platform.ARISTA_EOS, raw_config)
    lines = [child.cisco_style_text() for child in config.all_children()]
    assert "Building configuration..." not in lines
    assert "version 4.28.0F" not in lines
    assert "end" not in lines
    assert "interface Ethernet1" in lines
    assert "  description uplink" in lines


@pytest.mark.displaced_by(
    "rust:tests/driver_arista_eos.rs::test_arista_eos_bgp_sectional_exiting"
)
def test_arista_eos_bgp_sectional_exiting() -> None:
    """Test Arista EOS sectional exiting for BGP sub-modes."""
    platform = Platform.ARISTA_EOS
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "router bgp 65001",
            " address-family ipv4",
            "  neighbor 10.0.0.1 activate",
            " template peer-policy PEER-POLICY-1",
            "  route-map RM-IN in",
            " template peer-session PEER-SESSION-1",
            "  password 7 secret",
        ),
    )
    exits = {
        child.text: child.sectional_exit for child in generated_config.all_children()
    }
    assert exits["router bgp 65001"] == "exit"
    assert exits["address-family ipv4"] == "exit-address-family"
    assert exits["template peer-policy PEER-POLICY-1"] == "exit-peer-policy"
    assert exits["template peer-session PEER-SESSION-1"] == "exit-peer-session"
    assert exits["neighbor 10.0.0.1 activate"] is None


@pytest.mark.displaced_by("corpus:arista_eos/remediation_and_rollback")
def test_arista_eos_remediation_and_rollback() -> None:
    """Test full remediation and rollback workflow on Arista EOS."""
    running = (
        "interface Ethernet1\n"
        " description legacy-link\n"
        " switchport access vlan 10\n"
        "router bgp 65000\n"
        " router-id 1.1.1.1\n"
        " neighbor 10.0.0.1 remote-as 65001\n"
    )
    intended = (
        "interface Ethernet1\n"
        " description upgraded-link\n"
        " switchport access vlan 20\n"
        "router bgp 65000\n"
        " router-id 1.1.1.1\n"
        " neighbor 10.0.0.2 remote-as 65002\n"
    )

    workflow = WorkflowRemediation(
        get_hconfig(Platform.ARISTA_EOS, running),
        get_hconfig(Platform.ARISTA_EOS, intended),
    )
    rem_lines = [
        line.cisco_style_text()
        for line in workflow.remediation_config.all_children_sorted()
    ]

    # Verify changes in remediation
    assert "interface Ethernet1" in rem_lines
    assert "  description upgraded-link" in rem_lines
    assert "  switchport access vlan 20" in rem_lines

    # Verify rollback reverts intended back to running
    rb_lines = [
        line.cisco_style_text()
        for line in workflow.rollback_config.all_children_sorted()
    ]
    assert "interface Ethernet1" in rb_lines
    assert "  description legacy-link" in rb_lines
    assert "  switchport access vlan 10" in rb_lines
