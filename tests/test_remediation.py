"""Tests for unused object remediation functionality."""

from hier_config import get_hconfig
from hier_config.models import (
    MatchRule,
    Platform,
    ReferencePattern,
    UnusedObjectRule,
)
from hier_config.platforms.driver_base import HConfigDriverRules
from hier_config.platforms.generic.driver import HConfigDriverGeneric
from hier_config.remediation import UnusedObjectRemediator


class DriverWithUnusedObjectRules(HConfigDriverGeneric):
    """Test driver with unused object rules for testing."""

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        return HConfigDriverRules(
            unused_object_rules=[
                UnusedObjectRule(
                    object_type="test-acl",
                    definition_match=(
                        MatchRule(startswith="ip access-list extended "),
                    ),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="ip access-group "),
                            ),
                            extract_regex=r"ip access-group\s+(\S+)",
                            reference_type="interface-applied",
                        ),
                    ),
                    removal_template="no ip access-list extended {name}",
                    removal_order_weight=150,
                ),
                UnusedObjectRule(
                    object_type="test-route-map",
                    definition_match=(
                        MatchRule(startswith="route-map "),
                    ),
                    reference_patterns=(
                        ReferencePattern(
                            match_rules=(
                                MatchRule(startswith="interface "),
                                MatchRule(startswith="ip policy route-map "),
                            ),
                            extract_regex=r"ip policy route-map\s+(\S+)",
                            reference_type="pbr",
                        ),
                    ),
                    removal_template="no route-map {name}",
                    removal_order_weight=130,
                ),
            ]
        )


def test_find_acl_definitions() -> None:
    """Test finding ACL definitions in config."""
    config_text = """
ip access-list extended UNUSED_ACL
 permit ip any any
ip access-list extended USED_ACL
 deny ip any any
interface GigabitEthernet0/1
 ip access-group USED_ACL in
"""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, config_text.strip())

    remediator = UnusedObjectRemediator(config)
    rule = remediator.rules[0]  # test-acl rule

    definitions = remediator.find_definitions(rule)

    assert len(definitions) == 2
    acl_names = {d.name for d in definitions}
    assert "UNUSED_ACL" in acl_names
    assert "USED_ACL" in acl_names


def test_find_acl_references() -> None:
    """Test finding ACL references in config."""
    config_text = """
ip access-list extended UNUSED_ACL
 permit ip any any
ip access-list extended USED_ACL
 deny ip any any
interface GigabitEthernet0/1
 ip access-group USED_ACL in
interface GigabitEthernet0/2
 ip access-group USED_ACL out
"""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, config_text.strip())

    remediator = UnusedObjectRemediator(config)
    rule = remediator.rules[0]  # test-acl rule

    references = remediator.find_references(rule)

    assert len(references) == 2
    assert all(ref.name == "USED_ACL" for ref in references)
    assert all(ref.reference_type == "interface-applied" for ref in references)


def test_identify_unused_acls() -> None:
    """Test identifying unused ACLs."""
    config_text = """
ip access-list extended UNUSED_ACL
 permit ip any any
ip access-list extended USED_ACL
 deny ip any any
interface GigabitEthernet0/1
 ip access-group USED_ACL in
"""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, config_text.strip())

    remediator = UnusedObjectRemediator(config)
    analysis = remediator.analyze()

    assert analysis.total_defined == 2  # 2 ACLs
    assert analysis.total_unused == 1  # 1 unused ACL

    unused_acls = analysis.unused_objects["test-acl"]
    assert len(unused_acls) == 1
    assert unused_acls[0].name == "UNUSED_ACL"


def test_multiple_object_types() -> None:
    """Test analysis with multiple object types."""
    config_text = """
ip access-list extended ACL1
 permit ip any any
ip access-list extended ACL2
 deny ip any any
route-map RM1 permit 10
 match ip address ACL1
route-map RM2 permit 10
 match ip address ACL2
interface GigabitEthernet0/1
 ip access-group ACL1 in
 ip policy route-map RM1
"""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, config_text.strip())

    remediator = UnusedObjectRemediator(config)
    analysis = remediator.analyze()

    # Both ACLs are used (ACL1 on interface, ACL2 in route-map)
    assert len(analysis.unused_objects.get("test-acl", ())) == 1  # ACL2 not applied
    # RM1 is used, RM2 is not
    assert len(analysis.unused_objects.get("test-route-map", ())) == 1


def test_removal_commands() -> None:
    """Test generation of removal commands."""
    config_text = """
ip access-list extended UNUSED_ACL
 permit ip any any
ip access-list extended USED_ACL
 deny ip any any
route-map UNUSED_RM permit 10
interface GigabitEthernet0/1
 ip access-group USED_ACL in
"""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, config_text.strip())

    remediator = UnusedObjectRemediator(config)
    analysis = remediator.analyze()

    assert len(analysis.removal_commands) == 2
    assert "no ip access-list extended UNUSED_ACL" in analysis.removal_commands
    assert "no route-map UNUSED_RM" in analysis.removal_commands


