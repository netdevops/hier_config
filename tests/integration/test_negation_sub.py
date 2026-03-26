from hier_config import get_hconfig_fast_load
from hier_config.models import (
    MatchRule,
    NegationSubRule,
    Platform,
)
from hier_config.platforms.driver_base import HConfigDriverRules
from hier_config.platforms.generic.driver import HConfigDriverGeneric
from hier_config.utils import load_driver_rules


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
    remediation = running.remediation(generated)
    assert remediation.to_lines() == ("no snmp-server user admin",)


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
    remediation = running.remediation(generated)
    assert remediation.to_lines() == ("no ipv6 prefix-list PL seq 1",)


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
    remediation = running.remediation(generated)
    assert remediation.to_lines() == ("no hostname router1",)


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
    remediation = running.remediation(generated)
    assert remediation.to_lines() == ("no snmp-server user admin",)


def test_negation_sub_via_load_driver_rules() -> None:
    """Negation sub rules loaded via load_driver_rules work correctly."""
    options: dict[str, object] = {
        "negation_sub": [
            {
                "lineage": [{"startswith": "snmp-server user "}],
                "search": r"(no snmp-server user \S+).*",
                "replace": r"\1",
            },
        ],
    }
    driver = load_driver_rules(options, Platform.GENERIC)
    running = get_hconfig_fast_load(
        driver,
        ("snmp-server user admin auth sha secret",),
    )
    generated = get_hconfig_fast_load(driver, ())
    remediation = running.remediation(generated)
    assert remediation.to_lines() == ("no snmp-server user admin",)
