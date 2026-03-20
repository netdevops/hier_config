from hier_config import get_hconfig_fast_load
from hier_config.models import (
    MatchRule,
    Platform,
    ReferenceLocation,
    UnusedObjectRule,
)
from hier_config.platforms.driver_base import HConfigDriverRules
from hier_config.platforms.generic.driver import HConfigDriverGeneric


def _make_driver(
    rules: list[UnusedObjectRule],
) -> HConfigDriverGeneric:
    """Create a generic driver with custom unused object rules."""
    driver = HConfigDriverGeneric()
    driver.rules = HConfigDriverRules(unused_objects=rules)
    return driver


def test_unused_acl_detected() -> None:
    """An ACL defined but not referenced is yielded as unused."""
    driver = _make_driver(
        [
            UnusedObjectRule(
                match_rules=(MatchRule(startswith="ipv4 access-list "),),
                name_re=r"^ipv4 access-list (?P<name>\S+)",
                reference_locations=(
                    ReferenceLocation(
                        match_rules=(MatchRule(startswith="interface "),),
                        reference_re=r"\bipv4 access-group {name}\b",
                    ),
                ),
            ),
        ],
    )
    config = get_hconfig_fast_load(
        driver,
        (
            "ipv4 access-list USED_ACL",
            " 10 permit tcp any any",
            "ipv4 access-list UNUSED_ACL",
            " 10 deny ipv4 any any",
            "interface GigabitEthernet0/0/0/0",
            " ipv4 access-group USED_ACL ingress",
        ),
    )
    unused = [child.text for child in config.unused_objects()]
    assert unused == ["ipv4 access-list UNUSED_ACL"]


def test_used_acl_not_detected() -> None:
    """An ACL that is referenced should not be yielded."""
    driver = _make_driver(
        [
            UnusedObjectRule(
                match_rules=(MatchRule(startswith="ipv4 access-list "),),
                name_re=r"^ipv4 access-list (?P<name>\S+)",
                reference_locations=(
                    ReferenceLocation(
                        match_rules=(MatchRule(startswith="interface "),),
                        reference_re=r"\bipv4 access-group {name}\b",
                    ),
                ),
            ),
        ],
    )
    config = get_hconfig_fast_load(
        driver,
        (
            "ipv4 access-list MY_ACL",
            " 10 permit tcp any any",
            "interface GigabitEthernet0/0/0/0",
            " ipv4 access-group MY_ACL ingress",
        ),
    )
    unused = list(config.unused_objects())
    assert not unused


def test_no_unused_object_rules_yields_nothing() -> None:
    """A driver with no unused_objects rules yields nothing."""
    config = get_hconfig_fast_load(
        Platform.GENERIC,
        ("hostname router1",),
    )
    unused = list(config.unused_objects())
    assert not unused


def test_multiple_reference_locations() -> None:
    """An object referenced via the second reference location is not unused."""
    driver = _make_driver(
        [
            UnusedObjectRule(
                match_rules=(MatchRule(startswith="route-policy "),),
                name_re=r"^route-policy (?P<name>\S+)",
                reference_locations=(
                    ReferenceLocation(
                        match_rules=(MatchRule(startswith="interface "),),
                        reference_re=r"\broute-policy {name}\b",
                    ),
                    ReferenceLocation(
                        match_rules=(MatchRule(startswith="router bgp"),),
                        reference_re=r"\broute-policy {name}\b",
                    ),
                ),
            ),
        ],
    )
    config = get_hconfig_fast_load(
        driver,
        (
            "route-policy USED_IN_BGP",
            " pass",
            "route-policy UNUSED_POLICY",
            " drop",
            "router bgp 65000",
            " neighbor 10.0.0.1",
            "  route-policy USED_IN_BGP in",
        ),
    )
    unused = [child.text for child in config.unused_objects()]
    assert unused == ["route-policy UNUSED_POLICY"]


def test_xr_driver_unused_objects() -> None:
    """Test the XR driver's built-in unused object rules."""
    config = get_hconfig_fast_load(
        Platform.CISCO_XR,
        (
            "ipv4 access-list APPLIED_ACL",
            " 10 permit tcp any any",
            "ipv4 access-list ORPHAN_ACL",
            " 10 deny ipv4 any any",
            "interface GigabitEthernet0/0/0/0",
            " ipv4 access-group APPLIED_ACL ingress",
        ),
    )
    unused = [child.text for child in config.unused_objects()]
    assert "ipv4 access-list ORPHAN_ACL" in unused
    assert "ipv4 access-list APPLIED_ACL" not in unused
