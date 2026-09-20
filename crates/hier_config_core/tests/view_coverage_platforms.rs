//! Native equivalents of tests/unit/platforms/views, with boundary cases.
//!
//! Raw Generic trees deliberately preserve collapsed ranges and malformed commands
//! so view behavior is tested independently of vendor post-load normalization.
//! Expectations follow the Python views at upstream/next@0866dc2; total native
//! fallbacks (None/empty rather than Python exceptions) are tested separately.

use std::net::Ipv4Addr;

use hier_config_core::view::{
    InterfaceDot1qMode, InterfaceDuplex, InterfaceOps, InterfaceView, NacHostMode, StackMember,
    Vlan,
};
use hier_config_core::{
    ConfigView, MatchRule, Platform, Tree, config_from_text, config_view, view_ops_for_platform,
};

const PLATFORMS: [Platform; 6] = [
    Platform::AristaEos,
    Platform::ArubaAoscx,
    Platform::CiscoIos,
    Platform::CiscoNxos,
    Platform::CiscoXr,
    Platform::HpProcurve,
];

fn raw_tree(text: &str) -> Tree {
    Tree::from_str(Platform::Generic, text).unwrap()
}

fn view(tree: &Tree, platform: Platform) -> ConfigView<'_> {
    ConfigView::new(tree, view_ops_for_platform(platform).unwrap())
}

fn interface_tree(name: &str, commands: &[&str]) -> Tree {
    let mut tree = Tree::for_platform(Platform::Generic);
    let interface = tree
        .add_child(tree.root, &format!("interface {name}"), true, false)
        .unwrap();
    for command in commands {
        tree.add_child(interface, command, true, false).unwrap();
    }
    tree
}

fn interface(tree: &Tree, platform: Platform) -> InterfaceView<'_> {
    view(tree, platform).interface_views()[0]
}

#[test]
fn vendor_capabilities_and_default_physical_attributes() {
    for platform in PLATFORMS {
        let tree = interface_tree("Ethernet1/2", &[]);
        let interface = interface(&tree, platform);
        let physical = matches!(
            platform,
            Platform::CiscoIos | Platform::ArubaAoscx | Platform::HpProcurve
        );
        assert!(interface.ops().supports_vlan());
        assert_eq!(interface.is_physical(), physical, "{platform:?}");
        assert_eq!(interface.ops().supports_nac(), physical);
        assert_eq!(interface.module_number(), physical.then_some(1));
        assert_eq!(interface.port_number(), Some(2));
        assert_eq!(
            interface.duplex(),
            physical.then_some(InterfaceDuplex::Auto)
        );
        assert_eq!(interface.poe(), physical.then_some(true));
        assert_eq!(interface.speed(), None);
    }
}

#[test]
fn vendor_empty_interfaces_have_no_nac_or_addresses() {
    for platform in PLATFORMS {
        let tree = interface_tree("Ethernet1/2", &[]);
        let interface = interface(&tree, platform);
        assert_eq!(interface.description(), "");
        assert_eq!(interface.enabled(), platform != Platform::ArubaAoscx);
        assert_eq!(interface.ipv4_interface(), None);
        assert!(interface.ipv4_interfaces().is_empty());
        assert_eq!(interface.vrf(), "");
        assert!(!interface.has_nac());
        assert!(!interface.nac_control_direction_in());
        assert!(!interface.nac_mab_first());
        assert_eq!(interface.nac_host_mode(), None);
        let clients = (platform == Platform::HpProcurve).then_some(1);
        assert_eq!(interface.nac_max_dot1x_clients(), clients);
        assert_eq!(interface.nac_max_mab_clients(), clients);
    }
}

#[test]
fn vendor_empty_physical_interfaces_have_no_logical_parent() {
    for platform in PLATFORMS {
        let tree = interface_tree("Ethernet1/2", &[]);
        let interface = interface(&tree, platform);
        assert_eq!(interface.bundle_id(), None);
        assert_eq!(interface.bundle_name(), None);
        assert!(interface.bundle_member_interfaces().is_empty());
        assert!(!interface.is_bundle());
        assert!(!interface.is_loopback());
        assert!(!interface.is_svi());
        assert!(!interface.is_subinterface());
        assert_eq!(interface.parent_name(), None);
        assert_eq!(interface.subinterface_number(), None);
    }
}

