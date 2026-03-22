"""Integration tests for remediation, future, difference, and sectional overwrite."""

from hier_config import (
    HConfigChild,
    WorkflowRemediation,
    get_hconfig,
    get_hconfig_driver,
    get_hconfig_fast_load,
)
from hier_config.models import Platform


def test_config_to_get_to(platform_a: Platform) -> None:
    running_config_hier = get_hconfig(platform_a)
    interface = running_config_hier.add_child("interface Vlan2")
    interface.add_child("ip address 192.168.1.1/24")
    generated_config_hier = get_hconfig(platform_a)
    generated_config_hier.add_child("interface Vlan3")
    remediation_config_hier = running_config_hier.config_to_get_to(
        generated_config_hier,
    )
    assert len(tuple(remediation_config_hier.all_children())) == 2


def test_config_to_get_to2(platform_a: Platform) -> None:
    running_config_hier = get_hconfig(platform_a)
    running_config_hier.add_child("do not add me")
    generated_config_hier = get_hconfig(platform_a)
    generated_config_hier.add_child("do not add me")
    generated_config_hier.add_child("add me")
    delta = get_hconfig(platform_a)
    running_config_hier.config_to_get_to(
        generated_config_hier,
        delta,
    )
    assert "do not add me" not in delta.children
    assert "add me" in delta.children


def test_future_config(platform_a: Platform) -> None:
    running_config = get_hconfig(platform_a)
    running_config.add_children_deep(("a", "aa", "aaa", "aaaa"))
    running_config.add_children_deep(("a", "ab", "aba", "abaa"))
    config = get_hconfig(platform_a)
    config.add_children_deep(("a", "ac"))
    config.add_children_deep(("a", "no ab"))
    config.add_children_deep(("a", "no az"))

    future_config = running_config.future(config)
    assert tuple(c.cisco_style_text() for c in future_config.all_children()) == (
        "a",
        "  ac",  # config lines are added first
        "  no az",
        "  aa",  # self lines not in config are added last
        "    aaa",
        "      aaaa",
    )


def test_future_preserves_bgp_neighbor_description() -> None:
    """Validate Arista BGP neighbors keep untouched descriptions across future/rollback.

    This regression asserts that applying a candidate config via ``future()`` retains
    existing neighbor descriptions and the subsequent ``config_to_get_to`` rollback only
    negates the new commands.
    """
    platform = Platform.ARISTA_EOS
    running_raw = """router bgp 1
  neighbor 2.2.2.2 description neighbor2
  neighbor 2.2.2.2 remote-as 2
  !
"""
    change_raw = """router bgp 1
  neighbor 3.3.3.3 description neighbor3
  neighbor 3.3.3.3 remote-as 3
"""

    running_config = get_hconfig(platform, running_raw)
    change_config = get_hconfig(platform, change_raw)

    future_config = running_config.future(change_config)
    expected_future = (
        "router bgp 1",
        "  neighbor 3.3.3.3 description neighbor3",
        "  neighbor 3.3.3.3 remote-as 3",
        "  neighbor 2.2.2.2 description neighbor2",
        "  neighbor 2.2.2.2 remote-as 2",
        "  exit",
    )
    assert future_config.dump_simple(sectional_exiting=True) == expected_future

    rollback_config = future_config.config_to_get_to(running_config)
    expected_rollback = (
        "router bgp 1",
        "  no neighbor 3.3.3.3 description neighbor3",
        "  no neighbor 3.3.3.3 remote-as 3",
        "  exit",
    )
    assert rollback_config.dump_simple(sectional_exiting=True) == expected_rollback


def test_idempotent_commands() -> None:
    platform = Platform.HP_PROCURVE
    config_a = get_hconfig(platform)
    config_b = get_hconfig(platform)
    interface_name = "interface 1/1"
    config_a.add_children_deep((interface_name, "untagged vlan 1"))
    config_b.add_children_deep((interface_name, "untagged vlan 2"))
    interface = config_a.config_to_get_to(config_b).get_child(equals=interface_name)
    assert interface is not None
    assert interface.get_child(equals="untagged vlan 2")
    assert len(interface.children) == 1


