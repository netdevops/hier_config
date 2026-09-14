"""Deleted interface views must not panic or poison the owning configuration."""

import pytest

from hier_config import HConfig, Platform, get_hconfig_view


@pytest.mark.parametrize(
    "attribute",
    ("name", "description", "enabled", "ipv4_interfaces", "tagged_vlans", "config"),
)
def test_deleted_interface_view_raises_value_error(attribute: str) -> None:
    config = HConfig.from_text(
        Platform.CISCO_IOS,
        "hostname router\ninterface GigabitEthernet0/0\n description uplink",
    )
    view = get_hconfig_view(config)
    interface = view.interface_view_by_name("GigabitEthernet0/0")
    assert interface is not None
    interface.config.delete()

    with pytest.raises(ValueError, match="deleted"):
        getattr(interface, attribute)

    assert config.to_lines() == ("hostname router",)
    assert view.hostname == "router"
    config.add_child("interface GigabitEthernet0/1")
    assert view.interface_view_by_name("GigabitEthernet0/1") is not None
    with pytest.raises(ValueError, match="deleted"):
        getattr(interface, attribute)
