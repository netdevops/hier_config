"""Compare structured formats with frozen, explicitly attributed expectations.

``expected.json`` contains IOS/EOS results independently captured from the
pinned pure-Python upstream/next revision below. Parser-specific diagnostics
are normalized during comparison; exception classes and stable prefixes are
not. ``native-v1.json`` separately preserves Junos regression expectations:
the reference cannot remediate those unflattened JSON/XML trees because its
Junos driver requires set/delete commands, so they are not parity evidence.

``--check`` runs the current implementation against both frozen snapshots;
it does not generate an independent oracle. Only ``--capture-reference`` can
write the reference snapshot, and it refuses anything except the fingerprinted
pure-Python source. Put a ``git archive`` of REFERENCE_COMMIT on PYTHONPATH
before invoking it. Native snapshots must be reviewed separately, never
regenerated automatically to silence a mismatch.

Usage::

    python scripts/gen_formats_corpus.py --check
    PYTHONPATH=/path/to/reference python scripts/gen_formats_corpus.py --capture-reference
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import TypeAdapter

import hier_config
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
REFERENCE_PLATFORMS = (Platform.CISCO_IOS, Platform.ARISTA_EOS)
REFERENCE_COMMIT = "0866dc2316443909edea2d629117b44a3a9ed472"
REFERENCE_SOURCE_SHA256 = (
    "2b6bd6cd001b423390bd89c481c23d05798b2205f3879ba549ae03d753191dc1"
)
REFERENCE_PROVENANCE: dict[str, object] = {
    "schema_version": 1,
    "implementation": "pure-python",
    "reference_commit": REFERENCE_COMMIT,
    "source_sha256": REFERENCE_SOURCE_SHA256,
    "platforms": ["CISCO_IOS", "ARISTA_EOS"],
}
NATIVE_CORPUS = CORPUS.with_name("native-v1.json")
NATIVE_PROVENANCE: dict[str, object] = {
    "schema_version": 1,
    "implementation": "native",
    "snapshot_commit": "fa49af6fffd1a529807c0e14aeb5e6ff9dc83a6c",
    "platforms": ["JUNIPER_JUNOS"],
    "reason": "The pure-Python driver cannot remediate unflattened format trees",
}
DERIVED_SECTIONS = ("json", "xml", "netconf", "gnmi")

# Tail of the Junos swap error. The doubled space is real: ``negation_prefix``
# is ``"delete "`` and ``declaration_prefix`` is ``"set "``.
JUNOS_SWAP_ERROR_SUFFIX = "did not start with delete  or set ."

# Native-only cases whose recorded remediation the Junos negation fix withdrew.
#
# Junos negation of a line starting with neither ``set `` nor ``delete ``
# raises in the pure-Python baseline, which draws no distinction between CLI
# text and structured-format element names. The permissive fallback removed
# from the native driver emitted the line as its own negation instead, which
# is wrong on the wire: it told the device to set the value it should remove.
#
# ``native-v1.json`` is frozen parity-free evidence and is never regenerated,
# so these keys stay in the snapshot and are withdrawn at comparison time.
# The list is asserted to be exhaustive: a case that starts remediating again,
# or one that fails any other way, fails the check rather than passing quietly.
# It mirrors ``WITHDRAWN_NATIVE_CASES`` in
# ``crates/hier_config_core/tests/formats_corpus.rs``.
WITHDRAWN_NATIVE_CASES: frozenset[tuple[str, str]] = frozenset(
    (
        ("netconf", "attrs|JUNIPER_JUNOS|('id',)"),
        ("netconf", "attrs|JUNIPER_JUNOS|('name', 'id')"),
        ("netconf", "attrs|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("netconf", "attrs|JUNIPER_JUNOS|None"),
        ("netconf", "escapes|JUNIPER_JUNOS|('id',)"),
        ("netconf", "escapes|JUNIPER_JUNOS|('name', 'id')"),
        ("netconf", "escapes|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("netconf", "escapes|JUNIPER_JUNOS|None"),
        ("netconf", "mixed-text|JUNIPER_JUNOS|('id',)"),
        ("netconf", "mixed-text|JUNIPER_JUNOS|('name', 'id')"),
        ("netconf", "mixed-text|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("netconf", "mixed-text|JUNIPER_JUNOS|None"),
        ("netconf", "nested|JUNIPER_JUNOS|('id',)"),
        ("netconf", "nested|JUNIPER_JUNOS|('name', 'id')"),
        ("netconf", "nested|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("netconf", "nested|JUNIPER_JUNOS|None"),
        ("netconf", "repeated|JUNIPER_JUNOS|('name', 'id')"),
        ("netconf", "repeated|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("netconf", "repeated|JUNIPER_JUNOS|None"),
        ("netconf", "simple|JUNIPER_JUNOS|('id',)"),
        ("netconf", "simple|JUNIPER_JUNOS|('name', 'id')"),
        ("netconf", "simple|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("netconf", "simple|JUNIPER_JUNOS|None"),
        ("netconf", "single-keyed|JUNIPER_JUNOS|('id',)"),
        ("netconf", "single-keyed|JUNIPER_JUNOS|('name', 'id')"),
        ("netconf", "single-keyed|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("netconf", "single-keyed|JUNIPER_JUNOS|None"),
        ("gnmi", "id-keyed|JUNIPER_JUNOS|('id',)"),
        ("gnmi", "id-keyed|JUNIPER_JUNOS|('name', 'id')"),
        ("gnmi", "id-keyed|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("gnmi", "id-keyed|JUNIPER_JUNOS|None"),
        ("gnmi", "keyed-list|JUNIPER_JUNOS|('name', 'id')"),
        ("gnmi", "keyed-list|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("gnmi", "keyed-list|JUNIPER_JUNOS|None"),
        ("gnmi", "nested|JUNIPER_JUNOS|('id',)"),
        ("gnmi", "nested|JUNIPER_JUNOS|('name', 'id')"),
        ("gnmi", "nested|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("gnmi", "nested|JUNIPER_JUNOS|None"),
        ("gnmi", "scalar-list|JUNIPER_JUNOS|('id',)"),
        ("gnmi", "scalar-list|JUNIPER_JUNOS|('name', 'id')"),
        ("gnmi", "scalar-list|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("gnmi", "scalar-list|JUNIPER_JUNOS|None"),
        ("gnmi", "scalars|JUNIPER_JUNOS|('id',)"),
        ("gnmi", "scalars|JUNIPER_JUNOS|('name', 'id')"),
        ("gnmi", "scalars|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("gnmi", "scalars|JUNIPER_JUNOS|None"),
        ("gnmi", "special-chars|JUNIPER_JUNOS|('id',)"),
        ("gnmi", "special-chars|JUNIPER_JUNOS|('name', 'id')"),
        ("gnmi", "special-chars|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("gnmi", "special-chars|JUNIPER_JUNOS|None"),
        ("gnmi", "unicode|JUNIPER_JUNOS|('id',)"),
        ("gnmi", "unicode|JUNIPER_JUNOS|('name', 'id')"),
        ("gnmi", "unicode|JUNIPER_JUNOS|('name', 'id', 'key')"),
        ("gnmi", "unicode|JUNIPER_JUNOS|None"),
    )
)
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


def _remediate(running: HConfig, target: HConfig, platform: Platform) -> HConfig | None:
    """Remediate, withdrawing the cases the Junos negation fix stopped emitting.

    Returns ``None`` only for the Junos swap error on ``JUNIPER_JUNOS``. Any
    other ``ValueError``, and the same error on any other platform, propagates
    so an unrelated regression cannot masquerade as a withdrawn case.
    """
    try:
        return running.config_to_get_to(target)
    except ValueError as error:
        if platform is not Platform.JUNIPER_JUNOS or not str(error).endswith(
            JUNOS_SWAP_ERROR_SUFFIX
        ):
            raise
        return None


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
    remediation = _remediate(running, target, platform)
    if remediation is None:
        return parsed, None
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
    remediation = _remediate(running, target, platform)
    if remediation is None:
        return parsed, None
    return parsed, {
        "remediation": list(remediation.dump_simple()),
        "no_running": cap(lambda: hconfig_to_netconf_xml(remediation, list_keys=keys)),
        "with_running": cap(
            lambda: hconfig_to_netconf_xml(remediation, running=running, list_keys=keys)
        ),
    }


def build(
    platforms: tuple[Platform, ...] = PLATFORMS,
) -> dict[str, dict[str, object]]:
    """Run cases against whichever implementation this interpreter imports."""
    corpus: dict[str, dict[str, object]] = {
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
            for platform in platforms:
                for keys in KEY_SETS:
                    key = _case_key(name, platform, keys)
                    parsed, derived = builder(platform, keys, source, target_source)
                    corpus[parsed_section][key] = parsed
                    if derived is not None:
                        corpus[derived_section][key] = derived

    for name, call in ERROR_CASES.items():
        corpus["errors"][name] = {"err": cap(call)["err"]}

    return corpus


def render(corpus: dict[str, dict[str, object]]) -> str:
    """Serializes the corpus deterministically."""
    rendered = json.dumps(corpus, indent=1, sort_keys=True, ensure_ascii=False)
    return f"{rendered}\n"


def normalize_outcomes(value: object) -> object:
    """Ignore parser diagnostics only within errors of the expected class."""
    if isinstance(value, list):
        return [normalize_outcomes(item) for item in cast("list[object]", value)]
    if not isinstance(value, dict):
        return value
    result = {
        key: normalize_outcomes(item)
        for key, item in cast("dict[str, object]", value).items()
    }
    error = result.get("err")
    if isinstance(error, str):
        for format_name in ("JSON", "XML"):
            prefix = f"InvalidConfigError: The config is not valid {format_name}:"
            if error.startswith(prefix):
                result["err"] = prefix
    return result


def reference_source_matches() -> bool:
    """Verify all Python sources, not just the format converter or version label."""
    root = Path(hier_config.__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return (
        hier_config.HConfig.__module__ == "hier_config.root"
        and digest.hexdigest() == REFERENCE_SOURCE_SHA256
    )


def check_snapshot(
    path: Path,
    actual: dict[str, dict[str, object]],
    provenance: dict[str, object],
    withdrawn: frozenset[tuple[str, str]] = frozenset(),
) -> bool:
    """Compare without rewriting a snapshot or trusting its provenance blindly."""
    expected = TypeAdapter(dict[str, dict[str, object]]).validate_json(
        path.read_text(encoding="utf-8"), strict=True
    )
    if expected.pop("_provenance", None) != provenance:
        sys.stderr.write(f"{path}: missing or unexpected frozen provenance\n")
        return False
    if not _withdraw(path, expected, actual, withdrawn):
        return False
    if normalize_outcomes(expected) != normalize_outcomes(actual):
        sys.stderr.write(
            f"{path}: implementation differs from frozen expectations; "
            "investigate the behavior, do not regenerate from the failing backend\n"
        )
        return False
    return True


def _withdraw(
    path: Path,
    expected: dict[str, dict[str, object]],
    actual: dict[str, dict[str, object]],
    withdrawn: frozenset[tuple[str, str]],
) -> bool:
    """Drop withdrawn keys from a frozen snapshot, asserting the list is exact.

    The frozen snapshot is never regenerated, so cases the implementation
    deliberately stopped emitting are removed here instead. Requiring the
    observed gap to equal ``withdrawn`` exactly means a case that starts
    emitting again, or any other case that disappears, still fails.
    """
    missing = frozenset(
        (section, key)
        for section, cases in expected.items()
        for key in cases
        if key not in actual.get(section, {})
    )
    if missing != withdrawn:
        for section, key in sorted(withdrawn - missing):
            sys.stderr.write(
                f"{path}: {section}/{key} is listed as withdrawn but was emitted; "
                "remove it from the withdrawn list if the behavior is intended\n"
            )
        for section, key in sorted(missing - withdrawn):
            sys.stderr.write(
                f"{path}: {section}/{key} vanished from the implementation and is "
                "not a known withdrawal; investigate the behavior\n"
            )
        return False
    for section, key in withdrawn:
        del expected[section][key]
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the current implementation with frozen expectations",
    )
    parser.add_argument(
        "--capture-reference",
        action="store_true",
        help="capture only the pinned, fingerprinted pure-Python reference",
    )
    args = parser.parse_args()

    if args.check:
        parity_matches = check_snapshot(
            CORPUS, build(REFERENCE_PLATFORMS), REFERENCE_PROVENANCE
        )
        native = build((Platform.JUNIPER_JUNOS,))
        native_matches = check_snapshot(
            NATIVE_CORPUS,
            {section: native[section] for section in DERIVED_SECTIONS},
            NATIVE_PROVENANCE,
            WITHDRAWN_NATIVE_CASES,
        )
        return 0 if parity_matches and native_matches else 1

    if not args.capture_reference or not reference_source_matches():
        sys.stderr.write(
            "Snapshots are frozen. --capture-reference requires pure-Python "
            f"sources from {REFERENCE_COMMIT} on PYTHONPATH; "
            "the current native implementation cannot overwrite parity evidence.\n"
        )
        return 1

    reference = build(REFERENCE_PLATFORMS)
    reference["_provenance"] = REFERENCE_PROVENANCE
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    CORPUS.write_text(render(reference), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
