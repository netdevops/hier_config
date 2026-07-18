from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Any

from .base import HConfigBase
from .child import HConfigChild
from .models import Dump, DumpLine, Platform, ReferenceLocation
from .tree_algorithms import (
    compute_difference,
    compute_future,
    compute_remediation,
    compute_with_tags,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from hier_config.platforms.driver_base import HConfigDriverBase

logger = getLogger(__name__)

# Refactoring ideas:
# - Cases of children.index() could be replaced with an identity based approach.


class HConfig(HConfigBase):  # ruff:ignore[too-many-public-methods]
    """A class for representing and comparing Cisco like configurations in a
    hierarchical tree data structure.
    """

    __slots__ = ("_driver",)

    def __init__(self, driver: HConfigDriverBase) -> None:
        super().__init__()
        self._driver = driver

    @classmethod
    def from_text(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        config_text: Path | str = "",
    ) -> HConfig:
        """Create an HConfig from raw configuration text (or a Path to it)."""
        from .constructors import (
            hconfig_from_text,
        )

        return hconfig_from_text(platform_or_driver, config_text)

    @classmethod
    def from_lines(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        lines: list[str] | tuple[str, ...] | str,
    ) -> HConfig:
        """Create an HConfig from pre-split configuration lines (fast load)."""
        from .constructors import (
            hconfig_from_lines,
        )

        return hconfig_from_lines(platform_or_driver, lines)

    @classmethod
    def from_dump(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        dump: Dump,
    ) -> HConfig:
        """Reconstruct an HConfig from a serialized Dump."""
        from .constructors import (
            hconfig_from_dump,
        )

        return hconfig_from_dump(platform_or_driver, dump)

    @classmethod
    def from_json(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        data: str | dict[str, Any],
        *,
        list_keys: tuple[str, ...] = ("name", "id"),
    ) -> HConfig:
        """Create an HConfig from a JSON object or JSON text (#232).

        See `hier_config.formats` for the tree mapping rules. `list_keys`
        names the members that identify entries of keyed lists
        (OpenConfig-style).
        """
        from .formats import hconfig_from_json

        return hconfig_from_json(platform_or_driver, data, list_keys=list_keys)

    @classmethod
    def from_xml(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        source: str,
        *,
        list_keys: tuple[str, ...] = ("name", "id"),
    ) -> HConfig:
        """Create an HConfig from an XML document (#232).

        See `hier_config.formats` for the tree mapping rules. `list_keys`
        names the child elements that identify repeated sibling elements.
        """
        from .formats import hconfig_from_xml

        return hconfig_from_xml(platform_or_driver, source, list_keys=list_keys)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Render a tree built by `from_json` back to JSON text (#232)."""
        from .formats import hconfig_to_json

        return hconfig_to_json(self, indent=indent)

    def to_xml(self) -> str:
        """Render a tree built by `from_xml` back to XML text (#232)."""
        from .formats import hconfig_to_xml

        return hconfig_to_xml(self)

    def __str__(self) -> str:
        return "\n".join(str(c) for c in sorted(self.children))

    def __repr__(self) -> str:
        return (
            f"HConfig(driver={self.driver.__class__.__name__}, lines={self.to_lines()})"
        )

    def __hash__(self) -> int:
        return hash(*self.children)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HConfig):
            return NotImplemented

        return self.children == other.children

    @property
    def driver(self) -> HConfigDriverBase:
        return self._driver

    @property
    def real_indent_level(self) -> int:
        return -1

    @property
    def parent(self) -> HConfig:
        return self

    @property
    def root(self) -> HConfig:
        """The HConfig object at the base of the tree."""
        return self

    @property
    def is_leaf(self) -> bool:
        """True if there are no children and is not an instance of HConfig."""
        return False

    @property
    def is_branch(self) -> bool:
        """True if there are children or is an instance of HConfig."""
        return True

    def instantiate_child(self, text: str) -> HConfigChild:
        return HConfigChild(self, text)

    @property
    def tags(self) -> frozenset[str]:
        """Recursive access to tags on all leaf nodes."""
        found_tags: set[str] = set()
        for child in self.children:
            found_tags.update(child.tags)
        return frozenset(found_tags)

    @tags.setter
    def tags(self, value: frozenset[str]) -> None:
        """Recursive access to tags on all leaf nodes."""
        for child in self.children:
            child.tags = value

    def merge(self, other: HConfig | Iterable[HConfig]) -> HConfig:
        """Merges other HConfig objects into this one."""
        other_configs = (other,) if isinstance(other, HConfig) else other

        for other_config in other_configs:
            for child in other_config.children:
                self.add_deep_copy_of(child, merged=True)

        return self

    def add_children_deep(self, lines: Iterable[str]) -> HConfigChild:
        """Add child instances of HConfigChild deeply."""
        base: HConfig | HConfigChild = self
        for line in lines:
            base = base.add_child(line, return_if_present=True)
        if isinstance(base, HConfig):
            message = "base was an HConfig object for some reason."
            raise TypeError(message)
        return base

    def lineage(self) -> Iterator[HConfigChild]:  # ruff:ignore[no-self-use]
        """Yields the lineage of parent objects, up to but excluding the root."""
        yield from ()

    def lines(self, *, sectional_exiting: bool = False) -> Iterable[str]:
        for child in sorted(self.children):
            yield from child.lines(sectional_exiting=sectional_exiting)

    def to_lines(self, *, sectional_exiting: bool = False) -> tuple[str, ...]:
        return tuple(self.lines(sectional_exiting=sectional_exiting))

    def dump(self) -> Dump:
        """Dump loaded HConfig data."""
        return Dump(
            lines=tuple(
                DumpLine(
                    depth=c.depth,
                    text=c.text,
                    tags=frozenset(c.tags),
                    comments=frozenset(c.comments),
                    new_in_config=c.new_in_config,
                )
                for c in self.all_children_sorted()
            ),
        )

    @property
    def depth(self) -> int:
        """The distance to the root HConfig object i.e. indent level."""
        return 0

    def difference(self, target: HConfig) -> HConfig:
        """Creates a new HConfig object with the config from self that is not in target."""
        return compute_difference(self, target, HConfig(self.driver))

    def remediation(
        self,
        target: HConfig,
        delta: HConfig | None = None,
    ) -> HConfig:
        """Figures out what commands need to be executed to transition from self to target.
        self is the source data structure(i.e. the running_config),
        target is the destination(i.e. generated_config).
        """
        if delta is None:
            delta = HConfig(self.driver)

        return compute_remediation(self, target, delta)

    def add_ancestor_copy_of(
        self,
        parent_to_add: HConfigChild,
    ) -> HConfig | HConfigChild:
        """Add a copy of the ancestry of parent_to_add to self
        and return the deepest child which is equivalent to parent_to_add.
        """
        base: HConfig | HConfigChild = self
        for parent in parent_to_add.lineage():
            base = base.add_shallow_copy_of(parent)

        return base

    def set_order_weight(self) -> HConfig:
        """Sets self.order integer on all children."""
        for child in self.all_children():
            for rule in self.driver.rules.ordering:
                if child.is_lineage_match(rule.match_rules):
                    child.order_weight = rule.weight
        return self

    def future(self, config: HConfig) -> HConfig:
        """EXPERIMENTAL - predict the future config after config is applied to self.

        The quality of this method's output will in part depend on how well
        the OS options are tuned. Ensuring that idempotency rules are accurate is
        especially important.
        """
        future_config = HConfig(self.driver)
        compute_future(self, config, future_config)
        return future_config

    def with_tags(self, tags: Iterable[str]) -> HConfig:
        """Returns a new instance recursively containing children that only have a subset of tags."""
        return compute_with_tags(self, frozenset(tags), HConfig(self.driver))

    def all_children_sorted_by_tags(
        self,
        include_tags: Iterable[str],
        exclude_tags: Iterable[str],
    ) -> Iterator[HConfigChild]:
        """Yield all children recursively that match include/exclude tags."""
        for child in sorted(self.children):
            yield from child.all_children_sorted_by_tags(include_tags, exclude_tags)

    def deep_copy(self) -> HConfig:
        """Return a copy of this object."""
        new_instance = HConfig(self.driver)
        for child in self.children:
            new_instance.add_deep_copy_of(child)
        return new_instance

    def unused_objects(self) -> Iterator[HConfigChild]:
        """Yield top-level children that are defined objects with no references.

        Uses ``self.driver.rules.unused_objects`` to identify object definitions,
        extract their names, and search for references across the config tree.
        Objects with zero references are yielded.
        """
        from re import search as _re_search

        for rule in self.driver.rules.unused_objects:
            seen_names: set[str] = set()
            for definition in self.get_children_deep(rule.match_rules):
                match = _re_search(rule.name_re, definition.text)
                if not match:
                    continue
                name = match.group("name")
                if name in seen_names:
                    continue
                seen_names.add(name)

                if not self._is_object_referenced(name, rule.reference_locations):
                    yield definition

    def _is_object_referenced(
        self,
        name: str,
        reference_locations: tuple[ReferenceLocation, ...],
    ) -> bool:
        """Return True if *name* is found in any reference location."""
        from re import escape as _re_escape
        from re import search as _re_search

        for ref_location in reference_locations:
            pattern = ref_location.reference_re.format(name=_re_escape(name))
            for section in self.get_children_deep(ref_location.match_rules):
                if any(_re_search(pattern, d.text) for d in section.all_children()):
                    return True
        return False

    def _is_duplicate_child_allowed(self) -> bool:
        """Determine if duplicate(identical text) children are allowed at the root.

        A `ParentAllowsDuplicateChildRule` with empty `match_rules` applies to
        the root (#215); children can never match an empty rule because lineage
        matching requires equal lengths.
        """
        return any(
            not rule.match_rules
            for rule in self.driver.rules.parent_allows_duplicate_child
        )
