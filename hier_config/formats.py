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

Both mappings are invertible via ``hconfig_to_json`` / ``hconfig_to_xml``.
Known caveat: a JSON list of scalars with exactly one item renders back as a
bare scalar. NETCONF ``edit-config`` operation attributes are not yet given
remediation semantics.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # ruff:ignore[suspicious-xml-etree-import]
from json import JSONDecodeError, dumps, loads
from typing import TYPE_CHECKING, Any, cast

from .exceptions import InvalidConfigError
from .platforms.driver_base import HConfigDriverBase
from .registry import get_hconfig_driver
from .root import HConfig

if TYPE_CHECKING:
    from .base import HConfigBase
    from .child import HConfigChild
    from .models import Platform

DEFAULT_LIST_KEYS = ("name", "id")


def _resolve_driver(
    platform_or_driver: Platform | str | HConfigDriverBase,
) -> HConfigDriverBase:
    if isinstance(platform_or_driver, HConfigDriverBase):
        return platform_or_driver
    return get_hconfig_driver(platform_or_driver)


def hconfig_from_json(
    platform_or_driver: Platform | str | HConfigDriverBase,
    data: str | dict[str, Any],
    *,
    list_keys: tuple[str, ...] = DEFAULT_LIST_KEYS,
) -> HConfig:
    """Create an HConfig from a JSON object (or JSON text)."""
    parsed: object = data
    if isinstance(data, str):
        try:
            parsed = loads(data)
        except JSONDecodeError as exc:
            message = f"The config is not valid JSON: {exc}"
            raise InvalidConfigError(message) from exc
    if not isinstance(parsed, dict):
        message = "The top-level JSON value must be an object"
        raise InvalidConfigError(message)

    config = HConfig(_resolve_driver(platform_or_driver))
    _json_into(config, cast("dict[str, Any]", parsed), list_keys)
    return config


def hconfig_to_json(config: HConfig, *, indent: int | None = 2) -> str:
    """Render an HConfig built by `hconfig_from_json` back to JSON text."""
    return dumps(_node_to_json_object(config), indent=indent)


def hconfig_from_xml(
    platform_or_driver: Platform | str | HConfigDriverBase,
    source: str,
    *,
    list_keys: tuple[str, ...] = DEFAULT_LIST_KEYS,
) -> HConfig:
    """Create an HConfig from an XML document."""
    try:
        root_element = ET.fromstring(source)  # ruff:ignore[suspicious-xml-element-tree-usage]
    except ET.ParseError as exc:
        message = f"The config is not valid XML: {exc}"
        raise InvalidConfigError(message) from exc

    config = HConfig(_resolve_driver(platform_or_driver))
    _xml_element_into(config, root_element, "", list_keys)
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
    mapping: dict[str, Any],
    list_keys: tuple[str, ...],
) -> None:
    for raw_key, value in mapping.items():
        key = _json_key(raw_key)
        if isinstance(value, dict):
            value_mapping: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
            _json_into(parent.add_child(key), value_mapping, list_keys)
        elif isinstance(value, list):
            value_items: list[Any] = value  # pyright: ignore[reportUnknownVariableType]
            _json_list_into(parent, key, value_items, list_keys)
        else:
            parent.add_child(f"{key} {dumps(value)}")


def _json_list_into(
    parent: HConfigBase,
    key: str,
    items: list[Any],
    list_keys: tuple[str, ...],
) -> None:
    for item in items:
        if isinstance(item, dict):
            entry_mapping: dict[str, Any] = item  # pyright: ignore[reportUnknownVariableType]
            identity_key = next((k for k in list_keys if k in entry_mapping), None)
            if identity_key is None:
                message = (
                    f"List entries under {key!r} need one of {list_keys} to"
                    " identify them; pass list_keys= to name the identifying"
                    " member"
                )
                raise InvalidConfigError(message)
            entry = parent.add_child(f"{key} {dumps(entry_mapping[identity_key])}")
            _json_into(entry, entry_mapping, list_keys)
        elif isinstance(item, list):
            message = f"Nested JSON arrays are not supported (under {key!r})"
            raise InvalidConfigError(message)
        else:
            parent.add_child(f"{key} {dumps(item)}")


def _leaf_value(raw: str | None) -> object:
    if raw is None:
        return None
    try:
        return loads(raw)
    except JSONDecodeError:
        return raw


def _store_json_member(
    result: dict[str, Any],
    key: str,
    value: object,
    *,
    force_list: bool,
) -> None:
    if key in result:
        existing = result[key]
        if isinstance(existing, list):
            cast("list[object]", existing).append(value)
        else:
            result[key] = [existing, value]
    elif force_list:
        result[key] = [value]
    else:
        result[key] = value


def _node_to_json_object(node: HConfigBase) -> dict[str, Any]:
    result: dict[str, Any] = {}
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
        else:
            raw = words[1] if len(words) > 1 else None
            _store_json_member(result, key, _leaf_value(raw), force_list=False)
    return result


def _xml_element_into(
    parent: HConfigBase,
    element: ET.Element,
    node_suffix: str,
    list_keys: tuple[str, ...],
) -> None:
    node = parent.add_child(f"{element.tag}{node_suffix}")
    for name, value in element.attrib.items():
        node.add_child(f"@{name} {dumps(value)}")
    if text := (element.text or "").strip():
        node.add_child(f"#text {dumps(text)}")
    _xml_children_into(node, element, list_keys)


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


def _xml_children_into(
    node: HConfigChild,
    element: ET.Element,
    list_keys: tuple[str, ...],
) -> None:
    tag_counts: dict[str, int] = {}
    for child in element:
        tag_counts[child.tag] = tag_counts.get(child.tag, 0) + 1

    for child in element:
        is_leaf = not (len(child) or child.attrib)
        if is_leaf:
            text = (child.text or "").strip()
            node.add_child(f"{child.tag} {dumps(text)}" if text else child.tag)
        else:
            suffix = (
                _xml_identity_suffix(child, list_keys)
                if tag_counts[child.tag] > 1
                else ""
            )
            _xml_element_into(node, child, suffix, list_keys)


def _node_to_xml_element(node: HConfigChild) -> ET.Element:
    words = node.text.split(maxsplit=1)
    element = ET.Element(words[0])
    if not node.children:
        if len(words) > 1:
            value = _leaf_value(words[1])
            element.text = value if isinstance(value, str) else words[1]
        return element
    for child in node.children:
        child_words = child.text.split(maxsplit=1)
        if child_words[0].startswith("@") and not child.children:
            element.set(child_words[0][1:], str(_leaf_value(child_words[1])))
        elif child_words[0] == "#text" and not child.children:
            element.text = str(_leaf_value(child_words[1]))
        else:
            element.append(_node_to_xml_element(child))
    return element
