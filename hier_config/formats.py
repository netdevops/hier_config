"""Structured config format ingestion and rendering (#232).

Maps JSON (e.g. OpenConfig) and XML (e.g. NETCONF payloads) onto the same
`HConfig` tree used by the rest of the library, so structured configs can be
diffed and predicted like CLI text, and renders trees back to those formats.

Mapping rules (JSON):

- object key + scalar   -> leaf ``key <json-encoded scalar>``
- object key + object   -> node ``key`` with the object's members as children
- object key + list of scalars -> one leaf per item, ``key <json item>``
- object key + list of objects -> one node per entry, ``key <json identity>``,
  where the identity is the value of the first ``list_keys`` member present in
  the entry (OpenConfig-style keyed lists); all entry members, including the
  identity leaf, become children.

Mapping rules (XML):

- element -> node ``tag``, or ``tag <json identity>`` when the tag repeats
  among its siblings (identity from the first ``list_keys`` child element)
- attribute -> leaf ``@name <json string>``
- text content -> leaf ``tag <json string>`` for a childless, attribute-less
  element, otherwise a ``#text <json string>`` child leaf
- empty element -> single-word leaf ``tag``

The ``@``/``#text`` line encoding is an implementation detail of the XML
mapping and may change in a future release; treat the trees as opaque between
``hconfig_from_xml`` and ``hconfig_to_xml``.

Both mappings are invertible via ``hconfig_to_json`` / ``hconfig_to_xml``.
Known caveats: a JSON list of scalars with exactly one item renders back as a
bare scalar; empty JSON lists are dropped (the tree has no way to represent
them); duplicate list items or duplicate list-entry identities raise
``DuplicateChildError``.

Remediation between ``hconfig_from_xml`` trees can be rendered as a NETCONF
``edit-config`` payload via ``hconfig_to_netconf_xml`` (deletions become
``nc:operation="delete"`` elements; additions use the default merge
operation). Attribute-level changes cannot be expressed as NETCONF
operations and raise ``InvalidConfigError``.

Remediation between ``hconfig_from_json`` trees can be rendered as a
gNMI-SetRequest-style structure via ``hconfig_to_gnmi_json`` (deletions
become xpath-ish paths with ``[key=value]`` selectors for keyed list
entries; additions render into an ``update`` object using the JSON
mapping above).

The mapping itself lives in the Rust core (``hier_config_core::formats``); this
module is a thin facade so both Python and pure-Rust consumers render
identically. ``testdata/formats/expected.json`` pins the two together.
"""

from __future__ import annotations

from json import dumps
from typing import TYPE_CHECKING, Any, TypeAlias, TypedDict

from _hier_config_rust import (
    formats_from_json,
    formats_from_xml,
    formats_to_gnmi_json,
    formats_to_json,
    formats_to_netconf_xml,
    formats_to_xml,
)

from .registry import resolve_driver

if TYPE_CHECKING:
    from .models import Platform
    from .platforms.driver_base import HConfigDriverBase
    from .root import HConfig

DEFAULT_LIST_KEYS = ("name", "id")

NETCONF_BASE_NS = "urn:ietf:params:xml:ns:netconf:base:1.0"

JsonValue: TypeAlias = (
    "str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None"
)


class GnmiRemediation(TypedDict):
    """gNMI-SetRequest-style remediation: an update tree and delete paths."""

    update: dict[str, JsonValue]
    delete: list[str]


def _keys(list_keys: tuple[str, ...] | None) -> list[str] | None:
    return list(list_keys) if list_keys else None


def hconfig_from_json(
    platform_or_driver: Platform | str | HConfigDriverBase,
    data: str | dict[str, Any],
    *,
    list_keys: tuple[str, ...] | None = None,
) -> HConfig:
    """Create an HConfig from a JSON object (or JSON text)."""
    # Re-encoding a mapping keeps a single parser in the core: member order and
    # scalar formatting then match the JSON-text path exactly.
    source = data if isinstance(data, str) else dumps(data)
    return formats_from_json(
        resolve_driver(platform_or_driver), source, _keys(list_keys)
    )


def hconfig_to_json(config: HConfig, *, indent: int | None = 2) -> str:
    """Render an HConfig built by `hconfig_from_json` back to JSON text."""
    return formats_to_json(config, indent)


def hconfig_from_xml(
    platform_or_driver: Platform | str | HConfigDriverBase,
    source: str,
    *,
    list_keys: tuple[str, ...] | None = None,
) -> HConfig:
    """Create an HConfig from an XML document."""
    return formats_from_xml(
        resolve_driver(platform_or_driver), source, _keys(list_keys)
    )


def hconfig_to_xml(config: HConfig) -> str:
    """Render an HConfig built by `hconfig_from_xml` back to XML text."""
    return formats_to_xml(config)


def hconfig_to_netconf_xml(
    remediation: HConfig,
    *,
    running: HConfig | None = None,
    list_keys: tuple[str, ...] | None = None,
) -> str:
    """Render a remediation between `hconfig_from_xml` trees as NETCONF XML.

    Negated nodes become elements with ``nc:operation="delete"``; everything
    else uses the NETCONF default merge operation. When `running` is given,
    deletions of keyed list entries are expressed by their key leaf (found
    via `list_keys`); without it, deletions fall back to value-bearing leaf
    elements.
    """
    return formats_to_netconf_xml(remediation, running, _keys(list_keys))


def hconfig_to_gnmi_json(
    remediation: HConfig,
    *,
    running: HConfig | None = None,
    list_keys: tuple[str, ...] | None = None,
) -> GnmiRemediation:
    """Render a remediation between `hconfig_from_json` trees as gNMI-style sets.

    Negated nodes become xpath-ish delete paths; everything else renders
    into the `update` object via the JSON mapping. When `running` is given,
    deletions of keyed list entries get `[key=value]` selectors (keys found
    via `list_keys`); without it, deletions fall back to bare leaf paths.
    """
    return formats_to_gnmi_json(remediation, running, _keys(list_keys))
