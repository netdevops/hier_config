# Type stubs for the Rust-backed implementation in `_hier_config_rust`.
#
# griffe (mkdocstrings) and mypy cannot introspect a compiled extension,
# so this stub is the documented, typed view of the native class. It is
# generated from the live extension surface plus the v3.7.0 docstrings;
# see docs/dev/architecture.md.

from collections.abc import Iterable, Sequence
from os import PathLike
from typing import Any

from hier_config.base import HConfigBase
from hier_config.child import HConfigChild
from hier_config.models import Dump, DumpLine, Platform
from hier_config.platforms.driver_base import HConfigDriverBase
from hier_config.tree_algorithms import FutureReport

class HConfig(HConfigBase):
    """A class for representing and comparing Cisco like configurations in a
    hierarchical tree data structure.
    """

    def __init__(self, driver: HConfigDriverBase) -> None: ...
    def __deepcopy__(self, _memo: dict[int, Any]) -> HConfig: ...
    def __eq__(self, other: object) -> bool:
        """Return self==value."""

    def __hash__(self) -> int:
        """Return hash(self)."""

    def _load_fast_native(self, lines: Iterable[str], run_post_load: bool) -> None:
        """Parses pre-formatted `lines` into this tree inside a single FFI call.

        Mirrors [`Self::_load_native`] but applies only `per_line_sub` rules, matching
        the semantics of `get_hconfig_fast_load`.

        `lines` may be a single `str` — which is split on line boundaries in Rust,
        avoiding any per-line marshalling — or any iterable of `str`.

        # Errors

        Returns an error if `lines` is not a `str` or an iterable of `str`, or if a
        line cannot be inserted into the tree.
        """

    def _load_file_native(self, path: str, run_post_load: bool) -> None:
        """Reads and parses an on-disk config file into this tree inside a single FFI call.

        Reads the file directly via `std::fs::read_to_string` with the GIL released,
        avoiding intermediate Python `str` allocations.
        """

    def _load_from_dump_native(self, lines: Iterable[DumpLine]) -> None:
        """Reconstructs the tree structure from a [`Dump`] model inside a single FFI call.

        Unpacks line attributes and delegates tree reconstruction to native Rust in O(N)
        without per-node Python FFI round-trips.
        """

    def _load_native(self, config_text: str, run_post_load: bool) -> None:
        """Parses a raw configuration string entirely in Rust.

        Runs `full_text_sub`, the platform preprocessor, the line-by-line parse and
        sectional-exit removal in a single FFI call with the GIL released, allocating
        no Python objects. When `run_post_load` is true the natively-implemented
        post-load callbacks for the platform are applied as well; callers pass false
        when a custom driver supplies its own Python callbacks.
        """

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

    @classmethod
    def from_dump(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        dump: Dump,
    ) -> HConfig:
        """Reconstruct an `HConfig` from a serialized `Dump`."""

    @classmethod
    def from_json(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        data: str | dict[str, Any],
        *,
        list_keys: tuple[str, ...] | None = None,
    ) -> HConfig:
        """Create an `HConfig` from a JSON object or JSON text."""

    @classmethod
    def from_lines(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        lines: Iterable[str],
    ) -> HConfig:
        """Create an `HConfig` from pre-split configuration lines (fast load)."""

    @classmethod
    def from_text(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        config_text: str | PathLike[str] | None = None,
    ) -> HConfig:
        """Create an `HConfig` from raw configuration text (or a Path to it)."""

    @classmethod
    def from_xml(
        cls,
        platform_or_driver: Platform | str | HConfigDriverBase,
        source: str,
        *,
        list_keys: tuple[str, ...] | None = None,
    ) -> HConfig:
        """Create an `HConfig` from an XML document."""

    def future(self, config: HConfig, *, prune_empty_branches: bool = False) -> HConfig:
        """EXPERIMENTAL - predict the future config after config is applied to self.

        The quality of this method's output will in part depend on how well
        the OS options are tuned. Ensuring that idempotency rules are accurate is
        especially important.

        With `prune_empty_branches`, sections that the change emptied out are
        removed, matching devices that prune empty stanzas on commit; sections
        that were already empty are kept.
        """

    def future_with_report(
        self,
        config: HConfig,
        *,
        prune_empty_branches: bool = False,
    ) -> tuple[HConfig, FutureReport]:
        """Like `future()`, but also reports how negations resolved."""

    def instantiate_child(self, text: str) -> HConfigChild: ...
    def merge(self, other: HConfig | Iterable[HConfig]) -> HConfig:
        """Merges other HConfig objects into this one."""

    @property
    def parent(self) -> HConfig: ...
    @property
    def real_indent_level(self) -> int: ...
    def remediation(self, target: HConfig, delta: HConfig | None = None) -> HConfig:
        """v4 name for `config_to_get_to()`."""

    @property
    def root(self) -> HConfig:
        """The HConfig object at the base of the tree."""

    def set_order_weight(self) -> HConfig:
        """Sets self.order integer on all children."""

    def to_json(self, *, indent: int | None = 2) -> str:
        """Render a tree built by `from_json` back to JSON text."""

    def to_xml(self, *, indent: int | None = 2) -> str:
        """Render a tree built by `from_xml` back to XML text."""

    def unused_objects(self) -> Sequence[HConfigChild]:
        """Yield top-level children that are defined objects with no references.

        Uses ``self.driver.rules.unused_objects`` to identify object definitions,
        extract their names, and search for references across the config tree.
        Objects with zero references are yielded.
        """

    def with_tags(self, tags: Iterable[str]) -> HConfig:
        """Returns a new instance recursively containing children that only have a subset of tags."""
