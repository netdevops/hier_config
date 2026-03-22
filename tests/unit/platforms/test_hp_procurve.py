from hier_config.constructors import get_hconfig
from hier_config.models import Platform


def test_fixup_aaa_port_access_ranges() -> None:
    """Test post-load callback that expands interface ranges in AAA port-access commands (covers lines 33-38)."""
    platform = Platform.HP_PROCURVE
    config_text = "aaa port-access authenticator 1/15-1/20,1/26-1/28\naaa port-access mac-based 2/14-2/16\naaa port-access authenticator 1/1"
    config = get_hconfig(platform, config_text)

    assert config.get_child(equals="aaa port-access authenticator 1/15") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/16") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/17") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/18") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/19") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/20") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/26") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/27") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/28") is not None
    assert config.get_child(equals="aaa port-access mac-based 2/14") is not None
    assert config.get_child(equals="aaa port-access mac-based 2/15") is not None
    assert config.get_child(equals="aaa port-access mac-based 2/16") is not None
    assert config.get_child(equals="aaa port-access authenticator 1/1") is not None
    assert (
        config.get_child(equals="aaa port-access authenticator 1/15-1/20,1/26-1/28")
        is None
    )
    assert config.get_child(equals="aaa port-access mac-based 2/14-2/16") is None


def test_fixup_vlan_transformation() -> None:
    """Test post-load callback that transforms VLAN config to interface config (covers lines 63-88)."""
    platform = Platform.HP_PROCURVE
    config_text = "vlan 80\n   untagged 2/43-2/44,3/43-3/44\n   tagged 1/23,2/23,Trk1\nvlan 90\n   untagged 5/29\n   no untagged 1/2-1/5"
    config = get_hconfig(platform, config_text)

    interface_2_43 = config.get_child(equals="interface 2/43")
    assert interface_2_43 is not None
    assert interface_2_43.get_child(equals="untagged vlan 80") is not None

    interface_2_44 = config.get_child(equals="interface 2/44")
    assert interface_2_44 is not None
    assert interface_2_44.get_child(equals="untagged vlan 80") is not None

    interface_3_43 = config.get_child(equals="interface 3/43")
    assert interface_3_43 is not None
    assert interface_3_43.get_child(equals="untagged vlan 80") is not None

    interface_3_44 = config.get_child(equals="interface 3/44")
    assert interface_3_44 is not None
    assert interface_3_44.get_child(equals="untagged vlan 80") is not None

    interface_5_29 = config.get_child(equals="interface 5/29")
    assert interface_5_29 is not None
    assert interface_5_29.get_child(equals="untagged vlan 90") is not None

    interface_1_23 = config.get_child(equals="interface 1/23")
    assert interface_1_23 is not None
    assert interface_1_23.get_child(equals="tagged vlan 80") is not None

    interface_2_23 = config.get_child(equals="interface 2/23")
    assert interface_2_23 is not None
    assert interface_2_23.get_child(equals="tagged vlan 80") is not None

    interface_trk1 = config.get_child(equals="interface Trk1")
    assert interface_trk1 is not None
    assert interface_trk1.get_child(equals="tagged vlan 80") is not None

    vlan_80 = config.get_child(equals="vlan 80")

    assert vlan_80 is not None
    assert vlan_80.get_child(startswith="untagged ") is None
    assert vlan_80.get_child(startswith="tagged ") is None

    vlan_90 = config.get_child(equals="vlan 90")

    assert vlan_90 is not None
    assert vlan_90.get_child(startswith="untagged ") is None
    assert vlan_90.get_child(startswith="no untagged ") is None


def test_fixup_device_profile_tagged_vlans() -> None:
    """Test post-load callback that separates device-profile tagged-vlans onto individual lines (covers lines 104-110)."""
    platform = Platform.HP_PROCURVE
    config_text = 'device-profile name "phone"\n   tagged-vlan 10,20,30\ndevice-profile name "printer"\n   tagged-vlan 40'
    config = get_hconfig(platform, config_text)
    device_profile_phone = config.get_child(equals='device-profile name "phone"')

    assert device_profile_phone is not None
    assert device_profile_phone.get_child(equals="tagged-vlan 10") is not None
    assert device_profile_phone.get_child(equals="tagged-vlan 20") is not None
    assert device_profile_phone.get_child(equals="tagged-vlan 30") is not None
    assert device_profile_phone.get_child(equals="tagged-vlan 10,20,30") is None

    device_profile_printer = config.get_child(equals='device-profile name "printer"')

    assert device_profile_printer is not None
    assert device_profile_printer.get_child(equals="tagged-vlan 40") is not None
