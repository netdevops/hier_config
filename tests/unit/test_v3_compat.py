"""Tests for the permanent v3 name compatibility surface.

Every name here is a v3 public name that v4 renamed or removed. Each one is
restored as a thin delegation to its v4 counterpart, with no DeprecationWarning,
and is supported permanently. These tests lock that contract.
"""

import warnings
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from hier_config import (
    HConfig,
    HConfigDriverBase,
    HConfigDriverRules,
    MatchRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    NegationSubRule,
    Platform,
    get_hconfig,
    get_hconfig_fast_generic_load,
    get_hconfig_fast_load,
    get_hconfig_from_dump,
)
from hier_config.constructors import (
    get_hconfig_driver as get_hconfig_driver_from_constructors,
)
from hier_config.models import NegationRule, NegationStrategy
from hier_config.registry import get_hconfig_driver
from hier_config.utils import (
    HCONFIG_PLATFORM_V2_TO_V3_MAPPING,
    hconfig_v2_os_v3_platform_mapper,
    hconfig_v3_platform_v2_os_mapper,
    load_driver_rules,
    load_hconfig_v2_options,
    load_hconfig_v2_options_from_file,
    load_hconfig_v2_tags,
    load_tag_rules,
)

RUNNING = "interface Vlan2\n  ip address 10.0.0.1 255.255.255.0\n  no shutdown\n"
RUNNING_LINES: tuple[str, ...] = tuple(RUNNING.splitlines())
GENERATED = "interface Vlan2\n  ip address 10.0.0.2 255.255.255.0\n  shutdown\n"


# --- constructors ---------------------------------------------------------


def test_get_hconfig_matches_from_text() -> None:
    assert (
        get_hconfig(Platform.CISCO_IOS, RUNNING).to_lines()
        == HConfig.from_text(Platform.CISCO_IOS, RUNNING).to_lines()
    )


def test_get_hconfig_accepts_a_driver() -> None:
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    assert (
        get_hconfig(driver, RUNNING).to_lines()
        == HConfig.from_text(driver, RUNNING).to_lines()
    )


def test_get_hconfig_accepts_a_path() -> None:
    with NamedTemporaryFile(
        "w", suffix=".conf", delete=False, encoding="utf8"
    ) as handle:
        handle.write(RUNNING)
        path = Path(handle.name)
    try:
        assert (
            get_hconfig(Platform.CISCO_IOS, path).to_lines()
            == HConfig.from_text(Platform.CISCO_IOS, RUNNING).to_lines()
        )
    finally:
        path.unlink()


def test_get_hconfig_defaults_to_empty_config() -> None:
    assert not get_hconfig(Platform.CISCO_IOS).to_lines()


def test_get_hconfig_fast_load_matches_from_lines() -> None:
    lines = RUNNING_LINES
    assert (
        get_hconfig_fast_load(Platform.CISCO_IOS, lines).to_lines()
        == HConfig.from_lines(Platform.CISCO_IOS, lines).to_lines()
    )


def test_get_hconfig_fast_load_accepts_a_string() -> None:
    assert (
        get_hconfig_fast_load(Platform.CISCO_IOS, RUNNING).to_lines()
        == HConfig.from_lines(Platform.CISCO_IOS, RUNNING).to_lines()
    )


def test_get_hconfig_fast_generic_load_uses_the_generic_platform() -> None:
    config = get_hconfig_fast_generic_load(RUNNING_LINES)
    assert config.to_lines() == HConfig.from_lines(Platform.GENERIC, RUNNING).to_lines()


def test_get_hconfig_from_dump_matches_from_dump() -> None:
    dump = get_hconfig(Platform.CISCO_IOS, RUNNING).dump()
    assert (
        get_hconfig_from_dump(Platform.CISCO_IOS, dump).to_lines()
        == HConfig.from_dump(Platform.CISCO_IOS, dump).to_lines()
    )


def test_get_hconfig_driver_is_importable_from_constructors() -> None:
    driver = get_hconfig_driver_from_constructors(Platform.CISCO_IOS)
    assert isinstance(driver, HConfigDriverBase)
    assert get_hconfig_driver_from_constructors is get_hconfig_driver


# --- tree method aliases --------------------------------------------------


