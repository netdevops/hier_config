from hier_config import HConfig
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.nokia_srl.driver import HConfigDriverNokiaSRL


def test_negation_delete_to_set() -> None:
    """Negating a `delete` command yields the matching `set` command."""
    root = HConfig.from_text(Platform.NOKIA_SRL)
    child = HConfigChild(
        root, "delete interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )

    assert (
        child.negate().text
        == "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )


def test_negation_set_to_delete() -> None:
    """Negating a `set` command yields the matching `delete` command."""
    root = HConfig.from_text(Platform.NOKIA_SRL)
    child = HConfigChild(
        root, "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )

    assert (
        child.negate().text
        == "delete interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )


def test_negation_without_a_prefix_is_a_no_op() -> None:
    """Text carrying neither prefix has nothing to swap."""
    root = HConfig.from_text(Platform.NOKIA_SRL)
    child = HConfigChild(
        root, "interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )

    assert (
        child.negate().text
        == "interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    )


def test_prefixes() -> None:
    """The driver advertises the prefixes the core negates with."""
    driver = HConfigDriverNokiaSRL()

    assert driver.declaration_prefix == "set "
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
