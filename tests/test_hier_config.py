import tempfile
import types
from pathlib import Path

import pytest

from hier_config import (
    HConfigChild,
    WorkflowRemediation,
    get_hconfig,
    get_hconfig_driver,
    get_hconfig_fast_load,
    get_hconfig_from_dump,
)
from hier_config.exceptions import DuplicateChildError
from hier_config.models import Instance, MatchRule, Platform


def test_bool(platform_a: Platform) -> None:
    config = get_hconfig(platform_a)
    assert config


def test_hash(platform_a: Platform) -> None:
    config = get_hconfig_fast_load(platform_a, ("interface 1/1", "  untagged vlan 5"))
    assert hash(config)


def test_merge(platform_a: Platform, platform_b: Platform) -> None:
    hier1 = get_hconfig(platform_a)
    hier1.add_child("interface Vlan2")
    hier2 = get_hconfig(platform_b)
    hier2.add_child("interface Vlan3")

    assert len(tuple(hier1.all_children())) == 1
    assert len(tuple(hier2.all_children())) == 1

    hier1.merge(hier2)

    assert len(tuple(hier1.all_children())) == 2


def test_load_from_file(platform_a: Platform) -> None:
    config = "interface Vlan2\n ip address 1.1.1.1 255.255.255.0"

    with tempfile.NamedTemporaryFile(
        mode="r+",
        delete=False,
        encoding="utf8",
    ) as myfile:
        myfile.file.write(config)
        myfile.file.flush()
        myfile.close()
        hier = get_hconfig(get_hconfig_driver(platform_a), Path(myfile.name))
        Path(myfile.name).unlink()

    assert len(tuple(hier.all_children())) == 2


def test_load_from_config_text(platform_a: Platform) -> None:
    config = "interface Vlan2\n ip address 1.1.1.1 255.255.255.0"
    hier = get_hconfig(get_hconfig_driver(platform_a), config)
    assert len(tuple(hier.all_children())) == 2


def test_dump_and_load_from_dump_and_compare(platform_a: Platform) -> None:
    hier_pre_dump = get_hconfig(platform_a)
    b2 = hier_pre_dump.add_children_deep(("a1", "b2"))

    b2.order_weight = 400
    b2.tags_add("test")
    b2.comments.add("test comment")
    b2.new_in_config = True

    dump = hier_pre_dump.dump()
    hier_post_dump = get_hconfig_from_dump(hier_pre_dump.driver, dump)

    assert hier_pre_dump == hier_post_dump


def test_add_ancestor_copy_of(platform_a: Platform) -> None:
    source_config = get_hconfig(platform_a)
    ipv4_address = source_config.add_children_deep(
        ("interface Vlan2", "ip address 192.168.1.0/24")
    )
    destination_config = get_hconfig(platform_a)
    destination_config.add_ancestor_copy_of(ipv4_address)

    assert len(tuple(destination_config.all_children())) == 2
    assert isinstance(destination_config.all_children(), types.GeneratorType)


def test_depth(platform_a: Platform) -> None:
    ip_address = get_hconfig(platform_a).add_children_deep(
        ("interface Vlan2", "ip address 192.168.1.1 255.255.255.0"),
    )
    assert ip_address.depth() == 2


def test_get_child(platform_a: Platform) -> None:
    hier = get_hconfig(platform_a)
    hier.add_child("interface Vlan2")
    child = hier.get_child(equals="interface Vlan2")
    assert child is not None
    assert child.text == "interface Vlan2"


