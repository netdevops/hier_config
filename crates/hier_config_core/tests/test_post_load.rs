use hier_config_core::models::Platform;
use hier_config_core::post_load::{expand_range, hp_procurve_expand_range};
use hier_config_core::tree::Tree;

#[test]
fn test_expand_range_basic() {
    let result = expand_range("1-3,5,7-9").unwrap();
    assert_eq!(result, vec![1, 2, 3, 5, 7, 8, 9]);

    let dedup = expand_range("1-3,2,3").unwrap();
    assert_eq!(dedup, vec![1, 2, 3]);

    let single = expand_range("42").unwrap();
    assert_eq!(single, vec![42]);

    assert!(expand_range("5-2").is_err());
    assert!(expand_range("abc").is_err());
}

#[test]
fn test_hp_procurve_expand_range_basic() {
    let trk = hp_procurve_expand_range("Trk1-Trk3").unwrap();
    assert_eq!(trk, vec!["Trk1", "Trk2", "Trk3"]);

    let slot = hp_procurve_expand_range("5/A1-5/A3").unwrap();
    assert_eq!(slot, vec!["5/A1", "5/A2", "5/A3"]);

    let stack = hp_procurve_expand_range("1/1-1/3").unwrap();
    assert_eq!(stack, vec!["1/1", "1/2", "1/3"]);

    let ports = hp_procurve_expand_range("1-3").unwrap();
    assert_eq!(ports, vec!["1", "2", "3"]);

    assert!(hp_procurve_expand_range("1/1,1/1").is_err());
}

#[test]
fn test_cisco_ios_acl_sequence_numbers() {
    let raw = "ip access-list extended TEST\n permit ip any any\n permit tcp any any";
    let tree = Tree::from_str(Platform::CiscoIos, raw).unwrap();
    let lines = tree.dump_simple(false);
    assert_eq!(
        lines,
        vec![
            "ip access-list extended TEST",
            "  10 permit ip any any",
            "  20 permit tcp any any",
        ]
    );
}

#[test]
fn test_cisco_ios_acl_remarks_strip() {
    let raw = "ip access-list extended TEST\n remark THIS IS A TEST\n permit ip any any";
    let tree = Tree::from_str(Platform::CiscoIos, raw).unwrap();
    let lines = tree.dump_simple(false);
    assert_eq!(
        lines,
        vec!["ip access-list extended TEST", "  10 permit ip any any",]
    );
}

#[test]
fn test_aruba_aoscx_vlan_trunk_split() {
    let raw = "interface 1/1/1\n vlan trunk allowed 1,2,3,5";
    let tree = Tree::from_str(Platform::ArubaAoscx, raw).unwrap();
    let lines = tree.dump_simple(false);
    assert_eq!(
        lines,
        vec![
            "interface 1/1/1",
            "  vlan trunk allowed 1",
            "  vlan trunk allowed 2",
            "  vlan trunk allowed 3",
            "  vlan trunk allowed 5",
        ]
    );
}

#[test]
fn test_cisco_xr_comments_fixup() {
    let raw = "!\n! interface comment\ninterface GigabitEthernet0/0/0/0\n shutdown";
    let tree = Tree::from_str(Platform::CiscoXr, raw).unwrap();
    let lines = tree.dump_simple(false);
    assert_eq!(
        lines,
        vec!["interface GigabitEthernet0/0/0/0", "  shutdown",]
    );
    let iface_id = tree
        .get_child_by_text(tree.root, "interface GigabitEthernet0/0/0/0")
        .unwrap();
    assert!(
        tree.arena[iface_id]
            .comments()
            .contains("interface comment")
    );
}
