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
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # ruff:ignore[suspicious-xml-etree-import]
from collections import Counter
from json import JSONDecodeError, dumps, loads
from typing import TYPE_CHECKING, Any, NamedTuple, TypeAlias, TypedDict, cast

from .exceptions import InvalidConfigError
from .registry import resolve_driver
from .root import HConfig

if TYPE_CHECKING:
    from .base import HConfigBase
    from .child import HConfigChild
    from .models import Platform
    from .platforms.driver_base import HConfigDriverBase

DEFAULT_LIST_KEYS = ("name", "id")

NETCONF_BASE_NS = "urn:ietf:params:xml:ns:netconf:base:1.0"

JsonValue: TypeAlias = (
    "str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None"
)


class GnmiRemediation(TypedDict):
    """gNMI-SetRequest-style remediation: an update tree and delete paths."""

    update: dict[str, JsonValue]
    delete: list[str]


def hconfig_from_json(
    platform_or_driver: Platform | str | HConfigDriverBase,
    data: str | dict[str, Any],
    *,
    list_keys: tuple[str, ...] | None = None,
) -> HConfig:
    """Create an HConfig from a JSON object (or JSON text)."""
    if isinstance(data, str):
        try:
            data = loads(data)
        except JSONDecodeError as exc:
            message = f"The config is not valid JSON: {exc}"
            raise InvalidConfigError(message) from exc
    if not isinstance(data, dict):
        message = "The top-level JSON value must be an object"
        raise InvalidConfigError(message)

    config = HConfig(resolve_driver(platform_or_driver))
    _json_into(
        config,
        cast("dict[str, JsonValue]", data),
        list_keys or DEFAULT_LIST_KEYS,
    )
    return config


def hconfig_to_json(config: HConfig, *, indent: int | None = 2) -> str:
    """Render an HConfig built by `hconfig_from_json` back to JSON text."""
    return dumps(_node_to_json_object(config), indent=indent)


def hconfig_from_xml(
    platform_or_driver: Platform | str | HConfigDriverBase,
    source: str,
    *,
    list_keys: tuple[str, ...] | None = None,
) -> HConfig:
    """Create an HConfig from an XML document."""
    try:
        root_element = ET.fromstring(source)  # ruff:ignore[suspicious-xml-element-tree-usage]
    except ET.ParseError as exc:
        message = f"The config is not valid XML: {exc}"
        raise InvalidConfigError(message) from exc

    config = HConfig(resolve_driver(platform_or_driver))
    _xml_element_into(config, root_element, list_keys or DEFAULT_LIST_KEYS)
    return config


def hconfig_to_xml(config: HConfig) -> str:
    """Render an HConfig built by `hconfig_from_xml` back to XML text."""
    if len(config.children) != 1:
        message = "XML rendering requires a single root node"
        raise InvalidConfigError(message)
    root_node = next(iter(config.children))
    element = _node_to_xml_element(root_node)
    ET.indent(element)
    return ET.tostring(element, encoding="unicode")


def _json_key(key: object) -> str:
    if not isinstance(key, str) or not key or any(char.isspace() for char in key):
        message = f"Unsupported JSON key: {key!r} (keys must be non-empty strings without whitespace)"
        raise InvalidConfigError(message)
    return key


def _json_into(
    parent: HConfigBase,
    mapping: dict[str, JsonValue],
    list_keys: tuple[str, ...],
) -> None:
    for raw_key, value in mapping.items():
        key = _json_key(raw_key)
        if isinstance(value, dict):
            _json_into(parent.add_child(key), value, list_keys)
        elif isinstance(value, list):
            _json_list_into(parent, key, value, list_keys)
        else:
            parent.add_child(f"{key} {dumps(value)}")


def _json_list_into(
    parent: HConfigBase,
    key: str,
    items: list[JsonValue],
    list_keys: tuple[str, ...],
) -> None:
    for item in items:
        if isinstance(item, dict):
            identity_key = next((k for k in list_keys if k in item), None)
            if identity_key is None:
                message = (
                    f"List entries under {key!r} need one of {list_keys} to"
                    " identify them; pass list_keys= to name the identifying"
                    " member"
                )
                raise InvalidConfigError(message)
            entry = parent.add_child(f"{key} {dumps(item[identity_key])}")
            _json_into(entry, item, list_keys)
        elif isinstance(item, list):
            message = f"Nested JSON arrays are not supported (under {key!r})"
            raise InvalidConfigError(message)
        else:
            parent.add_child(f"{key} {dumps(item)}")


def _leaf_value(raw: str) -> JsonValue:
    try:
        return cast("JsonValue", loads(raw))
    except JSONDecodeError:
        return raw


def _store_json_member(
    result: dict[str, JsonValue],
    key: str,
    value: JsonValue,
    *,
    force_list: bool,
) -> None:
    if key in result:
        existing = result[key]
        if isinstance(existing, list):
            existing.append(value)
        else:
            result[key] = [existing, value]
    elif force_list:
        result[key] = [value]
    else:
        result[key] = value