def test_config_to_get_to_matches_remediation() -> None:
    running = get_hconfig(Platform.CISCO_IOS, RUNNING)
    generated = get_hconfig(Platform.CISCO_IOS, GENERATED)
    assert (
        running.config_to_get_to(generated).to_lines()
        == running.remediation(generated).to_lines()
    )


def test_config_to_get_to_accepts_a_delta() -> None:
    running = get_hconfig(Platform.CISCO_IOS, RUNNING)
    generated = get_hconfig(Platform.CISCO_IOS, GENERATED)
    delta = HConfig(running.driver)
    assert running.config_to_get_to(generated, delta) is delta


def test_dump_simple_matches_to_lines() -> None:
    config = get_hconfig(Platform.CISCO_IOS, RUNNING)
    assert config.dump_simple() == config.to_lines()


def test_dump_simple_forwards_sectional_exiting() -> None:
    config = get_hconfig(Platform.CISCO_IOS, RUNNING)
    assert config.dump_simple(sectional_exiting=True) == config.to_lines(
        sectional_exiting=True
    )


def test_cisco_style_text_matches_indented_text() -> None:
    config = get_hconfig(Platform.CISCO_IOS, RUNNING)
    for child in config.all_children():
        assert child.cisco_style_text() == child.indented_text()


def test_cisco_style_text_forwards_style_and_tag() -> None:
    config = get_hconfig(Platform.CISCO_IOS, RUNNING)
    child = next(iter(config.all_children()))
    child.comments.add("a comment")
    assert child.cisco_style_text("with_comments") == child.indented_text(
        "with_comments"
    )
    assert child.cisco_style_text("merged", "safe") == child.indented_text(
        "merged", "safe"
    )


def test_tags_add_matches_add_tags() -> None:
    config = get_hconfig(Platform.CISCO_IOS, RUNNING)
    child = next(iter(config.all_children()))
    child.tags_add("safe")
    assert "safe" in child.tags


def test_tags_add_accepts_an_iterable() -> None:
    config = get_hconfig(Platform.CISCO_IOS, RUNNING)
    child = next(iter(config.all_children()))
    child.tags_add({"safe", "risky"})
    assert {"safe", "risky"}.issubset(child.tags)


def test_tags_remove_matches_remove_tags() -> None:
    config = get_hconfig(Platform.CISCO_IOS, RUNNING)
    child = next(iter(config.all_children()))
    child.tags_add("safe")
    child.tags_remove("safe")
    assert "safe" not in child.tags


# --- utils ----------------------------------------------------------------


def test_platform_mapping_constant_is_restored() -> None:
    assert HCONFIG_PLATFORM_V2_TO_V3_MAPPING["iosxe"] is Platform.CISCO_IOS
    assert HCONFIG_PLATFORM_V2_TO_V3_MAPPING["aruba_aoscx"] is Platform.ARUBA_AOSCX


@pytest.mark.parametrize(
    ("os_name", "expected"),
    tuple(HCONFIG_PLATFORM_V2_TO_V3_MAPPING.items()),
)
def test_v2_os_mapper_resolves_every_known_name(
    os_name: str, expected: Platform
) -> None:
    assert hconfig_v2_os_v3_platform_mapper(os_name) is expected


def test_v2_os_mapper_strips_whitespace() -> None:
    assert hconfig_v2_os_v3_platform_mapper(" iosxe ") is Platform.CISCO_IOS


def test_v2_os_mapper_falls_back_to_generic() -> None:
    assert hconfig_v2_os_v3_platform_mapper("not_a_platform") is Platform.GENERIC


def test_v3_platform_mapper_round_trips() -> None:
    assert hconfig_v3_platform_v2_os_mapper(Platform.CISCO_IOS) == "ios"
    assert hconfig_v3_platform_v2_os_mapper(Platform.NOKIA_SRL) == "nokia_srl"


def test_v3_platform_mapper_falls_back_to_generic() -> None:
    assert hconfig_v3_platform_v2_os_mapper(Platform.GENERIC) == "generic"


def test_load_hconfig_v2_options_matches_load_driver_rules() -> None:
    options = {"negation_default_when": [{"lineage": [{"startswith": "interface"}]}]}
    legacy = load_hconfig_v2_options(options, Platform.CISCO_IOS)
    current = load_driver_rules(options, Platform.CISCO_IOS)
    assert legacy.rules.negation == current.rules.negation


