"""Post-load callbacks must run in the order the driver declared them (#302)."""

from hier_config import Platform
from hier_config.constructors import (
    _core_runs_post_load,  # pyright: ignore[reportPrivateUsage]
    hconfig_from_lines,
    hconfig_from_text,
)
from hier_config.registry import get_hconfig_driver
from hier_config.root import HConfig

_ACL_CONFIG = "ip access-list extended TEST\n  permit tcp any any eq 22\n"


def _append_permit_any(config: HConfig) -> None:
    """Custom callback in the style of the one the reviewer used."""
    for acl in config.get_children(startswith="ip access-list "):
        acl.add_child("permit ip any any")


def test_stock_ios_callbacks_let_the_core_run() -> None:
    """The stock list is core-owned first, so the core's pass is still used."""
    assert _core_runs_post_load(get_hconfig_driver(Platform.CISCO_IOS))


def test_callback_appended_after_the_stock_list_keeps_the_core_pass() -> None:
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.post_load_callbacks.append(_append_permit_any)

    assert _core_runs_post_load(driver)


def test_callback_inserted_before_a_core_owned_one_suppresses_the_core_pass() -> None:
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.post_load_callbacks.insert(0, _append_permit_any)

    assert not _core_runs_post_load(driver)


def test_callback_inserted_first_runs_before_the_stock_callbacks() -> None:
    """A callback ahead of `add_acl_sequence_numbers` must get numbered too."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.post_load_callbacks.insert(0, _append_permit_any)

    config = hconfig_from_text(driver, _ACL_CONFIG)

    acl = config.get_child(startswith="ip access-list ")
    assert acl is not None
    assert [child.text for child in acl.children] == [
        "10 permit tcp any any eq 22",
        "20 permit ip any any",
    ]


def test_callback_inserted_first_runs_before_stock_callbacks_on_fast_load() -> None:
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.post_load_callbacks.insert(0, _append_permit_any)

    config = hconfig_from_lines(driver, tuple(_ACL_CONFIG.splitlines()))

    acl = config.get_child(startswith="ip access-list ")
    assert acl is not None
    assert [child.text for child in acl.children] == [
        "10 permit tcp any any eq 22",
        "20 permit ip any any",
    ]


def test_callback_appended_last_still_runs_after_the_stock_callbacks() -> None:
    """The fast path must keep producing the unnumbered trailing entry."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.post_load_callbacks.append(_append_permit_any)

    config = hconfig_from_text(driver, _ACL_CONFIG)

    acl = config.get_child(startswith="ip access-list ")
    assert acl is not None
    assert [child.text for child in acl.children] == [
        "10 permit tcp any any eq 22",
        "permit ip any any",
    ]


def test_core_owned_callbacks_are_not_applied_twice_when_the_core_is_suppressed() -> (
    None
):
    """Suppressing the core pass must not double-number the ACL entries."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    driver.rules.post_load_callbacks.insert(0, _append_permit_any)

    config = hconfig_from_text(driver, _ACL_CONFIG)

    acl = config.get_child(startswith="ip access-list ")
    assert acl is not None
    assert all(
        not child.text.startswith(("10 10 ", "20 20 ")) for child in acl.children
    )
