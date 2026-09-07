"""Capture structured-format behavior as a corpus the Rust port is held to.

The JSON/XML/NETCONF/gNMI mapping was ported from Python to Rust. This script
records what the reference implementation produces -- including its error
messages -- so `crates/hier_config_core/tests/formats_corpus.rs` can assert the
port matches. Regenerate only when Python behavior is *intended* to change;
never edit the corpus to make Rust pass.

Usage::

    python scripts/gen_formats_corpus.py            # rewrite the corpus
    python scripts/gen_formats_corpus.py --check    # fail if it drifted
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hier_config.exceptions import HierConfigError
from hier_config.formats import (
    hconfig_from_json,
    hconfig_from_xml,
    hconfig_to_gnmi_json,
    hconfig_to_json,
    hconfig_to_netconf_xml,
    hconfig_to_xml,
)
from hier_config.models import Platform

if TYPE_CHECKING:
    from collections.abc import Callable

    from hier_config.root import HConfig

CORPUS = (
    Path(__file__).resolve().parent.parent / "testdata" / "formats" / "expected.json"
)

PLATFORMS = (Platform.CISCO_IOS, Platform.ARISTA_EOS, Platform.JUNIPER_JUNOS)
KEY_SETS: tuple[tuple[str, ...] | None, ...] = (
    None,
    ("name", "id"),
    ("id",),
    ("name", "id", "key"),
)

JSON_CASES: dict[str, tuple[str, str]] = {
    "scalars": (
        (
            '{"hostname": "sw1", "mtu": 9000, "enabled": true, "ratio": 1.5,'
            ' "nothing": null}'
        ),
        '{"hostname": "sw2", "mtu": 1500, "enabled": false, "ratio": 2.5}',
    ),
    "nested": (
        '{"system": {"dns": {"server": "8.8.8.8"}, "ntp": {"enabled": false}}}',
        '{"system": {"dns": {"server": "1.1.1.1"}}}',
    ),
    "empty-obj": ('{"system": {}}', '{"system": {}}'),
    "keyed-list": (
        '{"interfaces": [{"name": "Et1", "mtu": 1500}, {"name": "Et2", "mtu": 9000}]}',
        '{"interfaces": [{"name": "Et1", "mtu": 9000}]}',
    ),
    "id-keyed": (
        '{"vlans": [{"id": 10, "name": "OLD"}, {"id": 20, "name": "B"}]}',
        '{"vlans": [{"id": 10, "name": "NEW"}]}',
    ),
    "scalar-list": ('{"tags": ["a", "b", 3]}', '{"tags": ["a"]}'),
    "unicode": ('{"desc": "caf\u00e9 \u2013 dash"}', '{"desc": "na\u00efve"}'),
    "special-chars": (
        '{"desc": "a<b>c&d\\"e\'f"}',
        '{"desc": "x<y"}',
    ),
}

XML_CASES: dict[str, tuple[str, str]] = {
    "simple": (
        "<config><hostname>sw1</hostname></config>",
        "<config><hostname>sw2</hostname></config>",
    ),
    "nested": (
        "<config><system><dns><server>8.8.8.8</server></dns></system></config>",
        "<config><system><dns><server>1.1.1.1</server></dns></system></config>",
    ),
    "attrs": (
        '<config a="1" b="two"><x y="z">text</x></config>',
        '<config a="1" b="three"><x y="z">text</x></config>',
    ),
    "repeated": (
        (
            "<config><iface><name>Et1</name><mtu>1500</mtu></iface>"
            "<iface><name>Et2</name><mtu>9000</mtu></iface></config>"
        ),
        "<config><iface><name>Et1</name><mtu>9000</mtu></iface></config>",
    ),
    "single-keyed": (
        "<config><iface><name>Et1</name><mtu>1500</mtu></iface></config>",
        "<config><iface><name>Et1</name><mtu>9000</mtu></iface></config>",
    ),
    "empty-el": ("<config><flag/></config>", "<config><flag/></config>"),
    "escapes": (
        "<config><d>a&lt;b&amp;c</d></config>",
        "<config><d>x&gt;y</d></config>",
    ),
    "mixed-text": (
        "<config>lead<child>c</child></config>",
        "<config>lead2<child>c</child></config>",
    ),
}

ERROR_CASES: dict[str, Callable[[], object]] = {
    "bad-json": lambda: hconfig_from_json(Platform.CISCO_IOS, "{bad}"),
    "json-not-obj": lambda: hconfig_from_json(Platform.CISCO_IOS, "[1, 2]"),
    "empty-key": lambda: hconfig_from_json(Platform.CISCO_IOS, '{"": 1}'),
    "ws-key": lambda: hconfig_from_json(Platform.CISCO_IOS, '{"a b": 1}'),
    "unkeyed-list": lambda: hconfig_from_json(
        Platform.CISCO_IOS, '{"a": [{"x": 1}, {"x": 2}]}'
    ),
    "nested-array": lambda: hconfig_from_json(Platform.CISCO_IOS, '{"a": [[1]]}'),
    "bad-xml": lambda: hconfig_from_xml(Platform.CISCO_IOS, "<a>"),
}


def cap(call: Callable[[], object]) -> dict[str, object]:
    """Records a call's result or its exception type and message."""
    try:
        return {"ok": call()}
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        return {"err": f"{type(exc).__name__}: {exc}"}


