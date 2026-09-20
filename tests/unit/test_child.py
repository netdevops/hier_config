"""Tests for HConfigChild functionality."""
# pylint: disable=too-many-lines

import types

import pytest

from hier_config import HConfig, HConfigChild
from hier_config.exceptions import DuplicateChildError
from hier_config.models import Instance, MatchRule, Platform


def test_add_ancestor_copy_of(platform_a: Platform) -> None:
    source_config = HConfig.from_text(platform_a)
    ipv4_address = source_config.add_children_deep(
        ("interface Vlan2", "ip address 192.168.1.0/24")
    )
    destination_config = HConfig.from_text(platform_a)
    destination_config.add_ancestor_copy_of(ipv4_address)

    assert len(tuple(destination_config.all_children())) == 2
    assert isinstance(destination_config.all_children(), types.GeneratorType)


def test_depth(platform_a: Platform) -> None:
    ip_address = HConfig.from_text(platform_a).add_children_deep(
        ("interface Vlan2", "ip address 192.168.1.1 255.255.255.0"),
    )
    assert ip_address.depth == 2


def test_get_child(platform_a: Platform) -> None:
    hier = HConfig.from_text(platform_a)
    hier.add_child("interface Vlan2")
    child = hier.get_child(equals="interface Vlan2")
    assert child is not None
    assert child.text == "interface Vlan2"


def test_get_child_deep(platform_a: Platform) -> None:
    hier = HConfig.from_text(platform_a)
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
    config = HConfig.from_text(Platform.CISCO_IOS)

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
    hier = HConfig.from_text(platform_a)
    hier.add_child("interface Vlan2")
    hier.add_child("interface Vlan3")
    children = tuple(hier.get_children(startswith="interface"))
    assert len(children) == 2
    for child in children:
        assert child.text.startswith("interface Vlan")


def test_move(platform_a: Platform, platform_b: Platform) -> None:
    hier1 = HConfig.from_text(platform_a)
    interface1 = hier1.add_child("interface Vlan2")
    interface1.add_child("192.168.0.1/30")

    assert len(tuple(hier1.all_children())) == 2

    hier2 = HConfig.from_text(platform_b)

    assert not tuple(hier2.all_children())

    interface1.move(hier2)

    assert not tuple(hier1.all_children())
    assert len(tuple(hier2.all_children())) == 2


def test_del_child_by_text(platform_a: Platform) -> None:
    hier = HConfig.from_text(platform_a)
    hier.add_child("interface Vlan2")
    hier.children.delete("interface Vlan2")

    assert not tuple(hier.all_children())


def test_del_child(platform_a: Platform) -> None:
    hier1 = HConfig.from_text(platform_a)
    hier1.add_child("interface Vlan2")

    assert len(tuple(hier1.all_children())) == 1

    child_to_delete = hier1.get_child(startswith="interface")
    assert child_to_delete is not None
    hier1.children.delete(child_to_delete)

    assert not tuple(hier1.all_children())


def test_add_children(platform_a: Platform) -> None:
    interface_items1 = (
        "description switch-mgmt 192.168.1.0/24",
        "ip address 192.168.1.1/24",
    )
    hier1 = HConfig.from_text(platform_a)
    interface1 = hier1.add_child("interface Vlan2")
    interface1.add_children(interface_items1)

    assert len(tuple(hier1.all_children())) == 3

    interface_items2 = ("description switch-mgmt 192.168.1.0/24",)
    hier2 = HConfig.from_text(platform_a)
    interface2 = hier2.add_child("interface Vlan2")
    interface2.add_children(interface_items2)

    assert len(tuple(hier2.all_children())) == 2


def test_add_child(platform_a: Platform) -> None:
    config = HConfig.from_text(platform_a)
    interface = config.add_child("interface Vlan2")
    assert interface.depth == 1
    assert interface.text == "interface Vlan2"
    with pytest.raises(DuplicateChildError):
        config.add_child("interface Vlan2")
    assert config.children.get("interface Vlan2") is interface


