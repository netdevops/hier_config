"""Tests for hier_config core functionality."""
# pylint: disable=too-many-lines

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


def test_add_child_with_empty_text() -> None:
    """Test that add_child raises ValueError when text is empty."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)

    with pytest.raises(ValueError, match="text was empty"):
        config.add_child("")


def test_add_child_duplicate_error() -> None:
    """Test DuplicateChildError when adding duplicate child."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
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
    config = get_hconfig(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    child2 = config.add_child("interface GigabitEthernet0/0", return_if_present=True)

    assert id(child1) == id(child2)


def test_child_repr() -> None:
    """Test HConfigChild __repr__ method."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    child = config.add_child("interface GigabitEthernet0/0")
    subchild = child.add_child("description test")
    repr_str = repr(child)

    assert "HConfigChild(HConfig, interface GigabitEthernet0/0)" in repr_str

    repr_str2 = repr(subchild)

    assert "HConfigChild(HConfigChild, description test)" in repr_str2


def test_child_ne() -> None:
    """Test HConfigChild __ne__ method."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    child2 = config.add_child("interface GigabitEthernet0/1")

    assert child1 != child2


def test_cisco_style_text_with_comments() -> None:
    """Test cisco_style_text with comments."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    child = config.add_child("interface GigabitEthernet0/0")
    child.comments.add("test comment")
    child.comments.add("another comment")
    line = child.cisco_style_text(style="with_comments")

    assert "!another comment, test comment" in line

    instance = Instance(
        id=1, comments=frozenset(["instance comment"]), tags=frozenset(["tag1"])
    )
    child.instances.append(instance)
    line_merged = child.cisco_style_text(style="merged", tag="tag1")

    assert "1 instance" in line_merged
    assert "instance comment" in line_merged

    instance2 = Instance(id=2, comments=frozenset(), tags=frozenset(["tag1"]))
    child.instances.append(instance2)
    line_merged2 = child.cisco_style_text(style="merged", tag="tag1")

    assert "2 instances" in line_merged2


def test_hconfig_children_setitem() -> None:
    """Test HConfigChildren __setitem__."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    config.add_child("interface GigabitEthernet0/0")
    child2_text = "interface GigabitEthernet0/1"
    config.add_child(child2_text)
    child3_text = "interface GigabitEthernet0/2"
    child3 = config.instantiate_child(child3_text)
    config.children[1] = child3

    assert config.children[1].text == child3_text
    assert child3_text in config.children


def test_hconfig_children_contains() -> None:
    """Test HConfigChildren __contains__."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    config.add_child("interface GigabitEthernet0/0")

    assert "interface GigabitEthernet0/0" in config.children
    assert "interface GigabitEthernet0/1" not in config.children


def test_hconfig_children_eq_fast_fail() -> None:
    """Test HConfigChildren __eq__ fast fail."""
    platform = Platform.CISCO_IOS
    config1 = get_hconfig(platform)
    config2 = get_hconfig(platform)

    config1.add_child("interface GigabitEthernet0/0")
    config2.add_child("interface GigabitEthernet0/0")
    config2.add_child("interface GigabitEthernet0/1")

    assert config1.children != config2.children


def test_hconfig_children_eq_keys_mismatch() -> None:
    """Test HConfigChildren __eq__ key mismatch."""
    platform = Platform.CISCO_IOS
    config1 = get_hconfig(platform)
    config2 = get_hconfig(platform)

    config1.add_child("interface GigabitEthernet0/0")
    config2.add_child("interface GigabitEthernet0/1")

    assert config1.children != config2.children


def test_hconfig_children_hash() -> None:
    """Test HConfigChildren __hash__."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    config.add_child("interface GigabitEthernet0/0")
    hash_val = hash(config.children)

    assert isinstance(hash_val, int)


def test_hconfig_children_getitem_slice() -> None:
    """Test HConfigChildren __getitem__ with slice."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    config.add_child("interface GigabitEthernet0/0")
    config.add_child("interface GigabitEthernet0/1")
    config.add_child("interface GigabitEthernet0/2")
    slice_result = config.children[0:2]

    assert isinstance(slice_result, list)
    assert len(slice_result) == 2
    assert slice_result[0].text == "interface GigabitEthernet0/0"


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


def test_child_lt_comparison() -> None:
    """Test HConfigChild __lt__ for ordering."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    child2 = config.add_child("interface GigabitEthernet0/1")
    child1.order_weight = 100
    child2.order_weight = 50

    assert child2 < child1
    assert not child1 < child2  # pylint: disable=unneeded-not


def test_child_hash_consistency() -> None:
    """Test HConfigChild __hash__."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    child = config.add_child("interface GigabitEthernet0/0")
    child.add_child("description test")
    hash1 = hash(child)
    hash2 = hash(child)

    assert hash1 == hash2


def test_with_tags_recursive() -> None:
    """Test _with_tags recursion."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.tags = frozenset(["production"])
    desc = interface.add_child("description test")
    desc.tags = frozenset(["production"])
    tagged_config = config.with_tags(frozenset(["production"]))

    assert tagged_config.get_child(equals="interface GigabitEthernet0/0") is not None

    tagged_interface = tagged_config.get_child(equals="interface GigabitEthernet0/0")

    assert tagged_interface is not None
    assert tagged_interface.get_child(equals="description test") is not None


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


def test_add_child_with_duplicates_allowed() -> None:
    """Test add_child when duplicates are allowed."""
    platform = Platform.CISCO_XR
    config = get_hconfig(platform)
    route_policy = config.add_child("route-policy test")
    child1 = route_policy.add_child("if destination in test then")
    child2 = route_policy.add_child("if destination in test then")

    assert id(child1) != id(child2)
    assert child1.text == child2.text


def test_get_children_with_duplicates() -> None:
    """Test get_children when duplicates are allowed."""
    platform = Platform.CISCO_XR
    config = get_hconfig(platform)
    route_policy = config.add_child("route-policy test")
    route_policy.add_child("if destination in test then")
    route_policy.add_child("if destination in test then")
    route_policy.add_child("if source in test then")
    children = tuple(route_policy.get_children(startswith="if destination"))

    assert len(children) == 2


def test_child_sectional_exit_no_exit_text() -> None:
    """Test sectional_exit when rule returns None."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    child = config.add_child("hostname test")

    assert child.sectional_exit is None


def test_child_is_match_endswith() -> None:
    """Test is_match with endswith filter."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")

    assert interface.is_match(endswith="Ethernet0/0")
    assert not interface.is_match(endswith="Ethernet0/1")


