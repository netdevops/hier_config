"""Tests for HConfig root node behavior."""

import tempfile
from pathlib import Path

import pytest

from hier_config import (
    get_hconfig,
    get_hconfig_driver,
    get_hconfig_fast_load,
    get_hconfig_from_dump,
)
from hier_config.models import Platform


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