#[test]
fn cisco_style_bundles_match_complete_ids_and_preserve_member_order() {
    for (platform, prefix, membership) in [
        (Platform::AristaEos, "Port-Channel", "channel-group"),
        (Platform::CiscoIos, "Port-channel", "channel-group"),
        (Platform::CiscoNxos, "port-channel", "channel-group"),
        (Platform::CiscoXr, "Bundle-Ether", "bundle id"),
    ] {
        let tree = raw_tree(&format!(
            "interface {prefix}10\n\
             interface Ethernet2/3\n  {membership} 10 mode active\n\
             interface Ethernet2/4\n  {membership} 100 mode active\n\
             interface Ethernet2/5\n  {membership} 10 mode passive\n\
             interface Ethernet2/6\n  description unrelated\n\
             router bgp 1\n  {membership} 10"
        ));
        let config = view(&tree, platform);
        let bundle = config.interface_views()[0];
        assert!(bundle.is_bundle(), "{platform:?}");
        assert_eq!(bundle.number(), "10");
        assert_eq!(bundle.port_number(), Some(10));
        assert_eq!(bundle.bundle_id(), None);
        assert_eq!(
            bundle.bundle_member_interfaces(),
            ["Ethernet2/3", "Ethernet2/5"]
        );
        let member = config.interface_views()[1];
        assert_eq!(member.bundle_id().as_deref(), Some("10"));
        assert_eq!(member.bundle_name(), Some(format!("{prefix}10")));
        assert!(member.bundle_member_interfaces().is_empty());
        assert_eq!(member.parent_name(), None);
    }
}

#[test]
fn cisco_style_vlan_precedence_ranges_and_default_access() {
    let cases = [
        (
            "Ethernet1",
            vec![],
            Some(1),
            vec![],
            false,
            Some(InterfaceDot1qMode::Access),
        ),
        (
            "Ethernet1",
            vec!["switchport access vlan 22"],
            Some(22),
            vec![],
            false,
            Some(InterfaceDot1qMode::Access),
        ),
        (
            "Ethernet1",
            vec!["no switchport", "switchport access vlan 22"],
            None,
            vec![],
            false,
            None,
        ),
        (
            "Ethernet1",
            vec!["ip address dhcp", "switchport access vlan 22"],
            None,
            vec![],
            false,
            None,
        ),
        ("LoOpBaCk1", vec![], None, vec![], false, None),
        (
            "VlAn22",
            vec!["switchport access vlan 22"],
            None,
            vec![],
            false,
            None,
        ),
        (
            "Ethernet1",
            vec!["switchport mode trunk"],
            None,
            vec![],
            true,
            Some(InterfaceDot1qMode::TaggedAll),
        ),
        (
            "Ethernet1",
            vec!["switchport mode trunk", "switchport trunk native vlan 22"],
            Some(22),
            vec![],
            true,
            Some(InterfaceDot1qMode::TaggedAll),
        ),
        (
            "Ethernet1",
            vec![
                "switchport mode trunk",
                "switchport trunk allowed vlan 10-12,20",
            ],
            None,
            vec![10, 11, 12, 20],
            false,
            Some(InterfaceDot1qMode::Tagged),
        ),
    ];
    for platform in [Platform::AristaEos, Platform::CiscoIos, Platform::CiscoNxos] {
        for (name, commands, native, tagged, all, mode) in &cases {
            let tree = interface_tree(name, commands);
            let interface = interface(&tree, platform);
            assert_eq!(
                interface.native_vlan(),
                *native,
                "{platform:?} {commands:?}"
            );
            assert_eq!(interface.tagged_vlans(), *tagged);
            assert_eq!(interface.tagged_all(), *all);
            assert_eq!(interface.dot1q_mode(), *mode);
        }
    }
}

#[test]
fn subinterface_encapsulation_uses_vendor_spelling_and_token_index() {
    for (platform, encapsulation) in [
        (Platform::AristaEos, "encapsulation dot1q vlan 123"),
        (Platform::CiscoIos, "encapsulation dot1Q 123"),
        (Platform::CiscoNxos, "encapsulation dot1q 123"),
        (Platform::CiscoXr, "encapsulation dot1q 123"),
    ] {
        let tree = interface_tree(
            "Ethernet2/3.123",
            &[encapsulation, "no switchport", "ip address 192.0.2.1/24"],
        );
        let interface = interface(&tree, platform);
        assert!(interface.is_subinterface());
        assert_eq!(interface.number(), "2/3.123");
        assert_eq!(interface.parent_name().as_deref(), Some("Ethernet2/3"));
        assert_eq!(interface.subinterface_number(), Some(123));
        assert_eq!(interface.port_number(), Some(3));
        assert_eq!(interface.native_vlan(), Some(123), "{platform:?}");
        assert_eq!(interface.dot1q_mode(), Some(InterfaceDot1qMode::Access));
    }
}

