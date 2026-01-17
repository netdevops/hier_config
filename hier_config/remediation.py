"""Unused object remediation functionality for hier_config.

This module provides functionality to identify and generate remediation
commands for unused configuration objects (ACLs, prefix-lists, route-maps, etc.)
that are defined but never referenced in the configuration.
"""

from __future__ import annotations

import re
from logging import getLogger
from typing import TYPE_CHECKING

from hier_config.models import (
    UnusedObjectAnalysis,
    UnusedObjectDefinition,
    UnusedObjectReference,
    UnusedObjectRule,
)
from hier_config.root import HConfig

if TYPE_CHECKING:
    from hier_config.models import ReferencePattern

logger = getLogger(__name__)


class UnusedObjectRemediator:
    """Identifies and generates remediation for unused configuration objects.

    This class analyzes a configuration to find objects that are defined
    but never referenced, generating commands to safely remove them.

    Attributes:
        config: The HConfig object to analyze.
        driver: The driver associated with the config.
        rules: List of UnusedObjectRule instances from the driver.

    """

    def __init__(self, config: HConfig) -> None:
        """Initialize the remediator.

        Args:
            config: HConfig object to analyze for unused objects.

        """
        self.config = config
        self.driver = config.driver
        self.rules = self.driver.get_unused_object_rules()

    def analyze(self) -> UnusedObjectAnalysis:
        """Performs complete analysis of unused objects.

        Returns:
            UnusedObjectAnalysis containing all defined, referenced,
            and unused objects, along with removal commands.

        """
        defined_objects: dict[str, list[UnusedObjectDefinition]] = {}
        referenced_objects: dict[str, list[UnusedObjectReference]] = {}
        unused_objects: dict[str, list[UnusedObjectDefinition]] = {}
        all_removal_commands: list[str] = []

        for rule in self.rules:
            # Find all definitions
            definitions = self.find_definitions(rule)
            defined_objects[rule.object_type] = definitions

            # Find all references
            references = self.find_references(rule)
            referenced_objects[rule.object_type] = references

            # Identify unused objects
            unused = self.identify_unused(definitions, references, rule)
            unused_objects[rule.object_type] = unused

            # Generate removal commands
            removal_commands = self._generate_removal_commands(unused, rule)
            all_removal_commands.extend(removal_commands)

        # Convert lists to tuples for immutability
        total_defined = sum(len(defs) for defs in defined_objects.values())
        total_unused = sum(len(unused) for unused in unused_objects.values())

        return UnusedObjectAnalysis(
            defined_objects={k: tuple(v) for k, v in defined_objects.items()},
            referenced_objects={k: tuple(v) for k, v in referenced_objects.items()},
            unused_objects={k: tuple(v) for k, v in unused_objects.items()},
            total_defined=total_defined,
            total_unused=total_unused,
            removal_commands=tuple(all_removal_commands),
        )

    def find_definitions(self, rule: UnusedObjectRule) -> list[UnusedObjectDefinition]:
        """Finds all definitions of a specific object type.

        Args:
            rule: UnusedObjectRule defining the object type to find.

        Returns:
            List of UnusedObjectDefinition instances found in the config.

        """
        definitions: list[UnusedObjectDefinition] = []

        for child in self.config.all_children():
            # Check if this child matches any of the definition patterns
            for match_rule in rule.definition_match:
                if child.is_match(
                    equals=match_rule.equals,
                    startswith=match_rule.startswith,
                    endswith=match_rule.endswith,
                    contains=match_rule.contains,
                    re_search=match_rule.re_search,
                ):
                    # Extract the object name
                    name = self.extract_object_name(child.text)
                    if name:
                        # Build the lineage path
                        lineage = tuple(c.text for c in child.lineage())

                        # Extract any metadata (like ACL type)
                        metadata = self.extract_metadata(child.text)

                        definitions.append(
                            UnusedObjectDefinition(
                                object_type=rule.object_type,
                                name=name,
                                definition_location=lineage,
                                metadata=metadata,
                            )
                        )
                    break

        logger.debug("Found %d definitions for %s", len(definitions), rule.object_type)
        return definitions

    def find_references(self, rule: UnusedObjectRule) -> list[UnusedObjectReference]:
        """Finds all references to objects of a specific type.

        Args:
            rule: UnusedObjectRule defining the object type and reference patterns.

        Returns:
            List of UnusedObjectReference instances found in the config.

        """
        references: list[UnusedObjectReference] = []

        for ref_pattern in rule.reference_patterns:
            refs = self._find_references_for_pattern(rule, ref_pattern)
            references.extend(refs)

        logger.debug("Found %d references for %s", len(references), rule.object_type)
        return references

    def _find_references_for_pattern(
        self, rule: UnusedObjectRule, ref_pattern: ReferencePattern
    ) -> list[UnusedObjectReference]:
        """Finds references matching a specific reference pattern.

        Args:
            rule: The unused object rule.
            ref_pattern: The reference pattern to match.

        Returns:
            List of UnusedObjectReference instances.

        """
        references: list[UnusedObjectReference] = []

        for child in self.config.all_children():
            # Check if this child's lineage matches the reference pattern
            if child.is_lineage_match(ref_pattern.match_rules):
                # Extract the object name from the reference
                name = self.extract_reference_name(child.text, ref_pattern)
                if name:
                    # Check ignore patterns
                    if self.should_ignore_reference(name, ref_pattern):
                        continue

                    lineage = tuple(c.text for c in child.lineage())
                    references.append(
                        UnusedObjectReference(
                            object_type=rule.object_type,
                            name=name,
                            reference_location=lineage,
                            reference_type=ref_pattern.reference_type,
                        )
                    )

        return references

    @staticmethod
    def identify_unused(
        definitions: list[UnusedObjectDefinition],
        references: list[UnusedObjectReference],
        rule: UnusedObjectRule,
    ) -> list[UnusedObjectDefinition]:
        """Determines which defined objects are unused.

        Args:
            definitions: List of all object definitions.
            references: List of all object references.
            rule: The unused object rule for comparison logic.

        Returns:
            List of UnusedObjectDefinition instances that are unused.

        """
        # Build a set of referenced object names
        referenced_names: set[str] = set()
        for ref in references:
            if rule.case_sensitive:
                referenced_names.add(ref.name)
            else:
                referenced_names.add(ref.name.lower())

        # Find definitions that are not referenced
        unused: list[UnusedObjectDefinition] = []
        for defn in definitions:
            compare_name = defn.name if rule.case_sensitive else defn.name.lower()
            if compare_name not in referenced_names:
                unused.append(defn)

        logger.debug(
            "Identified %d unused objects for %s", len(unused), rule.object_type
        )
        return unused

    def generate_removal_config(
        self, unused_objects: list[UnusedObjectDefinition], rule: UnusedObjectRule
    ) -> HConfig:
        """Generates configuration to remove unused objects.

        Args:
            unused_objects: List of unused object definitions.
            rule: The unused object rule with removal template.

        Returns:
            HConfig object with removal commands.

        """
        removal_config = HConfig(self.driver)

        for obj in unused_objects:
            # Generate removal command from template
            removal_cmd = self.format_removal_command(obj, rule)
            if removal_cmd:
                # Add the command to the removal config
                child = removal_config.add_child(removal_cmd)
                child.order_weight = rule.removal_order_weight

        return removal_config

    def _generate_removal_commands(
        self, unused_objects: list[UnusedObjectDefinition], rule: UnusedObjectRule
    ) -> list[str]:
        """Generates removal command strings.

        Args:
            unused_objects: List of unused object definitions.
            rule: The unused object rule with removal template.

        Returns:
            List of removal command strings.

        """
        commands: list[str] = []
        for obj in unused_objects:
            cmd = self.format_removal_command(obj, rule)
            if cmd:
                commands.append(cmd)
        return commands

    @staticmethod
    def _extract_access_list_name(parts: list[str]) -> str | None:
        """Extract name from access-list definition."""
        # ip access-list [standard|extended] NAME (IOS format)
        if len(parts) >= 4 and parts[0] == "ip" and parts[1] == "access-list":
            acl_type_set = {"standard", "extended"}
            if parts[2] in acl_type_set:
                return parts[3]
        # ip access-list NAME (NX-OS format - no standard/extended keyword)
        if len(parts) >= 3 and parts[0] == "ip" and parts[1] == "access-list":
            return parts[2]
        # ipv6 access-list NAME
        if len(parts) >= 3 and parts[0] == "ipv6" and parts[1] == "access-list":
            return parts[2]
        return None

    @staticmethod
    def _extract_prefix_list_name(parts: list[str], text: str) -> str | None:
        """Extract name from prefix-list definition."""
        # ip prefix-list NAME or ipv6 prefix-list NAME or prefix-set NAME
        if "prefix-list" in text:
            idx = parts.index("prefix-list")
            if len(parts) > idx + 1:
                return parts[idx + 1]
        if "prefix-set" in text:
            idx = parts.index("prefix-set")
            if len(parts) > idx + 1:
                return parts[idx + 1]
        return None

    @staticmethod
    def _extract_vrf_name(parts: list[str]) -> str | None:
        """Extract name from VRF definition."""
        # vrf definition NAME
        if "definition" in parts:
            idx = parts.index("definition")
            if len(parts) > idx + 1:
                return parts[idx + 1]
        return None

    @staticmethod
    def extract_object_name(text: str) -> str | None:  # noqa: C901, PLR0911
        """Extracts the object name from a definition line.

        Args:
            text: The configuration line text.

        Returns:
            The extracted object name, or None if extraction failed.

        """
        # Strategy: parse based on common patterns
        # For most objects, the name is the second token
        parts = text.split()
        if len(parts) < 2:
            return None

        # Handle access-lists
        if "access-list" in text:
            return UnusedObjectRemediator._extract_access_list_name(parts)

        # Handle prefix-lists
        if "prefix-list" in text or "prefix-set" in text:
            return UnusedObjectRemediator._extract_prefix_list_name(parts, text)

        # Handle route-maps
        if text.startswith("route-map "):
            return parts[1]

        # Handle class-maps
        if text.startswith("class-map "):
            match_type_set = {"match-any", "match-all"}
            if len(parts) >= 3 and parts[1] in match_type_set:
                return parts[2]
            return parts[1]

        # Handle policy-maps
        if text.startswith("policy-map "):
            return parts[1]

        # Handle VRFs
        if "vrf" in text and "definition" in text:
            return UnusedObjectRemediator._extract_vrf_name(parts)

        # Handle object-groups
        if text.startswith("object-group ") and len(parts) >= 3:
            return parts[2]

        # Handle as-path-sets
        if text.startswith("as-path-set "):
            return parts[1]

        # Handle community-sets
        if text.startswith("community-set "):
            return parts[1]

        # Handle IPv6 general-prefix
        if text.startswith("ipv6 general-prefix "):
            return parts[2]

        # Default: return the second token
        return parts[1] if len(parts) >= 2 else None

    @staticmethod
    def extract_reference_name(text: str, ref_pattern: ReferencePattern) -> str | None:
        """Extracts the referenced object name using the pattern's regex.

        Args:
            text: The configuration line text.
            ref_pattern: The reference pattern with extraction regex.

        Returns:
            The extracted reference name, or None if extraction failed.

        """
        match = re.search(ref_pattern.extract_regex, text)
        if match and len(match.groups()) >= ref_pattern.capture_group:
            return match.group(ref_pattern.capture_group)
        return None

    @staticmethod
    def extract_metadata(text: str) -> dict[str, str]:
        """Extracts metadata from the definition line.

        Args:
            text: The configuration line text.

        Returns:
            Dictionary of metadata key-value pairs.

        """
        metadata: dict[str, str] = {}

        # Extract ACL type (standard/extended)
        if "access-list" in text:
            parts = text.split()
            if "standard" in parts:
                metadata["acl_type"] = "standard"
            elif "extended" in parts:
                metadata["acl_type"] = "extended"

        # Extract class-map match type
        if text.startswith("class-map "):
            parts = text.split()
            match_type_set = {"match-any", "match-all"}
            if len(parts) >= 2 and parts[1] in match_type_set:
                metadata["match_type"] = parts[1]

        # Extract object-group type
        if text.startswith("object-group "):
            parts = text.split()
            if len(parts) >= 2:
                metadata["group_type"] = parts[1]

        return metadata

    @staticmethod
    def format_removal_command(
        obj: UnusedObjectDefinition, rule: UnusedObjectRule
    ) -> str | None:
        """Formats the removal command using the template.

        Args:
            obj: The unused object definition.
            rule: The unused object rule with removal template.

        Returns:
            The formatted removal command, or None if formatting failed.

        """
        template = rule.removal_template

        # Build replacement dictionary
        replacements = {
            "name": obj.name,
            "object_type": obj.object_type,
            **obj.metadata,
        }

        # Replace placeholders in template
        try:
            return template.format(**replacements)
        except KeyError as e:
            logger.warning("Missing template variable %s for %s", e, obj.name)
            return None

    @staticmethod
    def should_ignore_reference(name: str, ref_pattern: ReferencePattern) -> bool:
        """Checks if a reference should be ignored.

        Args:
            name: The referenced object name.
            ref_pattern: The reference pattern with ignore patterns.

        Returns:
            True if the reference should be ignored, False otherwise.

        """
        return any(
            re.search(ignore_pattern, name)
            for ignore_pattern in ref_pattern.ignore_patterns
        )
