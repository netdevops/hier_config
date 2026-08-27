from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter

from hier_config import Platform, get_hconfig_driver
from hier_config.models import (
    FullTextSubRule,
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    IndentAdjustRule,
    MatchRule,
    NegationRule,
    NegationStrategy,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    ReferenceLocation,
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
    TagRule,
    UnusedObjectRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase


def _set_match_rule(lineage: dict[str, Any]) -> MatchRule | None:
    if startswith := lineage.get("startswith"):
        return MatchRule(startswith=startswith)
    if endswith := lineage.get("endswith"):
        return MatchRule(endswith=endswith)
    if contains := lineage.get("contains"):
        return MatchRule(contains=contains)
    if equals := lineage.get("equals"):
        return MatchRule(equals=equals)
    if re_search := lineage.get("re_search"):
        return MatchRule(re_search=re_search)

    return None


def _collect_match_rules(
    lineages: Iterable[dict[str, Any]],
) -> tuple[MatchRule, ...]:
    collected: list[MatchRule] = []
    for lineage in lineages:
        match_rule = _set_match_rule(lineage)
        if match_rule is not None:
            collected.append(match_rule)
    return tuple(collected)


def read_text_from_file(file_path: str) -> str:
    """Function that loads the contents of a file into memory.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        str: The configuration file contents as a string.

    """
    return Path(file_path).read_text(encoding="utf-8")


def load_hier_config_tags(tags_file: str) -> tuple[TagRule, ...]:
    """Loads and validates Hier Config tags from a YAML file.

    Args:
        tags_file (str): Path to the YAML file containing the tags.

    Returns:
        Tuple[TagRule, ...]: A tuple of validated TagRule objects.

    """
    tags_data = yaml.safe_load(read_text_from_file(file_path=tags_file))
    return TypeAdapter(tuple[TagRule, ...]).validate_python(tags_data)


def _process_simple_rules(
    options: dict[str, Any],
    key: str,
    rule_class: type[Any],
    append_to: Callable[[Any], None],
) -> None:
    """Process rules that only need match_rules."""
    for rule in options.get(key, ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        append_to(rule_class(match_rules=match_rules))


def _process_custom_rules(options: dict[str, Any], driver: HConfigDriverBase) -> None:
    """Process rules that require custom handling."""
    for rule in options.get("ordering", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        weight = rule.get("order", 500) - 500
        driver.rules.ordering.append(
            OrderingRule(match_rules=match_rules, weight=weight),
        )

    for rule in options.get("indent_adjust", ()):
        driver.rules.indent_adjust.append(
            IndentAdjustRule(
                start_expression=rule.get("start_expression"),
                end_expression=rule.get("end_expression"),
            )
        )

    for rule in options.get("sectional_exiting", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.sectional_exiting.append(
            SectionalExitingRule(
                match_rules=match_rules, exit_text=rule.get("exit_text", "")
            ),
        )

    for rule in options.get("full_text_sub", ()):
        driver.rules.full_text_sub.append(
            FullTextSubRule(
                search=rule.get("search", ""), replace=rule.get("replace", "")
            )
        )

    for rule in options.get("per_line_sub", ()):
        driver.rules.per_line_sub.append(
            PerLineSubRule(
                search=rule.get("search", ""), replace=rule.get("replace", "")
            )
        )

    for rule in options.get("negation_negate_with", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.negation.append(
            NegationRule(
                match_rules=match_rules,
                strategy=NegationStrategy.REPLACE,
                use=rule.get("use", ""),
            ),
        )

    for rule in options.get("negation_sub", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.negation.append(
            NegationRule(
                match_rules=match_rules,
                strategy=NegationStrategy.REGEX_SUB,
                search=rule.get("search", ""),
                replace=rule.get("replace", ""),
            ),
        )

    for rule in options.get("unused_objects", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        ref_locations = tuple(
            ReferenceLocation(
                match_rules=_collect_match_rules(ref.get("lineage", [])),
                reference_re=ref.get("reference_re", ""),
            )
            for ref in rule.get("reference_locations", [])
        )
        driver.rules.unused_objects.append(
            UnusedObjectRule(
                match_rules=match_rules,
                name_re=rule.get("name_re", ""),
                reference_locations=ref_locations,
            ),
        )


def load_driver_rules(
    options: dict[str, Any] | str, platform: Platform
) -> HConfigDriverBase:
    """Load driver rules from a dictionary or YAML file.

    Args:
        options: Either a dictionary containing driver rule options or
            a file path to a YAML file containing the options.
        platform: The Platform enum for the target platform.

    Returns:
        HConfigDriverBase: A driver instance with the loaded rules.

    """
    if isinstance(options, str):
        options = yaml.safe_load(read_text_from_file(file_path=options))

    if not isinstance(options, dict):
        msg = "options must be a dictionary or a valid file path."
        raise TypeError(msg)

    driver = get_hconfig_driver(platform)

    # Process simple rules that only need match_rules
    simple_rules: tuple[tuple[str, type[Any], Callable[[Any], None]], ...] = (
        (
            "sectional_overwrite",
            SectionalOverwriteRule,
            driver.rules.sectional_overwrite.append,
        ),
        (
            "sectional_overwrite_no_negate",
            SectionalOverwriteNoNegateRule,
            driver.rules.sectional_overwrite_no_negate.append,
        ),
        (
            "parent_allows_duplicate_child",
            ParentAllowsDuplicateChildRule,
            driver.rules.parent_allows_duplicate_child.append,
        ),
        (
            "idempotent_commands_blacklist",
            IdempotentCommandsAvoidRule,
            driver.rules.idempotent_commands_avoid.append,
        ),
        (
            "idempotent_commands",
            IdempotentCommandsRule,
            driver.rules.idempotent_commands.append,
        ),
    )
    for key, rule_class, append_to in simple_rules:
        _process_simple_rules(options, key, rule_class, append_to)

    for rule in options.get("negation_default_when", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.negation.append(
            NegationRule(match_rules=match_rules, strategy=NegationStrategy.DEFAULT),
        )

    # Process rules that require custom handling
    _process_custom_rules(options, driver)

    return driver


def load_tag_rules(
    tags: list[dict[str, Any]] | str,
) -> tuple[TagRule, ...]:
    """Load tag rules from a list of dictionaries or a YAML file.

    Args:
        tags: Either a list of dictionaries or a file path to a YAML file.
            Each dictionary should contain:
              - `lineage`: A list of dictionaries with rules (e.g., `startswith`, `endswith`).
              - `add_tags`: A string representing the tag to add.

    Returns:
        A tuple of TagRule objects.

    """
    if isinstance(tags, str):
        tags = yaml.safe_load(read_text_from_file(file_path=tags))

    if not isinstance(tags, list):
        msg = "tags must be a list of dictionaries or a valid file path."
        raise TypeError(msg)

    result: list[TagRule] = []

    for tag in tags:
        if "lineage" in tag and "add_tags" in tag:
            lineage_rules = tag["lineage"]
            tag_name = tag["add_tags"]

            match_rules = _collect_match_rules(lineage_rules)

            result.append(
                TagRule(match_rules=match_rules, apply_tags=frozenset([tag_name]))
            )

    return tuple(result)


# --- v3 compatibility -----------------------------------------------------
#
# The names below are the v3 spellings. They are supported permanently and
# emit no DeprecationWarning. The loader wrappers delegate to their v4
# counterparts and keep the v3 parameter names, because v3 callers pass them
# as keywords.

HCONFIG_PLATFORM_V2_TO_V3_MAPPING = {
    # netutils sets this platform's network_driver_mappings["hier_config"] to
    # "aruba_aoscx", and nautobot-golden-config resolves the driver by feeding
    # that string through this mapper, so the entry is required for AOS-CX to
    # resolve instead of falling back to GENERIC.
    "aruba_aoscx": Platform.ARUBA_AOSCX,
    "ios": Platform.CISCO_IOS,
    "iosxe": Platform.CISCO_IOS,
    "iosxr": Platform.CISCO_XR,
    "nxos": Platform.CISCO_NXOS,
    "eos": Platform.ARISTA_EOS,
    "junos": Platform.JUNIPER_JUNOS,
    "vyos": Platform.VYOS,
    "huawei_vrp": Platform.HUAWEI_VRP,
    "nokia_srl": Platform.NOKIA_SRL,
}


def hconfig_v2_os_v3_platform_mapper(os_name: str) -> Platform:
    """Map a Hier Config v2 operating system name to a Platform enumeration.

    Surrounding whitespace is stripped before lookup: consumers such as
    nautobot-golden-config pass ``platform.network_driver_mappings["hier_config"]``
    straight in, and a stray trailing space there would otherwise miss the table
    and silently fall back to ``Platform.GENERIC`` -- producing a wrong (often
    destructive) remediation with no error. Case is left untouched.

    Args:
        os_name: The name of the OS as defined in Hier Config v2.

    Returns:
        Platform: The corresponding Platform enumeration.

    Example:
        >>> hconfig_v2_os_v3_platform_mapper("ios")
        <Platform.CISCO_IOS: 3>

    """
    return HCONFIG_PLATFORM_V2_TO_V3_MAPPING.get(os_name.strip(), Platform.GENERIC)


def hconfig_v3_platform_v2_os_mapper(platform: Platform) -> str:
    """Map a Platform enumeration to a Hier Config v2 operating system name.

    Args:
        platform: A Platform enumeration.

    Returns:
        str: The corresponding OS name for Hier Config v2.

    Example:
        >>> hconfig_v3_platform_v2_os_mapper(Platform.CISCO_IOS)
        'ios'

    """
    for os_name, mapped in HCONFIG_PLATFORM_V2_TO_V3_MAPPING.items():
        if mapped == platform:
            return os_name

    return "generic"


def load_hconfig_v2_options(
    v2_options: dict[str, Any] | str, platform: Platform
) -> HConfigDriverBase:
    """v3 name for `load_driver_rules()`. Both spellings are supported."""
    return load_driver_rules(v2_options, platform)


def load_hconfig_v2_options_from_file(
    options_file: str, platform: Platform
) -> HConfigDriverBase:
    """v3 helper. Reads the YAML file, then calls `load_driver_rules()`."""
    return load_driver_rules(
        yaml.safe_load(read_text_from_file(file_path=options_file)), platform
    )


def load_hconfig_v2_tags(
    v2_tags: list[dict[str, Any]] | str,
) -> tuple[TagRule, ...]:
    """v3 name for `load_tag_rules()`. Both spellings are supported."""
    return load_tag_rules(v2_tags)
