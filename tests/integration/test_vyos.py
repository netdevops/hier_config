from hier_config import WorkflowRemediation, get_hconfig, get_hconfig_fast_load
from hier_config.models import Platform


def test_vyos_basic_remediation() -> None:
    """Test basic VyOS set/delete commands."""
    platform = Platform.VYOS
    running_config_str = "set interfaces ethernet eth0 address 192.168.1.1/24"
    generated_config_str = "set interfaces ethernet eth0 address 192.168.2.1/24"
    remediation_str = "delete interfaces ethernet eth0 address 192.168.1.1/24\nset interfaces ethernet eth0 address 192.168.2.1/24"

    workflow_remediation = WorkflowRemediation(
        get_hconfig_fast_load(platform, running_config_str),
        get_hconfig_fast_load(platform, generated_config_str),
    )

    assert workflow_remediation.remediation_config_filtered_text() == remediation_str


def test_interface_address_addition_scenario() -> None:
    """Test adding an interface address."""
    platform = Platform.VYOS
    running_config = get_hconfig_fast_load(
        platform,
        ("set interfaces ethernet eth0 address 192.168.1.1/24",),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set interfaces ethernet eth0 address 192.168.1.1/24",
            "set interfaces ethernet eth0 address 192.168.1.2/24",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set interfaces ethernet eth0 address 192.168.1.2/24",
    )


def test_interface_description_modification_scenario() -> None:
    """Test modifying interface description."""
    platform = Platform.VYOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set interfaces ethernet eth0 address 192.168.1.1/24",
            "set interfaces ethernet eth0 description Old Description",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set interfaces ethernet eth0 address 192.168.1.1/24",
            "set interfaces ethernet eth0 description New Description",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete interfaces ethernet eth0 description Old Description",
        "set interfaces ethernet eth0 description New Description",
    )


def test_interface_removal_scenario() -> None:
    """Test removing an interface configuration."""
    platform = Platform.VYOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set interfaces ethernet eth0 address 192.168.1.1/24",
            "set interfaces ethernet eth0 description WAN Interface",
            "set interfaces ethernet eth1 address 10.0.0.1/24",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set interfaces ethernet eth0 address 192.168.1.1/24",
            "set interfaces ethernet eth0 description WAN Interface",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete interfaces ethernet eth1 address 10.0.0.1/24",
    )


def test_system_configuration_scenario() -> None:
    """Test system configuration changes."""
    platform = Platform.VYOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set system host-name old-vyos-router",
            "set system domain-name example.com",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set system host-name new-vyos-router",
            "set system domain-name example.com",
            "set system time-zone America/New_York",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete system host-name old-vyos-router",
        "set system host-name new-vyos-router",
        "set system time-zone America/New_York",
    )


def test_empty_to_basic_config_scenario() -> None:
    """Test building configuration from empty state."""
    platform = Platform.VYOS
    running_config = get_hconfig(platform)
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set system host-name test-router",
            "set interfaces ethernet eth0 address 192.168.1.1/24",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set system host-name test-router",
        "set interfaces ethernet eth0 address 192.168.1.1/24",
    )
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == (
        "set system host-name test-router",
        "set interfaces ethernet eth0 address 192.168.1.1/24",
    )


def test_nat_configuration_scenario() -> None:
    """Test NAT configuration changes."""
    platform = Platform.VYOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set nat source rule 10 outbound-interface eth0",
            "set nat source rule 10 source address 192.168.1.0/24",
            "set nat source rule 10 translation address masquerade",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set nat source rule 10 outbound-interface eth0",
            "set nat source rule 10 source address 192.168.2.0/24",
            "set nat source rule 10 translation address masquerade",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete nat source rule 10 source address 192.168.1.0/24",
        "set nat source rule 10 source address 192.168.2.0/24",
    )


def test_firewall_rule_scenario() -> None:
    """Test firewall rule configuration."""
    platform = Platform.VYOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set firewall name WAN_LOCAL default-action drop",
            "set firewall name WAN_LOCAL rule 10 action accept",
            "set firewall name WAN_LOCAL rule 10 state established enable",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set firewall name WAN_LOCAL default-action drop",
            "set firewall name WAN_LOCAL rule 10 action accept",
            "set firewall name WAN_LOCAL rule 10 state established enable",
            "set firewall name WAN_LOCAL rule 10 state related enable",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set firewall name WAN_LOCAL rule 10 state related enable",
    )


def test_ipv6_address_configuration_scenario() -> None:
    """Test configuring IPv6 addresses on interfaces."""
    platform = Platform.VYOS
    running_config = get_hconfig_fast_load(
        platform,
        ("set interfaces ethernet eth0 address 2001:db8:1::1/64",),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        ("set interfaces ethernet eth0 address 2001:db8:2::1/64",),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete interfaces ethernet eth0 address 2001:db8:1::1/64",
        "set interfaces ethernet eth0 address 2001:db8:2::1/64",
    )
