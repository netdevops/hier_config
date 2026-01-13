from hier_config import WorkflowRemediation, get_hconfig, get_hconfig_fast_load
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.vyos.driver import HConfigDriverVYOS


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


def test_swap_negation_delete_to_set() -> None:
    """Test swapping from 'delete' to 'set' prefix (covers lines 9-11)."""
    platform = Platform.VYOS
    driver = HConfigDriverVYOS()
    root = get_hconfig(platform)

    # Create a child with 'delete' prefix
    child = HConfigChild(root, "delete interfaces ethernet eth0 address 192.168.1.1/24")

    # Swap negation should convert to 'set'
    result = driver.swap_negation(child)

    assert result.text == "set interfaces ethernet eth0 address 192.168.1.1/24"
    assert result.text.startswith("set ")


def test_swap_negation_set_to_delete() -> None:
    """Test swapping from 'set' to 'delete' prefix (covers lines 10, 12)."""
    platform = Platform.VYOS
    driver = HConfigDriverVYOS()
    root = get_hconfig(platform)

    # Create a child with 'set' prefix
    child = HConfigChild(root, "set interfaces ethernet eth0 address 192.168.1.1/24")

    # Swap negation should convert to 'delete'
    result = driver.swap_negation(child)

    assert result.text == "delete interfaces ethernet eth0 address 192.168.1.1/24"
    assert result.text.startswith("delete ")


def test_swap_negation_no_prefix() -> None:
    """Test swap_negation behavior when text has neither prefix (covers VyOS-specific behavior)."""
    platform = Platform.VYOS
    driver = HConfigDriverVYOS()
    root = get_hconfig(platform)

    # Create a child without proper prefix
    child = HConfigChild(root, "interfaces ethernet eth0 address 192.168.1.1/24")
    original_text = child.text

    # VyOS driver doesn't raise an error, it just returns the child unchanged
    result = driver.swap_negation(child)

    # Text should remain unchanged since neither if/elif matched
    assert result.text == original_text


def test_declaration_prefix() -> None:
    """Test declaration_prefix property (covers line 18)."""
    driver = HConfigDriverVYOS()
    assert driver.declaration_prefix == "set "


def test_negation_prefix() -> None:
    """Test negation_prefix property (covers line 22)."""
    driver = HConfigDriverVYOS()
    assert driver.negation_prefix == "delete "


def test_config_preprocessor() -> None:
    """Test config_preprocessor with hierarchical VyOS config (covers line 26)."""
    hierarchical_config = """interfaces {
    ethernet eth0 {
        address 192.168.1.1/24
        description "WAN Interface"
    }
}
system {
    host-name vyos-router
}"""

    result = HConfigDriverVYOS.config_preprocessor(hierarchical_config)

    # Should convert to set commands
    assert "set interfaces ethernet eth0 address 192.168.1.1/24" in result
    assert "set interfaces ethernet eth0 description" in result
    assert "set system host-name vyos-router" in result


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