#[test]
fn ipv4_addresses_preserve_host_bits_order_and_secondary_addresses() {
    for platform in PLATFORMS {
        let keyword = if platform == Platform::CiscoXr {
            "ipv4"
        } else {
            "ip"
        };
        let commands = [
            format!("{keyword} address dhcp"),
            format!("{keyword} address not-an-address"),
            format!("{keyword} address 192.0.2.7/24"),
            format!("{keyword} address 198.51.100.9/32 secondary"),
        ];
        let tree = interface_tree(
            "Ethernet1",
            &commands.iter().map(String::as_str).collect::<Vec<_>>(),
        );
        let interface = interface(&tree, platform);
        assert_eq!(
            interface
                .ipv4_interfaces()
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>(),
            ["192.0.2.7/24", "198.51.100.9/32"],
            "{platform:?}"
        );
        assert_eq!(
            interface.ipv4_interface().unwrap().to_string(),
            "192.0.2.7/24"
        );
    }
}

#[test]
fn dotted_netmasks_and_noncontiguous_masks_have_distinct_results() {
    for platform in [
        Platform::AristaEos,
        Platform::CiscoIos,
        Platform::CiscoNxos,
        Platform::CiscoXr,
        Platform::HpProcurve,
    ] {
        let keyword = if platform == Platform::CiscoXr {
            "ipv4"
        } else {
            "ip"
        };
        let commands = [
            format!("{keyword} address 192.0.2.9 255.255.255.0"),
            format!("{keyword} address 198.51.100.9 255.255.255.255 secondary"),
            format!("{keyword} address 198.51.100.10 255.0.255.0"),
            format!("{keyword} address 203.0.113.1/33"),
        ];
        let tree = interface_tree(
            "Ethernet1",
            &commands.iter().map(String::as_str).collect::<Vec<_>>(),
        );
        assert_eq!(
            interface(&tree, platform)
                .ipv4_interfaces()
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>(),
            ["192.0.2.9/24", "198.51.100.9/32"],
            "{platform:?}"
        );
    }
}

#[test]
fn vrf_syntax_is_vendor_specific_and_preserves_case() {
    for (platform, command) in [
        (Platform::AristaEos, "vrf BLUE"),
        (Platform::AristaEos, "vrf forwarding BLUE"),
        (Platform::CiscoIos, "ip vrf forwarding BLUE"),
        (Platform::CiscoNxos, "vrf member BLUE"),
        (Platform::CiscoXr, "vrf BLUE"),
        (Platform::ArubaAoscx, "vrf attach BLUE"),
    ] {
        let tree = interface_tree("Ethernet1", &[command]);
        assert_eq!(interface(&tree, platform).vrf(), "BLUE", "{platform:?}");
    }
    let tree = interface_tree("Ethernet1", &["vrf forwarding"]);
    assert_eq!(interface(&tree, Platform::AristaEos).vrf(), "");
}

#[test]
fn default_gateway_syntax_and_hostname_normalization() {
    for (platform, gateway) in [
        (Platform::AristaEos, "ip route 0.0.0.0/0 192.0.2.254"),
        (Platform::CiscoIos, "ip default-gateway 192.0.2.254"),
        (Platform::CiscoNxos, "ip route 0.0.0.0/0 192.0.2.254"),
        (Platform::ArubaAoscx, "ip route 0.0.0.0/0 192.0.2.254"),
        (Platform::HpProcurve, "ip default-gateway 192.0.2.254"),
        (
            Platform::CiscoXr,
            "router static\n  address-family ipv4 unicast\n    0.0.0.0/0 192.0.2.254",
        ),
    ] {
        let tree = raw_tree(&format!("hostname DC-CORE\n{gateway}"));
        let config = view(&tree, platform);
        assert_eq!(config.hostname().as_deref(), Some("dc-core"));
        assert_eq!(
            config.ipv4_default_gw(),
            Some(Ipv4Addr::new(192, 0, 2, 254))
        );
        let invalid_tree = raw_tree(&gateway.replace("192.0.2.254", "not-an-ip"));
        assert_eq!(view(&invalid_tree, platform).ipv4_default_gw(), None);
        assert_eq!(view(&invalid_tree, platform).hostname(), None);
    }
    let tree = raw_tree("hostname \"DC-CORE\"");
    assert_eq!(
        view(&tree, Platform::HpProcurve).hostname().as_deref(),
        Some("dc-core")
    );
}

#[test]
fn xr_gateway_requires_the_global_ipv4_static_route_hierarchy() {
    for text in [
        "",
        "router static",
        "router static\n  address-family ipv6 unicast\n    0.0.0.0/0 192.0.2.1",
        "router static\n  address-family ipv4 unicast\n    192.0.2.0/24 192.0.2.1",
        "router static\n  vrf BLUE\n    address-family ipv4 unicast\n      0.0.0.0/0 192.0.2.1",
        "ip route 0.0.0.0/0 192.0.2.1",
    ] {
        let tree = raw_tree(text);
        assert_eq!(
            view(&tree, Platform::CiscoXr).ipv4_default_gw(),
            None,
            "{text}"
        );
    }
}

