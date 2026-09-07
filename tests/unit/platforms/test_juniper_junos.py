from hier_config import HConfig
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.juniper_junos.driver import HConfigDriverJuniperJUNOS


def test_negation_delete_to_set() -> None:
    """Negating a `delete` command yields the matching `set` command."""
    root = HConfig.from_text(Platform.JUNIPER_JUNOS)
    child = HConfigChild(root, "delete vlans test_vlan vlan-id 100")

    assert child.negate().text == "set vlans test_vlan vlan-id 100"


def test_negation_set_to_delete() -> None:
    """Negating a `set` command yields the matching `delete` command."""
    root = HConfig.from_text(Platform.JUNIPER_JUNOS)
    child = HConfigChild(root, "set vlans test_vlan vlan-id 100")

    assert child.negate().text == "delete vlans test_vlan vlan-id 100"


def test_negation_without_a_prefix_is_a_no_op() -> None:
    """Text carrying neither prefix has nothing to swap."""
    root = HConfig.from_text(Platform.JUNIPER_JUNOS)
    child = HConfigChild(root, "vlans test_vlan vlan-id 100")

    assert child.negate().text == "vlans test_vlan vlan-id 100"


def test_prefixes() -> None:
    """The driver advertises the prefixes the core negates with."""
    driver = HConfigDriverJuniperJUNOS()

    assert driver.declaration_prefix == "set "
    assert driver.negation_prefix == "delete "
