from hier_config.child import HConfigChild
from hier_config.constructors import get_hconfig
from hier_config.models import Platform
from hier_config.platforms.fortinet_fortios.driver import HConfigDriverFortinetFortiOS


def test_swap_negation_direct() -> None:
    """Test swap_negation method directly to cover set-to-unset conversion."""
    driver = HConfigDriverFortinetFortiOS()
    config = get_hconfig(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, "set description 'test value'")
    result = driver.swap_negation(child)
    assert result.text == "unset description"

    child2 = HConfigChild(config, "unset description")
    result2 = driver.swap_negation(child2)

    assert result2.text == "set description"
