import pytest

from hier_config import WorkflowRemediation, get_hconfig, get_hconfig_fast_load
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.juniper_junos.driver import HConfigDriverJuniperJUNOS

# Tests moved from test_juniper_syntax.py


def test_junos_basic_remediation() -> None:
    platform = Platform.JUNIPER_JUNOS
    running_config_str = "set vlans switch_mgmt_10.0.2.0/24 vlan-id 2"
    generated_config_str = "set vlans switch_mgmt_10.0.3.0/24 vlan-id 3"
    remediation_str = "delete vlans switch_mgmt_10.0.2.0/24 vlan-id 2\nset vlans switch_mgmt_10.0.3.0/24 vlan-id 3"

    workflow_remediation = WorkflowRemediation(
        get_hconfig_fast_load(platform, running_config_str),
        get_hconfig_fast_load(platform, generated_config_str),
    )

    assert workflow_remediation.remediation_config_filtered_text() == remediation_str


def test_junos_convert_to_set(
    running_config_junos: str,
    generated_config_junos: str,
    remediation_config_flat_junos: str,
) -> None:
    platform = Platform.JUNIPER_JUNOS
    workflow_remediation = WorkflowRemediation(
        get_hconfig(platform, running_config_junos),
        get_hconfig(platform, generated_config_junos),
    )

    assert (
        workflow_remediation.remediation_config_filtered_text()
        == remediation_config_flat_junos
    )


def test_flat_junos_remediation(
    running_config_flat_junos: str,
    generated_config_flat_junos: str,
    remediation_config_flat_junos: str,
) -> None:
    platform = Platform.JUNIPER_JUNOS
    workflow_remediation = WorkflowRemediation(
        get_hconfig_fast_load(platform, running_config_flat_junos),
        get_hconfig_fast_load(platform, generated_config_flat_junos),
    )

    remediation_list = remediation_config_flat_junos.splitlines()
    for line in str(workflow_remediation.remediation_config).splitlines():
        assert line in remediation_list


# New comprehensive driver tests for 100% coverage


def test_swap_negation_delete_to_set() -> None:
    """Test swapping from 'delete' to 'set' prefix (covers line 9-11)."""
    platform = Platform.JUNIPER_JUNOS
    driver = HConfigDriverJuniperJUNOS()
    root = get_hconfig(platform)

    # Create a child with 'delete' prefix
    child = HConfigChild(root, "delete vlans test_vlan vlan-id 100")

    # Swap negation should convert to 'set'
    result = driver.swap_negation(child)

    assert result.text == "set vlans test_vlan vlan-id 100"
    assert result.text.startswith("set ")


def test_swap_negation_set_to_delete() -> None:
    """Test swapping from 'set' to 'delete' prefix (covers lines 10, 12)."""
    platform = Platform.JUNIPER_JUNOS
    driver = HConfigDriverJuniperJUNOS()
    root = get_hconfig(platform)

    # Create a child with 'set' prefix
    child = HConfigChild(root, "set vlans test_vlan vlan-id 100")

    # Swap negation should convert to 'delete'
    result = driver.swap_negation(child)

    assert result.text == "delete vlans test_vlan vlan-id 100"
    assert result.text.startswith("delete ")


def test_swap_negation_invalid_prefix() -> None:
    """Test ValueError when text has neither 'set' nor 'delete' prefix (covers lines 14-15)."""
    platform = Platform.JUNIPER_JUNOS
    driver = HConfigDriverJuniperJUNOS()
    root = get_hconfig(platform)

    # Create a child without proper prefix
    child = HConfigChild(root, "vlans test_vlan vlan-id 100")

    # Should raise ValueError
    with pytest.raises(ValueError, match="did not start with") as exc_info:
        driver.swap_negation(child)

    assert "did not start with" in str(exc_info.value)
    assert "delete " in str(exc_info.value)
    assert "set " in str(exc_info.value)


def test_vlan_addition_scenario() -> None:
    """Test adding a new VLAN to the configuration."""
    platform = Platform.JUNIPER_JUNOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set vlans switch_mgmt_10.0.2.0/24 vlan-id 2",
            "set vlans switch_mgmt_10.0.2.0/24 l3-interface irb.2",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set vlans switch_mgmt_10.0.2.0/24 vlan-id 2",
            "set vlans switch_mgmt_10.0.2.0/24 l3-interface irb.2",
            "set vlans switch_mgmt_10.0.3.0/24 vlan-id 3",
            "set vlans switch_mgmt_10.0.3.0/24 l3-interface irb.3",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set vlans switch_mgmt_10.0.3.0/24 vlan-id 3",
        "set vlans switch_mgmt_10.0.3.0/24 l3-interface irb.3",
    )


