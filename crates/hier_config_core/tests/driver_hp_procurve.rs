use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_fixup_aaa_port_access_ranges() {
    let raw = "aaa port-access authenticator 1/15-1/20,1/26-1/28\naaa port-access mac-based 2/14-2/16\naaa port-access authenticator 1/1";
    let tree = Tree::from_str(Platform::HpProcurve, raw).unwrap();

    let expected_present = [
        "aaa port-access authenticator 1/15",
        "aaa port-access authenticator 1/16",
        "aaa port-access authenticator 1/17",
        "aaa port-access authenticator 1/18",
        "aaa port-access authenticator 1/19",
        "aaa port-access authenticator 1/20",
        "aaa port-access authenticator 1/26",
        "aaa port-access authenticator 1/27",
        "aaa port-access authenticator 1/28",
        "aaa port-access mac-based 2/14",
        "aaa port-access mac-based 2/15",
        "aaa port-access mac-based 2/16",
        "aaa port-access authenticator 1/1",
    ];
    for cmd in expected_present {
        assert!(tree.get_child_by_text(tree.root, cmd).is_some());
    }

    assert!(
        tree.get_child_by_text(
            tree.root,
            "aaa port-access authenticator 1/15-1/20,1/26-1/28"
        )
        .is_none()
    );
    assert!(
        tree.get_child_by_text(tree.root, "aaa port-access mac-based 2/14-2/16")
            .is_none()
    );
}

#[test]
fn test_fixup_vlan_transformation() {
    let raw = "vlan 80\n   untagged 2/43-2/44,3/43-3/44\n   tagged 1/23,2/23,Trk1\nvlan 90\n   untagged 5/29\n   no untagged 1/2-1/5";
    let tree = Tree::from_str(Platform::HpProcurve, raw).unwrap();

    let if_2_43 = tree
        .get_child_by_text(tree.root, "interface 2/43")
        .expect("interface 2/43");
    assert!(
        tree.get_child_by_text(if_2_43, "untagged vlan 80")
            .is_some()
    );

    let if_2_44 = tree
        .get_child_by_text(tree.root, "interface 2/44")
        .expect("interface 2/44");
    assert!(
        tree.get_child_by_text(if_2_44, "untagged vlan 80")
            .is_some()
    );

    let if_3_43 = tree
        .get_child_by_text(tree.root, "interface 3/43")
        .expect("interface 3/43");
    assert!(
        tree.get_child_by_text(if_3_43, "untagged vlan 80")
            .is_some()
    );

    let if_3_44 = tree
        .get_child_by_text(tree.root, "interface 3/44")
        .expect("interface 3/44");
    assert!(
        tree.get_child_by_text(if_3_44, "untagged vlan 80")
            .is_some()
    );

    let if_5_29 = tree
        .get_child_by_text(tree.root, "interface 5/29")
        .expect("interface 5/29");
    assert!(
        tree.get_child_by_text(if_5_29, "untagged vlan 90")
            .is_some()
    );

    let if_1_23 = tree
        .get_child_by_text(tree.root, "interface 1/23")
        .expect("interface 1/23");
    assert!(tree.get_child_by_text(if_1_23, "tagged vlan 80").is_some());

    let if_2_23 = tree
        .get_child_by_text(tree.root, "interface 2/23")
        .expect("interface 2/23");
    assert!(tree.get_child_by_text(if_2_23, "tagged vlan 80").is_some());

    let if_trk1 = tree
        .get_child_by_text(tree.root, "interface Trk1")
        .expect("interface Trk1");
    assert!(tree.get_child_by_text(if_trk1, "tagged vlan 80").is_some());

    let vlan_80 = tree
        .get_child_by_text(tree.root, "vlan 80")
        .expect("vlan 80");
    assert!(
        tree.arena[vlan_80]
            .children
            .iter()
            .all(|id| !tree.arena[id].text.starts_with("untagged "))
    );
    assert!(
        tree.arena[vlan_80]
            .children
            .iter()
            .all(|id| !tree.arena[id].text.starts_with("tagged "))
    );

    let vlan_90 = tree
        .get_child_by_text(tree.root, "vlan 90")
        .expect("vlan 90");
    assert!(
        tree.arena[vlan_90]
            .children
            .iter()
            .all(|id| !tree.arena[id].text.starts_with("untagged "))
    );
    assert!(
        tree.arena[vlan_90]
            .children
            .iter()
            .all(|id| !tree.arena[id].text.starts_with("no untagged "))
    );
}

#[test]
fn test_fixup_device_profile_tagged_vlans() {
    let raw = "device-profile name \"phone\"\n   tagged-vlan 10,20,30\ndevice-profile name \"printer\"\n   tagged-vlan 40";
    let tree = Tree::from_str(Platform::HpProcurve, raw).unwrap();

    let dp_phone = tree
        .get_child_by_text(tree.root, "device-profile name \"phone\"")
        .expect("device-profile name \"phone\"");
    assert!(tree.get_child_by_text(dp_phone, "tagged-vlan 10").is_some());
    assert!(tree.get_child_by_text(dp_phone, "tagged-vlan 20").is_some());
    assert!(tree.get_child_by_text(dp_phone, "tagged-vlan 30").is_some());
    assert!(
        tree.get_child_by_text(dp_phone, "tagged-vlan 10,20,30")
            .is_none()
    );

    let dp_printer = tree
        .get_child_by_text(tree.root, "device-profile name \"printer\"")
        .expect("device-profile name \"printer\"");
    assert!(
        tree.get_child_by_text(dp_printer, "tagged-vlan 40")
            .is_some()
    );
}