def test_add_deep_copy_of(platform_a: Platform, platform_b: Platform) -> None:
    interface1 = HConfig.from_text(platform_a).add_child("interface Vlan2")
    interface1.add_children(
        ("description switch-mgmt-192.168.1.0/24", "ip address 192.168.1.0/24"),
    )

    hier2 = HConfig.from_text(platform_b)
    hier2.add_deep_copy_of(interface1)

    assert len(tuple(hier2.all_children())) == 3
    assert isinstance(hier2.all_children(), types.GeneratorType)


def test_path(platform_a: Platform) -> None:
    config_aaa = HConfig.from_text(platform_a).add_children_deep(("a", "aa", "aaa"))
    assert tuple(config_aaa.path()) == ("a", "aa", "aaa")


def test_indented_text(platform_a: Platform) -> None:
    ip_address = (
        HConfig.from_text(platform_a)
        .add_child("interface Vlan2")
        .add_child("ip address 192.168.1.1 255.255.255.0")
    )
    assert ip_address.indented_text() == "  ip address 192.168.1.1 255.255.255.0"
    assert isinstance(ip_address.indented_text(), str)
    assert not isinstance(ip_address.indented_text(), list)


def test_all_children_sorted_by_tags(platform_a: Platform) -> None:
    config = HConfig.from_text(platform_a)
    config_a = config.add_child("a")
    config_aa = config_a.add_child("aa")
    config_a.add_child("ab")
    config_aaa = config_aa.add_child("aaa")
    config_aab = config_aa.add_child("aab")
    config_aaa.add_tags("aaa")
    config_aab.add_tags("aab")

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
    hier = HConfig.from_text(platform_a)
    interface = hier.add_child("interface Vlan2")
    interface.add_child("standby 1 ip 10.15.11.1")
    assert len(tuple(hier.all_children_sorted())) == 2


def test_all_children(platform_a: Platform) -> None:
    hier = HConfig.from_text(platform_a)
    interface = hier.add_child("interface Vlan2")
    interface.add_child("standby 1 ip 10.15.11.1")
    assert len(tuple(hier.all_children())) == 2


def test_delete(platform_a: Platform) -> None:
    hier = HConfig.from_text(platform_a)
    config_a = hier.add_child("a")
    config_a.delete()
    assert not hier.children


def test_set_order_weight(platform_a: Platform) -> None:
    hier = HConfig.from_text(platform_a)
    child = hier.add_child("no vlan filter")
    hier.set_order_weight()
    assert child.order_weight == 200


def test_add_tags(platform_a: Platform) -> None:
    interface = HConfig.from_text(platform_a).add_child("interface Vlan2")
    ip_address = interface.add_child("ip address 192.168.1.1/24")
    assert not interface.tags
    assert not ip_address.tags
    ip_address.add_tags("a")
    assert "a" in interface.tags
    assert "a" in ip_address.tags
    assert "b" not in interface.tags
    assert "b" not in ip_address.tags
    interface.add_tags("c")
    assert "c" in ip_address.tags
    interface.remove_tags("c")
    assert "c" not in ip_address.tags


def test_append_tags(platform_a: Platform) -> None:
    config = HConfig.from_text(platform_a)
    interface = config.add_child("interface Vlan2")
    ip_address = interface.add_child("ip address 192.168.1.1/24")
    ip_address.add_tags("test_tag")
    assert "test_tag" in config.tags
    assert "test_tag" in interface.tags
    assert "test_tag" in ip_address.tags


def test_remove_tags(platform_a: Platform) -> None:
    config = HConfig.from_text(platform_a)
    interface = config.add_child("interface Vlan2")
    ip_address = interface.add_child("ip address 192.168.1.1/24")
    ip_address.add_tags("test_tag")
    assert "test_tag" in config.tags
    assert "test_tag" in interface.tags
    assert "test_tag" in ip_address.tags
    ip_address.remove_tags("test_tag")
    assert "test_tag" not in config.tags
    assert "test_tag" not in interface.tags
    assert "test_tag" not in ip_address.tags


