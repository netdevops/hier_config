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


def test_nested_if_endif_route_policy() -> None:
    """Test nested if/endif blocks in route-policy don't raise DuplicateChildError."""
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "route-policy EXAMPLE-POLICY",
            "  if (community matches-any COMM-SET-A) then",
            "    if (community matches-any COMM-SET-B) then",
            "      done",
            "    endif",
            "    if (community matches-any COMM-SET-C) then",
            "      done",
            "    endif",
            "    drop",
            "  endif",
            "  pass",
            "end-policy",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "route-policy EXAMPLE-POLICY",
            "  if (community matches-any COMM-SET-A) then",
            "    if (community matches-any COMM-SET-B) then",
            "      done",
            "    endif",
            "    if (community matches-any COMM-SET-D) then",
            "      set local-preference 200",
            "    endif",
            "    drop",
            "  endif",
            "  pass",
            "end-policy",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "route-policy EXAMPLE-POLICY",
        "  if (community matches-any COMM-SET-A) then",
        "    if (community matches-any COMM-SET-B) then",
        "      done",
        "      exit",
        "    endif",
        "    if (community matches-any COMM-SET-D) then",
        "      set local-preference 200",
        "      exit",
        "    endif",
        "    drop",
        "    exit",
        "  endif",
        "  pass",
        "  end-policy",
    )


def test_flow_exporter_template_indent_adjust() -> None:
    """Test that 'template timeout' inside flow exporter-map doesn't corrupt indentation."""
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "flow exporter-map EXPORTER1",
            " version v9",
            "  template timeout 60",
            " !",
            " transport udp 9999",
            "!",
            "route-policy POLICY1",
            "  if (destination in PREFIX-SET1) then",
            "    drop",
            "  endif",
            "  if (destination in PREFIX-SET2) then",
            "    done",
            "  endif",
            "  drop",
            "end-policy",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "flow exporter-map EXPORTER1",
            " version v9",
            "  template timeout 60",
            " !",
            " transport udp 9999",
            "!",
            "route-policy POLICY1",
            "  if (destination in PREFIX-SET1) then",
            "    drop",
            "  endif",
            "  if (destination in PREFIX-SET3) then",
            "    pass",
            "  endif",
            "  drop",
            "end-policy",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "route-policy POLICY1",
        "  if (destination in PREFIX-SET1) then",
        "    drop",
        "    exit",
        "  endif",
        "  if (destination in PREFIX-SET3) then",
        "    pass",
        "    exit",
        "  endif",
        "  drop",
        "  end-policy",
    )


def test_template_block_indent_adjust() -> None:
    """Test that template blocks still parse correctly with the indent_adjust rule."""
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        (
            "template ACCESS-PORT",
            " description Access Port - Standard Config",
            " load-interval 30",
            " ipv4 mtu 1500",
            " mtu 1518",
            " dampening",
            " carrier-delay up 5000 down 0",
            " spanning-tree portfast",
            "!",
            "template UPLINK-PORT",
            " description Uplink - Core Facing",
            " load-interval 30",
            " mtu 9000",
            " ipv4 mtu 8972",
            " dampening",
            " carrier-delay up 5000 down 0",
            " lldp",
            "  transmit",
            "  receive",
            " !",
            "!",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "template ACCESS-PORT",
            " description Access Port - Standard Config",
            " load-interval 30",
            " ipv4 mtu 1500",
            " mtu 1518",
            " dampening",
            " carrier-delay up 5000 down 0",
            " spanning-tree portfast",
            "!",
            "template UPLINK-PORT",
            " description Uplink - Core Facing",
            " load-interval 30",
            " mtu 9216",
            " ipv4 mtu 9000",
            " dampening",
            " carrier-delay up 5000 down 0",
            " lldp",
            "  transmit",
            "  receive",
            " !",
            "!",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "no template UPLINK-PORT",
        "template UPLINK-PORT",
        "  description Uplink - Core Facing",
        "  load-interval 30",
        "  mtu 9216",
        "  ipv4 mtu 9000",
        "  dampening",
        "  carrier-delay up 5000 down 0",
        "  lldp",
        "    transmit",
        "    receive",
        "    exit",
        "  end-template",
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