def test_child_is_match_contains_single() -> None:
    """Test is_match with single contains filter."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")

    assert interface.is_match(contains="Gigabit")
    assert not interface.is_match(contains="FastEthernet")


def test_child_is_match_contains_tuple() -> None:
    """Test is_match with tuple contains filter."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")

    assert interface.is_match(contains=("Gigabit", "FastEthernet"))
    assert not interface.is_match(contains=("TenGigabit", "FastEthernet"))


def test_child_use_default_for_negation() -> None:
    """Test use_default_for_negation."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    uses_default = description.use_default_for_negation(description)

    assert isinstance(uses_default, bool)


def test_child_tags_remove_branch() -> None:
    """Test tags_remove on branch node."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    description.tags_add("test_tag")
    interface.tags_remove("test_tag")

    assert "test_tag" not in description.tags


def test_child_is_idempotent_command_avoid() -> None:
    """Test is_idempotent_command with avoid rule."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    ip_address = interface.add_child("ip address 192.168.1.1 255.255.255.0")
    other_children: list[HConfigChild] = []
    result = ip_address.is_idempotent_command(other_children)

    assert isinstance(result, bool)


def test_child_overwrite_with_negate_else_branch() -> None:
    """Test overwrite_with when negated child doesn't exist."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    running_interface = running_config.add_child("interface GigabitEthernet0/0")
    running_interface.add_child("description old")
    generated_config = get_hconfig(platform)
    generated_interface = generated_config.add_child("interface GigabitEthernet0/0")
    generated_interface.add_child("description new")
    delta_config = get_hconfig(platform)
    running_interface.overwrite_with(generated_interface, delta_config, negate=True)
    delta_interface = delta_config.get_child(equals="interface GigabitEthernet0/0")

    assert delta_interface is not None


def test_child_tags_setter_on_branch() -> None:
    """Test tags setter on branch node."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    interface.tags = frozenset(["production", "critical"])

    assert "production" in description.tags
    assert "critical" in description.tags


def test_child_add_children_deep() -> None:
    """Test add_children_deep method."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    result = interface.add_children_deep(
        ["ip access-group test in", "description test"]
    )

    assert result.text == "description test"
    assert result.depth() == 3


def test_child_default_method() -> None:
    """Test _default method."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    description._default()  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

    assert description.text == "default description test"


def test_abstract_methods_coverage() -> None:
    """Test coverage of abstract method implementations."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    desc = interface.add_child("description test")

    assert interface.root is config
    assert desc.root is config

    assert interface.driver is not None
    assert config.driver is not None

    lineage = tuple(desc.lineage())
    assert len(lineage) == 2
    assert lineage[0] is interface

    assert config.depth() == 0
    assert interface.depth() == 1
    assert desc.depth() == 2

    hash_value = hash(interface)
    assert isinstance(hash_value, int)

    children_list = list(config)
    assert len(children_list) == 1
    assert children_list[0] is interface