def test_case_insensitive_matching() -> None:
    """Test case-insensitive object name matching."""

    class CaseInsensitiveDriver(HConfigDriverGeneric):
        @staticmethod
        def _instantiate_rules() -> HConfigDriverRules:
            return HConfigDriverRules(
                unused_object_rules=[
                    UnusedObjectRule(
                        object_type="test-acl",
                        definition_match=(
                            MatchRule(startswith="ip access-list extended "),
                        ),
                        reference_patterns=(
                            ReferencePattern(
                                match_rules=(
                                    MatchRule(startswith="interface "),
                                    MatchRule(startswith="ip access-group "),
                                ),
                                extract_regex=r"ip access-group\s+(\S+)",
                                reference_type="interface-applied",
                            ),
                        ),
                        removal_template="no ip access-list extended {name}",
                        case_sensitive=False,  # Case insensitive
                    ),
                ]
            )

    config_text = """
ip access-list extended MY_ACL
 permit ip any any
interface GigabitEthernet0/1
 ip access-group my_acl in
"""
    driver = CaseInsensitiveDriver()
    config = get_hconfig(driver, config_text.strip())

    remediator = UnusedObjectRemediator(config)
    analysis = remediator.analyze()

    # MY_ACL should be considered used (case-insensitive match with my_acl)
    assert analysis.total_unused == 0


def test_no_unused_objects() -> None:
    """Test when all objects are used."""
    config_text = """
ip access-list extended ACL1
 permit ip any any
interface GigabitEthernet0/1
 ip access-group ACL1 in
"""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, config_text.strip())

    remediator = UnusedObjectRemediator(config)
    analysis = remediator.analyze()

    assert analysis.total_unused == 0
    assert len(analysis.removal_commands) == 0


def test_driver_method() -> None:
    """Test using the driver's find_unused_objects method."""
    config_text = """
ip access-list extended UNUSED_ACL
 permit ip any any
"""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, config_text.strip())

    analysis = config.driver.find_unused_objects(config)

    assert analysis.total_defined == 1
    assert analysis.total_unused == 1


def test_extract_object_name_variations() -> None:
    """Test extraction of object names from various definition formats."""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, "")
    remediator = UnusedObjectRemediator(config)

    # Mock rule
    rule = UnusedObjectRule(
        object_type="test",
        definition_match=(MatchRule(startswith=""),),
        reference_patterns=(),
        removal_template="",
    )

    # Test various formats
    test_cases = [
        ("ip access-list extended MY_ACL", "MY_ACL"),
        ("ipv6 access-list MY_ACL6", "MY_ACL6"),
        ("ip prefix-list PL1 seq 5 permit 0.0.0.0/0", "PL1"),
        ("route-map RM1 permit 10", "RM1"),
        ("class-map match-any CM1", "CM1"),
        ("class-map CM2", "CM2"),
        ("vrf definition VRF1", "VRF1"),
        ("object-group ip OG1", "OG1"),
        ("as-path-set ASP1", "ASP1"),
        ("ipv6 general-prefix GP1 2001:db8::/32", "GP1"),
    ]

    for text, expected_name in test_cases:
        extracted_name = remediator._extract_object_name(text, rule)
        assert extracted_name == expected_name, (
            f"Failed to extract '{expected_name}' from '{text}', "
            f"got '{extracted_name}'"
        )


def test_metadata_extraction() -> None:
    """Test extraction of metadata from definitions."""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, "")
    remediator = UnusedObjectRemediator(config)

    rule = UnusedObjectRule(
        object_type="test",
        definition_match=(MatchRule(startswith=""),),
        reference_patterns=(),
        removal_template="",
    )

    # Test ACL type extraction
    metadata = remediator._extract_metadata("ip access-list extended ACL1", rule)
    assert metadata.get("acl_type") == "extended"

    metadata = remediator._extract_metadata("ip access-list standard ACL2", rule)
    assert metadata.get("acl_type") == "standard"

    # Test class-map match type
    metadata = remediator._extract_metadata("class-map match-any CM1", rule)
    assert metadata.get("match_type") == "match-any"

    # Test object-group type
    metadata = remediator._extract_metadata("object-group ip OG1", rule)
    assert metadata.get("group_type") == "ip"


def test_empty_config() -> None:
    """Test with empty configuration."""
    driver = DriverWithUnusedObjectRules()
    config = get_hconfig(driver, "")

    remediator = UnusedObjectRemediator(config)
    analysis = remediator.analyze()

    assert analysis.total_defined == 0
    assert analysis.total_unused == 0
    assert len(analysis.removal_commands) == 0


def test_driver_with_no_rules() -> None:
    """Test with a driver that has no unused object rules."""
    config = get_hconfig(Platform.GENERIC, "ip access-list extended ACL1\n permit ip any any")

    remediator = UnusedObjectRemediator(config)
    analysis = remediator.analyze()

    # Generic driver has no rules by default
    assert analysis.total_defined == 0
    assert analysis.total_unused == 0