def test_vlan_removal_scenario() -> None:
    """Test removing a VLAN from the configuration."""
    platform = Platform.JUNIPER_JUNOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set vlans switch_mgmt_10.0.2.0/24 vlan-id 2",
            "set vlans switch_mgmt_10.0.2.0/24 l3-interface irb.2",
            "set vlans switch_mgmt_10.0.3.0/24 vlan-id 3",
            "set vlans switch_mgmt_10.0.3.0/24 l3-interface irb.3",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set vlans switch_mgmt_10.0.2.0/24 vlan-id 2",
            "set vlans switch_mgmt_10.0.2.0/24 l3-interface irb.2",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete vlans switch_mgmt_10.0.3.0/24 vlan-id 3",
        "delete vlans switch_mgmt_10.0.3.0/24 l3-interface irb.3",
    )


def test_interface_unit_configuration_scenario() -> None:
    """Test configuring interface unit parameters."""
    platform = Platform.JUNIPER_JUNOS
    running_config = get_hconfig_fast_load(
        platform,
        ("set interfaces irb unit 2 family inet address 10.0.2.1/24",),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set interfaces irb unit 2 family inet address 10.0.2.1/24",
            "set interfaces irb unit 2 family inet filter input TEST",
            "set interfaces irb unit 2 family inet mtu 9000",
            "set interfaces irb unit 2 family inet description switch_mgmt_10.0.2.0/24",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set interfaces irb unit 2 family inet filter input TEST",
        "set interfaces irb unit 2 family inet mtu 9000",
        "set interfaces irb unit 2 family inet description switch_mgmt_10.0.2.0/24",
    )


def test_interface_address_change_scenario() -> None:
    """Test changing an interface IP address."""
    platform = Platform.JUNIPER_JUNOS
    running_config = get_hconfig_fast_load(
        platform,
        ("set interfaces irb unit 3 family inet address 10.0.4.1/16",),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        ("set interfaces irb unit 3 family inet address 10.0.3.1/16",),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete interfaces irb unit 3 family inet address 10.0.4.1/16",
        "set interfaces irb unit 3 family inet address 10.0.3.1/16",
    )


def test_interface_disable_enable_scenario() -> None:
    """Test disabling and enabling an interface."""
    platform = Platform.JUNIPER_JUNOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set interfaces irb unit 2 family inet address 10.0.2.1/24",
            "set interfaces irb unit 2 family inet disable",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        ("set interfaces irb unit 2 family inet address 10.0.2.1/24",),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete interfaces irb unit 2 family inet disable",
    )


def test_firewall_filter_configuration_scenario() -> None:
    """Test configuring firewall filter rules."""
    platform = Platform.JUNIPER_JUNOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set firewall family inet filter TEST term 1 from source-address 10.0.0.0/29",
            "set firewall family inet filter TEST term 1 then accept",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set firewall family inet filter TEST term 1 from source-address 10.0.0.0/29",
            "set firewall family inet filter TEST term 1 then accept",
            "set firewall family inet filter TEST term 2 from destination-address 192.168.1.0/24",
            "set firewall family inet filter TEST term 2 then reject",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set firewall family inet filter TEST term 2 from destination-address 192.168.1.0/24",
        "set firewall family inet filter TEST term 2 then reject",
    )


def test_physical_interface_configuration_scenario() -> None:
    """Test configuring physical interface with multiple families."""
    platform = Platform.JUNIPER_JUNOS
    running_config = get_hconfig(platform)
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set interfaces xe-0/0/0 description bb01.lax01:Ethernet2; ID:YT661812121",
            "set interfaces xe-0/0/0 mtu 9160",
            "set interfaces xe-0/0/0 unit 0 family iso",
            "set interfaces xe-0/0/0 unit 0 family mpls",
            "set interfaces xe-0/0/0 unit 0 family inet address 10.0.5.0/31",
            "set interfaces xe-0/0/0 unit 0 family inet6 address 2001:db8:5695::1/64",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set interfaces xe-0/0/0 description bb01.lax01:Ethernet2; ID:YT661812121",
        "set interfaces xe-0/0/0 mtu 9160",
        "set interfaces xe-0/0/0 unit 0 family iso",
        "set interfaces xe-0/0/0 unit 0 family mpls",
        "set interfaces xe-0/0/0 unit 0 family inet address 10.0.5.0/31",
        "set interfaces xe-0/0/0 unit 0 family inet6 address 2001:db8:5695::1/64",
    )
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == (
        "set interfaces xe-0/0/0 description bb01.lax01:Ethernet2; ID:YT661812121",
        "set interfaces xe-0/0/0 mtu 9160",
        "set interfaces xe-0/0/0 unit 0 family iso",
        "set interfaces xe-0/0/0 unit 0 family mpls",
        "set interfaces xe-0/0/0 unit 0 family inet address 10.0.5.0/31",
        "set interfaces xe-0/0/0 unit 0 family inet6 address 2001:db8:5695::1/64",
    )


def test_system_hostname_change_scenario() -> None:
    """Test changing system hostname."""
    platform = Platform.JUNIPER_JUNOS
    running_config = get_hconfig_fast_load(
        platform,
        ("set system host-name old-router.example.com",),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        ("set system host-name new-router.example.com",),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete system host-name old-router.example.com",
        "set system host-name new-router.example.com",
    )
