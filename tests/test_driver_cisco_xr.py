from hier_config import get_hconfig_fast_load
from hier_config.models import Platform


def test_duplicate_child_route_policy() -> None:
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "route-policy SET_COMMUNITY_AND_PERMIT",
            "  if destination in (192.0.2.0/24, 198.51.100.0/24) then",
            "    set community (65001:100) additive",
            "    pass",
            "  else",
            "    drop",
            "  endif",
            "end-policy",
            "",
            "route-policy SET_LOCAL_PREF_AND_PASS",
            "  if destination in (203.0.113.0/24) then",
            "    set local-preference 200",
            "    pass",
            "  else",
            "    drop",
            "  endif",
            "end-policy",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "route-policy SET_COMMUNITY_AND_PERMIT",
            "  if destination in (192.0.2.0/24, 198.51.100.0/24) then",
            "    set community (65001:100) additive",
            "    pass",
            "  else",
            "    drop",
            "  endif",
            "end-policy",
            "",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "no route-policy SET_LOCAL_PREF_AND_PASS",
    )


def test_ipv4_acl_sequence_number_idempotent() -> None:
    """Test IPv4 ACL sequence number idempotency (covers lines 25-31)."""
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "ipv4 access-list TEST_ACL",
            " 10 permit tcp any any eq 443",
            " 20 permit tcp any any eq 80",
            " 30 deny ipv4 any any",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "ipv4 access-list TEST_ACL",
            " 10 permit tcp any any eq 443",
            " 20 permit tcp any any eq 22",
            " 30 deny ipv4 any any",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)

    assert remediation_config.dump_simple() == (
        "ipv4 access-list TEST_ACL",
        "  20 permit tcp any any eq 22",
    )


def test_ipv6_acl_sequence_number_idempotent() -> None:
    """Test IPv6 ACL sequence number idempotency (covers lines 25-31)."""
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "ipv6 access-list TEST_IPV6_ACL",
            " 10 permit tcp any any eq 443",
            " 20 deny ipv6 any any",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "ipv6 access-list TEST_IPV6_ACL",
            " 10 permit tcp any any eq 22",
            " 20 deny ipv6 any any",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)

    assert remediation_config.dump_simple() == (
        "ipv6 access-list TEST_IPV6_ACL",
        "  10 permit tcp any any eq 22",
    )


def test_ipv4_acl_sequence_number_addition() -> None:
    """Test adding new IPv4 ACL entries with sequence numbers."""
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "ipv4 access-list TEST_ACL",
            " 10 permit tcp any any eq 443",
            " 30 deny ipv4 any any",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "ipv4 access-list TEST_ACL",
            " 10 permit tcp any any eq 443",
            " 20 permit tcp any any eq 22",
            " 30 deny ipv4 any any",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)

    assert remediation_config.dump_simple() == (
        "ipv4 access-list TEST_ACL",
        "  20 permit tcp any any eq 22",
    )


def test_sectional_exit_text_parent_level_route_policy() -> None:
    """Test that route-policy exit text appears at parent level (no indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "route-policy TEST",
            "  set local-preference 200",
            "  pass",
        ),
    )

    route_policy = config.get_child(equals="route-policy TEST")
    assert route_policy is not None
    assert route_policy.sectional_exit_text_parent_level is True

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "route-policy TEST",
        "  set local-preference 200",
        "  pass",
        "end-policy",
    )


def test_sectional_exit_text_parent_level_prefix_set() -> None:
    """Test that prefix-set exit text appears at parent level (no indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "prefix-set TEST_PREFIX",
            "  192.0.2.0/24",
            "  198.51.100.0/24",
        ),
    )

    prefix_set = config.get_child(equals="prefix-set TEST_PREFIX")
    assert prefix_set is not None
    assert prefix_set.sectional_exit_text_parent_level is True

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "prefix-set TEST_PREFIX",
        "  192.0.2.0/24",
        "  198.51.100.0/24",
        "end-set",
    )


