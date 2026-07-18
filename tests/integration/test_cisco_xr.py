from hier_config import HConfig
from hier_config.models import Platform


def test_multiple_groups_remediation() -> None:
    """Test remediation between configs with multiple group blocks."""
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
        platform,
        (
            "hostname router1",
            "group core",
            " interface 'Bundle-Ether.*'",
            "  mtu 9188",
            " !",
            "end-group",
            "group edge",
            " interface 'Bundle-Ether.*'",
            "  mtu 9092",
            " !",
            "end-group",
        ),
    )
    generated_config = HConfig.from_lines(
        platform,
        (
            "hostname router1",
            "group core",
            " interface 'Bundle-Ether.*'",
            "  mtu 9188",
            " !",
            "end-group",
        ),
    )
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines(sectional_exiting=True) == ("no group edge",)


def test_duplicate_child_route_policy() -> None:
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
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
    generated_config = HConfig.from_lines(
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines(sectional_exiting=True) == (
        "no route-policy SET_LOCAL_PREF_AND_PASS",
    )


def test_nested_if_endif_route_policy() -> None:
    """Test nested if/endif blocks in route-policy don't raise DuplicateChildError."""
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
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
    generated_config = HConfig.from_lines(
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines(sectional_exiting=True) == (
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
        "end-policy",
    )


def test_flow_exporter_template_indent_adjust() -> None:
    """Test that 'template timeout' inside flow exporter-map doesn't corrupt indentation."""
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
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
    generated_config = HConfig.from_lines(
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines(sectional_exiting=True) == (
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
        "end-policy",
    )


def test_flow_exporter_template_data_options_timeout_indent_adjust() -> None:
    """Test 'template data timeout' / 'template options timeout' inside flow exporter-map.

    Follow-up to issue #205: the negative lookahead added there covered only the bare
    'template timeout' form. The 'template data timeout' and 'template options timeout'
    leaf forms still triggered the indent_adjust rule, and with no 'end-template' ever
    arriving, every subsequent line in the config was nested under them.
    """
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
        platform,
        (
            "flow exporter-map EXPORTER1",
            " version v9",
            "  options interface-table timeout 300",
            "  options sampler-table timeout 300",
            "  template data timeout 15",
            "  template options timeout 15",
            " !",
            " transport udp 9999",
            "!",
            "interface Loopback0",
            " ipv4 address 10.0.0.1 255.255.255.255",
            "!",
            "router bgp 65000",
            " neighbor 10.0.0.2",
            "  remote-as 65001",
        ),
    )
    # Everything after the flow exporter-map must remain at the top level; with the
    # unguarded rule it is all swallowed under 'template data timeout 15'.
    assert running_config.get_child(equals="interface Loopback0") is not None
    assert running_config.get_child(equals="router bgp 65000") is not None
    exporter = running_config.get_child(equals="flow exporter-map EXPORTER1")
    assert exporter is not None
    version = exporter.get_child(equals="version v9")
    assert version is not None
    assert version.get_child(equals="template data timeout 15") is not None
    assert version.get_child(equals="template options timeout 15") is not None

    generated_config = HConfig.from_lines(
        platform,
        (
            "flow exporter-map EXPORTER1",
            " version v9",
            "  options interface-table timeout 300",
            "  options sampler-table timeout 300",
            "  template data timeout 15",
            "  template options timeout 15",
            " !",
            " transport udp 9999",
            "!",
            "interface Loopback0",
            " ipv4 address 10.0.0.1 255.255.255.255",
            "!",
            "router bgp 65000",
            " neighbor 10.0.0.3",
            "  remote-as 65001",
        ),
    )
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines(sectional_exiting=True) == (
        "router bgp 65000",
        "  no neighbor 10.0.0.2",
        "  neighbor 10.0.0.3",
        "    remote-as 65001",
        "    exit",
        "  root",
    )


def test_template_block_indent_adjust() -> None:
    """Test that template blocks still parse correctly with the indent_adjust rule."""
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
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
    generated_config = HConfig.from_lines(
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
    remediation_config = running_config.remediation(generated_config)
    assert remediation_config.to_lines(sectional_exiting=True) == (
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
        "end-template",
    )


def test_ipv4_acl_sequence_number_idempotent() -> None:
    """Test IPv4 ACL sequence number idempotency (covers lines 25-31)."""
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
        platform,
        (
            "ipv4 access-list TEST_ACL",
            " 10 permit tcp any any eq 443",
            " 20 permit tcp any any eq 80",
            " 30 deny ipv4 any any",
        ),
    )
    generated_config = HConfig.from_lines(
        platform,
        (
            "ipv4 access-list TEST_ACL",
            " 10 permit tcp any any eq 443",
            " 20 permit tcp any any eq 22",
            " 30 deny ipv4 any any",
        ),
    )
    remediation_config = running_config.remediation(generated_config)

    assert remediation_config.to_lines() == (
        "ipv4 access-list TEST_ACL",
        "  20 permit tcp any any eq 22",
    )


def test_ipv6_acl_sequence_number_idempotent() -> None:
    """Test IPv6 ACL sequence number idempotency (covers lines 25-31)."""
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
        platform,
        (
            "ipv6 access-list TEST_IPV6_ACL",
            " 10 permit tcp any any eq 443",
            " 20 deny ipv6 any any",
        ),
    )
    generated_config = HConfig.from_lines(
        platform,
        (
            "ipv6 access-list TEST_IPV6_ACL",
            " 10 permit tcp any any eq 22",
            " 20 deny ipv6 any any",
        ),
    )
    remediation_config = running_config.remediation(generated_config)

    assert remediation_config.to_lines() == (
        "ipv6 access-list TEST_IPV6_ACL",
        "  10 permit tcp any any eq 22",
    )


def test_ipv4_acl_sequence_number_addition() -> None:
    """Test adding new IPv4 ACL entries with sequence numbers."""
    platform = Platform.CISCO_XR
    running_config = HConfig.from_lines(
        platform,
        (
            "ipv4 access-list TEST_ACL",
            " 10 permit tcp any any eq 443",
            " 30 deny ipv4 any any",
        ),
    )
    generated_config = HConfig.from_lines(
        platform,
        (
            "ipv4 access-list TEST_ACL",
            " 10 permit tcp any any eq 443",
            " 20 permit tcp any any eq 22",
            " 30 deny ipv4 any any",
        ),
    )
    remediation_config = running_config.remediation(generated_config)

    assert remediation_config.to_lines() == (
        "ipv4 access-list TEST_ACL",
        "  20 permit tcp any any eq 22",
    )


def test_running_with_bang_separators_intended_without_no_remediation() -> None:
    """Running config with indented ! separators and intended without produces no remediation."""
    platform = Platform.CISCO_XR
    running = HConfig.from_text(
        platform,
        """\
telemetry model-driven
 destination-group DEST-GROUP-1
  address-family ipv4 10.0.0.1 port 57000
   encoding self-describing-gpb
   protocol tcp
  !
 !
 destination-group DEST-GROUP-2
  address-family ipv4 10.0.0.2 port 57000
   encoding self-describing-gpb
   protocol tcp
  !
 !
""",
    )
    intended = HConfig.from_text(
        platform,
        """\
telemetry model-driven
 destination-group DEST-GROUP-1
  address-family ipv4 10.0.0.1 port 57000
   encoding self-describing-gpb
   protocol tcp
 destination-group DEST-GROUP-2
  address-family ipv4 10.0.0.2 port 57000
   encoding self-describing-gpb
   protocol tcp
""",
    )
    assert running.remediation(intended).to_lines() == ()


def test_intended_with_bang_comments_running_without_no_remediation() -> None:
    """Intended config with ! comment lines and running without produces no remediation."""
    platform = Platform.CISCO_XR
    running = HConfig.from_text(
        platform,
        """\
telemetry model-driven
 destination-group DEST-GROUP-1
  address-family ipv4 10.0.0.1 port 57000
   encoding self-describing-gpb
   protocol tcp
 destination-group DEST-GROUP-2
  address-family ipv4 10.0.0.2 port 57000
   encoding self-describing-gpb
   protocol tcp
""",
    )
    intended = HConfig.from_text(
        platform,
        """\
telemetry model-driven
 ! This is a test comment
 ! This is a second test comment
 destination-group DEST-GROUP-1
  address-family ipv4 10.0.0.1 port 57000
   encoding self-describing-gpb
   protocol tcp
 destination-group DEST-GROUP-2
  address-family ipv4 10.0.0.2 port 57000
   encoding self-describing-gpb
   protocol tcp
""",
    )
    assert running.remediation(intended).to_lines() == ()


def test_differing_bang_comment_text_produces_no_remediation() -> None:
    """Differing ! comment text between running and intended produces no remediation."""
    platform = Platform.CISCO_XR
    running = HConfig.from_text(
        platform,
        """\
router isis backbone
 ! original comment
 net 49.0001.1921.2022.0222.00
""",
    )
    intended = HConfig.from_text(
        platform,
        """\
router isis backbone
 ! completely different comment
 net 49.0001.1921.2022.0222.00
""",
    )
    assert running.remediation(intended).to_lines() == ()
