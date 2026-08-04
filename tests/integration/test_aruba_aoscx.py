from hier_config import HConfig
from hier_config.models import Platform


def _remediation_text(running: str, intended: str) -> str:
    remediation = HConfig.from_text(Platform.ARUBA_AOSCX, running).remediation(
        HConfig.from_text(Platform.ARUBA_AOSCX, intended),
    )
    return "\n".join(line.indented_text() for line in remediation.all_children_sorted())


def test_interface_vlan_trunk_allowed_is_additive() -> None:
    # AOS-CX trunk allowed lists are additive: the driver splits them into one
    # VLAN per line, so remediation adds the missing VLAN and negates the extras
    # individually while leaving VLANs already present (26) untouched.
    running = """
interface 1/1/1
    vlan trunk allowed 20,21,26
"""
    intended = """
interface 1/1/1
    vlan trunk allowed 25,26
"""

    assert _remediation_text(running, intended).strip() == (
        "interface 1/1/1\n"
        "  no vlan trunk allowed 20\n"
        "  no vlan trunk allowed 21\n"
        "  vlan trunk allowed 25"
    )


def test_interface_vlan_trunk_allowed_expands_ranges() -> None:
    running = """
interface 1/1/1
    vlan trunk allowed 20-21,26
"""
    intended = """
interface 1/1/1
    vlan trunk allowed 25-26
"""

    assert _remediation_text(running, intended).strip() == (
        "interface 1/1/1\n"
        "  no vlan trunk allowed 20\n"
        "  no vlan trunk allowed 21\n"
        "  vlan trunk allowed 25"
    )


def test_interface_vlan_trunk_allowed_emits_minimal_delta() -> None:
    # A small change to a large trunk list (add 166, remove 1522) must produce
    # only that delta, not a full negate-and-re-add of the whole list. Also
    # covers multi-word interface names like a multi-chassis LAG.
    running = """
interface lag 1 multi-chassis
    vlan trunk allowed 554,1520-1522,2236,2240,3232
"""
    intended = """
interface lag 1 multi-chassis
    vlan trunk allowed 554,166,1520-1521,2236,2240,3232
"""

    assert _remediation_text(running, intended).strip() == (
        "interface lag 1 multi-chassis\n"
        "  no vlan trunk allowed 1522\n"
        "  vlan trunk allowed 166"
    )


def test_aruba_aoscx_splits_top_level_vlan_lists() -> None:
    config = HConfig.from_text(
        Platform.ARUBA_AOSCX,
        """
vlan 1,10
vlan 100-102
""",
    )

    assert tuple(line.indented_text() for line in config.all_children_sorted()) == (
        "vlan 1",
        "vlan 10",
        "vlan 100",
        "vlan 101",
        "vlan 102",
    )


def test_aruba_aoscx_top_level_vlan_lists_match_individual_vlans() -> None:
    running = """
vlan 1,10
"""
    intended = """
vlan 1
vlan 10
"""

    assert not _remediation_text(running, intended).strip()


def test_aruba_aoscx_collapsed_vlan_header_with_children_is_left_untouched() -> None:
    # A collapsed range that carries configuration is left as-is rather than
    # fanning a non-unique `name` onto every expanded VLAN (which the device
    # rejects). Real collapsed ranges are unnamed/childless.
    config = HConfig.from_text(
        Platform.ARUBA_AOSCX,
        """
vlan 10-12
    name USERS
""",
    )

    assert tuple(line.indented_text() for line in config.all_children_sorted()) == (
        "vlan 10-12",
        "  name USERS",
    )


def test_aruba_aoscx_trunk_overlapping_spec_is_not_destructive() -> None:
    # An overlapping/duplicated trunk spec de-duplicates and splits, rather than
    # staying collapsed and forcing a remove-and-re-add on an additive trunk.
    running = """
interface 1/1/1
    vlan trunk allowed 20-22,21
"""
    intended = """
interface 1/1/1
    vlan trunk allowed 20
    vlan trunk allowed 21
    vlan trunk allowed 22
"""

    assert not _remediation_text(running, intended).strip()