def test_load_hconfig_v2_options_accepts_v3_keyword_names() -> None:
    options = {"negation_default_when": [{"lineage": [{"startswith": "interface"}]}]}
    driver = load_hconfig_v2_options(v2_options=options, platform=Platform.CISCO_IOS)
    assert isinstance(driver, HConfigDriverBase)


def test_load_hconfig_v2_options_from_file() -> None:
    with NamedTemporaryFile(
        "w", suffix=".yml", delete=False, encoding="utf8"
    ) as handle:
        handle.write("negation_default_when:\n- lineage:\n  - startswith: interface\n")
        path = handle.name
    try:
        driver = load_hconfig_v2_options_from_file(path, Platform.CISCO_IOS)
    finally:
        Path(path).unlink()
    assert any(
        rule.strategy is NegationStrategy.DEFAULT
        for rule in driver.rules.all_negation_rules()
    )


def test_load_hconfig_v2_tags_matches_load_tag_rules(tags_file_path: str) -> None:
    assert load_hconfig_v2_tags(tags_file_path) == load_tag_rules(tags_file_path)


def test_load_hconfig_v2_tags_accepts_the_v3_keyword_name(tags_file_path: str) -> None:
    assert load_hconfig_v2_tags(v2_tags=tags_file_path) == load_tag_rules(
        tags_file_path
    )


# --- negation models ------------------------------------------------------


def test_negation_default_with_rule_converts() -> None:
    match_rules = (MatchRule(startswith="ip route"),)
    legacy = NegationDefaultWithRule(match_rules=match_rules, use="no ip route")
    assert legacy.to_negation_rule() == NegationRule(
        match_rules=match_rules,
        strategy=NegationStrategy.REPLACE,
        use="no ip route",
    )


def test_negation_default_when_rule_converts() -> None:
    match_rules = (MatchRule(startswith="interface"),)
    legacy = NegationDefaultWhenRule(match_rules=match_rules)
    assert legacy.to_negation_rule() == NegationRule(
        match_rules=match_rules,
        strategy=NegationStrategy.DEFAULT,
    )


def test_negation_sub_rule_converts() -> None:
    match_rules = (MatchRule(startswith="snmp-server user"),)
    legacy = NegationSubRule(
        match_rules=match_rules,
        search=r"^(no snmp-server user \S+).*$",
        replace=r"\1",
    )
    assert legacy.to_negation_rule() == NegationRule(
        match_rules=match_rules,
        strategy=NegationStrategy.REGEX_SUB,
        search=r"^(no snmp-server user \S+).*$",
        replace=r"\1",
    )


def _legacy_rules() -> HConfigDriverRules:
    return HConfigDriverRules(
        negate_with=[
            NegationDefaultWithRule(
                match_rules=(MatchRule(startswith="ip route"),),
                use="no ip route all",
            )
        ],
        negation_default_when=[
            NegationDefaultWhenRule(match_rules=(MatchRule(startswith="interface"),))
        ],
        negation_sub=[
            NegationSubRule(
                match_rules=(MatchRule(startswith="snmp-server user"),),
                search=r"^(no snmp-server user \S+).*$",
                replace=r"\1",
            )
        ],
    )


def _unified_rules() -> HConfigDriverRules:
    return HConfigDriverRules(
        negation=[
            NegationRule(
                match_rules=(MatchRule(startswith="interface"),),
                strategy=NegationStrategy.DEFAULT,
            ),
            NegationRule(
                match_rules=(MatchRule(startswith="ip route"),),
                strategy=NegationStrategy.REPLACE,
                use="no ip route all",
            ),
            NegationRule(
                match_rules=(MatchRule(startswith="snmp-server user"),),
                strategy=NegationStrategy.REGEX_SUB,
                search=r"^(no snmp-server user \S+).*$",
                replace=r"\1",
            ),
        ]
    )


def test_legacy_negation_fields_build_the_unified_list() -> None:
    assert _legacy_rules().all_negation_rules() == _unified_rules().negation


def test_legacy_negation_fields_accept_dicts() -> None:
    rules = HConfigDriverRules.model_validate(
        {"negation_default_when": [{"match_rules": [{"startswith": "interface"}]}]}
    )
    assert rules.all_negation_rules() == [
        NegationRule(
            match_rules=(MatchRule(startswith="interface"),),
            strategy=NegationStrategy.DEFAULT,
        )
    ]


