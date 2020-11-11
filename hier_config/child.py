from __future__ import annotations
from typing import Optional, Set, Union, Iterator, List, TYPE_CHECKING, Type, Iterable
from logging import getLogger

from .base import HConfigBase

if TYPE_CHECKING:
    from .root import HConfig
    from .host import Host


logger = getLogger(__name__)


class HConfigChild(HConfigBase):
    def __init__(self, parent: Union[HConfig, HConfigChild], text: str):
        super().__init__()
        self.parent = parent
        self.host = self.root.host
        self._text: str = text.strip()
        self.real_indent_level: Optional[int] = None
        # The intent is for self.order_weight values to range from 1 to 999
        # with the default weight being 500
        self.order_weight: int = 500
        self._tags: Set[str] = set()
        self.comments: Set[str] = set()
        self.new_in_config: bool = False
        self.instances: List[dict] = []
        self.facts = {}  # To store externally inserted facts

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        """
        Used for when self.text is changed after the object
        is instantiated to rebuild the children dictionary
        """
        self._text = value.strip()
        self.parent.rebuild_children_dict()

    def __repr__(self):
        if self.parent is self.root:
            return "HConfigChild(HConfig, {})".format(self.text)
        return "HConfigChild(HConfigChild, {})".format(self.text)

    def __str__(self):
        return self.text

    def __lt__(self, other):
        return self.order_weight < other.order_weight

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        if (
            self.text != other.text
            or self.tags != other.tags
            or self.comments != other.comments
            or self.new_in_config != other.new_in_config
        ):
            return False
        return super().__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def root(self) -> HConfig:
        """ returns the HConfig object at the base of the tree """
        return self.parent.root

    @property
    def logs(self) -> List[str]:
        return self.root.logs

    @property
    def options(self) -> dict:
        return self.root.options

    @property
    def _child_class(self) -> Type[HConfigChild]:
        return HConfigChild

    def depth(self) -> int:
        """ Returns the distance to the root HConfig object i.e. indent level """
        return self.parent.depth() + 1

    # Consider removing, no internal or other use that I am aware of
    def move(self, new_parent: Union[HConfig, HConfigChild]) -> None:
        """
        move one HConfigChild object to different HConfig parent object

        .. code:: python

            hier1 = HConfig(host=host)
            interface1 = hier1.add_child('interface Vlan2')
            interface1.add_child('ip address 10.0.0.1 255.255.255.252')

            hier2 = Hconfig(host)

            interface1.move(hier2)

        :param new_parent: HConfigChild object -> type list
        :return: None
        """
        new_parent.children.append(self)
        new_parent.rebuild_children_dict()
        self.delete()

    def lineage(self) -> Iterator[HConfigChild]:
        """ Yields the lineage of parent objects, up to but excluding the root """
        yield from self.parent.lineage()
        yield self

    def path(self) -> Iterator[str]:
        """ Return a list of the text instance variables from self.lineage """
        yield from (o.text for o in self.lineage())

    def cisco_style_text(
        self, style: str = "without_comments", tag: Optional[str] = None
    ) -> str:
        """ Return a Cisco style formated line i.e. indentation_level + text ! comments """

        comments = []
        if style == "without_comments":
            pass
        elif style == "merged":
            # count the number of instances that have the tag
            instance_count = 0
            instance_comments: Set[str] = set()
            for instance in self.instances:
                if tag is None or tag in instance["tags"]:
                    instance_count += 1
                    instance_comments.update(instance["comments"])

            # should the word 'instance' be plural?
            word = "instance" if instance_count == 1 else "instances"

            comments.append("{} {}".format(instance_count, word))
            comments.extend(instance_comments)
        elif style == "with_comments":
            comments.extend(self.comments)

        return "{}{}{}".format(
            "  " * (self.depth() - 1),  # render the indentation
            self.text,
            " !{}".format(", ".join(sorted(comments))) if comments else "",
        )

    def delete(self) -> None:
        """ Delete the current object from its parent """

        # TODO find a way to remove this when sub-classing in HCRoot
        self.parent.del_child(self)

    def append_tag(self, tag: str) -> None:
        """
        Add a tag to self._tags on all leaf nodes
        """
        if self.is_branch:
            for child in self.children:
                child.append_tag(tag)
        else:
            self._tags.add(tag)

    def append_tags(self, tags: Union[str, List[str], Set[str]]) -> None:
        """
        Add tags to self._tags on all leaf nodes
        """
        tags = self._to_set(tags)
        if self.is_branch:
            for child in self.children:
                child.append_tags(tags)
        else:
            self._tags.update(tags)

    def remove_tag(self, tag: str) -> None:
        """
        Remove a tag from self._tags on all leaf nodes
        """
        if self.is_branch:
            for child in self.children:
                child.remove_tag(tag)
        else:
            self._tags.remove(tag)

    def remove_tags(self, tags: Union[str, List[str], Set[str]]) -> None:
        """
        Remove tags from self._tags on all leaf nodes
        """
        tags = self._to_set(tags)
        if self.is_branch:
            for child in self.children:
                child.remove_tags(tags)
        else:
            self._tags.difference_update(tags)

    @staticmethod
    def _to_set(items: Union[str, List[str], Set[str]]) -> Set[str]:
        # There's code out in the wild that passes List[str] or str, need to normalize for now
        if isinstance(items, list):
            return set(items)
        if isinstance(items, str):
            return {items}
        # Assume it's a set of str
        return items

    def negate(self) -> HConfigChild:
        """ Negate self.text """
        for rule in self.options["negation_negate_with"]:
            if self.lineage_test(rule):
                self.text = rule["use"]
                return self

        for rule in self.options["negation_default_when"]:
            if self.lineage_test(rule):
                return self._default()

        return self._swap_negation()

    @property
    def is_leaf(self) -> bool:
        """ returns True if there are no children and is not an instance of HConfig """
        return not self.is_branch

    @property
    def is_branch(self) -> bool:
        """ returns True if there are children or is an instance of HConfig """
        return bool(self.children)

    @property
    def tags(self) -> Set[Optional[str]]:
        """ Recursive access to tags on all leaf nodes """
        if self.is_branch:
            found_tags = set()
            for child in self.children:
                found_tags.update(child.tags)
            return found_tags

        return self._tags or {None}

    @tags.setter
    def tags(self, value: Set[str]) -> None:
        """ Recursive access to tags on all leaf nodes """
        if self.is_branch:
            for child in self.children:
                child.tags = value
        else:
            self._tags = value

    def _swap_negation(self) -> HConfigChild:
        """ Swap negation of a self.text """
        if self.text.startswith(self._negation_prefix):
            self.text = self.text[len(self._negation_prefix):]
        else:
            self.text = self._negation_prefix + self.text

        return self

    def _default(self):
        """ Default self.text """
        if self.text.startswith(self._negation_prefix):
            self.text = "default " + self.text[len(self._negation_prefix) :]
        else:
            self.text = "default " + self.text
        return self

    def _idempotent_acl_check(self) -> bool:
        """
        Handle conditional testing to determine if idempotent acl handling for iosxr should be used
        """
        if self.host.os in {"iosxr"}:
            if isinstance(self.parent, HConfigChild):
                acl = ("ipv4 access-list ", "ipv6 access-list ")
                if self.parent.text.startswith(acl):
                    return True
        return False

    def is_idempotent_command(self, other_children: Iterable[HConfigChild]) -> bool:
        """ Determine if self.text is an idempotent change. """
        # Blacklist commands from matching as idempotent
        for rule in self.options["idempotent_commands_blacklist"]:
            if self.lineage_test(rule, True):
                return False

        # Handles idempotent acl entry identification
        if self._idempotent_acl_check():
            if self.host.os in {"iosxr"}:
                self_sn = self.text.split(" ", 1)[0]
                for other_child in other_children:
                    other_sn = other_child.text.split(" ", 1)[0]
                    if self_sn == other_sn:
                        return True

        # Idempotent command identification
        for rule in self.options["idempotent_commands"]:
            if self.lineage_test(rule, True):
                for other_child in other_children:
                    if other_child.lineage_test(rule, True):
                        return True

        return False

    def sectional_overwrite_no_negate_check(self) -> bool:
        """
        Check self's text to see if negation should be handled by
        overwriting the section without first negating it
        """
        for rule in self.options["sectional_overwrite_no_negate"]:
            if self.lineage_test(rule):
                return True
        return False

    def sectional_overwrite_check(self) -> bool:
        """ Determines if self.text matches a sectional overwrite rule """
        for rule in self.options["sectional_overwrite"]:
            if self.lineage_test(rule):
                return True
        return False

    def overwrite_with(
        self,
        other: HConfigChild,
        delta: Union[HConfig, HConfigChild],
        negate: bool = True,
    ) -> HConfigChild:
        """ Deletes delta.child[self.text], adds a deep copy of self to delta """
        if other.children != self.children:
            if negate:
                delta.del_child_by_text(self.text)
                deleted = delta.add_child(self.text).negate()
                deleted.comments.add("dropping section")
            if self.children:
                delta.del_child_by_text(self.text)
                new_item = delta.add_deep_copy_of(self)
                new_item.comments.add("re-create section")
        return delta

    def line_inclusion_test(
        self, include_tags: Set[str], exclude_tags: Set[str]
    ) -> bool:
        """
        Given the line_tags, include_tags, and exclude_tags,
        determine if the line should be included
        """
        include_line = False

        if include_tags:
            include_line = bool(self.tags.intersection(include_tags))
        if exclude_tags and (include_line or not include_tags):
            include_line = not bool(self.tags.intersection(exclude_tags))

        return include_line

    def _duplicate_child_allowed_check(self) -> bool:
        """ Determine if duplicate(identical text) children are allowed under the parent """
        for rule in self.options["parent_allows_duplicate_child"]:
            if self.lineage_test(rule):
                return True
        return False