def test_negate(platform_a: Platform) -> None:
    config = HConfig.from_text(platform_a)
    interface = config.add_child("interface Vlan2")
    interface.negate()
    assert interface.text == "no interface Vlan2"
    assert config.children.get("no interface Vlan2") is interface


def test_add_shallow_copy_of(platform_a: Platform) -> None:
    base_config = HConfig.from_text(platform_a)

    interface_a = HConfig.from_text(platform_a).add_child("interface Vlan2")
    interface_a.add_tags(frozenset(("ta", "tb")))
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
    ip_address_ab = HConfig.from_text(platform_a).add_children_deep(
        ("interface Vlan2", "ip address 192.168.2.1/24"),
    )
    ip_address_ab.add_tags(frozenset(("a", "b")))

    assert not ip_address_ab.line_inclusion_test(frozenset(("a",)), frozenset(("b",)))
    assert not ip_address_ab.line_inclusion_test(frozenset(), frozenset(("a",)))
    assert ip_address_ab.line_inclusion_test(frozenset(("a",)), frozenset())
    assert not ip_address_ab.line_inclusion_test(frozenset(), frozenset())


def test_add_child_with_empty_text() -> None:
    """Test that add_child raises ValueError when text is empty."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)

    with pytest.raises(ValueError, match="text was empty"):
        config.add_child("")


def test_add_child_duplicate_error() -> None:
    """Test DuplicateChildError when adding duplicate child."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    config.add_child("interface GigabitEthernet0/0")

    with pytest.raises(DuplicateChildError, match="Found a duplicate section"):
        config.add_child(
            "interface GigabitEthernet0/0",
            check_if_present=True,
            return_if_present=False,
        )


def test_add_child_return_if_present() -> None:
    """Test return_if_present option in add_child."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    child2 = config.add_child("interface GigabitEthernet0/0", return_if_present=True)

    assert id(child1) == id(child2)


def test_child_repr() -> None:
    """Test HConfigChild __repr__ method."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child = config.add_child("interface GigabitEthernet0/0")
    subchild = child.add_child("description test")
    repr_str = repr(child)

    assert "HConfigChild(HConfig, interface GigabitEthernet0/0)" in repr_str

    repr_str2 = repr(subchild)

    assert "HConfigChild(HConfigChild, description test)" in repr_str2


def test_child_ne() -> None:
    """Test HConfigChild __ne__ method."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    child2 = config.add_child("interface GigabitEthernet0/1")

    assert child1 != child2


def test_indented_text_with_comments() -> None:
    """Test indented_text with comments."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child = config.add_child("interface GigabitEthernet0/0")
    child.comments.add("test comment")
    child.comments.add("another comment")
    line = child.indented_text(style="with_comments")

    assert "!another comment, test comment" in line

    instance = Instance(
        id=1, comments=frozenset(["instance comment"]), tags=frozenset(["tag1"])
    )
    child.instances.append(instance)
    line_merged = child.indented_text(style="merged", tag="tag1")

    assert "1 instance" in line_merged
    assert "instance comment" in line_merged

    instance2 = Instance(id=2, comments=frozenset(), tags=frozenset(["tag1"]))
    child.instances.append(instance2)
    line_merged2 = child.indented_text(style="merged", tag="tag1")

    assert "2 instances" in line_merged2


def test_child_sectional_exit_no_exit_text() -> None:
    """Test sectional_exit when rule returns None."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child = config.add_child("hostname test")

    assert child.sectional_exit is None


def test_child_is_match_endswith() -> None:
    """Test is_match with endswith filter."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")

    assert interface.is_match(endswith="Ethernet0/0")
    assert not interface.is_match(endswith="Ethernet0/1")


