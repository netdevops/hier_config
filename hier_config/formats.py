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
``DuplicateChildError``; NETCONF ``edit-config`` operation attributes are not
yet given remediation semantics.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # ruff:ignore[suspicious-xml-etree-import]
from collections import Counter
from json import JSONDecodeError, dumps, loads
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from .exceptions import InvalidConfigError
from .registry import resolve_driver
from .root import HConfig

if TYPE_CHECKING:
    from .base import HConfigBase
    from .child import HConfigChild
    from .models import Platform
    from .platforms.driver_base import HConfigDriverBase

DEFAULT_LIST_KEYS = ("name", "id")

JsonValue: TypeAlias = (
    "str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None"
)


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
) -> str:
    for key in list_keys:
        if (identity := element.find(key)) is not None and identity.text:
            return f" {dumps(identity.text.strip())}"
    message = (
        f"Repeated <{element.tag}> elements need a child element named one of"
        f" {list_keys} to identify them; pass list_keys= to name the"
        " identifying element"
    )
    raise InvalidConfigError(message)


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
            suffix = (
                _xml_identity_suffix(child, list_keys)
                if tag_counts[child.tag] > 1
                else ""
            )
            _xml_element_into(node, child, list_keys, node_suffix=suffix)


def _node_to_xml_element(node: HConfigChild) -> ET.Element:
    words = node.text.split(maxsplit=1)
    element = ET.Element(words[0])
    if not node.children:
        if len(words) > 1:
            value = _leaf_value(words[1])
            element.text = value if isinstance(value, str) else words[1]
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