def test_get_child_deep(platform_a: Platform) -> None:
    hier = get_hconfig(platform_a)
    interface1 = hier.add_child("interface Vlan1")
    interface1.add_children(
        ("ip address 192.168.1.1 255.255.255.0", "description asdf1"),
    )
    interface2 = hier.add_child("interface Vlan2")
    interface2.add_children(
        ("ip address 192.168.2.1 255.255.255.0", "description asdf2"),
    )
    interface3 = hier.add_child("interface Vlan3")
    interface3.add_children(
        ("ip address 192.168.3.1 255.255.255.0", "description asdf3"),
    )

    # search all 'interface vlan' interfaces for 'ip address'
    children = tuple(
        hier.get_children_deep(
            (
                MatchRule(startswith="interface Vlan"),
                MatchRule(startswith="ip address "),
            ),
        ),
    )
    assert len(children) == 3
    children = tuple(
        hier.get_children_deep(
            (
                MatchRule(startswith="interface Vlan1"),
                MatchRule(startswith="ip address "),
            ),
        ),
    )
    assert len(children) == 1
    children = tuple(
        hier.get_children_deep(
            (
                MatchRule(equals="interface Vlan2"),
                MatchRule(equals="ip address 192.168.2.1 255.255.255.0"),
            ),
        ),
    )
    assert len(children) == 1


def test_child_deep2() -> None:
    config = get_hconfig(Platform.CISCO_IOS)

    config.add_children_deep(("a", "b"))
    config.add_children_deep(("a", "b1"))
    config.add_children_deep(("a", "b2"))

    assert (
        len(
            tuple(
                config.get_children_deep(
                    (MatchRule(startswith="a"), MatchRule(startswith="b")),
                ),
            ),
        )
        == 3
    )

    assert (
        len(
            tuple(
                config.get_children_deep(
                    (MatchRule(equals="a"), MatchRule(startswith="b2")),
                ),
            ),
        )
        == 1
    )


def test_get_children(platform_a: Platform) -> None:
    hier = get_hconfig(platform_a)
    hier.add_child("interface Vlan2")
    hier.add_child("interface Vlan3")
    children = tuple(hier.get_children(startswith="interface"))
    assert len(children) == 2
    for child in children:
        assert child.text.startswith("interface Vlan")


def test_move(platform_a: Platform, platform_b: Platform) -> None:
    hier1 = get_hconfig(platform_a)
    interface1 = hier1.add_child("interface Vlan2")
    interface1.add_child("192.168.0.1/30")

    assert len(tuple(hier1.all_children())) == 2

    hier2 = get_hconfig(platform_b)

    assert not tuple(hier2.all_children())

    interface1.move(hier2)

    assert not tuple(hier1.all_children())
    assert len(tuple(hier2.all_children())) == 2


def test_del_child_by_text(platform_a: Platform) -> None:
    hier = get_hconfig(platform_a)
    hier.add_child("interface Vlan2")
    hier.children.delete("interface Vlan2")

    assert not tuple(hier.all_children())


def test_del_child(platform_a: Platform) -> None:
    hier1 = get_hconfig(platform_a)
    hier1.add_child("interface Vlan2")

    assert len(tuple(hier1.all_children())) == 1

    child_to_delete = hier1.get_child(startswith="interface")
    assert child_to_delete is not None
    hier1.children.delete(child_to_delete)

    assert not tuple(hier1.all_children())


def test_rebuild_children_dict(platform_a: Platform) -> None:
    hier1 = get_hconfig(platform_a)
    interface = hier1.add_child("interface Vlan2")
    interface.add_children(
        ("description switch-mgmt-192.168.1.0/24", "ip address 192.168.1.0/24"),
    )
    delta_a = hier1
    hier1.children.rebuild_mapping()
    delta_b = hier1

    assert tuple(delta_a.all_children()) == tuple(delta_b.all_children())


def test_add_children(platform_a: Platform) -> None:
    interface_items1 = (
        "description switch-mgmt 192.168.1.0/24",
        "ip address 192.168.1.1/24",
    )
    hier1 = get_hconfig(platform_a)
    interface1 = hier1.add_child("interface Vlan2")
    interface1.add_children(interface_items1)

    assert len(tuple(hier1.all_children())) == 3

    interface_items2 = ("description switch-mgmt 192.168.1.0/24",)
    hier2 = get_hconfig(platform_a)
    interface2 = hier2.add_child("interface Vlan2")
    interface2.add_children(interface_items2)

    assert len(tuple(hier2.all_children())) == 2


def test_add_child(platform_a: Platform) -> None:
    config = get_hconfig(platform_a)
    interface = config.add_child("interface Vlan2")
    assert interface.depth() == 1
    assert interface.text == "interface Vlan2"
    with pytest.raises(DuplicateChildError):
        config.add_child("interface Vlan2")
    assert config.children.get("interface Vlan2") is interface


