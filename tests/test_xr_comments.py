from hier_config import get_hconfig, get_hconfig_fast_load
from hier_config.models import Platform


def test_xr_comment_attached_to_next_sibling() -> None:
    """IOS-XR inline comments are attached to the next sibling's comments set."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
router isis backbone
 ! ISIS network number should be encoded with 0-padded loopback IP
 net 49.0001.1921.2022.0222.00
""",
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    net_child = router_isis.get_child(
        startswith="net ",
    )
    assert net_child is not None
    assert (
        "ISIS network number should be encoded with 0-padded loopback IP"
        in net_child.comments
    )


def test_xr_multiple_comments_before_line() -> None:
    """Multiple consecutive comment lines are all attached to the next sibling."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
router isis backbone
 ! first comment
 ! second comment
 net 49.0001.1921.2022.0222.00
""",
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    net_child = router_isis.get_child(startswith="net ")
    assert net_child is not None
    assert "first comment" in net_child.comments
    assert "second comment" in net_child.comments


def test_xr_comment_lines_not_parsed_as_children() -> None:
    """Comment lines starting with ! should not appear as config children."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
router isis backbone
 ! this is a comment
 net 49.0001.1921.2022.0222.00
""",
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    for child in router_isis.all_children():
        assert not child.text.startswith("!")


def test_xr_top_level_bang_delimiters_stripped() -> None:
    """Top-level ! delimiters (with no comment text) are stripped."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
hostname router1
!
interface GigabitEthernet0/0/0/0
 description test
!
""",
    )
    children = [child.text for child in config.children]
    assert "hostname router1" in children
    assert "interface GigabitEthernet0/0/0/0" in children
    assert "!" not in children


def test_xr_comment_preservation_with_fast_load() -> None:
    """Comments are also preserved when using get_hconfig_fast_load."""
    config = get_hconfig_fast_load(
        Platform.CISCO_XR,
        (
            "router isis backbone",
            " ! loopback comment",
            " net 49.0001.0000.0000.0001.00",
        ),
    )
    router_isis = config.get_child(equals="router isis backbone")
    assert router_isis is not None
    net_child = router_isis.get_child(startswith="net ")
    assert net_child is not None
    assert "loopback comment" in net_child.comments


def test_xr_hash_comments_still_stripped() -> None:
    """Lines starting with # are still stripped (not preserved)."""
    config = get_hconfig(
        Platform.CISCO_XR,
        """\
hostname router1
# this should be stripped
interface GigabitEthernet0/0/0/0
""",
    )
    for child in config.all_children():
        assert not child.text.startswith("#")