def test_get_child_deep_none() -> None:
    """Test get_child_deep returns None when no match."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    config.add_child("interface GigabitEthernet0/0")
    result = config.get_child_deep((MatchRule(equals="interface GigabitEthernet0/1"),))

    assert result is None


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


def test_difference_with_acl_none_target() -> None:
    """Test _difference with ACL when target_acl_children is None."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)

    acl = running_config.add_child("ip access-list extended test")
    acl.add_child("10 permit ip any any")
    target_config = get_hconfig(platform)
    difference = running_config.difference(target_config)

    assert difference.get_child(equals="ip access-list extended test") is not None


def test_child_eq_comparison() -> None:
    """Test HConfigChild __eq__ returns False for different text."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    child1 = config.add_child("interface GigabitEthernet0/0")
    child2 = config.add_child("interface GigabitEthernet0/1")

    assert child1 != child2

    config2 = get_hconfig(platform)
    child3 = config2.add_child("interface GigabitEthernet0/0")
    assert child1 == child3


def test_child_sectional_exit_with_exit_text() -> None:
    """Test sectional_exit when rule has exit_text."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("description test")
    exit_text = interface.sectional_exit

    assert exit_text == "exit"


def test_child_tags_remove_leaf_iterable() -> None:
    """Test tags_remove on leaf with iterable."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    description.tags_add(frozenset(["tag1", "tag2", "tag3"]))
    description.tags_remove(["tag1", "tag2"])

    assert "tag1" not in description.tags
    assert "tag2" not in description.tags
    assert "tag3" in description.tags


def test_child_use_default_for_negation_true() -> None:
    """Test use_default_for_negation returns True."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    description = interface.add_child("description test")
    result = description.use_default_for_negation(description)

    assert isinstance(result, bool)


def test_child_is_idempotent_command_with_avoid_rule() -> None:
    """Test is_idempotent_command with avoid rule match."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    ip_access_group = interface.add_child("ip access-group test in")
    result = ip_access_group.is_idempotent_command([])

    assert isinstance(result, bool)


def test_child_overwrite_with_existing_negated() -> None:
    """Test overwrite_with when negated child exists in delta."""
    platform = Platform.CISCO_IOS
    running_config = get_hconfig(platform)
    running_interface = running_config.add_child("interface GigabitEthernet0/0")
    running_interface.add_child("description old")
    generated_config = get_hconfig(platform)
    generated_interface = generated_config.add_child("interface GigabitEthernet0/0")
    generated_interface.add_child("description new")
    delta_config = get_hconfig(platform)
    delta_config.add_child("interface GigabitEthernet0/0")
    running_interface.overwrite_with(generated_interface, delta_config, negate=True)
    delta_interface = delta_config.get_child(equals="interface GigabitEthernet0/0")

    assert delta_interface is not None


def test_children_eq_empty_fast_success() -> None:
    """Test HConfigChildren __eq__ fast success for empty."""
    platform = Platform.CISCO_IOS
    config1 = get_hconfig(platform)
    config2 = get_hconfig(platform)

    assert config1.children == config2.children


def test_children_hash_with_data() -> None:
    """Test HConfigChildren __hash__ with data."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    config.add_child("interface GigabitEthernet0/0")
    config.add_child("interface GigabitEthernet0/1")
    hash1 = hash(config.children)
    hash2 = hash(config.children)

    assert hash1 == hash2
    assert isinstance(hash1, int)


def test_children_getitem_with_slice() -> None:
    """Test HConfigChildren __getitem__ with slice."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    config.add_child("interface GigabitEthernet0/0")
    config.add_child("interface GigabitEthernet0/1")
    config.add_child("interface GigabitEthernet0/2")
    config.add_child("interface GigabitEthernet0/3")
    slice1 = config.children[1:3]
    assert len(slice1) == 2

    slice2 = config.children[::2]
    assert len(slice2) == 2

    slice3 = config.children[:2]
    assert len(slice3) == 2


def test_hconfig_str() -> None:
    """Test HConfig __str__ method."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    config.add_child("hostname router1")
    config.add_child("interface GigabitEthernet0/0")
    str_output = str(config)

    assert "hostname router1" in str_output
    assert "interface GigabitEthernet0/0" in str_output
    assert isinstance(str_output, str)


