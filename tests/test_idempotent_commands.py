from hier_config import get_hconfig_fast_load
from hier_config.models import (
    IdempotentCommandsRule,
    MatchRule,
    Platform,
)
from hier_config.platforms.driver_base import HConfigDriverRules
from hier_config.platforms.generic.driver import HConfigDriverGeneric


def _make_driver(
    rules: list[IdempotentCommandsRule],
) -> HConfigDriverGeneric:
    """Create a generic driver with custom idempotent rules."""
    driver = HConfigDriverGeneric()
    driver.rules = HConfigDriverRules(idempotent_commands=rules)
    return driver


def test_parameterized_regex_same_key_is_idempotent() -> None:
    """Commands with the same regex capture group value are idempotent."""
    driver = _make_driver(
        [
            IdempotentCommandsRule(
                match_rules=(MatchRule(re_search=r"^client (\S+) server-key"),),
            ),
        ],
    )
    running = get_hconfig_fast_load(
        driver,
        ("client 10.1.1.1 server-key KEY_OLD",),
    )
    generated = get_hconfig_fast_load(
        driver,
        ("client 10.1.1.1 server-key KEY_NEW",),
    )
    remediation = running.config_to_get_to(generated)
    assert remediation.dump_simple() == ("client 10.1.1.1 server-key KEY_NEW",)


def test_parameterized_regex_different_key_not_idempotent() -> None:
    """Commands with different regex capture group values are independent."""
    driver = _make_driver(
        [
            IdempotentCommandsRule(
                match_rules=(MatchRule(re_search=r"^client (\S+) server-key"),),
            ),
        ],
    )
    running = get_hconfig_fast_load(
        driver,
        (
            "client 10.1.1.1 server-key KEY1",
            "client 10.2.2.2 server-key KEY2",
        ),
    )
    generated = get_hconfig_fast_load(
        driver,
        ("client 10.1.1.1 server-key KEY1",),
    )
    remediation = running.config_to_get_to(generated)
    # 10.2.2.2 is removed because it's not in generated (not idempotent with 10.1.1.1)
    assert remediation.dump_simple() == ("no client 10.2.2.2 server-key KEY2",)


def test_bgp_neighbor_regex_idempotent() -> None:
    """BGP neighbor remote-as is idempotent per neighbor IP via regex capture group."""
    platform = Platform.CISCO_XR
    running = get_hconfig_fast_load(
        platform,
        (
            "router bgp 1001",
            "  neighbor 40.0.0.0 remote-as 33001",
            "  neighbor 40.0.0.17 remote-as 1002",
            "  neighbor 40.0.0.8 remote-as 2002",
        ),
    )
    generated = get_hconfig_fast_load(
        platform,
        (
            "router bgp 1001",
            "  neighbor 40.0.0.0 remote-as 44001",
            "  neighbor 1000:: remote-as 2001",
            "  neighbor 1000::8 remote-as 2002",
        ),
    )
    remediation = running.config_to_get_to(generated)
    lines = remediation.dump_simple()
    # The changed ASN for 40.0.0.0 should appear
    assert "  neighbor 40.0.0.0 remote-as 44001" in lines
    # New neighbors should be added
    assert "  neighbor 1000:: remote-as 2001" in lines
    assert "  neighbor 1000::8 remote-as 2002" in lines
    # Removed neighbors should be negated
    assert "  no neighbor 40.0.0.17 remote-as 1002" in lines
    assert "  no neighbor 40.0.0.8 remote-as 2002" in lines


def test_startswith_rules_do_not_cross_contaminate() -> None:
    """Separate idempotent rules with similar prefixes don't interfere."""
    driver = _make_driver(
        [
            IdempotentCommandsRule(
                match_rules=(MatchRule(startswith="hardware access-list tcam region"),),
            ),
            IdempotentCommandsRule(
                match_rules=(MatchRule(startswith="hardware profile tcam region"),),
            ),
        ],
    )
    running = get_hconfig_fast_load(
        driver,
        (
            "hardware access-list tcam region arp-ether 0",
            "hardware profile tcam region racl 0",
        ),
    )
    generated = get_hconfig_fast_load(
        driver,
        (
            "hardware access-list tcam region arp-ether 256",
            "hardware profile tcam region racl 512",
        ),
    )
    remediation = running.config_to_get_to(generated)
    lines = remediation.dump_simple()
    # Both should be updated independently (idempotent within their own rule)
    assert "hardware access-list tcam region arp-ether 256" in lines
    assert "hardware profile tcam region racl 512" in lines
    # Old values should NOT be negated (they're idempotent)
    assert "no hardware access-list tcam region arp-ether 0" not in lines
    assert "no hardware profile tcam region racl 0" not in lines
