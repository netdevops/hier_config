from hier_config import HConfig
from hier_config.child import HConfigChild
from hier_config.models import Platform
from hier_config.platforms.fortinet_fortios.driver import HConfigDriverFortinetFortiOS


def test_swap_negation_direct() -> None:
    """Test swap_negation method directly to cover set-to-unset conversion."""
    driver = HConfigDriverFortinetFortiOS()
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, "set description 'test value'")
    result = driver.swap_negation(child)
    assert result.text == "unset description"

    child2 = HConfigChild(config, "unset description")
    result2 = driver.swap_negation(child2)

    assert result2.text == "set description"


def test_swap_negation_drops_parameters_intentionally() -> None:
    """FortiOS negation resets an attribute to its default via `unset <attribute>`.

    The value is never part of the unset command, so parameters after the
    attribute name must be dropped (#225).
    """
    driver = HConfigDriverFortinetFortiOS()
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, 'set description "Port 1"')
    result = driver.swap_negation(child)

    assert result.text == "unset description"


def test_swap_negation_bare_set_is_unchanged() -> None:
    """A bare `set` command with no attribute has nothing to negate (#225)."""
    driver = HConfigDriverFortinetFortiOS()
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, "set")
    result = driver.swap_negation(child)

    assert result.text == "set"


def test_idempotent_for_matches_same_attribute() -> None:
    """Two `set` commands for the same attribute are idempotent (#225)."""
    driver = HConfigDriverFortinetFortiOS()
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, "set primary 192.0.2.1")
    other = HConfigChild(config, "set primary 192.0.2.3")

    assert driver.idempotent_for(child, [other]) is other


def test_idempotent_for_different_attribute_returns_none() -> None:
    """`set` commands for different attributes are not idempotent (#225)."""
    driver = HConfigDriverFortinetFortiOS()
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, "set primary 192.0.2.1")
    other = HConfigChild(config, "set secondary 192.0.2.3")

    assert driver.idempotent_for(child, [other]) is None


def test_idempotent_for_single_word_commands_do_not_crash() -> None:
    """Single-word commands must not raise IndexError in idempotent_for (#225)."""
    driver = HConfigDriverFortinetFortiOS()
    config = HConfig.from_text(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, "set")
    other = HConfigChild(config, "set")

    assert driver.idempotent_for(child, [other]) is None
