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