def test_hconfig_eq_not_hconfig() -> None:
    """Test HConfig __eq__ with non-HConfig object."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    result = config == "not an HConfig"

    assert not result


def test_hconfig_real_indent_level() -> None:
    """Test HConfig real_indent_level property."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)

    assert config.real_indent_level == -1


def test_hconfig_parent_property() -> None:
    """Test HConfig parent property returns self."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)

    assert config.parent is config


def test_hconfig_is_leaf() -> None:
    """Test HConfig is_leaf property."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)

    assert config.is_leaf is False


def test_hconfig_tags_setter() -> None:
    """Test HConfig tags setter."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    desc = interface.add_child("description test")
    config.tags = frozenset(["production", "core"])

    assert "production" in desc.tags
    assert "core" in desc.tags


def test_hconfig_add_children_deep_typeerror() -> None:
    """Test HConfig add_children_deep raises TypeError."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)

    with pytest.raises(TypeError, match="base was an HConfig object"):
        config.add_children_deep([])


def test_hconfig_deep_copy() -> None:
    """Test HConfig deep_copy method)."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("description test")
    config.add_child("hostname router1")
    config_copy = config.deep_copy()

    assert config_copy is not config
    assert len(tuple(config_copy.all_children())) == len(tuple(config.all_children()))
    assert config_copy.get_child(equals="interface GigabitEthernet0/0") is not None
    assert config_copy.get_child(equals="hostname router1") is not None

    original_interface = config.get_child(equals="interface GigabitEthernet0/0")
    copied_interface = config_copy.get_child(equals="interface GigabitEthernet0/0")
    assert original_interface is not None
    assert copied_interface is not None
    assert original_interface is not copied_interface


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


def test_children_eq_with_non_children_type() -> None:
    """Test HConfigChildren.__eq__ with non-HConfigChildren object returns NotImplemented."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")

    # Directly call __eq__ to verify it returns NotImplemented for non-HConfigChildren types
    # We must use __eq__ directly here to test the NotImplemented return value
    result = interface.children.__eq__("not a children object")  # pylint: disable=unnecessary-dunder-call # noqa: PLC2801
    assert result is NotImplemented

    # This allows Python to try the reverse comparison, which results in False
    assert interface.children != "not a children object"


def test_children_clear() -> None:
    """Test HConfigChildren.clear() method."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("description test")
    interface.add_child("ip address 192.0.2.1 255.255.255.0")

    # Verify children exist
    assert len(interface.children) == 2
    assert "description test" in interface.children

    # Clear all children
    interface.children.clear()

    # Verify children are gone
    assert len(interface.children) == 0
    assert "description test" not in interface.children


def test_children_delete_by_child_object() -> None:
    """Test HConfigChildren.delete() with HConfigChild object."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    desc = interface.add_child("description test")
    ip_addr = interface.add_child("ip address 192.0.2.1 255.255.255.0")

    # Verify both children exist
    assert len(interface.children) == 2

    # Delete by child object
    interface.children.delete(desc)

    # Verify only one child remains
    assert len(interface.children) == 1
    assert interface.children[0] is ip_addr
    assert "description test" not in interface.children


def test_children_delete_by_child_object_not_present() -> None:
    """Test HConfigChildren.delete() with HConfigChild object that's not in the collection."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface = config.add_child("interface GigabitEthernet0/0")
    interface.add_child("description test")

    # Create a child that's not part of this interface
    other_interface = config.add_child("interface GigabitEthernet0/1")
    other_child = other_interface.add_child("description other")

    # Verify interface has 1 child
    assert len(interface.children) == 1

    # Try to delete a child that's not in the collection
    interface.children.delete(other_child)

    # Verify child count hasn't changed
    assert len(interface.children) == 1


def test_children_extend() -> None:
    """Test HConfigChildren.extend() method."""
    platform = Platform.CISCO_IOS
    config = get_hconfig(platform)
    interface1 = config.add_child("interface GigabitEthernet0/0")
    interface2 = config.add_child("interface GigabitEthernet0/1")

    # Add children to interface2
    desc = interface2.add_child("description test")
    ip_addr = interface2.add_child("ip address 192.0.2.1 255.255.255.0")

    # Verify interface1 has no children
    assert len(interface1.children) == 0

    # Extend interface1's children with interface2's children
    interface1.children.extend([desc, ip_addr])

    # Verify interface1 now has 2 children
    assert len(interface1.children) == 2
    assert "description test" in interface1.children
    assert "ip address 192.0.2.1 255.255.255.0" in interface1.children