def _node_to_json_object(node: HConfigBase) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for child in node.children:
        words = child.text.split(maxsplit=1)
        key = words[0]
        if child.children:
            # A multi-word branch is a keyed list entry; grouped into a list.
            _store_json_member(
                result,
                key,
                _node_to_json_object(child),
                force_list=len(words) > 1,
            )
        elif len(words) > 1:
            _store_json_member(result, key, _leaf_value(words[1]), force_list=False)
        else:
            # from_json produces a single-word childless node only for an
            # empty object (scalar leaves always carry a value word).
            _store_json_member(result, key, {}, force_list=False)
    return result


def _xml_identity_suffix(
    element: ET.Element,
    list_keys: tuple[str, ...],
    *,
    required: bool,
) -> str:
    for key in list_keys:
        if (identity := element.find(key)) is not None and identity.text:
            return f" {dumps(identity.text.strip())}"
    if required:
        message = (
            f"Repeated <{element.tag}> elements need a child element named one"
            f" of {list_keys} to identify them; pass list_keys= to name the"
            " identifying element"
        )
        raise InvalidConfigError(message)
    return ""


def _xml_element_into(
    parent: HConfigBase,
    element: ET.Element,
    list_keys: tuple[str, ...],
    *,
    node_suffix: str = "",
) -> None:
    node = parent.add_child(f"{element.tag}{node_suffix}")
    for name, value in element.attrib.items():
        node.add_child(f"@{name} {dumps(value)}")
    if text := (element.text or "").strip():
        node.add_child(f"#text {dumps(text)}")

    tag_counts = Counter(child.tag for child in element)
    for child in element:
        if not (len(child) or child.attrib):
            child_text = (child.text or "").strip()
            node.add_child(
                f"{child.tag} {dumps(child_text)}" if child_text else child.tag
            )
        else:
            # Key the node whenever an identifying child exists so entries get
            # the same text regardless of sibling count - configs with
            # different entry counts must still diff surgically. An identity
            # is only mandatory when the tag actually repeats.
            suffix = _xml_identity_suffix(
                child,
                list_keys,
                required=tag_counts[child.tag] > 1,
            )
            _xml_element_into(node, child, list_keys, node_suffix=suffix)


def _node_to_xml_element(node: HConfigChild) -> ET.Element:
    words = node.text.split(maxsplit=1)
    element = ET.Element(words[0])
    if not node.children:
        if len(words) > 1:
            element.text = _xml_text(words[1])
        return element
    for child in node.children:
        if child.children:
            element.append(_node_to_xml_element(child))
        elif child.text.startswith("@"):
            name, _, raw = child.text.partition(" ")
            element.set(name[1:], str(_leaf_value(raw)))
        elif child.text.startswith("#text "):
            element.text = str(_leaf_value(child.text[len("#text ") :]))
        else:
            element.append(_node_to_xml_element(child))
    return element


def _xml_text(raw: str) -> str:
    value = _leaf_value(raw)
    return value if isinstance(value, str) else raw


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
    if len(remediation.children) != 1:
        message = "XML rendering requires a single root node"
        raise InvalidConfigError(message)
    root_node = next(iter(remediation.children))
    running_root = (
        running.get_child(equals=root_node.text) if running is not None else None
    )
    element = _netconf_element(
        root_node,
        remediation.driver.negation_prefix,
        running_root,
        list_keys or DEFAULT_LIST_KEYS,
    )
    element.set("xmlns:nc", NETCONF_BASE_NS)
    ET.indent(element)
    return ET.tostring(element, encoding="unicode")


def _netconf_element(
    node: HConfigChild,
    negation_prefix: str,
    running_node: HConfigChild | None,
    list_keys: tuple[str, ...],
) -> ET.Element:
    if node.text.startswith(negation_prefix):
        return _netconf_delete_element(
            node.text.removeprefix(negation_prefix),
            running_node,
            list_keys,
        )
    words = node.text.split(maxsplit=1)
    element = ET.Element(words[0])
    if not node.children:
        if len(words) > 1:
            element.text = _xml_text(words[1])
        return element
    for child in node.children:
        if not child.children and child.text.startswith("@"):
            name, _, raw = child.text.partition(" ")
            element.set(name[1:], str(_leaf_value(raw)))
        elif not child.children and child.text.startswith("#text "):
            element.text = _xml_text(child.text[len("#text ") :])
        else:
            # A negated child is looked up in the running parent by
            # _netconf_delete_element, so it receives the parent context.
            child_running = (
                running_node
                if child.text.startswith(negation_prefix)
                else running_node.get_child(equals=child.text)
                if running_node
                else None
            )
            element.append(
                _netconf_element(child, negation_prefix, child_running, list_keys)
            )
    return element


