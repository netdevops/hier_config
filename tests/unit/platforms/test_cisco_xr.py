from hier_config import get_hconfig, get_hconfig_fast_load
from hier_config.models import Platform


def test_multiple_groups_no_duplicate_child_error() -> None:
    """Test that multiple group blocks don't raise DuplicateChildError (issue #209)."""
    platform = Platform.CISCO_XR
    config_text = """\
hostname router1
group core
 interface 'Bundle-Ether.*'
  mtu 9188
 !
end-group
group edge
 interface 'Bundle-Ether.*'
  mtu 9092
 !
end-group
"""
    hconfig = get_hconfig(platform, config_text)
    children = [child.text for child in hconfig.children]
    assert "hostname router1" in children
    assert "group core" in children
    assert "group edge" in children


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


def test_indented_bang_section_separators_no_duplicate_child_error() -> None:
    """Test that indented ! section separators don't raise DuplicateChildError (issue #231)."""
    platform = Platform.CISCO_XR
    config_text = """\
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
 sensor-group SENSOR-1
  sensor-path openconfig-platform:components/component/cpu
  sensor-path openconfig-platform:components/component/memory
 !
 sensor-group SENSOR-2
  sensor-path openconfig-interfaces:interfaces/interface/state/counters
 !
!
"""
    hconfig = get_hconfig(platform, config_text)
    telemetry = hconfig.get_child(equals="telemetry model-driven")
    assert telemetry is not None
    child_texts = [child.text for child in telemetry.children]
    assert "destination-group DEST-GROUP-1" in child_texts
    assert "destination-group DEST-GROUP-2" in child_texts
    assert "sensor-group SENSOR-1" in child_texts
    assert "sensor-group SENSOR-2" in child_texts


def test_xr_comment_attached_to_next_sibling() -> None:
    """IOS-XR inline comments are attached to the next sibling's comments set."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
router isis backbone
 ! ISIS network number should be encoded with 0-padded loopback IP
 net 49.0001.1921.2022.0222.00
""",
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    net_child = router_isis.get_child(
        startswith="net ",
    )
    assert net_child is not None
    assert (
        "ISIS network number should be encoded with 0-padded loopback IP"
        in net_child.comments
    )


def test_xr_multiple_comments_before_line() -> None:
    """Multiple consecutive comment lines are all attached to the next sibling."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
router isis backbone
 ! first comment
 ! second comment
 net 49.0001.1921.2022.0222.00
""",
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    net_child = router_isis.get_child(startswith="net ")
    assert net_child is not None
    assert "first comment" in net_child.comments
    assert "second comment" in net_child.comments


def test_xr_comment_lines_not_parsed_as_children() -> None:
    """Comment lines starting with ! should not appear as config children."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
router isis backbone
 ! this is a comment
 net 49.0001.1921.2022.0222.00
""",
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    for child in router_isis.all_children():
        assert not child.text.startswith("!")


def test_xr_top_level_bang_delimiters_stripped() -> None:
    """Top-level ! delimiters (with no comment text) are stripped."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
hostname router1
!
interface GigabitEthernet0/0/0/0
 description test
!
""",
    )
    children = [child.text for child in config.children]
    assert "hostname router1" in children
    assert "interface GigabitEthernet0/0/0/0" in children
    assert "!" not in children


def test_xr_comment_preservation_with_fast_load() -> None:
    """Comments are also preserved when using get_hconfig_fast_load."""
    config = get_hconfig_fast_load(
        Platform.CISCO_XR,
        (
            "router isis backbone",
            " ! loopback comment",
            " net 49.0001.0000.0000.0001.00",
        ),
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    net_child = router_isis.get_child(startswith="net ")
    assert net_child is not None
    assert "loopback comment" in net_child.comments


def test_xr_hash_comments_still_stripped() -> None:
    """Lines starting with # are still stripped (not preserved)."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
hostname router1
# this should be stripped
interface GigabitEthernet0/0/0/0
""",
    )
    for child in config.all_children():
        assert not child.text.startswith("#")


def test_xr_comment_with_leading_bang_preserved() -> None:
    """A comment containing ! in its body is preserved correctly."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
router isis backbone
 ! !important note about ISIS
 net 49.0001.1921.2022.0222.00
""",
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    net_child = router_isis.get_child(startswith="net ")
    assert net_child is not None
    assert "!important note about ISIS" in net_child.comments


def test_xr_trailing_comment_with_no_following_sibling_is_dropped() -> None:
    """A trailing ! comment at the end of a section with no following sibling is silently dropped."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
router isis backbone
 net 49.0001.1921.2022.0222.00
 ! trailing comment with no following sibling
""",
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    net_child = router_isis.get_child(startswith="net ")
    assert net_child is not None
    assert len(net_child.comments) == 0
    for child in router_isis.all_children():
        assert not child.text.startswith("!")
