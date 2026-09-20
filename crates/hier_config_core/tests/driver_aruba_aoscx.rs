use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_aruba_aoscx_splits_top_level_vlan_lists() {
    let config = "\
vlan 1,10
vlan 100-102
";
    let tree = Tree::from_str(Platform::ArubaAoscx, config).expect("parse failed");
    assert_eq!(
        tree.dump_simple(false),
        vec![
            "vlan 1".to_string(),
            "vlan 10".to_string(),
            "vlan 100".to_string(),
            "vlan 101".to_string(),
            "vlan 102".to_string(),
        ]
    );
}

#[test]
fn test_aruba_aoscx_collapsed_vlan_header_with_children_is_left_untouched() {
    let config = "\
vlan 10-12
    name USERS
";
    let tree = Tree::from_str(Platform::ArubaAoscx, config).expect("parse failed");
    assert_eq!(
        tree.dump_simple(false),
        vec!["vlan 10-12".to_string(), "  name USERS".to_string()]
    );
}

#[test]
fn test_aruba_aoscx_leaves_unparseable_vlan_range_untouched() {
    let config = "vlan 10-\n";
    let tree = Tree::from_str(Platform::ArubaAoscx, config).expect("parse failed");
    assert_eq!(tree.dump_simple(false), vec!["vlan 10-".to_string()]);
}

#[test]
fn test_aruba_aoscx_leaves_empty_trunk_spec_untouched() {
    let config = "\
interface 1/1/1
    vlan trunk allowed ,
";
    let tree = Tree::from_str(Platform::ArubaAoscx, config).expect("parse failed");
    let intf_id = tree
        .get_child_by_text(tree.root, "interface 1/1/1")
        .expect("interface not found");
    let children: Vec<&str> = tree.arena[intf_id]
        .children
        .iter()
        .map(|id| tree.arena[id].text.as_ref())
        .collect();
    assert_eq!(children, vec!["vlan trunk allowed ,"]);
}

#[test]
fn test_aruba_aoscx_strips_terminal_prompt_lines() {
    let config = "\
cx-switch# show run
hostname cx-switch
cx-switch(config)# interface 1/1/1
interface 1/1/1
    description #P3# Test
cx-switch(config-if)# vlan trunk allowed 500
";
    let tree = Tree::from_str(Platform::ArubaAoscx, config).expect("parse failed");
    assert_eq!(
        tree.dump_simple(false),
        vec![
            "hostname cx-switch".to_string(),
            "interface 1/1/1".to_string(),
            "  description #P3# Test".to_string(),
        ]
    );
}