def test_idempotent_commands2() -> None:
    platform = Platform.CISCO_IOS
    config_a = get_hconfig(platform)
    config_b = get_hconfig(platform)
    interface_name = "interface 1/1"
    config_a.add_children_deep((interface_name, "authentication host-mode multi-auth"))
    config_b.add_children_deep(
        (interface_name, "authentication host-mode multi-domain"),
    )
    interface = config_a.config_to_get_to(config_b).get_child(equals=interface_name)
    assert interface is not None
    assert interface.get_child(equals="authentication host-mode multi-domain")
    assert len(interface.children) == 1


def test_future_config_no_command_in_source() -> None:
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig(platform)
    generated_config = get_hconfig(platform)
    generated_config.add_child("no service dhcp")

    remediation_config = running_config.config_to_get_to(generated_config)
    future_config = running_config.future(remediation_config)
    assert len(future_config.children) == 1
    assert future_config.get_child(equals="no service dhcp")
    assert not tuple(future_config.unified_diff(generated_config))
    rollback_config = future_config.config_to_get_to(running_config)
    assert len(rollback_config.children) == 1
    assert rollback_config.get_child(equals="service dhcp")
    calculated_running_config = future_config.future(rollback_config)
    assert not calculated_running_config.children
    assert not tuple(calculated_running_config.unified_diff(running_config))


def test_sectional_overwrite() -> None:
    platform = Platform.CISCO_XR
    # There is a sectional_overwrite rules in the CISCO_XR driver for "template".
    running_config = get_hconfig_fast_load(platform, "template test\n  a\n  b")
    generated_config = get_hconfig_fast_load(platform, "template test\n  a")
    expected_remediation_config = get_hconfig_fast_load(
        platform, "no template test\ntemplate test\n  a"
    )
    workflow_remediation = WorkflowRemediation(running_config, generated_config)
    remediation_config = workflow_remediation.remediation_config
    assert remediation_config == expected_remediation_config


def test_sectional_overwrite_no_negate() -> None:
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(platform, "as-path-set test\n  a\n  b")
    generated_config = get_hconfig_fast_load(platform, "as-path-set test\n  a")
    expected_remediation_config = get_hconfig_fast_load(
        platform, "as-path-set test\n  a"
    )
    workflow_remediation = WorkflowRemediation(running_config, generated_config)
    remediation_config = workflow_remediation.remediation_config
    assert remediation_config == expected_remediation_config


def test_sectional_overwrite_no_negate2() -> None:
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        "route-policy test\n  duplicate\n  not_duplicate1\n  duplicate\n  not_duplicate2",
    )
    generated_config = get_hconfig_fast_load(
        platform, "route-policy test\n  duplicate\n  not_duplicate1"
    )
    expected_remediation_config = get_hconfig_fast_load(
        platform, "route-policy test\n  duplicate\n  not_duplicate1"
    )
    workflow_remediation = WorkflowRemediation(running_config, generated_config)
    remediation_config = workflow_remediation.remediation_config
    assert remediation_config == expected_remediation_config


def test_overwrite_with_negate() -> None:
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform, "route-policy test\n  duplicate\n  not_duplicate\n  duplicate"
    )
    generated_config = get_hconfig_fast_load(
        platform, "route-policy test\n  duplicate\n  not_duplicate"
    )
    expected_config = get_hconfig_fast_load(
        platform,
        "no route-policy test\nroute-policy test\n  duplicate\n  not_duplicate",
    )
    delta_config = get_hconfig(platform)
    running_config.children["route-policy test"].overwrite_with(
        generated_config.children["route-policy test"], delta_config
    )
    assert delta_config == expected_config


