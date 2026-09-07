use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_rm_ipv6_acl_sequence_numbers() {
    let config_text = "ipv6 access-list TEST_IPV6_ACL\n sequence 10 permit tcp any any eq 443\n sequence 20 deny ipv6 any any\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();
    let acl_id = tree
        .get_child_by_text(tree.root, "ipv6 access-list TEST_IPV6_ACL")
        .expect("ACL not found");

    assert!(
        tree.get_child_by_text(acl_id, "permit tcp any any eq 443")
            .is_some()
    );
    assert!(
        tree.get_child_by_text(acl_id, "deny ipv6 any any")
            .is_some()
    );
    let children_texts: Vec<&str> = tree.arena[acl_id]
        .children
        .iter()
        .map(|id| tree.arena[id].text.as_ref())
        .collect();
    assert!(!children_texts.iter().any(|t| t.starts_with("sequence")));
}

#[test]
fn test_remove_ipv4_acl_remarks() {
    let config_text = "ip access-list extended TEST_ACL\n remark Allow HTTPS traffic\n permit tcp any any eq 443\n remark Block all other traffic\n deny ip any any\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();
    let acl_id = tree
        .get_child_by_text(tree.root, "ip access-list extended TEST_ACL")
        .expect("ACL not found");

    assert!(
        tree.get_child_by_text(acl_id, "10 permit tcp any any eq 443")
            .is_some()
    );
    assert!(
        tree.get_child_by_text(acl_id, "20 deny ip any any")
            .is_some()
    );
    let children_texts: Vec<&str> = tree.arena[acl_id]
        .children
        .iter()
        .map(|id| tree.arena[id].text.as_ref())
        .collect();
    assert!(!children_texts.iter().any(|t| t.starts_with("remark")));
}

#[test]
fn test_add_acl_sequence_numbers() {
    let config_text = "ip access-list extended TEST_ACL\n permit tcp any any eq 443\n permit tcp any any eq 80\n deny ip any any\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();
    let acl_id = tree
        .get_child_by_text(tree.root, "ip access-list extended TEST_ACL")
        .expect("ACL not found");

    assert!(
        tree.get_child_by_text(acl_id, "10 permit tcp any any eq 443")
            .is_some()
    );
    assert!(
        tree.get_child_by_text(acl_id, "20 permit tcp any any eq 80")
            .is_some()
    );
    assert!(
        tree.get_child_by_text(acl_id, "30 deny ip any any")
            .is_some()
    );
}

#[test]
fn test_vlan_id_list_split_on_load() {
    let config_text = "vlan 69,381\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();

    assert!(tree.get_child_by_text(tree.root, "vlan 69").is_some());
    assert!(tree.get_child_by_text(tree.root, "vlan 381").is_some());
    assert!(tree.get_child_by_text(tree.root, "vlan 69,381").is_none());
}

#[test]
fn test_vlan_id_range_split_on_load() {
    let config_text = "vlan 10-12\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();

    let children: Vec<&str> = tree.arena[tree.root]
        .children
        .iter()
        .map(|id| tree.arena[id].text.as_ref())
        .collect();
    assert_eq!(children, vec!["vlan 10", "vlan 11", "vlan 12"]);
}

#[test]
fn test_single_vlan_not_split_on_load() {
    let config_text = "vlan 44\n name servers\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();

    let vlan_id = tree
        .get_child_by_text(tree.root, "vlan 44")
        .expect("vlan 44 not found");
    assert!(tree.get_child_by_text(vlan_id, "name servers").is_some());
}

#[test]
fn test_non_vlan_id_line_not_split_on_load() {
    let config_text = "vlan internal allocation policy ascending\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();

    assert!(
        tree.get_child_by_text(tree.root, "vlan internal allocation policy ascending")
            .is_some()
    );
}

#[test]
fn test_malformed_vlan_range_left_untouched() {
    let config_text = "vlan 1-2-3\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();

    assert!(tree.get_child_by_text(tree.root, "vlan 1-2-3").is_some());
    assert!(tree.get_child_by_text(tree.root, "vlan 1").is_none());
}

#[test]
fn test_reversed_vlan_range_left_untouched() {
    let config_text = "vlan 5-3,7\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();

    assert!(tree.get_child_by_text(tree.root, "vlan 5-3,7").is_some());
    assert!(tree.get_child_by_text(tree.root, "vlan 7").is_none());
}

#[test]
fn test_cisco_ios_trunk_allowed_vlan_not_split() {
    let config_text = "interface GigabitEthernet0/1\n switchport trunk allowed vlan 150-166\n";
    let tree = Tree::from_str(Platform::CiscoIos, config_text).unwrap();

    let intf_id = tree
        .get_child_by_text(tree.root, "interface GigabitEthernet0/1")
        .expect("interface not found");
    let children: Vec<&str> = tree.arena[intf_id]
        .children
        .iter()
        .map(|id| tree.arena[id].text.as_ref())
        .collect();
    assert_eq!(children, vec!["switchport trunk allowed vlan 150-166"]);
}
