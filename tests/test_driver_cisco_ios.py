from hier_config import get_hconfig_fast_load
from hier_config.constructors import get_hconfig
from hier_config.models import Platform


def test_logging_console_emergencies_scenario_1() -> None:
    platform = Platform.CISCO_IOS
    running_config = get_hconfig_fast_load(platform, ("no logging console",))
    generated_config = get_hconfig_fast_load(platform, ("logging console emergencies",))
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == ("logging console emergencies",)
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == ("logging console emergencies",)
    rollback = future_config.config_to_get_to(running_config)
    assert rollback.dump_simple() == ("no logging console",)
    running_after_rollback = future_config.future(rollback)

    assert not tuple(running_config.unified_diff(running_after_rollback))


def test_logging_console_emergencies_scenario_2() -> None:
    platform = Platform.CISCO_IOS
    running_config = get_hconfig_fast_load(platform, ("logging console",))
    generated_config = get_hconfig_fast_load(platform, ("logging console emergencies",))
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == ("logging console emergencies",)
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == ("logging console emergencies",)
    rollback = future_config.config_to_get_to(running_config)
    assert rollback.dump_simple() == ("logging console",)
    running_after_rollback = future_config.future(rollback)

    assert not tuple(running_config.unified_diff(running_after_rollback))


def test_logging_console_emergencies_scenario_3() -> None:
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    generated_config = get_hconfig_fast_load(platform, ("logging console emergencies",))
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == ("logging console emergencies",)
    future_config = running_config.future(remediation_config)
    assert future_config.dump_simple() == ("logging console emergencies",)
    rollback = future_config.config_to_get_to(running_config)
    assert rollback.dump_simple() == ("logging console debugging",)
    running_after_rollback = future_config.future(rollback)

    assert not tuple(running_config.unified_diff(running_after_rollback))


def test_duplicate_child_router() -> None:
    platform = Platform.CISCO_IOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "router eigrp EIGRP_INSTANCE",
            " address-family ipv4 unicast autonomous-system 10000",
            "  af-interface default",
            "   passive-interface",
            "  exit-af-interface",
            "  af-interface Vlan100",
            "   no passive-interface",
            "  exit-af-interface",
            "  af-interface GigabitEthernet0/0/1",
            "   no passive-interface",
            "  exit-af-interface",
            "  topology base",
            "   default-metric 1500 100 255 1 1500",
            "   redistribute bgp 65001",
            "  exit-af-topology",
            "  network 10.0.0.0",
            " exit-address-family",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "router eigrp EIGRP_INSTANCE",
            " address-family ipv4 unicast autonomous-system 10000",
            "  af-interface default",
            "   passive-interface",
            "  exit-af-interface",
            "  af-interface Vlan100",
            "   no passive-interface",
            "  exit-af-interface",
            "  af-interface GigabitEthernet0/0/1",
            "   no passive-interface",
            "  exit-af-interface",
            "  topology base",
            "   default-metric 1500 100 255 1 1500",
            "   redistribute bgp 65001 route-map ROUTE_MAP_IN",
            "  exit-af-topology",
            "  network 10.0.0.0",
            " exit-address-family",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "router eigrp EIGRP_INSTANCE",
        "  address-family ipv4 unicast autonomous-system 10000",
        "    topology base",
        "      no redistribute bgp 65001",
        "      redistribute bgp 65001 route-map ROUTE_MAP_IN",
    )


def test_rm_ipv6_acl_sequence_numbers() -> None:
    """Test post-load callback that removes IPv6 ACL sequence numbers (covers lines 21-23)."""
    platform = Platform.CISCO_IOS
    config_text = "\n".join(
        [
            "ipv6 access-list TEST_IPV6_ACL",
            " sequence 10 permit tcp any any eq 443",
            " sequence 20 deny ipv6 any any",
        ]
    )
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ipv6 access-list TEST_IPV6_ACL")

    assert acl is not None
    assert acl.get_child(equals="permit tcp any any eq 443") is not None
    assert acl.get_child(equals="deny ipv6 any any") is not None
    assert acl.get_child(startswith="sequence") is None


def test_remove_ipv4_acl_remarks() -> None:
    """Test post-load callback that removes IPv4 ACL remarks (covers line 30)."""
    platform = Platform.CISCO_IOS
    config_text = "\n".join(
        [
            "ip access-list extended TEST_ACL",
            " remark Allow HTTPS traffic",
            " permit tcp any any eq 443",
            " remark Block all other traffic",
            " deny ip any any",
        ]
    )
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ip access-list extended TEST_ACL")

    assert acl is not None
    assert acl.get_child(equals="10 permit tcp any any eq 443") is not None
    assert acl.get_child(equals="20 deny ip any any") is not None
    assert acl.get_child(startswith="remark") is None


def test_add_acl_sequence_numbers() -> None:
    """Test post-load callback that adds sequence numbers to IPv4 ACLs (covers lines 42-43)."""
    platform = Platform.CISCO_IOS
    config_text = "\n".join(
        [
            "ip access-list extended TEST_ACL",
            " permit tcp any any eq 443",
            " permit tcp any any eq 80",
            " deny ip any any",
        ]
    )
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ip access-list extended TEST_ACL")

    assert acl is not None
    assert acl.get_child(equals="10 permit tcp any any eq 443") is not None
    assert acl.get_child(equals="20 permit tcp any any eq 80") is not None
    assert acl.get_child(equals="30 deny ip any any") is not None