def test_overwrite_with_no_negate() -> None:
    platform = Platform.CISCO_XR
    running_config = get_hconfig_fast_load(
        platform,
        "route-policy test\n  duplicate\n  not-duplicate\n  duplicate\n  duplicate",
    )
    generated_config = get_hconfig_fast_load(
        platform, "route-policy test\n  duplicate\n  not-duplicate\n  duplicate"
    )
    expected_config = get_hconfig_fast_load(
        platform,
        "route-policy test\n  duplicate\n  not-duplicate\n  duplicate",
    )
    delta_config = get_hconfig(platform)
    running_config.children["route-policy test"].overwrite_with(
        generated_config.children["route-policy test"], delta_config, negate=False
    )
    assert delta_config == expected_config


def test_config_to_get_to_parent_identity() -> None:
    interface_vlan2 = "interface Vlan2"
    platform = Platform.CISCO_IOS
    running_config_hier = get_hconfig(platform)
    running_config_hier.add_children_deep(
        (interface_vlan2, "ip address 192.168.1.1/24")
    )
    generated_config_hier = get_hconfig(platform)
    generated_config_hier.add_child(interface_vlan2)
    remediation_config_hier = running_config_hier.config_to_get_to(
        generated_config_hier,
    )
    remediation_config_interface = remediation_config_hier.get_child(
        equals=interface_vlan2
    )
    assert remediation_config_interface
    assert id(remediation_config_interface.parent) == id(remediation_config_hier)
    assert id(remediation_config_interface.root) == id(remediation_config_hier)


def test_difference1(platform_a: Platform) -> None:
    rc = ("a", " a1", " a2", " a3", "b")
    step = ("a", " a1", " a2", " a3", " a4", " a5", "b", "c", "d", " d1")
    rc_hier = get_hconfig(get_hconfig_driver(platform_a), "\n".join(rc))

    difference = get_hconfig(
        get_hconfig_driver(platform_a), "\n".join(step)
    ).difference(rc_hier)
    difference_children = tuple(
        c.cisco_style_text() for c in difference.all_children_sorted()
    )

    assert len(difference_children) == 6
    assert "c" in difference.children
    assert "d" in difference.children
    difference_a = difference.get_child(equals="a")
    assert isinstance(difference_a, HConfigChild)
    assert "a4" in difference_a.children
    assert "a5" in difference_a.children
    difference_d = difference.get_child(equals="d")
    assert isinstance(difference_d, HConfigChild)
    assert "d1" in difference_d.children


def test_difference2() -> None:
    platform = Platform.CISCO_IOS
    rc = ("a", " a1", " a2", " a3", "b")
    step = ("a", " a1", " a2", " a3", " a4", " a5", "b", "c", "d", " d1")
    rc_hier = get_hconfig(get_hconfig_driver(platform), "\n".join(rc))
    step_hier = get_hconfig(get_hconfig_driver(platform), "\n".join(step))

    difference_children = tuple(
        c.cisco_style_text()
        for c in step_hier.difference(rc_hier).all_children_sorted()
    )
    assert len(difference_children) == 6


def test_difference3() -> None:
    platform = Platform.CISCO_IOS
    rc = ("ip access-list extended test", " 10 a", " 20 b")
    step = ("ip access-list extended test", " 10 a", " 20 b", " 30 c")
    rc_hier = get_hconfig(get_hconfig_driver(platform), "\n".join(rc))
    step_hier = get_hconfig(get_hconfig_driver(platform), "\n".join(step))

    difference_children = tuple(
        c.cisco_style_text()
        for c in step_hier.difference(rc_hier).all_children_sorted()
    )
    assert difference_children == ("ip access-list extended test", "  30 c")


