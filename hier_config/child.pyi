# Type stubs for the Rust-backed implementation in `_hier_config_rust`.
#
# griffe (mkdocstrings) and mypy cannot introspect a compiled extension,
# so this stub is the documented, typed view of the native class. It is
# generated from the live extension surface plus the v3.7.0 docstrings;
# see docs/dev/architecture.md.

from collections.abc import Iterable
from typing import Any, TypeAlias

from hier_config.base import HConfigBase
from hier_config.models import Instance, MatchRule
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.root import HConfig

SetLikeOfStr: TypeAlias = frozenset[str] | set[str]

class HConfigChild(HConfigBase):
    """A single node in the hierarchical configuration tree.

    Each `HConfigChild` holds one configuration line (`text`), an ordered
    collection of its own children, optional tags/comments, and a reference
    back to its parent.  The tree is rooted at an `HConfig` instance; every
    other node is an `HConfigChild`.
    """

    def __init__(self, parent: HConfig | HConfigChild, text: str) -> None: ...
    def __lt__(self, other: HConfigChild) -> bool:
        """Return self<value."""

    def add_children_deep(self, lines: Iterable[str]) -> HConfigChild:
        """Add child instances of HConfigChild deeply."""

    @property
    def comments(self) -> set[str]: ...
    @comments.setter
    def comments(self, value: Iterable[str]) -> None: ...
    def delete(self) -> None:
        """Delete the current object from its parent."""

    @property
    def driver(self) -> HConfigDriverBase: ...
    @property
    def facts(self) -> dict[str, Any]: ...
    @facts.setter
    def facts(self, value: dict[str, Any]) -> None: ...
    @property
    def indentation(self) -> str: ...
    @property
    def instance(self) -> Instance: ...
    @property
    def instances(self) -> list[Instance]: ...
    @instances.setter
    def instances(self, value: Iterable[Instance]) -> None: ...
    def is_idempotent_command(self, other_children: Iterable[HConfigChild]) -> bool:
        """Determine if self.text is an idempotent change."""

    def is_lineage_match(self, rules: tuple[MatchRule, ...]) -> bool:
        """A generic test against a lineage of HConfigChild objects."""

    def is_match(
        self,
        *,
        equals: str | SetLikeOfStr | None = None,
        startswith: str | tuple[str, ...] | None = None,
        endswith: str | tuple[str, ...] | None = None,
        contains: str | tuple[str, ...] | None = None,
        re_search: str | None = None,
    ) -> bool:
        """Return True if ``self.text`` satisfies all supplied criteria.

        All arguments are optional.  When *all* arguments are ``None`` the
        method returns ``True`` (matches everything).  When multiple arguments
        are provided, **all** must match.

        Args:
            equals: Exact string match, or a frozenset of acceptable values.
            startswith: ``str.startswith`` prefix (str or tuple of strs).
            endswith: ``str.endswith`` suffix (str or tuple of strs).
            contains: Substring(s) that must appear in ``self.text``.
            re_search: Regular expression applied via :func:`re.search`.

        Returns:
            ``True`` if every non-``None`` criterion is satisfied.
        """

    def line_inclusion_test(
        self, include_tags: Iterable[str], exclude_tags: Iterable[str]
    ) -> bool:
        """Given the line_tags, include_tags, and exclude_tags,
        determine if the line should be included.
        """

    def move(self, new_parent: HConfig | HConfigChild) -> None:
        """Move one HConfigChild object to different HConfig parent object.

        .. code:: python

            hier1 = config_for_platform(host.platform)
            interface1 = hier1.add_child('interface Vlan2')
            interface1.add_child('ip address 10.0.0.1 255.255.255.252')

            hier2 = Hconfig(host)

            interface1.move(hier2)

        :param new_parent: HConfigChild object -> type list
        """

    def negate(self) -> HConfigChild:
        """Negate self.text using driver-specific negation rules.

        Negation is resolved in the following priority order:

        1. ``negate_with`` rule — replaces ``self.text`` with a custom
           negation string defined in the driver (e.g. ``no ip route``).
        2. ``negation_default_when`` rule — rewrites the command to its
           ``default`` form (e.g. ``no shutdown`` → ``default shutdown``).
        3. ``negation_sub`` rule — applies a regex substitution to the
           negated text (e.g. truncating after a specific token).
        4. ``swap_negation`` — toggles the negation prefix/declaration
           prefix (e.g. ``shutdown`` ↔ ``no shutdown``).

        Returns self so that callers can chain further operations.
        """

    @property
    def new_in_config(self) -> bool: ...
    @new_in_config.setter
    def new_in_config(self, value: bool) -> None: ...
    @property
    def order_weight(self) -> int: ...
    @order_weight.setter
    def order_weight(self, value: int) -> None: ...
    def overwrite_with(
        self,
        target: HConfigChild,
        delta: HConfig | HConfigChild,
        *,
        negate: bool = True,
    ) -> None:
        """Overwrite self's section in delta with a deep copy of target.

        When the children of self and target differ, this method mutates
        ``delta`` in-place: the existing entry for ``self.text`` is negated
        (if ``negate=True``) or simply deleted (if ``negate=False``), and a
        fresh deep copy of ``target`` is appended.  A ``"re-create section"``
        comment is attached to the new entry, and a ``"dropping section"``
        comment is added to the negated entry when applicable.

        Used by :meth:`_config_to_get_to_right` when a sectional-overwrite
        rule is active for ``self.text``.
        """

    @property
    def parent(self) -> HConfig | HConfigChild: ...
    @parent.setter
    def parent(self, value: HConfig | HConfigChild) -> None: ...
    @property
    def real_indent_level(self) -> int: ...
    @real_indent_level.setter
    def real_indent_level(self, value: int) -> None: ...
    @property
    def root(self) -> HConfig:
        """The HConfig object at the base of the tree."""

    @property
    def sectional_exit(self) -> str | None: ...
    @property
    def sectional_exit_text_parent_level(self) -> bool: ...
    @property
    def text(self) -> str: ...
    @text.setter
    def text(self, value: str) -> None: ...
    @property
    def text_without_negation(self) -> str: ...
    def use_default_for_negation(self, config: HConfigChild) -> bool: ...
