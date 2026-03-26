from hier_config import WorkflowRemediation, get_hconfig, get_hconfig_fast_load
from hier_config.models import Platform


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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
        "set interfaces xe-0/0/0 description bb01.lax01:Ethernet2; ID:YT661812121",
        "set interfaces xe-0/0/0 mtu 9160",
        "set interfaces xe-0/0/0 unit 0 family iso",
        "set interfaces xe-0/0/0 unit 0 family mpls",
        "set interfaces xe-0/0/0 unit 0 family inet address 10.0.5.0/31",
        "set interfaces xe-0/0/0 unit 0 family inet6 address 2001:db8:5695::1/64",
    )
    future_config = running_config.future(remediation_config)
    assert future_config.to_lines() == (
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines() == (
        "delete system host-name old-router.example.com",
        "set system host-name new-router.example.com",
    )