def test_difference_with_acl_none_target() -> None:
    """Test _difference with ACL when target_acl_children is None."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)

    acl = running_config.add_child("ip access-list extended test")
    acl.add_child("10 permit ip any any")
    target_config = get_hconfig(platform)
    difference = running_config.difference(target_config)

    assert difference.get_child(equals="ip access-list extended test") is not None


def test_difference_with_negation() -> None:
    """Test _difference with negation prefix."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    running_config.add_child("interface GigabitEthernet0/0")
    running_config.add_child("logging console")
    generated_config = get_hconfig(platform)
    generated_config.add_child("interface GigabitEthernet0/0")
    difference = running_config.difference(generated_config)

    assert difference.get_child(equals="logging console") is not None


def test_difference_with_default_prefix() -> None:
    """Test _difference skips lines with 'default' prefix."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    running_config.add_child("interface GigabitEthernet0/0")
    running_config.add_child("default interface GigabitEthernet0/1")
    generated_config = get_hconfig(platform)
    generated_config.add_child("interface GigabitEthernet0/0")
    difference = running_config.difference(generated_config)

    assert difference.get_child(startswith="default") is None


def test_future_with_negated_command_in_config() -> None:
    """Test _future with negated command."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    running_config.add_child("interface GigabitEthernet0/0")
    remediation_config = get_hconfig(platform)
    remediation_config.add_child("no interface GigabitEthernet0/0")
    future_config = running_config.future(remediation_config)

    assert future_config.get_child(equals="interface GigabitEthernet0/0") is None


def test_future_with_negation_prefix_match() -> None:
    """Test _future when negated form exists."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    running_config.add_child("no logging console")
    remediation_config = get_hconfig(platform)
    remediation_config.add_child("logging console")
    future_config = running_config.future(remediation_config)

    assert future_config.get_child(equals="logging console") is not None
    assert future_config.get_child(equals="no logging console") is None


def test_future_with_negation_prefix() -> None:
    """Test _future with negation prefix in self."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    running_config.add_child("no ip routing")
    remediation_config = get_hconfig(platform)
    remediation_config.add_child("ip routing")
    future_config = running_config.future(remediation_config)

    assert future_config.get_child(equals="ip routing") is None
    assert future_config.get_child(equals="no ip routing") is None


def test_future_self_child_not_in_negated_or_recursed() -> None:
    """Test _future when self_child is not in negated_or_recursed."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    running_config.add_child("hostname router1")
    running_config.add_child("interface GigabitEthernet0/0")
    remediation_config = get_hconfig(platform)
    remediation_config.add_child("hostname router2")
    future_config = running_config.future(remediation_config)

    assert future_config.get_child(equals="hostname router2") is not None
    assert future_config.get_child(equals="interface GigabitEthernet0/0") is not None


def test_future_with_idempotent_command() -> None:
    """Test _future with idempotent command."""
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig(platform)
    interface = running_config.add_child("interface 1/1")
    interface.add_child("untagged vlan 1")
    remediation_config = get_hconfig(platform)
    remediation_interface = remediation_config.add_child("interface 1/1")
    remediation_interface.add_child("untagged vlan 2")
    future_config = running_config.future(remediation_config)
    future_interface = future_config.get_child(equals="interface 1/1")

    assert future_interface is not None
    assert future_interface.get_child(equals="untagged vlan 2") is not None


def test_sectional_exit_text_parent_level_cisco_xr() -> None:
    """Test sectional_exit_text_parent_level returns True for Cisco XR configs with parent-level exit text."""
    platform = Platform.CISCO_XR
    config = get_hconfig(platform)

    # Test route-policy which has exit_text_parent_level=True
    route_policy = config.add_child("route-policy TEST")
    assert route_policy.sectional_exit_text_parent_level is True

    # Test prefix-set which has exit_text_parent_level=True
    prefix_set = config.add_child("prefix-set TEST")
    assert prefix_set.sectional_exit_text_parent_level is True

    # Test policy-map which has exit_text_parent_level=True
    policy_map = config.add_child("policy-map TEST")
    assert policy_map.sectional_exit_text_parent_level is True

    # Test class-map which has exit_text_parent_level=True
    class_map = config.add_child("class-map TEST")
    assert class_map.sectional_exit_text_parent_level is True

    # Test community-set which has exit_text_parent_level=True
    community_set = config.add_child("community-set TEST")
    assert community_set.sectional_exit_text_parent_level is True

    # Test extcommunity-set which has exit_text_parent_level=True
    extcommunity_set = config.add_child("extcommunity-set TEST")
    assert extcommunity_set.sectional_exit_text_parent_level is True

    # Test template which has exit_text_parent_level=True
    template = config.add_child("template TEST")
    assert template.sectional_exit_text_parent_level is True


def test_sectional_exit_text_parent_level_cisco_xr_false() -> None:
    """Test sectional_exit_text_parent_level returns False for Cisco XR configs without parent-level exit text."""
    platform = Platform.CISCO_XR
    config = get_hconfig(platform)

    # Test interface which has exit_text_parent_level=False (default)
    interface = config.add_child("interface GigabitEthernet0/0/0/0")
    assert interface.sectional_exit_text_parent_level is False

    # Test router bgp which has exit_text_parent_level=False (default)
    router_bgp = config.add_child("router bgp 65000")
    assert router_bgp.sectional_exit_text_parent_level is False


def test_sectional_exit_text_parent_level_cisco_ios() -> None:
    """Test sectional_exit_text_parent_level returns False for standard Cisco IOS configs."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)

    # Cisco IOS interfaces don't have exit_text_parent_level=True
    interface = config.add_child("interface GigabitEthernet0/0")
    assert interface.sectional_exit_text_parent_level is False

    # Cisco IOS router configurations don't have exit_text_parent_level=True
    router = config.add_child("router ospf 1")
    assert router.sectional_exit_text_parent_level is False

    # Standard configuration sections
    line = config.add_child("line vty 0 4")
    assert line.sectional_exit_text_parent_level is False