def _netconf_delete_element(
    positive_text: str,
    running_parent: HConfigChild | None,
    list_keys: tuple[str, ...],
) -> ET.Element:
    words = positive_text.split(maxsplit=1)
    if words[0].startswith("@"):
        message = (
            "Attribute changes cannot be expressed as NETCONF operations:"
            f" {positive_text!r}"
        )
        raise InvalidConfigError(message)
    element = ET.Element(words[0])
    element.set("nc:operation", "delete")
    if len(words) == 1:
        return element
    # A keyed list entry (branch in the running config) deletes by key leaf.
    key = _running_entry_key(running_parent, positive_text, words[1], list_keys)
    if key is not None:
        ET.SubElement(element, key).text = _xml_text(words[1])
        return element
    element.text = _xml_text(words[1])
    return element


def _matching_list_key(
    entry: HConfigBase,
    raw_value: str,
    list_keys: tuple[str, ...],
) -> str | None:
    for key in list_keys:
        if entry.get_child(equals=f"{key} {raw_value}") is not None:
            return key
    return None


def _running_entry_key(
    running_parent: HConfigBase | None,
    positive_text: str,
    raw_value: str,
    list_keys: tuple[str, ...],
) -> str | None:
    """Key leaf identifying `positive_text` as a keyed list entry, if any."""
    if running_parent is None:
        return None
    running_entry = running_parent.get_child(equals=positive_text)
    if running_entry is None or not running_entry.children:
        return None
    return _matching_list_key(running_entry, raw_value, list_keys)


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
    result: GnmiRemediation = {"update": {}, "delete": []}
    context = _GnmiContext(
        delete=result["delete"],
        negation_prefix=remediation.driver.negation_prefix,
        list_keys=list_keys or DEFAULT_LIST_KEYS,
    )
    _gnmi_into(remediation, result["update"], (), running, context)
    return result


class _GnmiContext(NamedTuple):
    delete: list[str]
    negation_prefix: str
    list_keys: tuple[str, ...]


def _gnmi_into(
    node: HConfigBase,
    update: dict[str, JsonValue],
    path: tuple[str, ...],
    running_node: HConfigBase | None,
    context: _GnmiContext,
) -> None:
    for child in node.children:
        if child.text.startswith(context.negation_prefix):
            # A negated child is resolved against the parent's running node.
            context.delete.append(
                _gnmi_delete_path(
                    path,
                    child.text.removeprefix(context.negation_prefix),
                    running_node,
                    context.list_keys,
                )
            )
            continue
        words = child.text.split(maxsplit=1)
        if not child.children:
            value: JsonValue = _leaf_value(words[1]) if len(words) > 1 else {}
            _store_json_member(update, words[0], value, force_list=False)
            continue
        running_child = (
            running_node.get_child(equals=child.text) if running_node else None
        )
        segment = words[0]
        key_name: str | None = None
        if len(words) > 1:
            key_name = _gnmi_identity_key(
                child, running_child, words[1], context.list_keys
            )
            segment = (
                f"{words[0]}[{key_name or context.list_keys[0]}"
                f"={_gnmi_selector_value(words[1])}]"
            )
        child_update: dict[str, JsonValue] = {}
        _gnmi_into(child, child_update, (*path, segment), running_child, context)
        if not child_update:
            # The branch contained only deletions.
            continue
        if key_name is not None and key_name not in child_update:
            child_update = {key_name: _leaf_value(words[1]), **child_update}
        _store_json_member(update, words[0], child_update, force_list=len(words) > 1)


def _gnmi_identity_key(
    entry: HConfigChild,
    running_entry: HConfigBase | None,
    raw_value: str,
    list_keys: tuple[str, ...],
) -> str | None:
    for source in (entry, running_entry):
        if source is None:
            continue
        key = _matching_list_key(source, raw_value, list_keys)
        if key is not None:
            return key
    return None


def _gnmi_selector_value(raw: str) -> str:
    return _xml_text(raw).replace("\\", "\\\\").replace("]", "\\]")


def _gnmi_delete_path(
    parent_path: tuple[str, ...],
    positive_text: str,
    running_parent: HConfigBase | None,
    list_keys: tuple[str, ...],
) -> str:
    words = positive_text.split(maxsplit=1)
    if words[0].startswith("@"):
        message = (
            "Attribute changes cannot be expressed as gNMI delete paths:"
            f" {positive_text!r}"
        )
        raise InvalidConfigError(message)
    segment = words[0]
    # A keyed list entry (branch in the running config) deletes by selector;
    # a scalar leaf deletes by its bare path (the value is dropped).
    if len(words) > 1:
        key = _running_entry_key(running_parent, positive_text, words[1], list_keys)
        if key is not None:
            segment = f"{words[0]}[{key}={_gnmi_selector_value(words[1])}]"
    return "/".join((*parent_path, segment))
