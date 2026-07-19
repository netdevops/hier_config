"""Tests for hier_config/formats.py — JSON/XML ingestion and rendering (#232)."""

import json

import pytest

from hier_config import HConfig, Platform
from hier_config.exceptions import DuplicateChildError, InvalidConfigError

OPENCONFIG_STYLE = {
    "system": {
        "config": {
            "hostname": "router1",
            "login-banner": "unauthorized access is prohibited",
        },
        "ntp": {"enabled": True, "port": 123},
    },
    "interfaces": {
        "interface": [
            {
                "name": "eth0",
                "config": {"description": "uplink", "mtu": 9000},
            },
            {
                "name": "eth1",
                "config": {"description": "downlink", "mtu": 1500},
            },
        ],
    },
    "dns-servers": ["192.0.2.1", "192.0.2.2"],
}


def test_from_json_builds_expected_tree() -> None:
    config = HConfig.from_json(Platform.GENERIC, OPENCONFIG_STYLE)

    system = config.get_child(equals="system")
    assert system is not None
    system_config = system.get_child(equals="config")
    assert system_config is not None
    assert system_config.get_child(equals='hostname "router1"') is not None

    ntp = system.get_child(equals="ntp")
    assert ntp is not None
    assert ntp.get_child(equals="enabled true") is not None
    assert ntp.get_child(equals="port 123") is not None

    interfaces = config.get_child(equals="interfaces")
    assert interfaces is not None
    eth0 = interfaces.get_child(equals='interface "eth0"')
    assert eth0 is not None
    assert eth0.get_child(equals='name "eth0"') is not None

    assert config.get_child(equals='dns-servers "192.0.2.1"') is not None
    assert config.get_child(equals='dns-servers "192.0.2.2"') is not None


def test_from_json_accepts_json_text() -> None:
    config = HConfig.from_json(Platform.GENERIC, json.dumps(OPENCONFIG_STYLE))
    assert config.get_child(equals="system") is not None


def test_json_round_trip() -> None:
    config = HConfig.from_json(Platform.GENERIC, OPENCONFIG_STYLE)
    assert json.loads(config.to_json()) == OPENCONFIG_STYLE


def test_json_round_trip_via_reparse() -> None:
    config = HConfig.from_json(Platform.GENERIC, OPENCONFIG_STYLE)
    reparsed = HConfig.from_json(Platform.GENERIC, config.to_json())
    assert reparsed == config


def test_from_json_invalid_text_raises() -> None:
    with pytest.raises(InvalidConfigError, match="not valid JSON"):
        HConfig.from_json(Platform.GENERIC, "{not json")


def test_from_json_non_object_root_raises() -> None:
    with pytest.raises(InvalidConfigError, match="must be an object"):
        HConfig.from_json(Platform.GENERIC, "[1, 2, 3]")


def test_from_json_whitespace_key_raises() -> None:
    with pytest.raises(InvalidConfigError, match="Unsupported JSON key"):
        HConfig.from_json(Platform.GENERIC, {"bad key": 1})


def test_from_json_unidentified_list_entry_raises() -> None:
    with pytest.raises(InvalidConfigError, match="identify"):
        HConfig.from_json(Platform.GENERIC, {"vlans": [{"vid": 100}]})


def test_from_json_custom_list_keys() -> None:
    config = HConfig.from_json(
        Platform.GENERIC, {"vlans": [{"vid": 100}]}, list_keys=("vid",)
    )
    assert config.get_child(equals="vlans 100") is not None


def test_json_diff_between_structured_configs() -> None:
    """Structured configs work with the tree diff engine."""
    running = HConfig.from_json(
        Platform.GENERIC, {"system": {"hostname": "old", "domain": "example.com"}}
    )
    generated = HConfig.from_json(
        Platform.GENERIC, {"system": {"hostname": "new", "domain": "example.com"}}
    )
    remediation = running.remediation(generated)
    system = remediation.get_child(equals="system")
    assert system is not None
    assert system.get_child(equals='no hostname "old"') is not None
    assert system.get_child(equals='hostname "new"') is not None