def test_aruba_aoscx_leaves_unparseable_vlan_range_untouched() -> None:
    config = HConfig.from_text(Platform.ARUBA_AOSCX, "vlan 10-\n")

    assert tuple(line.indented_text() for line in config.all_children_sorted()) == (
        "vlan 10-",
    )


def test_aruba_aoscx_leaves_empty_trunk_spec_untouched() -> None:
    # A trunk line whose spec expands to nothing must not be deleted, otherwise
    # the interface looks like it has no allowed VLANs at all.
    config = HConfig.from_text(
        Platform.ARUBA_AOSCX,
        """
interface 1/1/1
    vlan trunk allowed ,
""",
    )
    interface = config.get_child(equals="interface 1/1/1")
    assert interface is not None
    assert [child.text for child in interface.children] == ["vlan trunk allowed ,"]


def test_aruba_aoscx_orders_new_vlans_before_interfaces() -> None:
    # A newly created VLAN must sort ahead of the interface that references it.
    running = """
interface 1/1/1
    vlan access 10
"""
    intended = """
vlan 40
    name NEW
interface 1/1/1
    vlan access 40
"""
    text = _remediation_text(running, intended)
    assert text.index("vlan 40") < text.index("interface 1/1/1")


def test_aruba_aoscx_top_level_vlan_lists_remove_only_extra_vlans() -> None:
    running = """
vlan 1,10,20
"""
    intended = """
vlan 1
vlan 10
"""

    assert _remediation_text(running, intended).strip() == "no vlan 20"


def test_aruba_aoscx_strips_terminal_prompt_lines() -> None:
    config = HConfig.from_text(
        Platform.ARUBA_AOSCX,
        """
cx-switch# show run
hostname cx-switch
cx-switch(config)# interface 1/1/1
interface 1/1/1
    description #P3# Test
cx-switch(config-if)# vlan trunk allowed 500
""",
    )

    assert tuple(line.indented_text() for line in config.all_children_sorted()) == (
        "hostname cx-switch",
        "interface 1/1/1",
        "  description #P3# Test",
    )


def test_aruba_aoscx_replaces_single_value_interface_commands() -> None:
    running = """
interface 1/1/1
    description OLD
    vlan access 10
interface vlan 10
    ip address 10.0.0.2/24
"""
    intended = """
interface 1/1/1
    description USER-PORT
    vlan access 20
interface vlan 10
    ip address 10.0.0.3/24
"""

    assert _remediation_text(running, intended).strip() == (
        "interface 1/1/1\n"
        "  description USER-PORT\n"
        "  vlan access 20\n"
        "interface vlan 10\n"
        "  ip address 10.0.0.3/24"
    )


def test_aruba_aoscx_evpn_section_adds_and_removes_vlans() -> None:
    # EVPN is remediated like any other section (Arista/NXOS style): individual
    # VLANs are added or negated, while unchanged children such as
    # arp-suppression and vlan 10 are left untouched.
    running = """
evpn
    arp-suppression
    vlan 10
        rd auto
    vlan 20
        rd auto
"""
    intended = """
evpn
    arp-suppression
    vlan 10
        rd auto
    vlan 30
        rd auto
"""

    assert _remediation_text(running, intended).strip() == (
        "evpn\n  no vlan 20\n  vlan 30\n    rd auto"
    )


def test_aruba_aoscx_vxlan_section_adds_and_removes_vnis() -> None:
    running = """
interface vxlan 1
    no shutdown
    vni 100010
        vlan 10
    vni 100020
        vlan 20
"""
    intended = """
interface vxlan 1
    no shutdown
    vni 100010
        vlan 10
    vni 100030
        vlan 30
"""

    assert _remediation_text(running, intended).strip() == (
        "interface vxlan 1\n  no vni 100020\n  vni 100030\n    vlan 30"
    )