def test_legacy_negation_fields_append_after_unified_entries() -> None:
    unified = NegationRule(
        match_rules=(MatchRule(startswith="vlan"),),
        strategy=NegationStrategy.DEFAULT,
    )
    rules = HConfigDriverRules(
        negation=[unified],
        negation_default_when=[
            NegationDefaultWhenRule(match_rules=(MatchRule(startswith="interface"),))
        ],
    )
    resolved = rules.all_negation_rules()
    assert resolved[0] == unified
    assert resolved[1].match_rules == (MatchRule(startswith="interface"),)


def test_all_negation_rules_returns_negation_itself_when_no_v3_fields() -> None:
    """The no-v3-rules path must not allocate a copy on every negation."""
    rules = _unified_rules()
    assert rules.all_negation_rules() is rules.negation


def test_legacy_negation_fields_stay_live_after_construction() -> None:
    """v3's own custom-driver docs teach `rules.negate_with.append(...)`."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.negate_with.append(
        NegationDefaultWithRule(
            match_rules=(MatchRule(startswith="ip route"),), use="no ip route all"
        )
    )
    child = HConfig(driver).add_child("ip route 0.0.0.0 0.0.0.0 10.0.0.1")
    assert child.negate().text == "no ip route all"


def test_appending_to_negation_still_works() -> None:
    """The v4 spelling must keep working alongside the v3 fields."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.negation.append(
        NegationRule(
            match_rules=(MatchRule(startswith="ip route"),),
            strategy=NegationStrategy.REPLACE,
            use="no ip route all",
        )
    )
    child = HConfig(driver).add_child("ip route 0.0.0.0 0.0.0.0 10.0.0.1")
    assert child.negate().text == "no ip route all"


def test_v3_fields_are_not_folded_in_twice_on_revalidation() -> None:
    """`HConfigDriverRules(**base.model_dump(), ...)` must not duplicate rules."""
    rules = _legacy_rules()
    round_tripped = HConfigDriverRules.model_validate(rules.model_dump())
    assert round_tripped.all_negation_rules() == rules.all_negation_rules()


def test_use_default_for_negation() -> None:
    driver = _driver_for(_legacy_rules())
    config = HConfig(driver)
    interface = config.add_child("interface Vlan2")
    route = config.add_child("ip route 0.0.0.0 0.0.0.0 10.0.0.1")
    assert interface.use_default_for_negation(interface)
    assert not route.use_default_for_negation(route)


def _driver_for(rules: HConfigDriverRules) -> HConfigDriverBase:
    class _Driver(HConfigDriverBase):
        @staticmethod
        def _instantiate_rules() -> HConfigDriverRules:
            return rules

    return _Driver()


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        ("ip route 0.0.0.0 0.0.0.0 10.0.0.1", "no ip route all"),
        ("interface Vlan2", "default interface Vlan2"),
        (
            "snmp-server user admin network-admin auth md5 secret",
            "no snmp-server user admin",
        ),
        ("hostname router", "no hostname router"),
    ),
)
def test_legacy_negation_fields_negate_like_the_unified_list(
    text: str, expected: str
) -> None:
    legacy_config = HConfig(_driver_for(_legacy_rules()))
    unified_config = HConfig(_driver_for(_unified_rules()))
    legacy_child = legacy_config.add_child(text)
    unified_child = unified_config.add_child(text)
    assert legacy_child.negate().text == expected
    assert unified_child.negate().text == expected


def test_the_v3_surface_raises_no_deprecation_warning(tags_file_path: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        running = get_hconfig(Platform.CISCO_IOS, RUNNING)
        generated = get_hconfig(Platform.CISCO_IOS, GENERATED)
        running.config_to_get_to(generated).dump_simple()
        get_hconfig_fast_load(Platform.CISCO_IOS, RUNNING)
        get_hconfig_fast_generic_load(RUNNING)
        get_hconfig_from_dump(Platform.CISCO_IOS, running.dump())
        hconfig_v2_os_v3_platform_mapper("ios")
        hconfig_v3_platform_v2_os_mapper(Platform.CISCO_IOS)
        load_hconfig_v2_tags(tags_file_path)
        _legacy_rules()

    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]