def test_json_future_renders_back_to_json() -> None:
    """future() of a structured config renders back to valid JSON."""
    running = HConfig.from_json(Platform.GENERIC, {"system": {"hostname": "old"}})
    generated = HConfig.from_json(Platform.GENERIC, {"system": {"hostname": "new"}})
    future = running.future(running.remediation(generated))
    assert json.loads(future.to_json()) == {"system": {"hostname": "new"}}


XML_TEXT = (
    "<config>"
    '<system foo="bar">'
    "<hostname>router1</hostname>"
    "<location/>"
    "</system>"
    "<interfaces>"
    "<interface><name>eth0</name><mtu>9000</mtu></interface>"
    "<interface><name>eth1</name><mtu>1500</mtu></interface>"
    "</interfaces>"
    "</config>"
)


def test_from_xml_builds_expected_tree() -> None:
    config = HConfig.from_xml(Platform.GENERIC, XML_TEXT)

    root = config.get_child(equals="config")
    assert root is not None
    system = root.get_child(equals="system")
    assert system is not None
    assert system.get_child(equals='@foo "bar"') is not None
    assert system.get_child(equals='hostname "router1"') is not None
    assert system.get_child(equals="location") is not None

    interfaces = root.get_child(equals="interfaces")
    assert interfaces is not None
    eth0 = interfaces.get_child(equals='interface "eth0"')
    assert eth0 is not None
    assert eth0.get_child(equals='mtu "9000"') is not None


def test_xml_round_trip() -> None:
    config = HConfig.from_xml(Platform.GENERIC, XML_TEXT)
    reparsed = HConfig.from_xml(Platform.GENERIC, config.to_xml())
    assert reparsed == config


def test_from_xml_invalid_raises() -> None:
    with pytest.raises(InvalidConfigError, match="not valid XML"):
        HConfig.from_xml(Platform.GENERIC, "<config><unclosed></config>")


def test_from_xml_repeated_elements_without_identity_raises() -> None:
    xml_text = "<c><item><x>1</x></item><item><x>2</x></item></c>"
    with pytest.raises(InvalidConfigError, match="identify"):
        HConfig.from_xml(Platform.GENERIC, xml_text)


def test_to_xml_requires_single_root() -> None:
    config = HConfig.from_json(Platform.GENERIC, {"a": {"x": 1}, "b": {"y": 2}})
    with pytest.raises(InvalidConfigError, match="single root"):
        config.to_xml()


def test_xml_mixed_text_content() -> None:
    xml_text = "<c><a>text<b>inner</b></a></c>"
    config = HConfig.from_xml(Platform.GENERIC, xml_text)
    outer = config.get_child(equals="c")
    assert outer is not None
    element_a = outer.get_child(equals="a")
    assert element_a is not None
    assert element_a.get_child(equals='#text "text"') is not None
    assert element_a.get_child(equals='b "inner"') is not None
    reparsed = HConfig.from_xml(Platform.GENERIC, config.to_xml())
    assert reparsed == config


def test_detection_error_mentions_structured_constructors() -> None:
    with pytest.raises(InvalidConfigError, match="from_json"):
        HConfig.from_text(Platform.GENERIC, '{"a": 1}')
    with pytest.raises(InvalidConfigError, match="from_xml"):
        HConfig.from_text(Platform.GENERIC, "<config/>")


def test_empty_object_round_trips() -> None:
    """An empty JSON object must not collapse to null (#279 review)."""
    data: dict[str, object] = {"system": {}, "count": 1, "missing": None}
    config = HConfig.from_json(Platform.GENERIC, data)
    assert json.loads(config.to_json()) == data


def test_duplicate_list_items_raise_hier_config_error() -> None:
    """Duplicate scalar items and duplicate identities surface as tree errors."""
    with pytest.raises(DuplicateChildError):
        HConfig.from_json(Platform.GENERIC, {"dns": ["192.0.2.1", "192.0.2.1"]})
    with pytest.raises(DuplicateChildError):
        HConfig.from_json(
            Platform.GENERIC, {"interface": [{"name": "e0"}, {"name": "e0"}]}
        )
