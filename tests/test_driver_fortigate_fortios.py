from hier_config import get_hconfig_fast_load
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
    assert remediation_config.dump_simple() == (
        "config system interface",
        "  edit port1",
        "    unset description",
        "  next",
        "end",
    )
