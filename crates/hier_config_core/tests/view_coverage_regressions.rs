//! Boundary regressions against upstream/next@0866dc2316443909edea2d629117b44a3a9ed472.

use hier_config_core::{Platform, Tree, config_view};

#[test]
fn descriptions_skip_separator_whitespace_but_preserve_internal_whitespace() {
    // ConfigViewInterfaceBase.description and ConfigViewInterfaceHPProcurve.description
    // use split(maxsplit=1), not a split at the first whitespace character.
    for (platform, keyword, expected) in [
        (Platform::CiscoIos, "description", "\"uplink  to core\""),
        (Platform::HpProcurve, "name", "uplink  to core"),
    ] {
        let mut tree = Tree::for_platform(platform);
        let interface = tree
            .add_child(tree.root, "interface Ethernet1", true, false)
            .unwrap();
        tree.add_child(
            interface,
            &format!("{keyword} \t  \"uplink  to core\""),
            true,
            false,
        )
        .unwrap();
        let view = config_view(&tree).unwrap();
        assert_eq!(
            view.interface_view_by_name("Ethernet1")
                .unwrap()
                .description(),
            expected,
            "{platform:?}"
        );
    }
}

#[test]
fn zero_native_vlan_does_not_imply_access_mode() {
    // InterfaceVlanViewMixin.dot1q_mode checks Python truthiness of native_vlan.
    for (platform, command) in [
        (Platform::CiscoIos, "switchport access vlan 0"),
        (Platform::ArubaAoscx, "vlan access 0"),
        (Platform::HpProcurve, "untagged vlan 0"),
        (Platform::CiscoXr, "encapsulation dot1q 0"),
    ] {
        let mut tree = Tree::for_platform(platform);
        let node = tree
            .add_child(tree.root, "interface Ethernet1.0", true, false)
            .unwrap();
        tree.add_child(node, command, true, false).unwrap();
        let view = config_view(&tree).unwrap();
        let interface = view.interface_view_by_name("Ethernet1.0").unwrap();
        assert_eq!(interface.native_vlan(), Some(0), "{platform:?}");
        assert_eq!(interface.dot1q_mode(), None, "{platform:?}");
    }
}

#[test]
fn zero_native_vlan_is_not_inferred_into_the_config_vlan_inventory() {
    // HConfigViewBase.vlans and Aruba/ProCurve overrides use the same truthiness
    // check as dot1q_mode before creating an inferred Vlan (whose id is positive).
    for (platform, command) in [
        (Platform::CiscoIos, "switchport access vlan 0"),
        (Platform::ArubaAoscx, "vlan access 0"),
        (Platform::HpProcurve, "untagged vlan 0"),
    ] {
        let mut tree = Tree::for_platform(platform);
        let interface = tree
            .add_child(tree.root, "interface Ethernet1", true, false)
            .unwrap();
        tree.add_child(interface, command, true, false).unwrap();
        assert!(
            config_view(&tree).unwrap().vlans().is_empty(),
            "{platform:?}"
        );
    }
}

#[test]
fn vlan_names_skip_separator_whitespace_without_collapsing_name_spaces() {
    // HConfigViewBase.vlans uses name.text.split(maxsplit=1).
    let mut tree = Tree::for_platform(Platform::CiscoIos);
    let vlan = tree.add_child(tree.root, "vlan 10", true, false).unwrap();
    tree.add_child(vlan, "name \t  \"Staff  VLAN\"", true, false)
        .unwrap();
    let vlans = config_view(&tree).unwrap().vlans();
    assert_eq!(vlans.len(), 1);
    assert_eq!(vlans[0].name.as_deref(), Some("Staff  VLAN"));
}

#[test]
fn snmp_location_skips_separator_whitespace_without_collapsing_location_spaces() {
    // HConfigViewBase.location uses location.text.split(maxsplit=2).
    let mut tree = Tree::for_platform(Platform::CiscoIos);
    tree.add_child(
        tree.root,
        "snmp-server location \t  \"Rack  1\"",
        true,
        false,
    )
    .unwrap();
    assert_eq!(config_view(&tree).unwrap().location(), "Rack  1");
}
