from hier_config import get_hconfig
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.nokia_srl.driver import HConfigDriverNokiaSRL


def test_swap_negation_delete_to_set() -> None:
    """Test swapping from 'delete' to 'set' prefix."""
    platform = Platform.NOKIA_SRL
    driver = HConfigDriverNokiaSRL()
    root = get_hconfig(platform)

    child = HConfigChild(
        root, "delete interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    result = driver.swap_negation(child)

    assert (
        result.text
        == "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    assert result.text.startswith("set ")


def test_swap_negation_set_to_delete() -> None:
    """Test swapping from 'set' to 'delete' prefix."""
    platform = Platform.NOKIA_SRL
    driver = HConfigDriverNokiaSRL()
    root = get_hconfig(platform)

    child = HConfigChild(
        root, "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    result = driver.swap_negation(child)

    assert (
        result.text
        == "delete interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    assert result.text.startswith("delete ")


def test_swap_negation_no_prefix() -> None:
    """Test swap_negation when text has neither prefix."""
    driver = HConfigDriverNokiaSRL()
    root = get_hconfig(Platform.NOKIA_SRL)

    child = HConfigChild(
        root, "interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )
    original_text = child.text

    result = driver.swap_negation(child)
    assert result.text == original_text


def test_declaration_prefix() -> None:
    """Test declaration_prefix property."""
    driver = HConfigDriverNokiaSRL()
    assert driver.declaration_prefix == "set "


def test_negation_prefix() -> None:
    """Test negation_prefix property."""
    driver = HConfigDriverNokiaSRL()
    assert driver.negation_prefix == "delete "


def test_config_preprocessor() -> None:
    """Test config_preprocessor with hierarchical SRL config."""
    hierarchical_config = """interface {
    ethernet-1/1 {
        subinterface 0 {
            ipv4 {
                admin-state enable
                address 192.168.1.1/24
            }
        }
    }
}
system {
    name {
        host-name srl-router
    }
}"""

    result = HConfigDriverNokiaSRL.config_preprocessor(hierarchical_config)

    assert "set interface ethernet-1/1 subinterface 0 ipv4 admin-state enable" in result
    assert (
        "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
        in result
    )
    assert "set system name host-name srl-router" in result