#[test]
fn xr_never_invents_a_switchport_native_vlan() {
    for (name, commands, expected) in [
        ("Ethernet1", vec!["encapsulation dot1q 12"], None),
        ("Ethernet1.12", vec![], None),
        ("Ethernet1.12", vec!["encapsulation dot1q bad"], None),
        ("Ethernet1.12", vec!["encapsulation dot1q 12"], Some(12)),
    ] {
        let tree = interface_tree(name, &commands);
        assert_eq!(interface(&tree, Platform::CiscoXr).native_vlan(), expected);
    }
}

#[test]
fn ios_nac_enablement_has_independent_mab_and_dot1x_paths() {
    for (commands, enabled) in [
        (vec![], false),
        (vec!["authentication port-control auto"], true),
        (vec!["mab"], true),
        (vec!["authentication port-control force-authorized"], false),
    ] {
        let tree = interface_tree("GigabitEthernet1/1", &commands);
        assert_eq!(interface(&tree, Platform::CiscoIos).has_nac(), enabled);
    }
    for (word, expected) in [
        ("single-host", Some(NacHostMode::SingleHost)),
        ("multi-domain", Some(NacHostMode::MultiDomain)),
        ("multi-auth", Some(NacHostMode::MultiAuth)),
        ("multi-host", Some(NacHostMode::MultiHost)),
        ("unknown", None),
    ] {
        let command = format!("authentication host-mode {word}");
        let tree = interface_tree(
            "GigabitEthernet1/1",
            &[
                &command,
                "authentication control-direction in",
                "authentication order mab dot1x",
            ],
        );
        let interface = interface(&tree, Platform::CiscoIos);
        assert_eq!(interface.nac_host_mode(), expected);
        assert!(interface.nac_control_direction_in());
        assert!(interface.nac_mab_first());
    }
}

#[test]
fn ios_and_aruba_physical_attributes_override_defaults() {
    for (platform, no_poe) in [
        (Platform::CiscoIos, "power inline never"),
        (Platform::ArubaAoscx, "no power-over-ethernet"),
    ] {
        for (duplex, expected) in [
            ("full", InterfaceDuplex::Full),
            ("half", InterfaceDuplex::Half),
            ("auto", InterfaceDuplex::Auto),
            ("unknown", InterfaceDuplex::Auto),
        ] {
            let duplex_command = format!("duplex {duplex}");
            let tree = interface_tree("Ethernet2/5", &[&duplex_command, "speed 1000", no_poe]);
            let interface = interface(&tree, platform);
            assert_eq!(interface.duplex(), Some(expected));
            assert_eq!(interface.speed(), Some(vec![1000]));
            assert_eq!(interface.poe(), Some(false));
            assert_eq!(interface.module_number(), Some(2));
        }
        for speed in ["speed auto", "speed not-a-number", "speed 4294967296"] {
            let tree = interface_tree("Ethernet1", &[speed]);
            assert_eq!(interface(&tree, platform).speed(), None);
        }
    }
}

#[test]
fn ios_stack_member_priorities_are_derived_not_read_from_priority_lines() {
    let tree = raw_tree(
        "switch 1 provision c9300\nswitch 2 provision c9200\n\
         switch 2 priority 12\nswitch invalid provision ignored\n\
         switch 256 provision boundary",
    );
    assert_eq!(
        view(&tree, Platform::CiscoIos).stack_members(),
        [
            StackMember {
                id: 1,
                priority: 255,
                model: "c9300".into(),
                mac_address: None
            },
            StackMember {
                id: 2,
                priority: 254,
                model: "c9200".into(),
                mac_address: None
            },
            StackMember {
                id: 256,
                priority: 0,
                model: "boundary".into(),
                mac_address: None
            },
        ]
    );
}

#[test]
fn aruba_lag_multichassis_keeps_full_name_and_resolves_exact_membership() {
    let tree = raw_tree(
        "interface lag 48 multi-chassis\n\
         interface 1/1/47\n  lag 48\n\
         interface 1/1/48\n  lag 48\n\
         interface 1/1/49\n  lag 480\n\
         interface 1/1/50\n  lag 48 extra\n\
         interface 1/1/47.7\n  lag 48",
    );
    let config = view(&tree, Platform::ArubaAoscx);
    let bundle = config.interface_views()[0];
    assert_eq!(bundle.name(), "lag 48 multi-chassis");
    assert_eq!(bundle.number(), "48 multi-chassis");
    assert_eq!(bundle.bundle_id().as_deref(), Some("48"));
    assert_eq!(bundle.bundle_name().as_deref(), Some("lag 48"));
    assert_eq!(bundle.parent_name(), None);
    assert_eq!(
        bundle.bundle_member_interfaces(),
        ["1/1/47", "1/1/48", "1/1/47.7"]
    );
    let member = config.interface_views()[1];
    assert_eq!(member.parent_name().as_deref(), Some("lag 48"));
    assert_eq!(member.bundle_name().as_deref(), Some("lag 48"));
    assert!(member.bundle_member_interfaces().is_empty());
    let subinterface = config.interface_views()[5];
    assert_eq!(subinterface.parent_name().as_deref(), Some("1/1/47"));
    assert_eq!(subinterface.subinterface_number(), Some(7));
}

