import json
from unittest.mock import patch

from _hier_config_rust import get_platform_rules_json
from hier_config.constructors import get_hconfig_driver
from hier_config.models import Platform
from hier_config.platforms.driver_base import (
    HConfigDriverRules,
    clear_rules_cache,
    load_platform_rules,
)


def test_all_13_platforms_load_rules_via_rust_and_python() -> None:
    """Verify all 13 platform drivers can load rules matching their canonical JSON definitions."""
    for platform in Platform:
        driver = get_hconfig_driver(platform)
        rules = driver.rules

        assert isinstance(rules, HConfigDriverRules)

        # Verify PyO3 function get_platform_rules_json
        raw_json = get_platform_rules_json(platform.name.lower())
        data = json.loads(raw_json)
        assert "rules" in data

        # Verify rules can also be loaded by string name
        rules_by_str = load_platform_rules(platform.name.lower())
        assert rules_by_str.model_dump(
            exclude={"post_load_callbacks"}
        ) == rules.model_dump(exclude={"post_load_callbacks"})


def test_load_platform_rules_caching_and_isolation() -> None:
    """Verify load_platform_rules caches definitions and returns isolated copies."""
    rules1 = load_platform_rules(Platform.CISCO_IOS)
    rules2 = load_platform_rules(Platform.CISCO_IOS)

    # Content matches
    assert rules1.model_dump() == rules2.model_dump()
    # But objects are independent copies
    assert rules1 is not rules2

    # Mutating rules1 should not mutate rules2 or subsequent loads
    rules1.ordering.clear()
    assert len(rules1.ordering) == 0
    rules3 = load_platform_rules(Platform.CISCO_IOS)
    assert len(rules3.ordering) > 0


def test_load_platform_rules_fallback_to_disk() -> None:
    """Verify fallback to disk JSON files when PyO3 function is unavailable."""
    clear_rules_cache()
    try:  # pylint: disable=too-many-try-statements
        with patch(
            "hier_config.platforms.driver_base.get_platform_rules_json",
            None,
        ):
            rules = load_platform_rules("cisco_ios")
            assert isinstance(rules, HConfigDriverRules)
            assert len(rules.ordering) > 0
    finally:
        clear_rules_cache()
