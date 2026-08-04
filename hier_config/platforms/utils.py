"""Shared helpers for platform drivers that transform a parsed config tree."""

from hier_config.platforms.functions import expand_range
from hier_config.root import HConfig


def split_vlan_id_lists(config: HConfig) -> None:
    """Split a collapsed ``vlan 1,10`` / ``vlan 10-12`` header into one per VLAN.

    Several platforms (Cisco IOS, Aruba AOS-CX, ...) can render unnamed VLANs
    collapsed onto a single comma/range line. Splitting them at load time lets
    the diff engine match VLANs block-to-block against an intended config that
    lists them separately, avoiding a destructive ``no vlan 1,10``.

    Only a bare (childless) collapsed header is split: a real collapsed range is
    unnamed, because devices reject per-VLAN settings such as ``name`` on a
    range, so a header that carries configuration is left untouched rather than
    fanning its children (and a non-unique ``name``) onto every expanded VLAN. A
    spec that does not parse as pure integers/ranges is likewise left untouched.
    """
    for vlan in tuple(config.get_children(re_search=r"^vlan \d[\d,\-]*$")):
        spec = vlan.text.split(maxsplit=1)[1]
        if not any(separator in spec for separator in (",", "-")):
            continue
        if vlan.children:
            continue
        try:
            vlan_ids = expand_range(spec)
        except ValueError:
            continue
        if not vlan_ids:
            continue
        for vlan_id in vlan_ids:
            config.add_child(f"vlan {vlan_id}", return_if_present=True)
        vlan.delete()
