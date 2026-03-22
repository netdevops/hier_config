import pytest

from hier_config.child import HConfigChild
from hier_config.constructors import get_hconfig
from hier_config.models import Platform
from hier_config.platforms.juniper_junos.driver import HConfigDriverJuniperJUNOS


def test_swap_negation_delete_to_set() -> None:
    """Test swapping from 'delete' to 'set' prefix."""
    platform = Platform.JUNIPER_JUNOS
    driver = HConfigDriverJuniperJUNOS()
    root = get_hconfig(platform)
    child = HConfigChild(root, "delete vlans test_vlan vlan-id 100")
    result = driver.swap_negation(child)
    assert result.text == "set vlans test_vlan vlan-id 100"
    assert result.text.startswith("set ")


def test_swap_negation_set_to_delete() -> None:
    """Test swapping from 'set' to 'delete' prefix."""
    platform = Platform.JUNIPER_JUNOS
    driver = HConfigDriverJuniperJUNOS()
    root = get_hconfig(platform)
    child = HConfigChild(root, "set vlans test_vlan vlan-id 100")
    result = driver.swap_negation(child)
    assert result.text == "delete vlans test_vlan vlan-id 100"
    assert result.text.startswith("delete ")


def test_swap_negation_invalid_prefix() -> None:
    """Test ValueError when text has neither 'set' nor 'delete' prefix."""
    platform = Platform.JUNIPER_JUNOS
    driver = HConfigDriverJuniperJUNOS()
    root = get_hconfig(platform)
    child = HConfigChild(root, "vlans test_vlan vlan-id 100")
    with pytest.raises(ValueError, match="did not start with") as exc_info:
        driver.swap_negation(child)
    assert "did not start with" in str(exc_info.value)
    assert "delete " in str(exc_info.value)
    assert "set " in str(exc_info.value)