def test_child_is_match_contains_single() -> None:
    """Test is_match with single contains filter."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")

    assert interface.is_match(contains="Gigabit")
    assert not interface.is_match(contains="FastEthernet")


def test_child_is_match_contains_tuple() -> None:
    """Test is_match with tuple contains filter."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")

    assert interface.is_match(contains=("Gigabit", "FastEthernet"))
    assert not interface.is_match(contains=("TenGigabit", "FastEthernet"))


def test_child_negate_default_strategy() -> None:
    """A DEFAULT-strategy negation rule rewrites to the default form (#220)."""
    platform = Platform.ARISTA_EOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface Ethernet1")
    logging_event = interface.add_child("logging event link-status")

    assert logging_event.negate().text == "default logging event link-status"


def test_child_remove_tags_leaf_iterable() -> None:
    """Test remove_tags on leaf with iterable."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    description.add_tags(frozenset(["tag1", "tag2", "tag3"]))
    description.remove_tags(["tag1", "tag2"])

    assert "tag1" not in description.tags
    assert "tag2" not in description.tags
    assert "tag3" in description.tags


def test_child_tags_setter_on_branch() -> None:
    """Test tags setter on branch node."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    interface.tags = frozenset(["production", "critical"])

    assert "production" in description.tags
    assert "critical" in description.tags


def test_child_is_idempotent_command_avoid() -> None:
    """Test is_idempotent_command with avoid rule."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    ip_address = interface.add_child("ip address 192.168.1.1 255.255.255.0")
    other_children: list[HConfigChild] = []
    result = ip_address.is_idempotent_command(other_children)

    assert isinstance(result, bool)


def test_child_is_idempotent_command_with_avoid_rule() -> None:
    """Test is_idempotent_command with avoid rule match."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    ip_access_group = interface.add_child("ip access-group test in")
    result = ip_access_group.is_idempotent_command([])

    assert isinstance(result, bool)


def test_child_overwrite_with_negate_else_branch() -> None:
    """Test overwrite_with when negated child doesn't exist."""
    platform = Platform.CISCO_IOS
    running_config = HConfig.from_text(platform)
    running_interface = running_config.add_child("interface GigabitEthernet0/0")
    running_interface.add_child("description old")
    generated_config = HConfig.from_text(platform)
    generated_interface = generated_config.add_child("interface GigabitEthernet0/0")
    generated_interface.add_child("description new")
    delta_config = HConfig.from_text(platform)
    running_interface.overwrite_with(generated_interface, delta_config, negate=True)
    delta_interface = delta_config.get_child(equals="interface GigabitEthernet0/0")

    assert delta_interface is not None


def test_child_overwrite_with_existing_negated() -> None:
    """Test overwrite_with when negated child exists in delta."""
    platform = Platform.CISCO_IOS
    running_config = HConfig.from_text(platform)
    running_interface = running_config.add_child("interface GigabitEthernet0/0")
    running_interface.add_child("description old")
    generated_config = HConfig.from_text(platform)
    generated_interface = generated_config.add_child("interface GigabitEthernet0/0")
    generated_interface.add_child("description new")
    delta_config = HConfig.from_text(platform)
    delta_config.add_child("interface GigabitEthernet0/0")
    running_interface.overwrite_with(generated_interface, delta_config, negate=True)
    delta_interface = delta_config.get_child(equals="interface GigabitEthernet0/0")

    assert delta_interface is not None


def test_child_remove_tags_branch() -> None:
    """Test remove_tags on branch node."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    description.add_tags("test_tag")
    interface.remove_tags("test_tag")

    assert "test_tag" not in description.tags


def test_child_add_children_deep() -> None:
    """Test add_children_deep method."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    result = interface.add_children_deep(
        ["ip access-group test in", "description test"]
    )

    assert result.text == "description test"
    assert result.depth == 3


