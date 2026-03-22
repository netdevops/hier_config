from hier_config import get_hconfig
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.vyos.driver import HConfigDriverVYOS


def test_swap_negation_delete_to_set() -> None:
    """Test swapping from 'delete' to 'set' prefix (covers lines 9-11)."""
    platform = Platform.VYOS
    driver = HConfigDriverVYOS()
    root = get_hconfig(platform)

    # Create a child with 'delete' prefix
    child = HConfigChild(root, "delete interfaces ethernet eth0 address 192.168.1.1/24")

    # Swap negation should convert to 'set'
    result = driver.swap_negation(child)

    assert result.text == "set interfaces ethernet eth0 address 192.168.1.1/24"
    assert result.text.startswith("set ")


def test_swap_negation_set_to_delete() -> None:
    """Test swapping from 'set' to 'delete' prefix (covers lines 10, 12)."""
    platform = Platform.VYOS
    driver = HConfigDriverVYOS()
    root = get_hconfig(platform)

    # Create a child with 'set' prefix
    child = HConfigChild(root, "set interfaces ethernet eth0 address 192.168.1.1/24")

    # Swap negation should convert to 'delete'
    result = driver.swap_negation(child)

    assert result.text == "delete interfaces ethernet eth0 address 192.168.1.1/24"
    assert result.text.startswith("delete ")


def test_swap_negation_no_prefix() -> None:
    """Test swap_negation behavior when text has neither prefix (covers VyOS-specific behavior)."""
    platform = Platform.VYOS
    driver = HConfigDriverVYOS()
    root = get_hconfig(platform)

    # Create a child without proper prefix
    child = HConfigChild(root, "interfaces ethernet eth0 address 192.168.1.1/24")
    original_text = child.text

    # VyOS driver doesn't raise an error, it just returns the child unchanged
    result = driver.swap_negation(child)

    # Text should remain unchanged since neither if/elif matched
    assert result.text == original_text


def test_declaration_prefix() -> None:
    """Test declaration_prefix property (covers line 18)."""
    driver = HConfigDriverVYOS()
    assert driver.declaration_prefix == "set "


def test_negation_prefix() -> None:
    """Test negation_prefix property (covers line 22)."""
    driver = HConfigDriverVYOS()
    assert driver.negation_prefix == "delete "


def test_config_preprocessor() -> None:
    """Test config_preprocessor with hierarchical VyOS config (covers line 26)."""
    hierarchical_config = """interfaces {
    ethernet eth0 {
        address 192.168.1.1/24
        description "WAN Interface"
    }
}
system {
    host-name vyos-router
}"""

    result = HConfigDriverVYOS.config_preprocessor(hierarchical_config)

    # Should convert to set commands
    assert "set interfaces ethernet eth0 address 192.168.1.1/24" in result
    assert "set interfaces ethernet eth0 description" in result
    assert "set system host-name vyos-router" in result
