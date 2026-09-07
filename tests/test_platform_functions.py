"""Tests for the Python-level platform helper functions.

``split_vlan_id_lists`` and the pure-Python ``convert_to_set_commands``
fallback remain part of the public Python surface even though the equivalent
work is normally done inside the Rust core, so they are exercised directly
here.
"""

import pytest

from hier_config import Platform, get_hconfig
from hier_config.platforms import functions
from hier_config.platforms.functions import convert_to_set_commands, expand_range
from hier_config.platforms.utils import split_vlan_id_lists


def test_expand_range_deduplicates_overlaps() -> None:
    """Overlapping segments collapse instead of repeating ids."""
    assert expand_range("10,10-12") == (10, 11, 12)


def test_expand_range_mixes_ranges_and_singletons() -> None:
    """A comma-separated spec may combine spans with individual ids."""
    assert expand_range("1-3,7") == (1, 2, 3, 7)


@pytest.mark.parametrize("spec", ("1-2-3", "a", "5-1"))
def test_expand_range_rejects_malformed_segments(spec: str) -> None:
    """Malformed or reversed segments raise rather than truncate."""
    with pytest.raises(ValueError, match=r".*"):
        expand_range(spec)


def test_split_vlan_id_lists_expands_comma_and_range() -> None:
    """A childless collapsed VLAN header fans out into one header per VLAN."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("vlan 1,10")
    config.add_child("vlan 20-22")

    split_vlan_id_lists(config)

    assert config.dump_simple() == (
        "vlan 1",
        "vlan 10",
        "vlan 20",
        "vlan 21",
        "vlan 22",
    )


def test_split_vlan_id_lists_leaves_single_vlan_untouched() -> None:
    """A header with no separator is not a collapsed range."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("vlan 10")

    split_vlan_id_lists(config)

    assert config.dump_simple() == ("vlan 10",)


def test_split_vlan_id_lists_leaves_configured_header_untouched() -> None:
    """A collapsed header carrying children is left alone rather than fanned out."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_children_deep(("vlan 10,20", "name legacy"))

    split_vlan_id_lists(config)

    assert config.dump_simple() == ("vlan 10,20", "  name legacy")


def test_split_vlan_id_lists_leaves_unparsable_spec_untouched() -> None:
    """A spec that is not pure integers/ranges is left untouched."""
    config = get_hconfig(Platform.CISCO_IOS)
    config.add_child("vlan 1-2-3")

    split_vlan_id_lists(config)

    assert config.dump_simple() == ("vlan 1-2-3",)


def test_convert_to_set_commands_matches_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pure-Python fallback produces the same output as the Rust path."""
    config_raw = (
        "system {\n"
        "    host-name router1;\n"
        "    services {\n"
        "        ssh;\n"
        "    }\n"
        "}\n"
        "set interfaces ge-0/0/0 unit 0"
    )
    native_result = convert_to_set_commands(config_raw)

    monkeypatch.setattr(functions, "_convert_to_set_commands_rust", None)
    fallback_result = convert_to_set_commands(config_raw)

    assert fallback_result == native_result
    assert "set system host-name router1" in fallback_result
    assert "set system services ssh" in fallback_result
    assert "set interfaces ge-0/0/0 unit 0" in fallback_result


def test_convert_to_set_commands_fallback_skips_blank_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blank lines in the source config do not emit empty set commands."""
    monkeypatch.setattr(functions, "_convert_to_set_commands_rust", None)
    assert convert_to_set_commands("\n\nsystem {\n\n    host-name r1;\n}\n") == (
        "set system host-name r1"
    )