def test_child_default_method() -> None:
    """Test _default method."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    description._default()  # ruff:ignore[private-member-access]  # pyright: ignore[reportPrivateUsage]

    assert description.text == "default description test"


def test_abstract_methods_coverage() -> None:
    """Test coverage of abstract method implementations."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    desc = interface.add_child("description test")

    assert interface.root is config
    assert desc.root is config

    assert interface.driver is not None
    assert config.driver is not None

    lineage = tuple(desc.lineage())
    assert len(lineage) == 2
    assert lineage[0] is interface

    assert config.depth == 0
    assert interface.depth == 1
    assert desc.depth == 2

    hash_value = hash(interface)
    assert isinstance(hash_value, int)

    children_list = list(config)
    assert len(children_list) == 1
    assert children_list[0] is interface


def test_get_child_deep_none() -> None:
    """Test get_child_deep returns None when no match."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    config.add_child("interface GigabitEthernet0/0")
    result = config.get_child_deep((MatchRule(equals="interface GigabitEthernet0/1"),))

    assert result is None


def test_child_eq_comparison() -> None:
    """Test HConfigChild __eq__ returns False for different text."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    child2 = config.add_child("interface GigabitEthernet0/1")

    assert child1 != child2

    config2 = HConfig.from_text(platform)
    child3 = config2.add_child("interface GigabitEthernet0/0")
    assert child1 == child3


def test_child_hash_consistency() -> None:
    """Test HConfigChild __hash__."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child = config.add_child("interface GigabitEthernet0/0")
    child.add_child("description test")
    hash1 = hash(child)
    hash2 = hash(child)

    assert hash1 == hash2


def test_with_tags_recursive() -> None:
    """Test _with_tags recursion."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.tags = frozenset(["production"])
    desc = interface.add_child("description test")
    desc.tags = frozenset(["production"])
    tagged_config = config.with_tags(frozenset(["production"]))

    assert tagged_config.get_child(equals="interface GigabitEthernet0/0") is not None

    tagged_interface = tagged_config.get_child(equals="interface GigabitEthernet0/0")

    assert tagged_interface is not None
    assert tagged_interface.get_child(equals="description test") is not None


