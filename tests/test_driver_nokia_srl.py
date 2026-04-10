from hier_config import WorkflowRemediation, get_hconfig, get_hconfig_fast_load
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.nokia_srl.driver import HConfigDriverNokiaSRL


def test_nokia_srl_basic_remediation() -> None:
    """Test basic Nokia SRL set/delete commands."""
    platform = Platform.NOKIA_SRL
    running_config_str = "set interface ethernet-1/1 subinterface 0 ipv4 admin-state enable address 192.168.1.1/24"
    generated_config_str = "set interface ethernet-1/1 subinterface 0 ipv4 admin-state enable address 192.168.2.1/24"
    remediation_str = "delete interface ethernet-1/1 subinterface 0 ipv4 admin-state enable address 192.168.1.1/24\nset interface ethernet-1/1 subinterface 0 ipv4 admin-state enable address 192.168.2.1/24"

    workflow_remediation = WorkflowRemediation(
        get_hconfig_fast_load(platform, running_config_str),
        get_hconfig_fast_load(platform, generated_config_str),
    )

    assert workflow_remediation.remediation_config_filtered_text() == remediation_str


def test_swap_negation_delete_to_set() -> None:
    """Test swapping from 'delete' to 'set' prefix."""
    platform = Platform.NOKIA_SRL
    driver = HConfigDriverNokiaSRL()
    root = get_hconfig(platform)

    child = HConfigChild(
        root, "delete interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    result = driver.swap_negation(child)

    assert (
        result.text
        == "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    assert result.text.startswith("set ")


def test_swap_negation_set_to_delete() -> None:
    """Test swapping from 'set' to 'delete' prefix."""
    platform = Platform.NOKIA_SRL
    driver = HConfigDriverNokiaSRL()
    root = get_hconfig(platform)

    child = HConfigChild(
        root, "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    result = driver.swap_negation(child)

    assert (
        result.text
        == "delete interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    assert result.text.startswith("delete ")


def test_swap_negation_no_prefix() -> None:
    """Test swap_negation when text has neither prefix."""
    driver = HConfigDriverNokiaSRL()
    root = get_hconfig(Platform.NOKIA_SRL)

    child = HConfigChild(
        root, "interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    original_text = child.text

    result = driver.swap_negation(child)
    assert result.text == original_text


def test_declaration_prefix() -> None:
    """Test declaration_prefix property."""
    driver = HConfigDriverNokiaSRL()
    assert driver.declaration_prefix == "set "


def test_negation_prefix() -> None:
    """Test negation_prefix property."""
    driver = HConfigDriverNokiaSRL()
    assert driver.negation_prefix == "delete "


def test_config_preprocessor() -> None:
    """Test config_preprocessor with hierarchical SRL config."""
    hierarchical_config = """interface {
    ethernet-1/1 {
        subinterface 0 {
            ipv4 {
                admin-state enable
                address 192.168.1.1/24
            }
        }
    }
}
system {
    name {
        host-name srl-router
    }
}"""

    result = HConfigDriverNokiaSRL.config_preprocessor(hierarchical_config)

    assert "set interface ethernet-1/1 subinterface 0 ipv4 admin-state enable" in result
    assert (
        "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
        in result
    )
    assert "set system name host-name srl-router" in result


def test_interface_address_addition() -> None:
    """Test adding an interface address."""
    platform = Platform.NOKIA_SRL
    running_config = get_hconfig_fast_load(
        platform,
        ("set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",
            "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.2/24",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.2/24",
    )


def test_interface_description_modification() -> None:
    """Test modifying interface description."""
    platform = Platform.NOKIA_SRL
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set interface ethernet-1/1 description Old Description",
            "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set interface ethernet-1/1 description New Description",
            "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete interface ethernet-1/1 description Old Description",
        "set interface ethernet-1/1 description New Description",
    )


def test_interface_removal() -> None:
    """Test removing an interface configuration."""
    platform = Platform.NOKIA_SRL
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",
            "set interface ethernet-1/2 subinterface 0 ipv4 address 10.0.0.1/24",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        ("set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete interface ethernet-1/2 subinterface 0 ipv4 address 10.0.0.1/24",
    )


def test_network_instance_remediation() -> None:
    """Test network-instance (VRF) block handling."""
    platform = Platform.NOKIA_SRL
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set network-instance default router-id 10.0.0.1",
            "set network-instance default interface ethernet-1/1.0",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set network-instance default router-id 10.0.0.2",
            "set network-instance default interface ethernet-1/1.0",
            "set network-instance mgmt interface mgmt0.0",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete network-instance default router-id 10.0.0.1",
        "set network-instance default router-id 10.0.0.2",
        "set network-instance mgmt interface mgmt0.0",
    )


def test_system_configuration() -> None:
    """Test system configuration changes."""
    platform = Platform.NOKIA_SRL
    running_config = get_hconfig_fast_load(
        platform,
        (
            "set system name host-name old-srl-router",
            "set system dns network-instance mgmt",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set system name host-name new-srl-router",
            "set system dns network-instance mgmt",
            "set system ntp network-instance mgmt",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete system name host-name old-srl-router",
        "set system name host-name new-srl-router",
        "set system ntp network-instance mgmt",
    )


def test_empty_to_basic_config() -> None:
    """Test building configuration from empty state."""
    platform = Platform.NOKIA_SRL
    running_config = get_hconfig(platform)
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set system name host-name srl-router",
            "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set system name host-name srl-router",
        "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",
    )
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == (
        "set system name host-name srl-router",
        "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24",
    )


def test_routing_policy_configuration() -> None:
    """Test routing-policy configuration changes."""
    platform = Platform.NOKIA_SRL
    running_config = get_hconfig_fast_load(
        platform,
        ("set routing-policy policy accept-all default-action policy-result accept",),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "set routing-policy policy accept-all default-action policy-result accept",
            "set routing-policy policy deny-all default-action policy-result reject",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "set routing-policy policy deny-all default-action policy-result reject",
    )


def test_ipv6_address_configuration() -> None:
    """Test configuring IPv6 addresses on interfaces."""
    platform = Platform.NOKIA_SRL
    running_config = get_hconfig_fast_load(
        platform,
        ("set interface ethernet-1/1 subinterface 0 ipv6 address 2001:db8:1::1/64",),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        ("set interface ethernet-1/1 subinterface 0 ipv6 address 2001:db8:2::1/64",),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "delete interface ethernet-1/1 subinterface 0 ipv6 address 2001:db8:1::1/64",
        "set interface ethernet-1/1 subinterface 0 ipv6 address 2001:db8:2::1/64",
    )
