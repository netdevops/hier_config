"""Helper utilities for creating and managing unused object rules.

This module provides simplified APIs for creating UnusedObjectRule instances
and loading them from external configuration files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hier_config.models import MatchRule, ReferencePattern, UnusedObjectRule

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

YAML_AVAILABLE = yaml is not None


class UnusedObjectRuleBuilder:
    r"""Builder class for creating UnusedObjectRule instances with a fluent API.

    This builder provides a more convenient way to create unused object rules
    without having to construct all the nested structures at once.

    Example:
        >>> builder = UnusedObjectRuleBuilder("my-custom-acl")
        >>> builder.define_with(startswith="custom-acl ")
        >>> builder.referenced_in(
        ...     context_match={"startswith": "interface "},
        ...     extract_regex=r"apply-custom-acl\s+(\S+)",
        ...     reference_type="interface-applied",
        ... )
        >>> builder.remove_with("no custom-acl {name}")
        >>> rule = builder.build()

    """

    def __init__(self, object_type: str) -> None:
        """Initialize the builder.

        Args:
            object_type: User-defined identifier for the object type.

        """
        self.object_type = object_type
        self._definition_matches: list[MatchRule] = []
        self._reference_patterns: list[ReferencePattern] = []
        self.removal_template: str | None = None
        self.removal_order_weight: int = 100
        self.case_sensitive: bool = True
        self.allow_in_comment: bool = False
        self.require_exact_match: bool = True

    def define_with(
        self,
        equals: str | frozenset[str] | None = None,
        startswith: str | tuple[str, ...] | None = None,
        endswith: str | tuple[str, ...] | None = None,
        contains: str | tuple[str, ...] | None = None,
        re_search: str | None = None,
    ) -> UnusedObjectRuleBuilder:
        """Add a definition match pattern.

        Args:
            equals: Match lines that equal this string or are in this set.
            startswith: Match lines that start with this string or tuple of strings.
            endswith: Match lines that end with this string or tuple of strings.
            contains: Match lines that contain this string or tuple of strings.
            re_search: Match lines that match this regular expression.

        Returns:
            Self for method chaining.

        """
        self._definition_matches.append(
            MatchRule(
                equals=equals,
                startswith=startswith,
                endswith=endswith,
                contains=contains,
                re_search=re_search,
            )
        )
        return self

    def referenced_in(
        self,
        context_match: dict[str, Any] | list[dict[str, Any]],
        extract_regex: str,
        reference_type: str,
        ignore_patterns: tuple[str, ...] = (),
        capture_group: int = 1,
    ) -> UnusedObjectRuleBuilder:
        """Add a reference pattern.

        Args:
            context_match: Dictionary or list of dictionaries defining MatchRule parameters
                for locating the reference context. Each dict can have keys: equals,
                startswith, endswith, contains, re_search.
            extract_regex: Regular expression to extract the object name from references.
            reference_type: Descriptive type for this reference (e.g., "interface-applied").
            ignore_patterns: Regex patterns for references to ignore.
            capture_group: Which capture group in extract_regex contains the name.

        Returns:
            Self for method chaining.

        """
        # Convert single dict to list
        if isinstance(context_match, dict):
            context_match = [context_match]

        # Build match rules from dictionaries
        match_rules = [MatchRule(**match_dict) for match_dict in context_match]

        self._reference_patterns.append(
            ReferencePattern(
                match_rules=tuple(match_rules),
                extract_regex=extract_regex,
                reference_type=reference_type,
                ignore_patterns=ignore_patterns,
                capture_group=capture_group,
            )
        )
        return self

    def remove_with(self, template: str) -> UnusedObjectRuleBuilder:
        """Set the removal command template.

        Args:
            template: Template string using {name} and other metadata placeholders.

        Returns:
            Self for method chaining.

        """
        self.removal_template = template
        return self

    def with_weight(self, weight: int) -> UnusedObjectRuleBuilder:
        """Set the removal order weight.

        Args:
            weight: Lower weights are removed first.

        Returns:
            Self for method chaining.

        """
        self.removal_order_weight = weight
        return self

    def case_insensitive(self) -> UnusedObjectRuleBuilder:
        """Make object name matching case-insensitive.

        Returns:
            Self for method chaining.

        """
        self.case_sensitive = False
        return self

    def allow_comments(self) -> UnusedObjectRuleBuilder:
        """Allow references in comments to count as valid usage.

        Returns:
            Self for method chaining.

        """
        self.allow_in_comment = True
        return self

    def build(self) -> UnusedObjectRule:
        """Build the UnusedObjectRule.

        Returns:
            The constructed UnusedObjectRule.

        Raises:
            ValueError: If required fields are missing.

        """
        if not self._definition_matches:
            msg = "At least one definition match pattern is required"
            raise ValueError(msg)

        if not self._reference_patterns:
            msg = "At least one reference pattern is required"
            raise ValueError(msg)

        if not self.removal_template:
            msg = "Removal template is required"
            raise ValueError(msg)

        return UnusedObjectRule(
            object_type=self.object_type,
            definition_match=tuple(self._definition_matches),
            reference_patterns=tuple(self._reference_patterns),
            removal_template=self.removal_template,
            removal_order_weight=self.removal_order_weight,
            case_sensitive=self.case_sensitive,
            allow_in_comment=self.allow_in_comment,
            require_exact_match=self.require_exact_match,
        )


def load_unused_object_rules_from_dict(data: dict[str, Any]) -> list[UnusedObjectRule]:
    r"""Load unused object rules from a dictionary structure.

    Args:
        data: Dictionary containing 'rules' key with a list of rule definitions.

    Returns:
        List of UnusedObjectRule instances.

    Example dict structure:
        {
            "rules": [
                {
                    "object_type": "my-acl",
                    "definition_match": [
                        {"startswith": "my-acl "}
                    ],
                    "reference_patterns": [
                        {
                            "match_rules": [
                                {"startswith": "interface "}
                            ],
                            "extract_regex": "apply-acl\\s+(\\S+)",
                            "reference_type": "interface-applied"
                        }
                    ],
                    "removal_template": "no my-acl {name}",
                    "removal_order_weight": 100,
                    "case_sensitive": false
                }
            ]
        }

    """
    rules: list[UnusedObjectRule] = []

    for rule_data in data.get("rules", []):
        # Parse definition matches
        definition_matches = [
            MatchRule(**match) for match in rule_data["definition_match"]
        ]

        # Parse reference patterns
        reference_patterns: list[ReferencePattern] = []
        for ref_pattern_data in rule_data["reference_patterns"]:
            match_rules = [
                MatchRule(**match) for match in ref_pattern_data["match_rules"]
            ]
            reference_patterns.append(
                ReferencePattern(
                    match_rules=tuple(match_rules),
                    extract_regex=ref_pattern_data["extract_regex"],
                    reference_type=ref_pattern_data["reference_type"],
                    ignore_patterns=tuple(ref_pattern_data.get("ignore_patterns", [])),
                    capture_group=ref_pattern_data.get("capture_group", 1),
                )
            )

        # Create the rule
        rule = UnusedObjectRule(
            object_type=rule_data["object_type"],
            definition_match=tuple(definition_matches),
            reference_patterns=tuple(reference_patterns),
            removal_template=rule_data["removal_template"],
            removal_order_weight=rule_data.get("removal_order_weight", 100),
            case_sensitive=rule_data.get("case_sensitive", True),
            allow_in_comment=rule_data.get("allow_in_comment", False),
            require_exact_match=rule_data.get("require_exact_match", True),
        )
        rules.append(rule)

    return rules


def load_unused_object_rules_from_yaml(file_path: str | Path) -> list[UnusedObjectRule]:
    """Load unused object rules from a YAML file.

    Args:
        file_path: Path to the YAML file.

    Returns:
        List of UnusedObjectRule instances.

    Raises:
        ImportError: If PyYAML is not installed.

    """
    if not YAML_AVAILABLE:
        msg = (
            "PyYAML is required to load YAML files. Install it with: pip install pyyaml"
        )
        raise ImportError(msg)

    path = Path(file_path)
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)  # type: ignore[union-attr]

    return load_unused_object_rules_from_dict(data)


def load_unused_object_rules_from_json(file_path: str | Path) -> list[UnusedObjectRule]:
    """Load unused object rules from a JSON file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        List of UnusedObjectRule instances.

    """
    path = Path(file_path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    return load_unused_object_rules_from_dict(data)


def create_simple_rule(  # noqa: PLR0913
    object_type: str,
    definition_pattern: str,
    reference_pattern: str,
    reference_context: str,
    *,
    removal_template: str,
    case_sensitive: bool = True,
    removal_weight: int = 100,
) -> UnusedObjectRule:
    r"""Create a simple unused object rule with common defaults.

    This is a convenience function for the most common case: an object type
    that is defined with a single pattern and referenced in a single context.

    Args:
        object_type: User-defined identifier for the object type.
        definition_pattern: String that object definitions start with.
        reference_pattern: Regex to extract object name from references.
        reference_context: String that reference lines start with.
        removal_template: Template for removal command using {name} (keyword-only).
        case_sensitive: Whether name matching is case-sensitive (keyword-only).
        removal_weight: Removal order weight (keyword-only).

    Returns:
        UnusedObjectRule configured with the specified parameters.

    Example:
        >>> rule = create_simple_rule(
        ...     object_type="my-acl",
        ...     definition_pattern="my-acl ",
        ...     reference_pattern=r"apply-acl\s+(\S+)",
        ...     reference_context="interface ",
        ...     removal_template="no my-acl {name}",
        ...     case_sensitive=False,
        ... )

    """
    return UnusedObjectRule(
        object_type=object_type,
        definition_match=(MatchRule(startswith=definition_pattern),),
        reference_patterns=(
            ReferencePattern(
                match_rules=(MatchRule(startswith=reference_context),),
                extract_regex=reference_pattern,
                reference_type="applied",
            ),
        ),
        removal_template=removal_template,
        removal_order_weight=removal_weight,
        case_sensitive=case_sensitive,
    )