def test_add_deep_copy_of(platform_a: Platform, platform_b: Platform) -> None:
    interface1 = get_hconfig(platform_a).add_child("interface Vlan2")
    interface1.add_children(
        ("description switch-mgmt-192.168.1.0/24", "ip address 192.168.1.0/24"),
    )

    hier2 = get_hconfig(platform_b)
    hier2.add_deep_copy_of(interface1)

    assert len(tuple(hier2.all_children())) == 3
    assert isinstance(hier2.all_children(), types.GeneratorType)


def test_path(platform_a: Platform) -> None:
    config_aaa = get_hconfig(platform_a).add_children_deep(("a", "aa", "aaa"))
    assert tuple(config_aaa.path()) == ("a", "aa", "aaa")


def test_cisco_style_text(platform_a: Platform) -> None:
    ip_address = (
        get_hconfig(platform_a)
        .add_child("interface Vlan2")
        .add_child("ip address 192.168.1.1 255.255.255.0")
    )
    assert ip_address.cisco_style_text() == "  ip address 192.168.1.1 255.255.255.0"
    assert isinstance(ip_address.cisco_style_text(), str)
    assert not isinstance(ip_address.cisco_style_text(), list)


def test_all_children_sorted_by_tags(platform_a: Platform) -> None:
    config = get_hconfig(platform_a)
    config_a = config.add_child("a")
    config_aa = config_a.add_child("aa")
    config_a.add_child("ab")
    config_aaa = config_aa.add_child("aaa")
    config_aab = config_aa.add_child("aab")
    config_aaa.tags_add("aaa")
    config_aab.tags_add("aab")

    case_1_matches = [
        c.text
        for c in config.all_children_sorted_by_tags(frozenset(("aaa",)), frozenset())
    ]
    assert case_1_matches == ["a", "aa", "aaa"]
    case_2_matches = [
        c.text
        for c in config.all_children_sorted_by_tags(frozenset(), frozenset(("aab",)))
    ]
    assert case_2_matches == ["a", "aa", "aaa", "ab"]
    case_3_matches = [
        c.text
        for c in config.all_children_sorted_by_tags(
            frozenset(("aaa",)),
            frozenset(("aab",)),
        )
    ]
    assert case_3_matches == ["a", "aa", "aaa"]


def test_all_children_sorted(platform_a: Platform) -> None:
    hier = get_hconfig(platform_a)
    interface = hier.add_child("interface Vlan2")
    interface.add_child("standby 1 ip 10.15.11.1")
    assert len(tuple(hier.all_children_sorted())) == 2


def test_all_children(platform_a: Platform) -> None:
    hier = get_hconfig(platform_a)
    interface = hier.add_child("interface Vlan2")
    interface.add_child("standby 1 ip 10.15.11.1")
    assert len(tuple(hier.all_children())) == 2


def test_delete(platform_a: Platform) -> None:
    hier = get_hconfig(platform_a)
    config_a = hier.add_child("a")
    config_a.delete()
    assert not hier.children


def test_set_order_weight(platform_a: Platform) -> None:
    hier = get_hconfig(platform_a)
    child = hier.add_child("no vlan filter")
    hier.set_order_weight()
    assert child.order_weight == 200


def test_tags_add(platform_a: Platform) -> None:
    interface = get_hconfig(platform_a).add_child("interface Vlan2")
    ip_address = interface.add_child("ip address 192.168.1.1/24")
    assert not interface.tags
    assert not ip_address.tags
    ip_address.tags_add("a")
    assert "a" in interface.tags
    assert "a" in ip_address.tags
    assert "b" not in interface.tags
    assert "b" not in ip_address.tags
    interface.tags_add("c")
    assert "c" in ip_address.tags
    interface.tags_remove("c")
    assert "c" not in ip_address.tags