def test_sectional_exit_text_parent_level_policy_map() -> None:
    """Test that policy-map exit text appears at parent level (no indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "policy-map TEST_POLICY",
            "  class TEST_CLASS",
            "    set precedence 5",
        ),
    )

    policy_map = config.get_child(equals="policy-map TEST_POLICY")
    assert policy_map is not None
    assert policy_map.sectional_exit_text_parent_level is True

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "policy-map TEST_POLICY",
        "  class TEST_CLASS",
        "    set precedence 5",
        "    exit",
        "end-policy-map",
    )


def test_sectional_exit_text_parent_level_class_map() -> None:
    """Test that class-map exit text appears at parent level (no indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "class-map match-any TEST_CLASS",
            "  match access-group TEST_ACL",
        ),
    )

    class_map = config.get_child(equals="class-map match-any TEST_CLASS")
    assert class_map is not None
    assert class_map.sectional_exit_text_parent_level is True

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "class-map match-any TEST_CLASS",
        "  match access-group TEST_ACL",
        "end-class-map",
    )


def test_sectional_exit_text_parent_level_community_set() -> None:
    """Test that community-set exit text appears at parent level (no indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "community-set TEST_COMM",
            "  65001:100",
            "  65001:200",
        ),
    )

    community_set = config.get_child(equals="community-set TEST_COMM")
    assert community_set is not None
    assert community_set.sectional_exit_text_parent_level is True

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "community-set TEST_COMM",
        "  65001:100",
        "  65001:200",
        "end-set",
    )


def test_sectional_exit_text_parent_level_extcommunity_set() -> None:
    """Test that extcommunity-set exit text appears at parent level (no indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "extcommunity-set rt TEST_RT",
            "  1:100",
            "  2:200",
        ),
    )

    extcommunity_set = config.get_child(equals="extcommunity-set rt TEST_RT")
    assert extcommunity_set is not None
    assert extcommunity_set.sectional_exit_text_parent_level is True

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "extcommunity-set rt TEST_RT",
        "  1:100",
        "  2:200",
        "end-set",
    )


def test_sectional_exit_text_parent_level_template() -> None:
    """Test that template exit text appears at parent level (no indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "template TEST_TEMPLATE",
            "  description test template",
        ),
    )

    template = config.get_child(equals="template TEST_TEMPLATE")
    assert template is not None
    assert template.sectional_exit_text_parent_level is True

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "template TEST_TEMPLATE",
        "  description test template",
        "end-template",
    )


def test_sectional_exit_text_current_level_interface() -> None:
    """Test that interface exit text appears at current level (with indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "interface GigabitEthernet0/0/0/0",
            "  description test interface",
            "  ipv4 address 192.0.2.1 255.255.255.0",
        ),
    )

    interface = config.get_child(equals="interface GigabitEthernet0/0/0/0")
    assert interface is not None
    assert interface.sectional_exit_text_parent_level is False

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "interface GigabitEthernet0/0/0/0",
        "  description test interface",
        "  ipv4 address 192.0.2.1 255.255.255.0",
        "  root",
    )


def test_sectional_exit_text_current_level_router_bgp() -> None:
    """Test that router bgp exit text appears at current level (with indentation)."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "router bgp 65000",
            "  bgp router-id 192.0.2.1",
            "  address-family ipv4 unicast",
        ),
    )

    router_bgp = config.get_child(equals="router bgp 65000")
    assert router_bgp is not None
    assert router_bgp.sectional_exit_text_parent_level is False

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "router bgp 65000",
        "  bgp router-id 192.0.2.1",
        "  address-family ipv4 unicast",
        "  root",
    )


def test_sectional_exit_text_multiple_sections() -> None:
    """Test multiple sections with different exit text level behaviors."""
    platform = Platform.CISCO_XR
    config = get_hconfig_fast_load(
        platform,
        (
            "route-policy TEST1",
            "  pass",
            "!",
            "interface GigabitEthernet0/0/0/0",
            "  description test",
            "!",
            "prefix-set TEST_PREFIX",
            "  192.0.2.0/24",
        ),
    )

    route_policy = config.get_child(equals="route-policy TEST1")
    assert route_policy is not None
    assert route_policy.sectional_exit_text_parent_level is True

    interface = config.get_child(equals="interface GigabitEthernet0/0/0/0")
    assert interface is not None
    assert interface.sectional_exit_text_parent_level is False

    prefix_set = config.get_child(equals="prefix-set TEST_PREFIX")
    assert prefix_set is not None
    assert prefix_set.sectional_exit_text_parent_level is True

    output = config.dump_simple(sectional_exiting=True)
    assert output == (
        "route-policy TEST1",
        "  pass",
        "end-policy",
        "interface GigabitEthernet0/0/0/0",
        "  description test",
        "  root",
        "prefix-set TEST_PREFIX",
        "  192.0.2.0/24",
        "end-set",
    )