def test_sectional_exit_text_parent_level_no_match() -> None:
    """Test sectional_exit_text_parent_level returns False when no rules match."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)

    # A child that doesn't match any sectional_exiting rules
    hostname = config.add_child("hostname TEST")
    assert hostname.sectional_exit_text_parent_level is False

    # A simple config line without children
    ntp = config.add_child("ntp server 10.0.0.1")
    assert ntp.sectional_exit_text_parent_level is False


def test_sectional_exit_text_parent_level_with_nested_children() -> None:
    """Test sectional_exit_text_parent_level with nested child configurations."""
    platform = Platform.CISCO_XR
    config = get_hconfig(platform)

    # Create a route-policy with nested children
    route_policy = config.add_child("route-policy TEST")
    if_statement = route_policy.add_child("if destination in (192.0.2.0/24) then")

    # Parent (route-policy) should have exit_text_parent_level=True
    assert route_policy.sectional_exit_text_parent_level is True

    # Nested child should not match the sectional_exiting rule for route-policy
    assert if_statement.sectional_exit_text_parent_level is False


def test_sectional_exit_text_parent_level_indentation_in_lines() -> None:
    """Test that sectional_exit_text_parent_level affects indentation in lines output."""
    platform = Platform.CISCO_XR
    config = get_hconfig(platform)

    # Create a route-policy with children - exit text should be at parent level (depth - 1)
    route_policy = config.add_child("route-policy TEST")
    route_policy.add_child("set local-preference 200")
    route_policy.add_child("pass")

    # Get lines with sectional_exiting=True
    lines = list(config.lines(sectional_exiting=True))

    # The last line should be "end-policy" at depth 0 (parent level)
    # route-policy is at depth 1, so exit text at depth 0 means no indentation
    assert lines[-1] == "end-policy"
    assert not lines[-1].startswith(" ")


def test_sectional_exit_text_parent_level_generic_platform() -> None:
    """Test sectional_exit_text_parent_level with generic platform."""
    platform = Platform.GENERIC
    config = get_hconfig(platform)

    # Generic platform has no specific sectional_exiting rules with parent_level=True
    section = config.add_child("section test")
    assert section.sectional_exit_text_parent_level is False