def test_append_tags(platform_a: Platform) -> None:
    config = get_hconfig(platform_a)
    interface = config.add_child("interface Vlan2")
    ip_address = interface.add_child("ip address 192.168.1.1/24")
    ip_address.tags_add("test_tag")
    assert "test_tag" in config.tags
    assert "test_tag" in interface.tags
    assert "test_tag" in ip_address.tags


def test_remove_tags(platform_a: Platform) -> None:
    config = get_hconfig(platform_a)
    interface = config.add_child("interface Vlan2")
    ip_address = interface.add_child("ip address 192.168.1.1/24")
    ip_address.tags_add("test_tag")
    assert "test_tag" in config.tags
    assert "test_tag" in interface.tags
    assert "test_tag" in ip_address.tags
    ip_address.tags_remove("test_tag")
    assert "test_tag" not in config.tags
    assert "test_tag" not in interface.tags
    assert "test_tag" not in ip_address.tags


def test_negate(platform_a: Platform) -> None:
    config = get_hconfig(platform_a)
    interface = config.add_child("interface Vlan2")
    interface.negate()
    assert interface.text == "no interface Vlan2"
    assert config.children.get("no interface Vlan2") is interface


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


def test_add_shallow_copy_of(platform_a: Platform) -> None:
    base_config = get_hconfig(platform_a)

    interface_a = get_hconfig(platform_a).add_child("interface Vlan2")
    interface_a.tags_add(frozenset(("ta", "tb")))
    interface_a.comments.add("ca")
    interface_a.order_weight = 200

    copied_interface = base_config.add_shallow_copy_of(interface_a, merged=True)
    assert copied_interface.tags == frozenset(("ta", "tb"))
    assert copied_interface.comments == frozenset(("ca",))
    assert copied_interface.order_weight == 200
    assert copied_interface.instances == [
        Instance(
            id=id(interface_a.root),
            comments=frozenset(interface_a.comments),
            tags=interface_a.tags,
        ),
    ]


def test_line_inclusion_test(platform_a: Platform) -> None:
    ip_address_ab = get_hconfig(platform_a).add_children_deep(
        ("interface Vlan2", "ip address 192.168.2.1/24"),
    )
    ip_address_ab.tags_add(frozenset(("a", "b")))

    assert not ip_address_ab.line_inclusion_test(frozenset(("a",)), frozenset(("b",)))
    assert not ip_address_ab.line_inclusion_test(frozenset(), frozenset(("a",)))
    assert ip_address_ab.line_inclusion_test(frozenset(("a",)), frozenset())
    assert not ip_address_ab.line_inclusion_test(frozenset(), frozenset())


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


def test_idempotency_key_with_equals_string() -> None:
    """Test idempotency key generation with equals constraint as string."""
    from hier_config.models import IdempotentCommandsRule
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()
    # Add a rule with equals as string
    driver.rules.idempotent_commands.append(
        IdempotentCommandsRule(
            match_rules=(MatchRule(equals="logging console"),),
        )
    )

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Test the idempotency with equals string
    key = driver._idempotency_key(child, (MatchRule(equals="logging console"),))
    assert key == ("equals|logging console",)


def test_idempotency_key_with_equals_frozenset() -> None:
    """Test idempotency key generation with equals constraint as frozenset."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Test the idempotency with equals frozenset (should fall back to text)
    key = driver._idempotency_key(
        child, (MatchRule(equals=frozenset(["logging console", "other"])),)
    )
    assert key == ("equals|logging console",)


def test_idempotency_key_no_match_rules() -> None:
    """Test idempotency key falls back to text when no match rules apply."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """some command
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Empty MatchRule should fall back to text
    key = driver._idempotency_key(child, (MatchRule(),))
    assert key == ("text|some command",)


def test_idempotency_key_prefix_no_match() -> None:
    """Test idempotency key when prefix doesn't match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Prefix that doesn't match should fall back to text
    key = driver._idempotency_key(child, (MatchRule(startswith="interface"),))
    assert key == ("text|logging console",)


def test_idempotency_key_suffix_no_match() -> None:
    """Test idempotency key when suffix doesn't match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Suffix that doesn't match should fall back to text
    key = driver._idempotency_key(child, (MatchRule(endswith="emergency"),))
    assert key == ("text|logging console",)


