from hier_config import get_hconfig_fast_load
from hier_config.child import HConfigChild
from hier_config.constructors import get_hconfig
from hier_config.models import Platform
from hier_config.platforms.fortinet_fortios.driver import HConfigDriverFortinetFortiOS


def test_swap_negation() -> None:
    platform = Platform.FORTINET_FORTIOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "config system interface",
            "  edit port1",
            "    set description 'Port 1'",
            "    set status down",
            "  next",
            "end",
            "config system dns",
            "  set primary 192.0.2.1",
            "  set secondary 192.0.2.2",
            "end",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "config system interface",
            "  edit port1",
            "    set status down",
            "  next",
            "end",
            "config system dns",
            "  set primary 192.0.2.1",
            "end",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "config system interface",
        "  edit port1",
        "    unset description",
        "    next",
        "  end",
        "config system dns",
        "  unset secondary",
        "  end",
    )


def test_idempotent_for() -> None:
    platform = Platform.FORTINET_FORTIOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "config system interface",
            "  edit port1",
            "    set description 'Old Description'",
            "    set status up",
            "  next",
            "end",
            "config system dns",
            "  set primary 192.0.2.1",
            "  set secondary 192.0.2.2",
            "end",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "config system interface",
            "  edit port1",
            "    set description 'New Description'",
            "    set status up",
            "  next",
            "end",
            "config system dns",
            "  set primary 192.0.2.1",
            "  set secondary 192.0.2.3",
            "end",
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "config system interface",
        "  edit port1",
        "    set description 'New Description'",
        "    next",
        "  end",
        "config system dns",
        "  set secondary 192.0.2.3",
        "  end",
    )


def test_future() -> None:
    platform = Platform.FORTINET_FORTIOS
    running_config = get_hconfig(platform)
    remediation_config = get_hconfig_fast_load(
        platform,
        (
            "config system interface",
            "  edit port2",
            "    set description 'Port 2'",
            "    set status up",
            "  next",
            "end",
        ),
    )
    future_config = running_config.future(remediation_config)
    assert not tuple(remediation_config.unified_diff(future_config))


def test_swap_negation_direct() -> None:
    """Test swap_negation method directly to cover set-to-unset conversion (covers line 45)."""
    driver = HConfigDriverFortinetFortiOS()
    config = get_hconfig(Platform.FORTINET_FORTIOS)
    child = HConfigChild(config, "set description 'test value'")
    result = driver.swap_negation(child)
    assert result.text == "unset description"

    child2 = HConfigChild(config, "unset description")
    result2 = driver.swap_negation(child2)

    assert result2.text == "set description"
