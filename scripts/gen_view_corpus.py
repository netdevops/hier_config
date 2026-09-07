"""Generate the expected view snapshots for the shared ``testdata/views`` corpus.

The Python view layer is the reference implementation. This script serializes it
mechanically -- iterating a fixed, declared property list -- so that the Rust
port in ``hier_config_core::view`` can be held to it. Snapshots must always be
regenerated from Python and then made to pass in Rust, never the reverse.

Usage::

    python scripts/gen_view_corpus.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from enum import Enum
from ipaddress import IPv4Address, IPv4Interface
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel as PydanticBaseModel

from hier_config import HConfig, Platform, get_hconfig_view

if TYPE_CHECKING:
    from hier_config.platforms.view_base import (
        ConfigViewInterfaceBase,
        HConfigViewBase,
    )

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "testdata" / "views"

#: Interface properties every view exposes, in serialization order.
INTERFACE_BASE_PROPERTIES = (
    "name",
    "number",
    "parent_name",
    "description",
    "enabled",
    "is_bundle",
    "is_subinterface",
    "is_loopback",
    "is_svi",
    "module_number",
    "port_number",
    "subinterface_number",
    "ipv4_interfaces",
    "vrf",
)
#: Bundle-mixin properties.
INTERFACE_BUNDLE_PROPERTIES = ("bundle_id", "bundle_name", "bundle_member_interfaces")
#: VLAN-mixin properties.
INTERFACE_VLAN_PROPERTIES = ("native_vlan", "tagged_all", "tagged_vlans", "dot1q_mode")
#: NAC-mixin properties.
INTERFACE_NAC_PROPERTIES = (
    "has_nac",
    "nac_control_direction_in",
    "nac_host_mode",
    "nac_mab_first",
    "nac_max_dot1x_clients",
    "nac_max_mab_clients",
)
#: Physical-mixin properties.
INTERFACE_PHYSICAL_PROPERTIES = ("duplex", "poe", "speed")


def _encode(value: object) -> Any:  # ruff: ignore[any-type] - heterogeneous values
    """Render a view value as JSON-safe data."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, (IPv4Address, IPv4Interface)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, PydanticBaseModel):
        return {key: _encode(item) for key, item in value.model_dump().items()}
    if isinstance(value, (list, tuple, set, frozenset, Iterator)):
        return [_encode(item) for item in value]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return str(value)


def _read(
    view: object,
    name: str,
    raises: dict[str, str] | None = None,
) -> Any:  # ruff: ignore[any-type] - heterogeneous view values
    """Read one property, recording the exception type when it raises.

    A raising property has no reference value, so the corpus records the
    exception under ``raises`` and the Rust side skips comparing that key. This
    keeps known Python/Rust divergences visible instead of hiding them behind a
    ``null``.
    """
    try:
        return _encode(getattr(view, name))
    except (AttributeError, NotImplementedError, TypeError, ValueError) as exc:
        if raises is not None:
            raises[name] = type(exc).__name__
        return None


def _serialize_interface(view: ConfigViewInterfaceBase) -> dict[str, Any]:
    """Serialize one interface view over the declared property list."""
    names: list[str] = list(INTERFACE_BASE_PROPERTIES)
    names.extend(INTERFACE_BUNDLE_PROPERTIES)
    names.extend(INTERFACE_VLAN_PROPERTIES)
    if hasattr(type(view), "has_nac"):
        names.extend(INTERFACE_NAC_PROPERTIES)
    if hasattr(type(view), "poe"):
        names.extend(INTERFACE_PHYSICAL_PROPERTIES)
    raises: dict[str, str] = {}
    snapshot: dict[str, Any] = {name: _read(view, name, raises) for name in names}
    snapshot["raises"] = raises
    return snapshot


def serialize_view(view: HConfigViewBase) -> dict[str, Any]:
    """Serialize a whole-config view into the corpus snapshot shape."""
    raises: dict[str, str] = {}
    return {
        "hostname": _read(view, "hostname", raises),
        "ipv4_default_gw": _read(view, "ipv4_default_gw", raises),
        "location": _read(view, "location", raises),
        "module_numbers": _read(view, "module_numbers", raises),
        "stack_members": _read(view, "stack_members", raises),
        "vlans": _read(view, "vlans", raises),
        "interface_names_mentioned": sorted(view.interface_names_mentioned),
        "interfaces": [
            _serialize_interface(interface) for interface in view.interface_views
        ],
        "raises": raises,
    }


def snapshot_for(platform: Platform, config_text: str) -> dict[str, Any]:
    """Build the snapshot for one corpus case."""
    config = HConfig.from_text(platform, config_text)
    return serialize_view(get_hconfig_view(config))


def _render(snapshot: dict[str, Any]) -> str:
    """Render a snapshot exactly as it is stored on disk."""
    return f"{json.dumps(snapshot, indent=2, sort_keys=False)}\n"


def main(*, check: bool = False) -> int:
    """Regenerate every snapshot under ``testdata/views``.

    With ``check``, nothing is written: the committed snapshots are compared
    against freshly generated ones and a non-zero status is returned when they
    have drifted. That is how the test suite guards the corpus.
    """
    stale: list[str] = []
    for case_dir in sorted(CORPUS_DIR.iterdir()):
        if not case_dir.is_dir():
            continue
        platform = Platform[case_dir.name.upper()]
        config_text = (case_dir / "config.txt").read_text(encoding="utf-8")
        rendered = _render(snapshot_for(platform, config_text))
        target = case_dir / "expected.json"
        relative = target.relative_to(REPO_ROOT)
        if check:
            current = target.read_text(encoding="utf-8") if target.is_file() else ""
            if current != rendered:
                stale.append(str(relative))
            continue
        target.write_text(rendered, encoding="utf-8")
        print(f"wrote {relative}")  # ruff: ignore[print]

    if stale:
        joined = ", ".join(stale)
        print(  # ruff: ignore[print]
            f"stale view snapshots: {joined}. "
            f"Re-run `python scripts/gen_view_corpus.py`."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv[1:]))