#[test]
fn aruba_enabled_requires_explicit_no_shutdown_even_with_conflicting_shutdown() {
    for (commands, expected) in [
        (vec![], false),
        (vec!["shutdown"], false),
        (vec!["no shutdown"], true),
        (vec!["shutdown", "no shutdown"], true),
    ] {
        let tree = interface_tree("1/1/1", &commands);
        assert_eq!(interface(&tree, Platform::ArubaAoscx).enabled(), expected);
    }
}

#[test]
fn aruba_vlan_membership_unions_sorts_deduplicates_and_skips_bad_ranges() {
    let tree = interface_tree(
        "1/1/1",
        &[
            "vlan access 3",
            "vlan trunk native 7",
            "vlan trunk allowed 20-22,7",
            "vlan trunk allowed 21,2",
            "vlan trunk allowed 10-12-13",
            "vlan trunk allowed none",
        ],
    );
    let interface = interface(&tree, Platform::ArubaAoscx);
    assert_eq!(interface.native_vlan(), Some(7));
    assert_eq!(interface.tagged_vlans(), [2, 7, 20, 21, 22]);
    assert!(!interface.tagged_all());
    assert_eq!(interface.dot1q_mode(), Some(InterfaceDot1qMode::Tagged));
    for name in ["loopback 1", "vlan 7"] {
        let logical_tree = interface_tree(name, &["vlan access 7"]);
        assert_eq!(
            view(&logical_tree, Platform::ArubaAoscx).interface_views()[0].native_vlan(),
            None
        );
    }
    let all_tree = interface_tree("1/1/1", &["vlan trunk allowed all", "vlan access 7"]);
    let all = view(&all_tree, Platform::ArubaAoscx).interface_views()[0];
    assert!(all.tagged_all());
    assert_eq!(all.dot1q_mode(), Some(InterfaceDot1qMode::TaggedAll));
}

#[test]
fn aruba_nac_is_scoped_to_the_interface_not_global_aaa() {
    let tree = raw_tree(
        "aaa authentication port-access global\ninterface 1/1/1\n\
         interface 1/1/2\n  aaa authentication port-access dot1x authenticator",
    );
    let interfaces = view(&tree, Platform::ArubaAoscx).interface_views();
    assert!(!interfaces[0].has_nac());
    assert!(interfaces[1].has_nac());
    assert!(!interfaces[1].nac_control_direction_in());
    assert!(!interfaces[1].nac_mab_first());
    assert_eq!(interfaces[1].nac_host_mode(), None);
}

#[test]
fn aruba_vlan_inventory_includes_unnamed_members_once_after_explicit_vlans() {
    let tree = raw_tree(
        "vlan 10-11\n  name \"Staff\"\nvlan 12\n  name \"\"\nvlan 10-12-13\n\
         interface 1/1/1\n  vlan trunk allowed 11,20\n  vlan access 30\n\
         interface 1/1/2\n  vlan trunk allowed 20\n  vlan access 30",
    );
    assert_eq!(
        view(&tree, Platform::ArubaAoscx).vlans(),
        [
            Vlan {
                id: 10,
                name: Some("Staff".into())
            },
            Vlan {
                id: 11,
                name: Some("Staff".into())
            },
            Vlan { id: 12, name: None },
            Vlan { id: 20, name: None },
            Vlan { id: 30, name: None },
        ]
    );
}

#[test]
fn procurve_bundles_expand_physical_port_ranges_and_capitalize_names() {
    let tree = raw_tree(
        "trunk 1/45-1/46,2/45 trk1 lacp\n\
         interface Trk1\ninterface 1/45\ninterface 1/46\ninterface 2/45\ninterface 2/46",
    );
    let interfaces = view(&tree, Platform::HpProcurve).interface_views();
    assert!(interfaces[0].is_bundle());
    assert_eq!(
        interfaces[0].bundle_member_interfaces(),
        ["1/45", "1/46", "2/45"]
    );
    for member in &interfaces[1..4] {
        assert_eq!(member.bundle_name().as_deref(), Some("Trk1"));
        assert_eq!(member.bundle_id().as_deref(), Some("1"));
    }
    assert_eq!(interfaces[4].bundle_name(), None);
    assert_eq!(interfaces[4].bundle_id(), None);
}