def test_idempotency_key_contains_no_match() -> None:
    """Test idempotency key when contains doesn't match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Contains that doesn't match should fall back to text
    key = driver._idempotency_key(child, (MatchRule(contains="interface"),))
    assert key == ("text|logging console",)


def test_idempotency_key_regex_no_match() -> None:
    """Test idempotency key when regex doesn't match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Regex that doesn't match should fall back to text
    key = driver._idempotency_key(child, (MatchRule(re_search="^interface"),))
    assert key == ("text|logging console",)


def test_idempotency_key_prefix_tuple_no_match() -> None:
    """Test idempotency key with tuple of prefixes that don't match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Tuple of prefixes that don't match should fall back to text
    key = driver._idempotency_key(
        child, (MatchRule(startswith=("interface", "router", "vlan")),)
    )
    assert key == ("text|logging console",)


def test_idempotency_key_prefix_tuple_match() -> None:
    """Test idempotency key with tuple of prefixes that match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Tuple of prefixes with one matching - should return longest match
    key = driver._idempotency_key(
        child, (MatchRule(startswith=("log", "logging", "logging console")),)
    )
    assert key == ("startswith|logging console",)


def test_idempotency_key_suffix_tuple_no_match() -> None:
    """Test idempotency key with tuple of suffixes that don't match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Tuple of suffixes that don't match should fall back to text
    key = driver._idempotency_key(
        child, (MatchRule(endswith=("emergency", "alert", "critical")),)
    )
    assert key == ("text|logging console",)


def test_idempotency_key_suffix_tuple_match() -> None:
    """Test idempotency key with tuple of suffixes that match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Tuple of suffixes with one matching - should return longest match
    key = driver._idempotency_key(
        child, (MatchRule(endswith=("ole", "sole", "console")),)
    )
    assert key == ("endswith|console",)


def test_idempotency_key_contains_tuple_no_match() -> None:
    """Test idempotency key with tuple of contains that don't match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Tuple of contains that don't match should fall back to text
    key = driver._idempotency_key(
        child, (MatchRule(contains=("interface", "router", "vlan")),)
    )
    assert key == ("text|logging console",)


def test_idempotency_key_contains_tuple_match() -> None:
    """Test idempotency key with tuple of contains that match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Tuple of contains with matches - should return longest match
    key = driver._idempotency_key(
        child, (MatchRule(contains=("log", "console", "logging console")),)
    )
    assert key == ("contains|logging console",)


def test_idempotency_key_regex_with_groups() -> None:
    """Test idempotency key with regex capture groups."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """router bgp 1
  neighbor 10.1.1.1 description peer1
"""
    config = get_hconfig(driver, config_raw)
    bgp_child = list(config.children)[0]
    neighbor_child = list(bgp_child.children)[0]

    # Regex with capture groups should use groups
    key = driver._idempotency_key(
        neighbor_child,
        (
            MatchRule(startswith="router bgp"),
            MatchRule(re_search=r"neighbor (\S+) description"),
        ),
    )
    assert key == ("startswith|router bgp", "re|10.1.1.1")


def test_idempotency_key_regex_with_empty_groups() -> None:
    """Test idempotency key with regex that has empty capture groups."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Regex with empty/None groups should fall back to match result
    key = driver._idempotency_key(child, (MatchRule(re_search=r"logging ()?(console)"),))
    # Group 1 is empty, group 2 has "console", so should use groups
    assert "re|" in key[0]


def test_idempotency_key_regex_greedy_pattern() -> None:
    """Test idempotency key with greedy regex pattern (.* or .+)."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console emergency
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Regex with .* should be trimmed
    key = driver._idempotency_key(child, (MatchRule(re_search=r"logging console.*"),))
    assert key == ("re|logging console",)


def test_idempotency_key_regex_greedy_pattern_with_dollar() -> None:
    """Test idempotency key with greedy regex pattern with $ anchor."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console emergency
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Regex with .*$ should be trimmed
    key = driver._idempotency_key(child, (MatchRule(re_search=r"logging console.*$"),))
    assert key == ("re|logging console",)


