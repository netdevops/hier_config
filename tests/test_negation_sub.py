from hier_config import get_hconfig_fast_load
from hier_config.models import (
    MatchRule,
    NegationSubRule,
    Platform,
)
from hier_config.platforms.driver_base import HConfigDriverRules
from hier_config.platforms.generic.driver import HConfigDriverGeneric
from hier_config.utils import load_hconfig_v2_options


def _make_driver(
    rules: list[NegationSubRule],
) -> HConfigDriverGeneric:
    """Create a generic driver with custom negation_sub rules."""
    driver = HConfigDriverGeneric()
    driver.rules = HConfigDriverRules(negation_sub=rules)
    return driver


def test_negation_sub_truncates_snmp_user() -> None:
    """SNMP user negation is truncated after the username."""
    driver = _make_driver(
        [
            NegationSubRule(
                match_rules=(MatchRule(startswith="snmp-server user "),),
                search=r"(no snmp-server user \S+).*",
                replace=r"\1",
            ),
        ],
    )
    running = get_hconfig_fast_load(
        driver,
        ("snmp-server user admin auth sha secret",),
    )
    generated = get_hconfig_fast_load(driver, ())
    remediation = running.config_to_get_to(generated)
    assert remediation.dump_simple() == ("no snmp-server user admin",)


def test_negation_sub_truncates_prefix_list() -> None:
    """Prefix-list negation is truncated after the sequence number."""
    driver = _make_driver(
        [
            NegationSubRule(
                match_rules=(MatchRule(startswith="ipv6 prefix-list "),),
                search=r"(no ipv6 prefix-list \S+ seq \d+).*",
                replace=r"\1",
            ),
        ],
    )
    running = get_hconfig_fast_load(
        driver,
        ("ipv6 prefix-list PL seq 1 permit 2801::/64 ge 65",),
    )
    generated = get_hconfig_fast_load(driver, ())
    remediation = running.config_to_get_to(generated)
    assert remediation.dump_simple() == ("no ipv6 prefix-list PL seq 1",)


def test_negation_sub_no_match_uses_normal_negation() -> None:
    """Commands not matching any negation_sub rule get normal swap_negation."""
    driver = _make_driver(
        [
            NegationSubRule(
                match_rules=(MatchRule(startswith="snmp-server user "),),
                search=r"(no snmp-server user \S+).*",
                replace=r"\1",
            ),
        ],
    )
    running = get_hconfig_fast_load(
        driver,
        ("hostname router1",),
    )
    generated = get_hconfig_fast_load(driver, ())
    remediation = running.config_to_get_to(generated)
    assert remediation.dump_simple() == ("no hostname router1",)


def test_negation_sub_full_remediation() -> None:
    """Full remediation: removed entry uses truncated negation, kept entry unchanged."""
    driver = _make_driver(
        [
            NegationSubRule(
                match_rules=(MatchRule(startswith="snmp-server user "),),
                search=r"(no snmp-server user \S+).*",
                replace=r"\1",
            ),
        ],
    )
    running = get_hconfig_fast_load(
        driver,
        (
            "snmp-server user admin auth sha secret",
            "snmp-server user monitor auth sha secret2",
        ),
    )
    generated = get_hconfig_fast_load(
        driver,
        ("snmp-server user monitor auth sha secret2",),
    )
    remediation = running.config_to_get_to(generated)
    assert remediation.dump_simple() == ("no snmp-server user admin",)


def test_negation_sub_via_v2_options() -> None:
    """Negation sub rules loaded via load_hconfig_v2_options work correctly."""
    v2_options: dict[str, object] = {
        "negation_sub": [
            {
                "lineage": [{"startswith": "snmp-server user "}],
                "search": r"(no snmp-server user \S+).*",
                "replace": r"\1",
            },
        ],
    }
    driver = load_hconfig_v2_options(v2_options, Platform.GENERIC)
    running = get_hconfig_fast_load(
        driver,
        ("snmp-server user admin auth sha secret",),
    )
    generated = get_hconfig_fast_load(driver, ())
    remediation = running.config_to_get_to(generated)
    assert remediation.dump_simple() == ("no snmp-server user admin",)