#[test]
fn procurve_missing_or_malformed_trunks_have_total_native_fallbacks() {
    for text in [
        "interface Trk1",
        "trunk 1/A1-1/B2 trk1 lacp\ninterface Trk1",
        "trunk 1/A1-1/B2 trk1 lacp\ninterface 1/1",
        "trunk 1/1\ninterface 1/1",
    ] {
        let tree = raw_tree(text);
        let interface = interface(&tree, Platform::HpProcurve);
        assert_eq!(interface.bundle_name(), None);
        assert!(interface.bundle_member_interfaces().is_empty());
    }
}

#[test]
fn procurve_interface_names_include_addressed_vlan_blocks_but_not_l2_vlans() {
    let tree = raw_tree(
        "interface 1/1\nvlan 10\n  ip address 192.0.2.1 255.255.255.0\n\
         vlan 20\n  name Layer2\nvlan 30\n  ip address dhcp",
    );
    let config = view(&tree, Platform::HpProcurve);
    assert_eq!(config.interfaces().len(), 1);
    assert_eq!(config.interface_names(), ["1/1", "vlan 10", "vlan 30"]);
    let vlan = config.interface_view_by_name("vlan 10").unwrap();
    assert!(vlan.is_svi());
    assert_eq!(vlan.ipv4_interface().unwrap().to_string(), "192.0.2.1/24");
    assert!(
        config
            .interface_view_by_name("vlan 30")
            .unwrap()
            .ipv4_interfaces()
            .is_empty()
    );
}

#[test]
fn procurve_nac_global_commands_match_exact_port_not_prefix() {
    let tree = raw_tree(
        "interface 1/1\ninterface 1/10\ninterface 1/2\n\
         aaa port-access authenticator 1/1\n\
         aaa port-access mac-based 1/2\n\
         aaa port-access 1/1 controlled-direction in\n\
         aaa port-access 1/1 auth-order mac-based authenticator\n\
         aaa port-access authenticator 1/1 client-limit 8\n\
         aaa port-access mac-based 1/1 addr-limit 12",
    );
    let interfaces = view(&tree, Platform::HpProcurve).interface_views();
    let first = interfaces[0];
    assert!(first.has_nac());
    assert!(first.nac_control_direction_in());
    assert!(first.nac_mab_first());
    assert_eq!(first.nac_host_mode(), None);
    assert_eq!(first.nac_max_dot1x_clients(), Some(8));
    assert_eq!(first.nac_max_mab_clients(), Some(12));
    let unrelated = interfaces[1];
    assert!(!unrelated.has_nac());
    assert!(!unrelated.nac_control_direction_in());
    assert!(!unrelated.nac_mab_first());
    assert_eq!(unrelated.nac_max_dot1x_clients(), Some(1));
    assert_eq!(unrelated.nac_max_mab_clients(), Some(1));
    assert!(interfaces[2].has_nac());
}

#[test]
fn procurve_mentioned_ports_include_negations_but_exclude_non_numeric_port_forms() {
    let tree = raw_tree(
        "interface 1/1\n\
         aaa port-access authenticator 1/2\n\
         no aaa port-access mac-based 1/3\n\
         aaa port-access 4 controlled-direction in\n\
         aaa port-access authenticator active\n\
         aaa port-access authenticator\n\
         aaa port-access mac-based 1/A1\n\
         aaa port-access mac-based 1/2/3\n\
         aaa port-access Trk1 controlled-direction in",
    );
    assert_eq!(
        view(&tree, Platform::HpProcurve)
            .interface_names_mentioned()
            .into_iter()
            .collect::<Vec<_>>(),
        ["1/1", "1/2", "1/3", "4"]
    );
}

#[test]
fn procurve_vlan_inventory_uses_interface_tagged_and_untagged_commands() {
    let tree = raw_tree(
        "vlan 10-11\n  name \"Staff\"\n\
         interface 1/1\n  tagged vlan 11\n  tagged vlan 20\n  untagged vlan 30\n\
         interface 1/2\n  tagged vlan 20\n  untagged vlan 30",
    );
    let config = view(&tree, Platform::HpProcurve);
    let first = config.interface_views()[0];
    assert_eq!(first.tagged_vlans(), [11, 20]);
    assert_eq!(first.native_vlan(), Some(30));
    assert!(!first.tagged_all());
    assert_eq!(first.dot1q_mode(), Some(InterfaceDot1qMode::Tagged));
    assert_eq!(
        config.vlans(),
        [
            Vlan {
                id: 10,
                name: Some("Staff".into())
            },
            Vlan {
                id: 11,
                name: Some("Staff".into())
            },
            Vlan { id: 20, name: None },
            Vlan { id: 30, name: None },
        ]
    );
}