def test_idempotency_key_regex_only_greedy() -> None:
    """Test idempotency key with regex that is only greedy pattern."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Regex that is only .* should not trim to empty
    key = driver._idempotency_key(child, (MatchRule(re_search=r".*"),))
    # Should use the full match result
    assert key == ("re|logging console",)


def test_idempotency_key_lineage_mismatch() -> None:
    """Test idempotency key when lineage length doesn't match rules length."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """interface GigabitEthernet1/1
  description test
"""
    config = get_hconfig(driver, config_raw)
    interface_child = list(config.children)[0]
    desc_child = list(interface_child.children)[0]

    # Try to match with wrong number of rules (desc has 2 lineage levels, only 1 rule)
    key = driver._idempotency_key(desc_child, (MatchRule(startswith="description"),))
    # Should return empty tuple when lineage length != match_rules length
    assert key == ()


def test_idempotency_key_negated_command() -> None:
    """Test idempotency key with negated command."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """no logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Negated command should strip 'no ' prefix for matching
    key = driver._idempotency_key(child, (MatchRule(startswith="logging"),))
    assert key == ("startswith|logging",)


def test_idempotency_key_regex_fallback_to_original() -> None:
    """Test idempotency key regex matching fallback to original text."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """no logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Regex that matches original but not normalized (tests lines 328-329)
    key = driver._idempotency_key(child, (MatchRule(re_search=r"^no logging"),))
    assert "re|no logging" in key[0]


def test_idempotency_key_suffix_single_match() -> None:
    """Test idempotency key with single suffix that matches (not tuple)."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Single suffix that matches (tests line 359)
    key = driver._idempotency_key(child, (MatchRule(endswith="console"),))
    assert key == ("endswith|console",)


def test_idempotency_key_contains_single_match() -> None:
    """Test idempotency key with single contains that matches (not tuple)."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console emergency
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Single contains that matches (tests line 372)
    key = driver._idempotency_key(child, (MatchRule(contains="console"),))
    assert key == ("contains|console",)


def test_idempotency_key_regex_greedy_with_plus() -> None:
    """Test idempotency key with greedy regex using .+ suffix."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """interface GigabitEthernet1
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Regex with .+ should be trimmed similar to .*
    # Tests the .+ branch in line 389
    key = driver._idempotency_key(child, (MatchRule(re_search=r"interface .+"),))
    # Should trim to just "interface " and use that
    assert key == ("re|interface",)


def test_idempotency_key_regex_trimmed_to_no_match() -> None:
    """Test idempotency key when trimmed regex doesn't match."""
    from hier_config.platforms.cisco_ios.driver import HConfigDriverCiscoIOS

    driver = HConfigDriverCiscoIOS()

    config_raw = """logging console
"""
    config = get_hconfig(driver, config_raw)
    child = list(config.children)[0]

    # Regex "interface.*" matches nothing, but after trimming .* we get "interface"
    # which also doesn't match "logging console", so we fall back to full match result
    # This should hit the break at line 399 because trimmed_match is None
    key = driver._idempotency_key(child, (MatchRule(re_search=r"interface.*"),))
    # Since "interface.*" doesn't match "logging console", should fall back to text
    assert key == ("text|logging console",)


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


def test_unified_diff() -> None:
    platform = Platform.CISCO_IOS

    config_a = get_hconfig(platform)
    config_b = get_hconfig(platform)
    # deep differences
    config_a.add_children_deep(("a", "aa", "aaa", "aaaa"))
    config_b.add_children_deep(("a", "aa", "aab", "aaba"))
    # these children will be the same and should not appear in the diff
    config_a.add_children_deep(("b", "ba", "baa"))
    config_b.add_children_deep(("b", "ba", "baa"))
    # root level differences
    config_a.add_children_deep(("c", "ca"))
    config_b.add_child("d")

    diff = tuple(config_a.unified_diff(config_b))
    assert diff == (
        "a",
        "  aa",
        "    - aaa",
        "      - aaaa",
        "    + aab",
        "      + aaba",
        "- c",
        "  - ca",
        "+ d",
    )


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
