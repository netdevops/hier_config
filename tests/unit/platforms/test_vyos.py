from hier_config import HConfig
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.vyos.driver import HConfigDriverVYOS


def test_negation_delete_to_set() -> None:
    """Negating a `delete` command yields the matching `set` command."""
    root = HConfig.from_text(Platform.VYOS)
    child = HConfigChild(root, "delete system host-name router1")

    assert child.negate().text == "set system host-name router1"


def test_negation_set_to_delete() -> None:
    """Negating a `set` command yields the matching `delete` command."""
    root = HConfig.from_text(Platform.VYOS)
    child = HConfigChild(root, "set system host-name router1")

    assert child.negate().text == "delete system host-name router1"


def test_negation_without_a_prefix_is_a_no_op() -> None:
    """Text carrying neither prefix has nothing to swap."""
    root = HConfig.from_text(Platform.VYOS)
    child = HConfigChild(root, "system host-name router1")

    assert child.negate().text == "system host-name router1"


def test_prefixes() -> None:
    """The driver advertises the prefixes the core negates with."""
    driver = HConfigDriverVYOS()

    assert driver.declaration_prefix == "set "
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
