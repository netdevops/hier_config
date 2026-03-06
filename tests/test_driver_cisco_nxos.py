from hier_config import get_hconfig_fast_load
from hier_config.models import Platform
from hier_config.utils import load_hconfig_v2_options


def test_line_console_terminal_settings_negation_negate_with() -> None:
    """Verify that negation_negate_with produces valid NX-OS remediation commands.

    NX-OS does not accept 'no terminal length <value>' or 'no terminal width <value>'.
    The correct remediation is to reset to platform defaults via negation_negate_with.
    """
    driver = load_hconfig_v2_options(
        {
            "negation_negate_with": [
                {
                    "lineage": [
                        {"equals": "line console"},
                        {"startswith": "terminal length"},
                    ],
                    "use": "terminal length 24",
                },
                {
                    "lineage": [
                        {"equals": "line console"},
                        {"startswith": "terminal width"},
                    ],
                    "use": "terminal width 80",
                },
            ],
        },
        Platform.CISCO_NXOS,
    )

    running_config = get_hconfig_fast_load(
        driver,
        (
            "line console",
            "  exec-timeout 10",
            "  terminal length 45",
            "  terminal width 160",
        ),
    )
    generated_config = get_hconfig_fast_load(
        driver,
        (
            "line console",
            "  exec-timeout 10",
        ),
    )

    remediation = running_config.config_to_get_to(generated_config)

    assert remediation.dump_simple() == (
        "line console",
        "  terminal length 24",
        "  terminal width 80",
    )
