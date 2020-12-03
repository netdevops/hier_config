from __future__ import annotations
from typing import (
    Optional,
    List,
    Iterator,
    Dict,
    Tuple,
    Union,
    Set,
    TYPE_CHECKING,
    Type,
)
from logging import getLogger
from abc import ABC, abstractmethod
from functools import cached_property

from . import text_match

if TYPE_CHECKING:
    from .child import HConfigChild
    from .root import HConfig
    from .host import Host

logger = getLogger(__name__)


class HConfigBase(ABC):  # pylint: disable=too-many-public-methods
    def __init__(self) -> None:
        self.children: List[HConfigChild] = []
        self.children_dict: Dict[str, HConfigChild] = {}
        self.host: Host

    def __str__(self) -> str:
        return "\n".join(c.cisco_style_text() for c in self.all_children())

    def __len__(self) -> int:
        return len(list(self.all_children()))

    def __bool__(self) -> bool:
        return bool(self.children)

    def __contains__(self, item: str) -> bool:
        return item in self.children_dict

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HConfigBase):
            return NotImplemented

        if len(self.children) != len(other.children):
            return False

        for self_child, other_child in zip(
            sorted(self.children), sorted(other.children)
        ):
            if self_child != other_child:
                return False

        return True

    @abstractmethod
    def _duplicate_child_allowed_check(self) -> bool:
        pass

    @property
    @abstractmethod
    def options(self) -> dict:
        pass

    @property
    @abstractmethod
    def root(self) -> HConfig:
        pass

    @abstractmethod
    def lineage(self) -> Iterator[HConfigChild]:
        pass

    @abstractmethod
    def depth(self) -> int:
        pass

    @property
    @abstractmethod
    def logs(self) -> List[str]:
        pass

    @property
    @abstractmethod
    def _child_class(self) -> Type[HConfigChild]:
        pass

    def has_children(self) -> bool:
        return bool(self.children)

    def add_children(self, lines: List[str]) -> None:
        """
        Add child instances of HConfigChild

        :param lines: HConfigChild object -> type list
        :return: None
        """
        for line in lines:
            self.add_child(line)

    def add_child(
        self,
        text: str,
        alert_on_duplicate: bool = False,
        idx: Optional[int] = None,
        force_duplicate: bool = False,
    ) -> HConfigChild:
        """ Add a child instance of HConfigChild """

        if idx is None:
            idx = len(self.children)
        # if child does not exist
        if text not in self:
            new_item = self._child_class(self, text)  # type: ignore
            self.children.insert(idx, new_item)
            self.children_dict[text] = new_item
            return new_item
        # if child does exist and is allowed to be installed as a duplicate
        if self._duplicate_child_allowed_check() or force_duplicate:
            new_item = self._child_class(self, text)  # type: ignore
            self.children.insert(idx, new_item)
            self.rebuild_children_dict()
            return new_item

        # If the child is already present and the parent does not allow
        # duplicate children, return the existing child
        # Ignore duplicate remarks in ACLs
        if alert_on_duplicate and not text.startswith("remark "):
            self.logs.append(f"Found a duplicate section: {list(self.path()) + [text]}")
        return self.children_dict[text]

    def path(self) -> Iterator[str]:  # pylint: disable=no-self-use
        yield from ()

    def add_deep_copy_of(
        self, child_to_add: HConfigChild, merged: bool = False
    ) -> HConfigChild:
        """Add a nested copy of a child to self"""
        new_child = self.add_shallow_copy_of(child_to_add, merged=merged)
        for child in child_to_add.children:
            new_child.add_deep_copy_of(child, merged=merged)

        return new_child

    def to_tag_spec(self, tags: Set[str]) -> List[dict]:
        """
        Returns the configuration as a tag spec definition

        This is handy when you have a segment of config and need to
        generate a tag spec to tag configuration in another instance
        """
        tag_spec = []
        for child in self.all_children():
            if not child.children:
                child_spec = [{"equals": t} for t in child.path()]
                tag_spec.append({"section": child_spec, "add_tags": tags})
        return tag_spec

    def del_child_by_text(self, text: str) -> None:
        """ Delete all children with the provided text """
        if text in self.children_dict:
            self.children[:] = [c for c in self.children if c.text != text]
            self.rebuild_children_dict()

    def del_child(self, child: HConfigChild) -> None:
        """Delete a child from self.children and self.children_dict"""
        try:
            self.children.remove(child)
        except ValueError:
            pass
        else:
            self.rebuild_children_dict()

    def all_children_sorted_untagged(self) -> Iterator[HConfigChild]:
        """ Yield all children recursively that are untagged """
        yield from (c for c in self.all_children_sorted() if None in c.tags)

    def all_children_sorted_by_tags(
        self, include_tags: Set[str], exclude_tags: Set[str]
    ) -> Iterator[HConfigChild]:
        """ Yield all children recursively that match include/exlcude tags """
        for child in self.all_children_sorted():
            if child.line_inclusion_test(include_tags, exclude_tags):
                yield child

    def all_children_sorted(self) -> Iterator[HConfigChild]:
        """ Recursively find and yield all children sorted at each hierarchy """
        for child in sorted(self.children):
            yield child
            yield from child.all_children_sorted()

    def all_children_sorted_with_lineage_rules(
        self, rules: List[dict]
    ) -> Iterator[HConfigChild]:
        """ Recursively find and yield all children sorted at each hierarchy given lineage rules """
        yielded = set()
        matched: Set[HConfigChild] = set()
        # pylint: disable=too-many-nested-blocks
        for child in self.all_children_sorted():
            for ancestor in child.lineage():
                if ancestor in matched:
                    yield child
                    yielded.add(child)
                    break
            else:
                for rule in rules:
                    if child.lineage_test(rule, False):
                        matched.add(child)
                        for ancestor in child.lineage():
                            if ancestor in yielded:
                                continue
                            yield ancestor
                            yielded.add(ancestor)
                        break

    def all_children(self) -> Iterator[HConfigChild]:
        """ Recursively find and yield all children at each hierarchy """
        for child in self.children:
            yield child
            yield from child.all_children()

    def get_child(self, test: str, expression: str) -> Optional[HConfigChild]:
        """ Find a child by text_match rule. If it is not found, return None """
        if test == "equals":
            return self.children_dict.get(expression, None)

        try:
            return next(self.get_children(test, expression))
        except StopIteration:
            return None

    def get_child_deep(
        self, test_expression_pairs: List[Tuple[str, str]]
    ) -> Optional[HConfigChild]:
        """
        Find a child recursively with a list of test/expression pairs

        e.g.

        .. code:: python

            result = hier_obj.get_child_deep([('equals', 'control-plane'),
                                              ('equals', 'service-policy input system-cpp-policy')])
        """

        test, expression = test_expression_pairs.pop(0)
        if test == "equals":
            result = self.children_dict.get(expression, None)
            if result and test_expression_pairs:
                return result.get_child_deep(test_expression_pairs)
            return result

        try:
            result = next(self.get_children(test, expression))
        except StopIteration:
            return None
        if result and test_expression_pairs:
            return result.get_child_deep(test_expression_pairs)
        return result

    def get_children(self, test: str, expression: str) -> Iterator[HConfigChild]:
        """ Find all children matching a text_match rule and return them. """
        for child in self.children:
            if text_match.dict_call(test, child.text, expression):
                yield child

    def add_shallow_copy_of(
        self, child_to_add: HConfigChild, merged: bool = False
    ) -> HConfigChild:
        """ Add a nested copy of a child_to_add to self.children """

        new_child = self.add_child(child_to_add.text)

        if merged:
            new_child.instances.append(
                {
                    "hostname": child_to_add.host.hostname,
                    "comments": child_to_add.comments,
                    "tags": child_to_add.tags,
                }
            )
        new_child.comments.update(child_to_add.comments)
        new_child.tags.update(child_to_add.tags)
        new_child.order_weight = child_to_add.order_weight

        return new_child

    def rebuild_children_dict(self) -> None:
        """ Rebuild self.children_dict """
        self.children_dict = {}
        for child in self.children:
            self.children_dict.setdefault(child.text, child)

    def delete_all_children(self) -> None:
        """ Delete all children """
        self.children.clear()
        self.rebuild_children_dict()

    def _with_tags(
        self, tags: Set[str], new_instance: Union[HConfig, HConfigChild]
    ) -> Union[HConfig, HConfigChild]:
        """
        Returns a new instance containing only sub-objects
        with one of the tags in tags
        """
        for child in self.children:
            if tags.intersection(child.tags):
                new_child = new_instance.add_shallow_copy_of(child)
                # pylint: disable=protected-access
                child._with_tags(tags, new_instance=new_child)

        return new_instance

    def _config_to_get_to(
        self, target: Union[HConfig, HConfigChild], delta: Union[HConfig, HConfigChild]
    ) -> Union[HConfig, HConfigChild]:
        """
        Figures out what commands need to be executed to transition from self to target.
        self is the source data structure(i.e. the running_config),
        target is the destination(i.e. generated_config)

        """
        self._config_to_get_to_left(target, delta)
        self._config_to_get_to_right(target, delta)

        return delta

    def _difference(
        self,
        target: Union[HConfig, HConfigChild],
        delta: Union[HConfig, HConfigChild],
    ) -> Union[HConfig, HConfigChild]:
        for self_child in self.children:
            # Not dealing with negations and defaults for now
            if self_child.text.startswith((self._negation_prefix, "default ")):
                continue

            target_child = target.get_child("equals", self_child.text)

            if target_child is None:
                delta.add_deep_copy_of(self_child)
            else:
                delta_child = delta.add_child(self_child.text)
                # pylint: disable=protected-access
                self_child._difference(target_child, delta_child)
                if not delta_child.children:
                    delta_child.delete()

        return delta

    def _config_to_get_to_left(
        self, target: Union[HConfig, HConfigChild], delta: Union[HConfig, HConfigChild]
    ) -> None:
        # find self.children that are not in target.children
        # i.e. what needs to be negated or defaulted
        # Also, find out if another command in self.children will overwrite
        # i.e. be idempotent
        for self_child in self.children:
            if self_child.text in target:
                continue
            if self_child.is_idempotent_command(target.children):
                continue

            # in other but not self
            # add this node but not any children
            deleted = delta.add_child(self_child.text)
            deleted.negate()
            if self_child.children:
                deleted.comments.add(f"removes {len(self_child.children) + 1} lines")

    def _config_to_get_to_right(
        self, target: Union[HConfig, HConfigChild], delta: Union[HConfig, HConfigChild]
    ) -> None:
        # find what would need to be added to source_config to get to self
        for target_child in target.children:
            # if the child exist, recurse into its children
            self_child = self.get_child("equals", target_child.text)
            # the child is absent, add it
            if self_child is None:
                new_item = delta.add_deep_copy_of(target_child)
                # mark the new item and all of its children as new_in_config
                new_item.new_in_config = True
                for child in new_item.all_children():
                    child.new_in_config = True
                if new_item.children:
                    new_item.comments.add("new section")
            else:
                # This creates a new HConfigChild object just in case there are some delta children
                # Not very efficient, think of a way to not do this
                subtree = delta.add_child(target_child.text)
                # pylint: disable=protected-access
                self_child._config_to_get_to(target_child, subtree)
                if not subtree.children:
                    subtree.delete()
                # Do we need to rewrite the child and its children as well?
                elif self_child.sectional_overwrite_check():
                    target_child.overwrite_with(self_child, delta, True)
                elif self_child.sectional_overwrite_no_negate_check():
                    target_child.overwrite_with(self_child, delta, False)

    @cached_property
    def _negation_prefix(self) -> str:
        return str(self.options["negation"]) + " "
