from hier_config.platforms.aruba_aoscx.driver import (
    HConfigDriverArubaAOSCX,
    split_interface_vlan_trunk_allowed,
)
from hier_config.platforms.utils import split_vlan_id_lists


def test_default_post_load_callbacks_are_public() -> None:
    """Built-in AOS-CX post-load callbacks are public, pinned by identity (#286)."""
    callbacks = HConfigDriverArubaAOSCX().rules.post_load_callbacks

    assert split_vlan_id_lists in callbacks
    assert split_interface_vlan_trunk_allowed in callbacks
