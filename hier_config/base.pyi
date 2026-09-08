# Type stubs for the Rust-backed implementation in `_hier_config_rust`.
#
# griffe (mkdocstrings) and mypy cannot introspect a compiled extension,
# so this stub is the documented, typed view of the native class. It is
# generated from the live extension surface plus the v3.7.0 docstrings;
# see docs/dev/architecture.md.

from collections.abc import Iterable, Iterator, Sequence
from typing import TypeAlias

from hier_config.child import HConfigChild
from hier_config.children import HConfigChildren
from hier_config.models import MatchRule, TextStyle
from hier_config.root import HConfig

SetLikeOfStr: TypeAlias = frozenset[str] | set[str]

class HConfigBase:
    """Abstract base class for the hierarchical configuration tree.

    Both `HConfig` (the root) and `HConfigChild` (individual nodes) inherit from
    this class.  It provides the shared tree-manipulation API: adding, searching,
    and diffing children, as well as the `_future` / `_config_to_get_to` algorithms
    that power `WorkflowRemediation`.
    """

    def __init__(self) -> None: ...
    def __bool__(self) -> bool:
        """True if self else False"""

    def __contains__(self, item: str) -> bool:
        """Return key in self."""

    def __iter__(self) -> Iterator[HConfigChild]:
        """Implement iter(self)."""

    def __len__(self) -> int:
        """Return len(self)."""

    def add_child(
        self,
        text: str,
        *,
        return_if_present: bool = False,
        check_if_present: bool = True,
    ) -> HConfigChild:
        """Add a child instance of HConfigChild."""

    def add_children(self, lines: Iterable[str]) -> None:
        """Add child instances of HConfigChild."""

    def add_deep_copy_of(
        self, child_to_add: HConfigChild, *, merged: bool = False
    ) -> HConfigChild:
        """Add a nested copy of a child to self."""

    def add_shallow_copy_of(
        self, child_to_add: HConfigChild, *, merged: bool = False
    ) -> HConfigChild:
        """Add a nested copy of a child_to_add to self.children."""

    def add_tags(self, tag: str | Iterable[str]) -> None:
        """v4 name for `tags_add()`."""

    def all_children(self) -> Iterator[HConfigChild]:
        """Recursively find and yield all children at each hierarchy."""

    def all_children_sorted(self) -> Sequence[HConfigChild]:
        """Recursively find and yield all children sorted at each hierarchy."""

    def all_children_sorted_by_tags(
        self, include_tags: Iterable[str], exclude_tags: Iterable[str]
    ) -> Sequence[HConfigChild]:
        """Yield all children recursively that match include/exclude tags."""

    @property
    def children(self) -> HConfigChildren:
        """The direct children of this node."""

    def cisco_style_text(
        self, style: TextStyle = "without_comments", tag: str | None = None
    ) -> str:
        """Return a Cisco style formated line i.e. indentation_level + text ! comments."""

    def del_child(self, child: HConfigChild) -> None: ...
    def del_child_by_text(self, text: str) -> None: ...
    def delete_sectional_exit(self) -> None: ...
    @property
    def depth(self) -> int:
        """Distance from the root of the configuration tree."""

    def dump_simple(self, *, sectional_exiting: bool = False) -> tuple[str, ...]: ...
    def get_child(
        self,
        *,
        equals: str | SetLikeOfStr | None = None,
        startswith: str | tuple[str, ...] | None = None,
        endswith: str | tuple[str, ...] | None = None,
        contains: str | tuple[str, ...] | None = None,
        re_search: str | None = None,
    ) -> HConfigChild | None:
        """Find a child by text_match rule. If it is not found, return None."""

    def get_child_deep(self, match_rules: tuple[MatchRule, ...]) -> HConfigChild | None:
        """Find the first child recursively given a tuple of MatchRules."""

    def get_children(
        self,
        *,
        equals: str | SetLikeOfStr | None = None,
        startswith: str | tuple[str, ...] | None = None,
        endswith: str | tuple[str, ...] | None = None,
        contains: str | tuple[str, ...] | None = None,
        re_search: str | None = None,
    ) -> Sequence[HConfigChild]:
        """Find all children matching a text_match rule and return them."""

    def get_children_deep(
        self, match_rules: tuple[MatchRule, ...]
    ) -> Sequence[HConfigChild]:
        """Find children recursively given a tuple of MatchRules."""

    def get_children_object(self) -> HConfigChildren: ...
    def indented_text(
        self, style: TextStyle = "without_comments", tag: str | None = None
    ) -> str:
        """v4 name for `cisco_style_text()`."""

    @property
    def is_branch(self) -> bool:
        """True if there are children or is an instance of HConfig."""

    @property
    def is_leaf(self) -> bool:
        """True if there are no children and is not an instance of HConfig."""

    def lineage(self) -> Sequence[HConfigChild]: ...
    def lines(self, *, sectional_exiting: bool = False) -> Iterable[str]: ...
    def move_child(self, child: HConfigChild) -> None: ...
    def path(self) -> Sequence[str]: ...
    def remove_tags(self, tag: str | Iterable[str]) -> None:
        """v4 name for `tags_remove()`."""

    @property
    def tags(self) -> frozenset[str]:
        """Recursive access to tags on all leaf nodes."""

    @tags.setter
    def tags(self, value: frozenset[str]) -> None: ...
    def tags_add(self, tag: str | Iterable[str]) -> None:
        """Add a tag to self._tags on all leaf nodes."""

    def tags_remove(self, tag: str | Iterable[str]) -> None:
        """Remove a tag from self._tags on all leaf nodes."""

    def to_lines(self, *, sectional_exiting: bool = False) -> tuple[str, ...]:
        """v4 name for `dump_simple()`."""

    def unified_diff(self, target: HConfig | HConfigChild) -> Sequence[str]:
        """Yield unified-diff lines comparing self to target.

        Each yielded string is prefixed with ``-`` (present in self but not
        target) or ``+`` (present in target but not self), followed by the
        appropriate indentation and the command text.

        .. note::
            This algorithm does not account for duplicate child differences
            (e.g. two ``endif`` tokens in an IOS-XR route-policy) and does
            not preserve command order where it matters (e.g. ACLs without
            sequence numbers).  Use sequence numbers in ACL entries when
            order is significant.

        Produces output similar to :func:`difflib.unified_diff`.
        """

    def use_sectional_overwrite(self) -> bool:
        """Determines if self.text matches a sectional overwrite rule."""

    def use_sectional_overwrite_without_negation(self) -> bool:
        """Check self's text to see if negation should be handled by
        overwriting the section without first negating it.
        """
