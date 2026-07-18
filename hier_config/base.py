from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import chain
from logging import getLogger
from typing import TYPE_CHECKING, TypeVar

from .children import HConfigChildren
from .exceptions import DuplicateChildError
from .tree_algorithms import (
    compute_difference,
    compute_future,
    compute_remediation,
    compute_with_tags,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from .child import HConfigChild
    from .models import MatchRule, SetLikeOfStr
    from .platforms.driver_base import HConfigDriverBase
    from .root import HConfig

    _HConfigRootOrChildT = TypeVar("_HConfigRootOrChildT", bound=HConfig | HConfigChild)

logger = getLogger(__name__)


class HConfigBase(ABC):  # noqa: PLR0904
    """Abstract base class for the hierarchical configuration tree.

    Both `HConfig` (the root) and `HConfigChild` (individual nodes) inherit from
    this class.  It provides the shared tree-manipulation API: adding, searching,
    and diffing children, as well as the `_future` / `_remediation` algorithms
    that power `WorkflowRemediation`.
    """

    __slots__ = ("children",)

    def __init__(self) -> None:
        self.children = HConfigChildren()

    def __len__(self) -> int:
        return sum(1 for _ in self.all_children())

    def __bool__(self) -> bool:
        return True

    @abstractmethod
    def __hash__(self) -> int:
        pass

    def __iter__(self) -> Iterator[HConfigChild]:
        return iter(self.children)

    @property
    @abstractmethod
    def root(self) -> HConfig:
        pass

    @property
    @abstractmethod
    def driver(self) -> HConfigDriverBase:
        pass

    @abstractmethod
    def lineage(self) -> Iterator[HConfigChild]:
        pass

    @property
    @abstractmethod
    def depth(self) -> int:
        pass

    def add_children(self, lines: Iterable[str]) -> None:
        """Add child instances of HConfigChild."""
        for line in lines:
            self.add_child(line)

    def add_child(
        self,
        text: str,
        *,
        return_if_present: bool = False,
        check_if_present: bool = True,
    ) -> HConfigChild:
        """Add a child instance of HConfigChild."""
        if not text:
            message = "text was empty"
            raise ValueError(message)

        if check_if_present and (child := self.children.get(text)):
            if self._is_duplicate_child_allowed():
                new_child = self.instantiate_child(text)
                self.children.append(new_child, update_mapping=False)
                return new_child
            if return_if_present:
                return child
            message = f"Found a duplicate section: {(*self.path(), text)}"
            raise DuplicateChildError(message)

        new_child = self.instantiate_child(text)
        self.children.append(new_child)
        return new_child

    def path(self) -> Iterator[str]:  # noqa: PLR6301
        yield from ()

    def add_deep_copy_of(
        self,
        child_to_add: HConfigChild,
        *,
        merged: bool = False,
    ) -> HConfigChild:
        """Add a nested copy of a child to self."""
        new_child = self.add_shallow_copy_of(child_to_add, merged=merged)
        for child in child_to_add.children:
            new_child.add_deep_copy_of(child, merged=merged)

        return new_child

    def all_children_sorted(self) -> Iterator[HConfigChild]:
        """Recursively find and yield all children sorted at each hierarchy."""
        for child in sorted(self.children):
            yield child
            yield from child.all_children_sorted()

    def all_children(self) -> Iterator[HConfigChild]:
        """Recursively find and yield all children at each hierarchy."""
        for child in self.children:
            yield child
            yield from child.all_children()

    def get_child_deep(self, match_rules: tuple[MatchRule, ...]) -> HConfigChild | None:
        """Find the first child recursively given a tuple of MatchRules."""
        return next(self.get_children_deep(match_rules), None)

    def get_children_deep(
        self,
        match_rules: tuple[MatchRule, ...],
    ) -> Iterator[HConfigChild]:
        """Find children recursively given a tuple of MatchRules."""
        rule = match_rules[0]
        remaining_rules = match_rules[1:]
        for child in self.get_children(
            equals=rule.equals,
            startswith=rule.startswith,
            endswith=rule.endswith,
            contains=rule.contains,
            re_search=rule.re_search,
        ):
            if remaining_rules:
                yield from child.get_children_deep(remaining_rules)
            else:
                yield child

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
        return next(
            self.get_children(
                equals=equals,
                startswith=startswith,
                endswith=endswith,
                contains=contains,
                re_search=re_search,
            ),
            None,
        )

    def get_children(
        self,
        *,
        equals: str | SetLikeOfStr | None = None,
        startswith: str | tuple[str, ...] | None = None,
        endswith: str | tuple[str, ...] | None = None,
        contains: str | tuple[str, ...] | None = None,
        re_search: str | None = None,
    ) -> Iterator[HConfigChild]:
        """Find all children matching a text_match rule and return them."""
        # For isinstance(equals, str) only matches, find the first child using children_dict
        children_slice = slice(None, None)
        if (
            isinstance(equals, str)
            and startswith is endswith is contains is re_search is None
        ):
            if child := self.children.get(equals):
                yield child
                children_slice = slice(self.children.index(child) + 1, None)
            else:
                return

        elif (
            isinstance(startswith, (str, tuple))
            and equals is endswith is contains is re_search is None
        ):
            duplicates_allowed = None
            for index, child in enumerate(self.children):
                if child.text.startswith(startswith):
                    yield child
                    if duplicates_allowed is None:
                        duplicates_allowed = self._is_duplicate_child_allowed()
                    if duplicates_allowed:
                        children_slice = slice(index + 1, None)
                        break
            else:
                return

        for child in self.children[children_slice]:
            if child.is_match(
                equals=equals,
                startswith=startswith,
                endswith=endswith,
                contains=contains,
                re_search=re_search,
            ):
                yield child

    def add_shallow_copy_of(
        self,
        child_to_add: HConfigChild,
        *,
        merged: bool = False,
    ) -> HConfigChild:
        """Add a nested copy of a child_to_add to self.children."""
        new_child = self.add_child(child_to_add.text, return_if_present=merged)

        if merged:
            new_child.instances.append(child_to_add.instance)
        new_child.comments.update(child_to_add.comments)
        new_child.order_weight = child_to_add.order_weight
        if child_to_add.is_leaf:
            new_child.add_tags(child_to_add.tags)

        return new_child

    def unified_diff(self, target: HConfig | HConfigChild) -> Iterator[str]:
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
        # if a self child is missing from the target "- self_child.text"
        for self_child in self.children:
            self_iter = iter((f"{self_child.indentation}{self_child.text}",))
            if target_child := target.children.get(self_child.text, None):
                found = self_child.unified_diff(target_child)
                if peek := next(found, None):
                    yield from chain(self_iter, (peek,), found)
            else:
                yield f"{self_child.indentation}- {self_child.text}"
                yield from (
                    f"{c.indentation}- {c.text}"
                    for c in self_child.all_children_sorted()
                )
        # if a target child is missing from self "+ target_child.text"
        for target_child in target.children:
            if target_child.text not in self.children:
                yield f"{target_child.indentation}+ {target_child.text}"
                yield from (
                    f"{c.indentation}+ {c.text}"
                    for c in target_child.all_children_sorted()
                )

    def _future(
        self,
        config: HConfig | HConfigChild,
        future_config: HConfig | HConfigChild,
    ) -> None:
        """Delegates to :func:`hier_config.tree_algorithms.compute_future`."""
        compute_future(self, config, future_config)

    @abstractmethod
    def instantiate_child(self, text: str) -> HConfigChild:
        pass

    @abstractmethod
    def _is_duplicate_child_allowed(self) -> bool:
        pass

    def _with_tags(
        self,
        tags: frozenset[str],
        new_instance: _HConfigRootOrChildT,
    ) -> _HConfigRootOrChildT:
        """Delegates to :func:`hier_config.tree_algorithms.compute_with_tags`."""
        return compute_with_tags(self, tags, new_instance)

    def _remediation(
        self,
        target: _HConfigRootOrChildT,
        delta: _HConfigRootOrChildT,
    ) -> _HConfigRootOrChildT:
        """Delegates to :func:`hier_config.tree_algorithms.compute_remediation`."""
        return compute_remediation(self, target, delta)

    def _difference(
        self,
        target: _HConfigRootOrChildT,
        delta: _HConfigRootOrChildT,
    ) -> _HConfigRootOrChildT:
        """Delegates to :func:`hier_config.tree_algorithms.compute_difference`."""
        return compute_difference(self, target, delta)
