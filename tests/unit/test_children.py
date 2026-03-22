"""Unit tests for HConfigChildren."""

from hier_config import get_hconfig
from hier_config.models import Platform


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