#[test]
fn procurve_physical_attributes_preserve_upstream_full_command_speed_bug() {
    // upstream/next@0866dc2 hp_procurve/view.py speed passes "speed-duplex ..."
    // to a helper expecting only "100-full": consequently speed is always None.
    for (command, duplex) in [
        ("speed-duplex 100-full", Some(InterfaceDuplex::Full)),
        ("speed-duplex 10-half", Some(InterfaceDuplex::Half)),
        ("speed-duplex auto", None),
        ("speed-duplex auto-10-100", None),
    ] {
        let tree = interface_tree("1/1", &[command, "disable", "no power-over-ethernet"]);
        let interface = interface(&tree, Platform::HpProcurve);
        assert_eq!(interface.speed(), None);
        assert_eq!(interface.duplex(), duplex);
        assert_eq!(interface.poe(), Some(false));
        assert!(!interface.enabled());
        assert_eq!(interface.vrf(), "");
    }
}

#[test]
fn procurve_stacking_ignores_priority_and_incomplete_lines() {
    let tree = raw_tree(
        "stacking
  member 1 type \"JL123\" mac-address abc123-def456
  member 2 type \"JL456\" mac-address 001122-334455
  member 2 priority 15
  member 3 type \"JL789\"
  member bad type \"ignored\" mac-address ignored
  member",
    );
    assert_eq!(
        view(&tree, Platform::HpProcurve).stack_members(),
        [
            StackMember {
                id: 1,
                priority: 255,
                model: "JL123".into(),
                mac_address: Some("abc123-def456".into())
            },
            StackMember {
                id: 2,
                priority: 254,
                model: "JL456".into(),
                mac_address: Some("001122-334455".into())
            },
        ]
    );
}

#[test]
fn all_vendor_views_work_after_real_driver_loading() {
    for (platform, text, name, native) in [
        (
            Platform::CiscoIos,
            "interface GigabitEthernet1/1\n switchport access vlan 42",
            "GigabitEthernet1/1",
            42,
        ),
        (
            Platform::AristaEos,
            "interface Ethernet1\n switchport access vlan 42",
            "Ethernet1",
            42,
        ),
        (
            Platform::CiscoNxos,
            "interface Ethernet1/1\n switchport access vlan 42",
            "Ethernet1/1",
            42,
        ),
        (
            Platform::CiscoXr,
            "interface GigabitEthernet0/0/0/1.42\n encapsulation dot1q 42",
            "GigabitEthernet0/0/0/1.42",
            42,
        ),
        (
            Platform::ArubaAoscx,
            "interface 1/1/1\n vlan access 42",
            "1/1/1",
            42,
        ),
        (
            Platform::HpProcurve,
            "interface 1\n untagged vlan 42",
            "1",
            42,
        ),
    ] {
        let tree = config_from_text(platform, text).unwrap();
        let config = config_view(&tree).unwrap();
        let interface = config.interface_view_by_name(name).unwrap();
        assert_eq!(interface.native_vlan(), Some(native), "{platform:?}");
        assert_eq!(interface.dot1q_mode(), Some(InterfaceDot1qMode::Access));
    }
}

#[derive(Debug, Clone, Copy)]
struct Unsupported;
impl InterfaceOps for Unsupported {}
static UNSUPPORTED: Unsupported = Unsupported;

#[test]
fn unsupported_capabilities_do_not_leak_cisco_syntax_or_default_values() {
    let tree = interface_tree(
        "Ethernet1/2",
        &[
            "ip address 192.0.2.1/24",
            "vrf BLUE",
            "switchport mode trunk",
            "switchport trunk allowed vlan 10",
            "switchport access vlan 20",
            "mab",
            "speed 1000",
            "duplex full",
            "channel-group 1",
        ],
    );
    let node = tree
        .get_child(tree.root, &MatchRule::startswith("interface "))
        .unwrap();
    let interface = InterfaceView::new(&tree, node, &UNSUPPORTED);
    assert_eq!(interface.dot1q_mode(), None);
    assert_eq!(interface.native_vlan(), None);
    assert!(interface.tagged_vlans().is_empty());
    assert!(!interface.tagged_all());
    assert!(!interface.is_bundle());
    assert_eq!(interface.bundle_name(), None);
    assert_eq!(interface.bundle_id(), None);
    assert!(interface.bundle_member_interfaces().is_empty());
    assert_eq!(interface.ipv4_interface(), None);
    assert_eq!(interface.vrf(), "");
}

#[test]
fn unsupported_nac_and_physical_capabilities_ignore_configured_commands() {
    let tree = interface_tree("Ethernet1/2", &["mab", "speed 1000", "duplex full"]);
    let node = tree
        .get_child(tree.root, &MatchRule::startswith("interface "))
        .unwrap();
    let interface = InterfaceView::new(&tree, node, &UNSUPPORTED);
    assert!(!interface.has_nac());
    assert!(!interface.nac_control_direction_in());
    assert_eq!(interface.nac_host_mode(), None);
    assert!(!interface.nac_mab_first());
    assert_eq!(interface.nac_max_dot1x_clients(), None);
    assert_eq!(interface.nac_max_mab_clients(), None);
    assert!(!interface.is_physical());
    assert_eq!(interface.module_number(), None);
    assert_eq!(interface.speed(), None);
    assert_eq!(interface.duplex(), None);
    assert_eq!(interface.poe(), None);
}

