from hier_config import get_hconfig_fast_load
from hier_config.constructors import get_hconfig
from hier_config.models import Platform


def test_negate_with() -> None:
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig_fast_load(
        platform,
        (
            "aaa port-access authenticator 1/1 tx-period 3",
            "aaa port-access authenticator 1/1 supplicant-timeout 3",
            "aaa port-access authenticator 1/1 client-limit 4",
            "aaa port-access mac-based 1/1 addr-limit 4",
            "aaa port-access mac-based 1/1 logoff-period 3",
            'aaa port-access 1/1 critical-auth user-role "allowall"',
        ),
    )
    generated_config = get_hconfig(platform)
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "aaa port-access authenticator 1/1 tx-period 30",
        "aaa port-access authenticator 1/1 supplicant-timeout 30",
        "no aaa port-access authenticator 1/1 client-limit",
        "aaa port-access mac-based 1/1 addr-limit 1",
        "aaa port-access mac-based 1/1 logoff-period 300",
        "no aaa port-access 1/1 critical-auth user-role",
    )


def test_idempotent_for() -> None:
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig_fast_load(
        platform,
        (
            "aaa port-access authenticator 1/1 tx-period 3",
            "aaa port-access authenticator 1/1 supplicant-timeout 3",
            "aaa port-access authenticator 1/1 client-limit 4",
            "aaa port-access mac-based 1/1 addr-limit 4",
            "aaa port-access mac-based 1/1 logoff-period 3",
            'aaa port-access 1/1 critical-auth user-role "allowall"',
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        (
            "aaa port-access authenticator 1/1 tx-period 4",
            "aaa port-access authenticator 1/1 supplicant-timeout 4",
            "aaa port-access authenticator 1/1 client-limit 5",
            "aaa port-access mac-based 1/1 addr-limit 5",
            "aaa port-access mac-based 1/1 logoff-period 4",
            'aaa port-access 1/1 critical-auth user-role "allownone"',
        ),
    )
    remediation_config = running_config.config_to_get_to(generated_config)
    assert remediation_config.dump_simple() == (
        "aaa port-access authenticator 1/1 tx-period 4",
        "aaa port-access authenticator 1/1 supplicant-timeout 4",
        "aaa port-access authenticator 1/1 client-limit 5",
        "aaa port-access mac-based 1/1 addr-limit 5",
        "aaa port-access mac-based 1/1 logoff-period 4",
        'aaa port-access 1/1 critical-auth user-role "allownone"',
    )


def test_future() -> None:
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig(platform)
    remediation_config = get_hconfig_fast_load(
        platform,
        (
            "aaa port-access authenticator 3/34",
            "aaa port-access authenticator 3/34 tx-period 10",
            "aaa port-access authenticator 3/34 supplicant-timeout 10",
            "aaa port-access authenticator 3/34 client-limit 2",
            "aaa port-access mac-based 3/34",
            "aaa port-access mac-based 3/34 addr-limit 2",
            'aaa port-access 3/34 critical-auth user-role "allowall"',
        ),
    )
    future_config = running_config.future(remediation_config)
    assert not tuple(remediation_config.unified_diff(future_config))


def test_fixup_aaa_port_access_ranges() -> None:
    """Test post-load callback that expands interface ranges in AAA port-access commands (covers lines 33-38)."""
    platform = Platform.HP_PROCURVE
    config_text = "\n".join(
        [
            "aaa port-access authenticator 1/15-1/20,1/26-1/28",
            "aaa port-access mac-based 2/14-2/16",
            "aaa port-access authenticator 1/1",
        ]
    )
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
    config_text = "\n".join(
        [
            "vlan 80",
            "   untagged 2/43-2/44,3/43-3/44",
            "   tagged 1/23,2/23,Trk1",
            "vlan 90",
            "   untagged 5/29",
            "   no untagged 1/2-1/5",
        ]
    )
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
    config_text = "\n".join(
        [
            'device-profile name "phone"',
            "   tagged-vlan 10,20,30",
            'device-profile name "printer"',
            "   tagged-vlan 40",
        ]
    )
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


def test_negate_with_child_config() -> None:
    """Test negate_with returns None for non-root config without special rule (covers line 166)."""
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig_fast_load(
        platform,
        (
            "interface 1/1",
            "   speed-duplex auto",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        ("interface 1/1",),
    )
    remediation_config = running_config.config_to_get_to(generated_config)

    assert remediation_config.dump_simple() == (
        "interface 1/1",
        "  no speed-duplex auto",
    )


def test_negate_with_from_base_driver() -> None:
    """Test negate_with uses parent driver rule when applicable (covers line 163)."""
    platform = Platform.HP_PROCURVE
    running_config = get_hconfig_fast_load(
        platform,
        (
            "interface 1/1",
            "   disable",
        ),
    )
    generated_config = get_hconfig_fast_load(
        platform,
        ("interface 1/1",),
    )
    remediation_config = running_config.config_to_get_to(generated_config)

    assert remediation_config.dump_simple() == (
        "interface 1/1",
        "  enable",
    )
