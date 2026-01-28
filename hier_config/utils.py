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
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
    TagRule,
)
from hier_config.platforms.driver_base import HConfigDriverBase

HCONFIG_PLATFORM_V2_TO_V3_MAPPING = {
    "ios": Platform.CISCO_IOS,
    "iosxe": Platform.CISCO_IOS,
    "iosxr": Platform.CISCO_XR,
    "nxos": Platform.CISCO_NXOS,
    "eos": Platform.ARISTA_EOS,
    "junos": Platform.JUNIPER_JUNOS,
    "vyos": Platform.VYOS,
}


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


def hconfig_v2_os_v3_platform_mapper(os_name: str) -> Platform:
    """Map a Hier Config v2 operating system name to a v3 Platform enumeration.

    Args:
        os_name (str): The name of the OS as defined in Hier Config v2.

    Returns:
        Platform: The corresponding Platform enumeration for Hier Config v3.

    Example:
        >>> hconfig_v2_os_v3_platform_mapper("CISCO_IOS")
        <Platform.CISCO_IOS: 'ios'>

    """
    return HCONFIG_PLATFORM_V2_TO_V3_MAPPING.get(os_name, Platform.GENERIC)


def hconfig_v3_platform_v2_os_mapper(platform: Platform) -> str:
    """Map a Hier Config v3 Platform enumeration to a v2 operating system name.

    Args:
        platform (Platform): A Platform enumeration from Hier Config v3.

    Returns:
        str: The corresponding OS name for Hier Config v2.

    Example:
        >>> hconfig_v3_platform_v2_os_mapper(Platform.CISCO_IOS)
        "ios"

    """
    for os_name, plat in HCONFIG_PLATFORM_V2_TO_V3_MAPPING.items():
        if plat == platform:
            return os_name

    return "generic"


def _process_simple_rules(
    v2_options: dict[str, Any],
    key: str,
    rule_class: type[Any],
    append_to: Callable[[Any], None],
) -> None:
    """Process v2 rules that only need match_rules."""
    for rule in v2_options.get(key, ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        append_to(rule_class(match_rules=match_rules))


def _process_custom_rules(
    v2_options: dict[str, Any], driver: HConfigDriverBase
) -> None:
    """Process v2 rules that require custom handling."""
    for rule in v2_options.get("ordering", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        weight = rule.get("order", 500) - 500
        driver.rules.ordering.append(
            OrderingRule(match_rules=match_rules, weight=weight),
        )

    for rule in v2_options.get("indent_adjust", ()):
        driver.rules.indent_adjust.append(
            IndentAdjustRule(
                start_expression=rule.get("start_expression"),
                end_expression=rule.get("end_expression"),
            )
        )

    for rule in v2_options.get("sectional_exiting", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.sectional_exiting.append(
            SectionalExitingRule(
                match_rules=match_rules, exit_text=rule.get("exit_text", "")
            ),
        )

    for rule in v2_options.get("full_text_sub", ()):
        driver.rules.full_text_sub.append(
            FullTextSubRule(
                search=rule.get("search", ""), replace=rule.get("replace", "")
            )
        )

    for rule in v2_options.get("per_line_sub", ()):
        driver.rules.per_line_sub.append(
            PerLineSubRule(
                search=rule.get("search", ""), replace=rule.get("replace", "")
            )
        )

    for rule in v2_options.get("negation_negate_with", ()):
        match_rules = _collect_match_rules(rule.get("lineage", []))
        driver.rules.negate_with.append(
            NegationDefaultWithRule(match_rules=match_rules, use=rule.get("use", "")),
        )


def load_hconfig_v2_options(
    v2_options: dict[str, Any] | str, platform: Platform
) -> HConfigDriverBase:
    """Load Hier Config v2 options to v3 driver format from either a dictionary or a file.

    Args:
        v2_options (Union[dict, str]): Either a dictionary containing v2 options or
            a file path to a YAML file containing the v2 options.
        platform (Platform): The Hier Config v3 Platform enum for the target platform.

    Returns:
        HConfigDriverBase: A v3 driver instance with the migrated rules.

    """
    if isinstance(v2_options, str):
        v2_options = yaml.safe_load(read_text_from_file(file_path=v2_options))

    if not isinstance(v2_options, dict):
        msg = "v2_options must be a dictionary or a valid file path."
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
        (
            "negation_default_when",
            NegationDefaultWhenRule,
            driver.rules.negation_default_when.append,
        ),
    )
    for key, rule_class, append_to in simple_rules:
        _process_simple_rules(v2_options, key, rule_class, append_to)

    # Process rules that require custom handling
    _process_custom_rules(v2_options, driver)

    return driver


def load_hconfig_v2_options_from_file(
    options_file: str, platform: Platform
) -> HConfigDriverBase:
    """Load Hier Config v2 options file to v3 driver format.

    Args:
        options_file (str): The v2 options file.
        platform (Platform): The Hier Config v3 Platform enum for the target platform.

    Returns:
        HConfigDriverBase: A v3 driver instance with the migrated rules.

    """
    hconfig_options = yaml.safe_load(read_text_from_file(file_path=options_file))
    return load_hconfig_v2_options(v2_options=hconfig_options, platform=platform)


def load_hconfig_v2_tags(
    v2_tags: list[dict[str, Any]] | str,
) -> tuple["TagRule"] | tuple["TagRule", ...]:
    """Convert v2-style tags into v3-style TagRule Pydantic objects for Hier Config.

    Args:
        v2_tags (Union[list[dict[str, Any]], str]):
            Either a list of dictionaries representing v2-style tags or a file path
            to a YAML file containing the v2-style tags.
            - If a list is provided, each dictionary should contain:
              - `lineage`: A list of dictionaries with rules (e.g., `startswith`, `endswith`).
              - `add_tags`: A string representing the tag to add.
            - If a file path is provided, it will be read and parsed as YAML.

    Returns:
        Tuple[TagRule]: A tuple of TagRule Pydantic objects representing v3-style tags.

    """
    # Load tags from a file if a string is provided
    if isinstance(v2_tags, str):
        v2_tags = yaml.safe_load(read_text_from_file(file_path=v2_tags))

    # Ensure v2_tags is a list
    if not isinstance(v2_tags, list):
        msg = "v2_tags must be a list of dictionaries or a valid file path."
        raise TypeError(msg)

    v3_tags: list[TagRule] = []

    for v2_tag in v2_tags:
        if "lineage" in v2_tag and "add_tags" in v2_tag:
            # Extract the v2 fields
            lineage_rules = v2_tag["lineage"]
            tags = v2_tag["add_tags"]

            # Convert to MatchRule objects
            match_rules = tuple(
                match_rule
                for lineage in lineage_rules
                if (match_rule := _set_match_rule(lineage)) is not None
            )

            # Create the TagRule object
            v3_tag = TagRule(match_rules=match_rules, apply_tags=frozenset([tags]))
            v3_tags.append(v3_tag)

    return tuple(v3_tags)