#[test]
fn interface_queries_are_scoped_and_preserve_config_order() {
    let tree = raw_tree(
        "description global
interface Ethernet1
  description first
  speed 100
  tagged vlan 20
  tagged vlan 10
interface Ethernet2
  description second",
    );
    let first = interface(&tree, Platform::CiscoIos);
    assert_eq!(
        first.tree().get(first.node()).unwrap().text.as_ref(),
        "interface Ethernet1"
    );
    assert_eq!(
        first.child_text(&MatchRule::startswith("description ")),
        Some("description first")
    );
    assert_eq!(
        first.children_text(&MatchRule::startswith("tagged vlan ")),
        ["tagged vlan 20", "tagged vlan 10"]
    );
    assert_eq!(first.child_word("speed ", 1), Some("100"));
    assert_eq!(first.child_word("speed ", 2), None);
    assert_eq!(first.child_number("speed ", 1), Some(100));
    assert_eq!(first.child_number("description ", 1), None);
    assert_eq!(
        first.sibling_text(&MatchRule::equals("description global")),
        Some("description global")
    );
    assert_eq!(
        first.siblings_text(&MatchRule::startswith("interface ")),
        ["interface Ethernet1", "interface Ethernet2"]
    );
    assert_eq!(
        first
            .sibling_views(&MatchRule::startswith("interface "))
            .iter()
            .map(InterfaceView::name)
            .collect::<Vec<_>>(),
        ["Ethernet1", "Ethernet2"]
    );
    assert!(first.has_sibling("interface Ethernet2"));
    assert!(!first.has_sibling("interface Ethernet3"));
    assert_eq!(
        format!("{first:?}"),
        "InterfaceView { name: \"Ethernet1\" }"
    );
}

#[test]
fn root_and_deleted_node_views_have_no_parent_or_siblings() {
    let mut tree = interface_tree("Ethernet1", &[]);
    let removed = tree
        .get_child(tree.root, &MatchRule::startswith("interface "))
        .unwrap();
    tree.delete_child(removed);
    for node in [tree.root, removed] {
        let interface = InterfaceView::new(&tree, node, &UNSUPPORTED);
        assert_eq!(interface.name(), "");
        assert_eq!(interface.number(), "");
        assert_eq!(interface.text(), "");
        assert_eq!(interface.parent(), None);
        assert_eq!(interface.sibling_text(&MatchRule::startswith("")), None);
        assert!(
            interface
                .siblings_text(&MatchRule::startswith(""))
                .is_empty()
        );
        assert!(
            interface
                .sibling_views(&MatchRule::startswith(""))
                .is_empty()
        );
        assert_eq!(interface.port_number(), None);
        assert_eq!(interface.subinterface_number(), None);
    }
}

#[test]
fn detached_bundle_cannot_enumerate_members_from_an_unrelated_root() {
    let mut tree = raw_tree("interface Port-channel1\ninterface Ethernet1\n  channel-group 1");
    let bundle = tree
        .get_child(tree.root, &MatchRule::equals("interface Port-channel1"))
        .unwrap();
    tree.get_mut(bundle).unwrap().parent = None;
    let interface = InterfaceView::new(
        &tree,
        bundle,
        view_ops_for_platform(Platform::CiscoIos)
            .unwrap()
            .interface_ops(),
    );
    assert!(interface.is_bundle());
    assert_eq!(interface.parent(), None);
    assert!(interface.bundle_member_interfaces().is_empty());
}

#[test]
fn cisco_vlan_command_errors_return_total_fallbacks() {
    for (commands, native, all) in [
        (vec!["switchport access vlan invalid"], Some(1), false),
        (
            vec![
                "switchport mode trunk",
                "switchport trunk native vlan invalid",
            ],
            None,
            true,
        ),
        (
            vec![
                "switchport mode trunk",
                "switchport trunk allowed vlan 10-12-13",
            ],
            None,
            true,
        ),
        (
            vec![
                "switchport mode trunk",
                "switchport trunk allowed vlan 10-12 extra",
            ],
            None,
            true,
        ),
    ] {
        let tree = interface_tree("Ethernet1", &commands);
        let interface = interface(&tree, Platform::CiscoIos);
        assert_eq!(interface.native_vlan(), native);
        assert!(interface.tagged_vlans().is_empty());
        assert_eq!(interface.tagged_all(), all);
    }
}
