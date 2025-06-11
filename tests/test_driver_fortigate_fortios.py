from hier_config import get_hconfig_fast_load
from hier_config.constructors import get_hconfig
from hier_config.models import Platform


def test_negate_with() -> None:
    platform = Platform.FORTIGATE_FORTIOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "config system interface",
            "  edit port1",
            "    set description 'Port 1'",
            "    set status down",
            "  next",
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
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "config system interface",
        "  edit port1",
        "    unset description",
        "    next",
        "  end",
    )


def test_idempotent_for() -> None:
    platform = Platform.FORTIGATE_FORTIOS
    running_config = get_hconfig_fast_load(
        platform,
        (
            "config system interface",
            "  edit port1",
            "    set description 'Old Description'",
            "    set status up",
            "  next",
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
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple(sectional_exiting=True) == (
        "config system interface",
        "  edit port1",
        "    set description 'New Description'",
        "    next",
        "  end",
    )


def test_future() -> None:
    platform = Platform.FORTIGATE_FORTIOS
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
