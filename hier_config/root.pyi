# Type stubs for the Rust-backed implementation in `_hier_config_rust`.
#
# griffe (mkdocstrings) and mypy cannot introspect a compiled extension,
# so this stub is the documented, typed view of the native class. It is
# generated from the live extension surface plus the v3.7.0 docstrings;
# see docs/dev/architecture.md.

from collections.abc import Iterable, Sequence
from typing import Any

from hier_config.base import HConfigBase
from hier_config.child import HConfigChild
from hier_config.models import Dump
from hier_config.platforms.driver_base import HConfigDriverBase

class HConfig(HConfigBase):
    """A class for representing and comparing Cisco like configurations in a
    hierarchical tree data structure.
    """

    def __init__(self, driver: HConfigDriverBase) -> None: ...
    def __deepcopy__(self, _memo: dict[int, Any]) -> HConfig: ...
    def add_ancestor_copy_of(
        self, parent_to_add: HConfigChild
    ) -> HConfig | HConfigChild:
        """Add a copy of the ancestry of parent_to_add to self
        and return the deepest child which is equivalent to parent_to_add.
        """

    def add_children_deep(self, lines: Iterable[str]) -> HConfigChild:
        """Add child instances of HConfigChild deeply."""

    def config_to_get_to(
        self, target: HConfig, delta: HConfig | None = None
    ) -> HConfig:
        """Figures out what commands need to be executed to transition from self to target.
        self is the source data structure(i.e. the running_config),
        target is the destination(i.e. generated_config).
        """

    def deep_copy(self) -> HConfig:
        """Return a copy of this object."""

    def difference(self, target: HConfig) -> HConfig:
        """Creates a new HConfig object with the config from self that is not in target."""

    @property
    def driver(self) -> HConfigDriverBase: ...
    def dump(self) -> Dump:
        """Dump loaded HConfig data."""

    def future(self, config: HConfig, *, prune_empty_branches: bool = False) -> HConfig:
        """EXPERIMENTAL - predict the future config after config is applied to self.

        The quality of this method's output will in part depend on how well
        the OS options are tuned. Ensuring that idempotency rules are accurate is
        especially important.

        With `prune_empty_branches`, sections that the change emptied out are
        removed, matching devices that prune empty stanzas on commit; sections
        that were already empty are kept.
        """

    def instantiate_child(self, text: str) -> HConfigChild: ...
    def merge(self, other: HConfig | Iterable[HConfig]) -> HConfig:
        """Merges other HConfig objects into this one."""

    @property
    def parent(self) -> HConfig: ...
    @property
    def real_indent_level(self) -> int: ...
    @property
    def root(self) -> HConfig:
        """The HConfig object at the base of the tree."""

    def set_order_weight(self) -> HConfig:
        """Sets self.order integer on all children."""

    def unused_objects(self) -> Sequence[HConfigChild]:
        """Yield top-level children that are defined objects with no references.

        Uses ``self.driver.rules.unused_objects`` to identify object definitions,
        extract their names, and search for references across the config tree.
        Objects with zero references are yielded.
        """

    def with_tags(self, tags: Iterable[str]) -> HConfig:
        """Returns a new instance recursively containing children that only have a subset of tags."""