def _gnmi(
    remediation: HConfig, running: HConfig | None, keys: tuple[str, ...] | None
) -> object:
    result = hconfig_to_gnmi_json(remediation, running=running, list_keys=keys)
    return {"update": result["update"], "delete": result["delete"]}


def _case_key(name: str, platform: Platform, keys: tuple[str, ...] | None) -> str:
    return f"{name}|{platform.name}|{keys!r}"


def _json_case(
    platform: Platform,
    keys: tuple[str, ...] | None,
    source: str,
    target_source: str,
) -> tuple[dict[str, object], dict[str, object] | None]:
    """Captures one JSON case: the parse result and, if parsable, its gNMI form."""

    def parse() -> HConfig:
        return hconfig_from_json(platform, source, list_keys=keys)

    parsed = cap(
        lambda: {
            "simple": list(parse().dump_simple()),
            "to_json": cap(lambda: hconfig_to_json(parse())),
            "to_json_flat": cap(lambda: hconfig_to_json(parse(), indent=None)),
        }
    )
    try:  # pylint: disable=too-many-try-statements
        running = parse()
        target = hconfig_from_json(platform, target_source, list_keys=keys)
    except HierConfigError:
        return parsed, None
    remediation = running.config_to_get_to(target)
    return parsed, {
        "remediation": list(remediation.dump_simple()),
        "no_running": cap(lambda: _gnmi(remediation, None, keys)),
        "with_running": cap(lambda: _gnmi(remediation, running, keys)),
    }


def _xml_case(
    platform: Platform,
    keys: tuple[str, ...] | None,
    source: str,
    target_source: str,
) -> tuple[dict[str, object], dict[str, object] | None]:
    """Captures one XML case: the parse result and, if parsable, its NETCONF form."""

    def parse() -> HConfig:
        return hconfig_from_xml(platform, source, list_keys=keys)

    parsed = cap(
        lambda: {
            "simple": list(parse().dump_simple()),
            "to_xml": cap(lambda: hconfig_to_xml(parse())),
        }
    )
    try:  # pylint: disable=too-many-try-statements
        running = parse()
        target = hconfig_from_xml(platform, target_source, list_keys=keys)
    except HierConfigError:
        return parsed, None
    remediation = running.config_to_get_to(target)
    return parsed, {
        "remediation": list(remediation.dump_simple()),
        "no_running": cap(lambda: hconfig_to_netconf_xml(remediation, list_keys=keys)),
        "with_running": cap(
            lambda: hconfig_to_netconf_xml(remediation, running=running, list_keys=keys)
        ),
    }


def build() -> dict[str, dict[str, Any]]:
    """Runs every case against the reference implementation."""
    corpus: dict[str, dict[str, Any]] = {
        # The Rust corpus test reads its inputs back out of here, so the two
        # implementations can never drift onto different source configs.
        "sources": {
            "json": {
                name: {"config": config, "target": target}
                for name, (config, target) in JSON_CASES.items()
            },
            "xml": {
                name: {"config": config, "target": target}
                for name, (config, target) in XML_CASES.items()
            },
        },
        "json": {},
        "xml": {},
        "netconf": {},
        "gnmi": {},
        "errors": {},
    }

    for cases, builder, parsed_section, derived_section in (
        (JSON_CASES, _json_case, "json", "gnmi"),
        (XML_CASES, _xml_case, "xml", "netconf"),
    ):
        for name, (source, target_source) in cases.items():
            for platform in PLATFORMS:
                for keys in KEY_SETS:
                    key = _case_key(name, platform, keys)
                    parsed, derived = builder(platform, keys, source, target_source)
                    corpus[parsed_section][key] = parsed
                    if derived is not None:
                        corpus[derived_section][key] = derived

    for name, call in ERROR_CASES.items():
        corpus["errors"][name] = {"err": cap(call)["err"]}

    return corpus


def render(corpus: dict[str, dict[str, Any]]) -> str:
    """Serializes the corpus deterministically."""
    rendered = json.dumps(corpus, indent=1, sort_keys=True, ensure_ascii=False)
    return f"{rendered}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the corpus on disk is stale",
    )
    args = parser.parse_args()

    rendered = render(build())
    if args.check:
        if not CORPUS.exists() or CORPUS.read_text(encoding="utf-8") != rendered:
            sys.stderr.write(
                f"{CORPUS} is stale; rerun scripts/gen_formats_corpus.py\n"
            )
            return 1
        return 0

    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    CORPUS.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