def test_child_sectional_exit_with_exit_text() -> None:
    """Test sectional_exit when rule has exit_text."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("description test")
    exit_text = interface.sectional_exit

    assert exit_text == "exit"


def test_child_negate_swap_fallback() -> None:
    """A command matching no negation rule falls back to swap_negation (#220)."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")

    assert description.negate().text == "no description test"


def test_child_lt_comparison() -> None:
    """Test HConfigChild __lt__ for ordering."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    child2 = config.add_child("interface GigabitEthernet0/1")
    child1.order_weight = 100
    child2.order_weight = 50

    assert child2 < child1
    assert not child1 < child2  # pylint: disable=unneeded-not


def test_add_child_with_duplicates_allowed() -> None:
    """Test add_child when duplicates are allowed."""
    platform = Platform.CISCO_XR
    config = HConfig.from_text(platform)
    route_policy = config.add_child("route-policy test")
    child1 = route_policy.add_child("if destination in test then")
    child2 = route_policy.add_child("if destination in test then")

    assert id(child1) != id(child2)
    assert child1.text == child2.text


def test_get_children_with_duplicates() -> None:
    """Test get_children when duplicates are allowed."""
    platform = Platform.CISCO_XR
    config = HConfig.from_text(platform)
    route_policy = config.add_child("route-policy test")
    route_policy.add_child("if destination in test then")
    route_policy.add_child("if destination in test then")
    route_policy.add_child("if source in test then")
    children = tuple(route_policy.get_children(startswith="if destination"))

    assert len(children) == 2


def test_child_hash_eq_consistency_new_in_config() -> None:
    """Test that equal HConfigChild objects have equal hashes regardless of new_in_config.

    Validates the bug in issue #185: __hash__ includes new_in_config but __eq__ does not,
    violating the Python invariant that a == b implies hash(a) == hash(b).
    """
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    config2 = HConfig.from_text(platform)
    child2 = config2.add_child("interface GigabitEthernet0/0")

    child1.new_in_config = False
    child2.new_in_config = True

    # These two children compare as equal (same text, no tags, no children)
    assert child1 == child2
    # Python invariant: equal objects must have equal hashes
    assert hash(child1) == hash(child2)


def test_child_hash_eq_consistency_order_weight() -> None:
    """Test that equal HConfigChild objects have equal hashes regardless of order_weight.

    Validates the bug in issue #185: __hash__ includes order_weight but __eq__ does not,
    violating the Python invariant that a == b implies hash(a) == hash(b).
    """
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    config2 = HConfig.from_text(platform)
    child2 = config2.add_child("interface GigabitEthernet0/0")

    child1.order_weight = 0
    child2.order_weight = 100

    # These two children compare as equal (same text, no tags, no children)
    assert child1 == child2
    # Python invariant: equal objects must have equal hashes
    assert hash(child1) == hash(child2)


def test_child_hash_eq_consistency_tags() -> None:
    """Test that __hash__ and __eq__ agree on whether tags affect equality.

    Validates the bug in issue #185: __eq__ checks tags but __hash__ does not include
    tags, meaning two objects that compare unequal could have the same hash (not a
    correctness violation, but inconsistent) while also raising the question of whether
    tags should be part of the hash.
    """
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    config2 = HConfig.from_text(platform)
    child2 = config2.add_child("interface GigabitEthernet0/0")

    child1.tags = frozenset({"safe"})
    child2.tags = frozenset()

    # __eq__ considers tags, so these are unequal
    assert child1 != child2
    # Since they are unequal, their hashes should differ to avoid excessive collisions
    # (not strictly required by the invariant, but required for correctness in reverse:
    # if hash(a) != hash(b) then a != b must hold — currently tags are in __eq__ but
    # not __hash__, so unequal objects can share a hash, which means dict/set lookup
    # will fall back to __eq__ unexpectedly)
    assert hash(child1) != hash(child2)


def test_child_set_deduplication_with_new_in_config() -> None:
    """Test that equal HConfigChild objects are deduplicated correctly in sets.

    Validates the practical impact of issue #185: when new_in_config differs,
    two logically equal children occupy different set buckets, causing duplicates.
    """
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    config2 = HConfig.from_text(platform)
    child2 = config2.add_child("interface GigabitEthernet0/0")

    child1.new_in_config = False
    child2.new_in_config = True

    assert child1 == child2
    # Equal objects must collapse to one entry in a set
    assert len({child1, child2}) == 1


def test_child_dict_key_lookup_with_order_weight() -> None:
    """Test that HConfigChild objects with differing order_weight work as dict keys.

    Validates the practical impact of issue #185: when order_weight differs, a
    logically equal child cannot be found as a dict key.
    """
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    config2 = HConfig.from_text(platform)
    child2 = config2.add_child("interface GigabitEthernet0/0")

    child1.order_weight = 0
    child2.order_weight = 100

    assert child1 == child2
    lookup: dict[HConfigChild, str] = {child1: "found"}
    # child2 is equal to child1, so it must find the same dict entry
    assert lookup[child2] == "found"


def test_indented_text_style_literal_values() -> None:
    """Test that indented_text accepts each valid TextStyle literal value."""
    platform = Platform.CISCO_IOS
    config = HConfig.from_text(platform)
    child = config.add_child("interface GigabitEthernet0/0")
    child.comments.add("a comment")

    # without_comments: should NOT include the comment
    result_without = child.indented_text(style="without_comments")
    assert "interface GigabitEthernet0/0" in result_without
    assert "!" not in result_without

    # with_comments: should include the comment
    result_with = child.indented_text(style="with_comments")
    assert "interface GigabitEthernet0/0" in result_with
    assert "!a comment" in result_with

    # merged: should include instance count info
    instance = Instance(
        id=1, comments=frozenset(["inst comment"]), tags=frozenset(["tag1"])
    )
    child.instances.append(instance)
    result_merged = child.indented_text(style="merged")
    assert "1 instance" in result_merged
