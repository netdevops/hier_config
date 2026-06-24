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
    config_text = "ipv6 access-list TEST_IPV6_ACL\n sequence 10 permit tcp any any eq 443\n sequence 20 deny ipv6 any any"
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ipv6 access-list TEST_IPV6_ACL")

    assert acl is not None
    assert acl.get_child(equals="permit tcp any any eq 443") is not None
    assert acl.get_child(equals="deny ipv6 any any") is not None
    assert acl.get_child(startswith="sequence") is None


def test_remove_ipv4_acl_remarks() -> None:
    """Test post-load callback that removes IPv4 ACL remarks (covers line 30)."""
    platform = Platform.CISCO_IOS
    config_text = "ip access-list extended TEST_ACL\n remark Allow HTTPS traffic\n permit tcp any any eq 443\n remark Block all other traffic\n deny ip any any"
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ip access-list extended TEST_ACL")

    assert acl is not None
    assert acl.get_child(equals="10 permit tcp any any eq 443") is not None
    assert acl.get_child(equals="20 deny ip any any") is not None
    assert acl.get_child(startswith="remark") is None


def test_add_acl_sequence_numbers() -> None:
    """Test post-load callback that adds sequence numbers to IPv4 ACLs (covers lines 42-43)."""
    platform = Platform.CISCO_IOS
    config_text = "ip access-list extended TEST_ACL\n permit tcp any any eq 443\n permit tcp any any eq 80\n deny ip any any"
    config = get_hconfig(platform, config_text)
    acl = config.get_child(equals="ip access-list extended TEST_ACL")

    assert acl is not None
    assert acl.get_child(equals="10 permit tcp any any eq 443") is not None
    assert acl.get_child(equals="20 permit tcp any any eq 80") is not None
    assert acl.get_child(equals="30 deny ip any any") is not None


def test_vlan_id_list_split_on_load() -> None:
    """The post-load callback expands 'vlan 69,381' into one block per VLAN id."""
    config = get_hconfig(Platform.CISCO_IOS, "vlan 69,381\n")
    assert config.get_child(equals="vlan 69") is not None
    assert config.get_child(equals="vlan 381") is not None
    assert config.get_child(equals="vlan 69,381") is None


def test_vlan_id_range_split_on_load() -> None:
    """The post-load callback expands ranges into individual VLAN ids."""
    config = get_hconfig(Platform.CISCO_IOS, "vlan 10-12\n")
    assert [c.text for c in config.children] == ["vlan 10", "vlan 11", "vlan 12"]


def test_single_vlan_not_split_on_load() -> None:
    """A single VLAN id is left untouched (no comma/range separator)."""
    config = get_hconfig(Platform.CISCO_IOS, "vlan 44\n name servers\n")
    vlan = config.get_child(equals="vlan 44")
    assert vlan is not None
    assert vlan.get_child(equals="name servers") is not None


def test_non_vlan_id_line_not_split_on_load() -> None:
    """Lines like 'vlan internal allocation policy ...' are not VLAN id lists."""
    text = "vlan internal allocation policy ascending\n"
    config = get_hconfig(Platform.CISCO_IOS, text)
    assert (
        config.get_child(equals="vlan internal allocation policy ascending") is not None
    )


def test_vlan_id_list_rename_is_not_destructive() -> None:
    """Renaming one VLAN in a collapsed list must not negate the whole list."""
    running_config = get_hconfig(Platform.CISCO_IOS, "vlan 69,381\n")
    generated_config = get_hconfig(
        Platform.CISCO_IOS, "vlan 69\n name newname\nvlan 381\n"
    )
    remediation = running_config.config_to_get_to(generated_config).dump_simple()
    assert remediation == ("vlan 69", "  name newname")
    assert not any(line.lstrip().startswith("no vlan") for line in remediation)


def test_vlan_id_list_naming_middle_vlan_regroups_cleanly() -> None:
    """Naming a VLAN regroups IOS commas (69,70,71 -> 69,71 + 70); diff stays surgical."""
    running_config = get_hconfig(Platform.CISCO_IOS, "vlan 69,70,71\n")
    generated_config = get_hconfig(
        Platform.CISCO_IOS, "vlan 69,71\nvlan 70\n name MIDDLE\n"
    )
    remediation = running_config.config_to_get_to(generated_config).dump_simple()
    assert remediation == ("vlan 70", "  name MIDDLE")
    assert not any(line.lstrip().startswith("no vlan") for line in remediation)


def test_vlan_id_list_partial_removal_is_surgical() -> None:
    """Removing only some VLANs from a collapsed list negates just those ids."""
    running_config = get_hconfig(Platform.CISCO_IOS, "vlan 69,381,400\n")
    generated_config = get_hconfig(Platform.CISCO_IOS, "vlan 69\nvlan 381\n")
    remediation = running_config.config_to_get_to(generated_config).dump_simple()
    assert remediation == ("no vlan 400",)


def test_vlan_id_list_pure_add_emits_one_line_per_vlan() -> None:
    """Adding a collapsed VLAN list emits one (non-destructive) line per VLAN."""
    running_config = get_hconfig(Platform.CISCO_IOS, "")
    generated_config = get_hconfig(Platform.CISCO_IOS, "vlan 10-12,20\n")
    remediation = running_config.config_to_get_to(generated_config).dump_simple()
    assert remediation == ("vlan 10", "vlan 11", "vlan 12", "vlan 20")


def test_vlan_id_list_no_change_is_idempotent() -> None:
    """Identical collapsed VLAN lists produce no remediation."""
    running_config = get_hconfig(Platform.CISCO_IOS, "vlan 69,381\n")
    generated_config = get_hconfig(Platform.CISCO_IOS, "vlan 69,381\n")
    remediation = running_config.config_to_get_to(generated_config).dump_simple()
    assert remediation == ()
