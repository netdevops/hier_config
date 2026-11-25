use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_multiple_groups_no_duplicate_child_error() {
    let config_text = "\
hostname router1
group core
 interface 'Bundle-Ether.*'
  mtu 9188
 !
end-group
group edge
 interface 'Bundle-Ether.*'
  mtu 9092
 !
end-group
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let children: Vec<&str> = tree.arena[tree.root]
        .children
        .iter()
        .map(|id| tree.arena[id].text.as_ref())
        .collect();

    assert!(children.contains(&"hostname router1"));
    assert!(children.contains(&"group core"));
    assert!(children.contains(&"group edge"));
}

#[test]
fn test_sectional_exit_text_parent_level_route_policy() {
    let config_text = "\
route-policy TEST
  set local-preference 200
  pass
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "route-policy TEST")
        .expect("node not found");

    assert!(tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "route-policy TEST",
            "  set local-preference 200",
            "  pass",
            "end-policy",
        ]
    );
}

#[test]
fn test_sectional_exit_text_parent_level_prefix_set() {
    let config_text = "\
prefix-set TEST_PREFIX
  192.0.2.0/24
  198.51.100.0/24
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "prefix-set TEST_PREFIX")
        .expect("node not found");

    assert!(tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "prefix-set TEST_PREFIX",
            "  192.0.2.0/24",
            "  198.51.100.0/24",
            "end-set",
        ]
    );
}

#[test]
fn test_sectional_exit_text_parent_level_policy_map() {
    let config_text = "\
policy-map TEST_POLICY
  class TEST_CLASS
    set precedence 5
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "policy-map TEST_POLICY")
        .expect("node not found");

    assert!(tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "policy-map TEST_POLICY",
            "  class TEST_CLASS",
            "    set precedence 5",
            "    exit",
            "end-policy-map",
        ]
    );
}

#[test]
fn test_sectional_exit_text_parent_level_class_map() {
    let config_text = "\
class-map match-any TEST_CLASS
  match access-group TEST_ACL
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "class-map match-any TEST_CLASS")
        .expect("node not found");

    assert!(tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "class-map match-any TEST_CLASS",
            "  match access-group TEST_ACL",
            "end-class-map",
        ]
    );
}

#[test]
fn test_sectional_exit_text_parent_level_community_set() {
    let config_text = "\
community-set TEST_COMM
  65001:100
  65001:200
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "community-set TEST_COMM")
        .expect("node not found");

    assert!(tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "community-set TEST_COMM",
            "  65001:100",
            "  65001:200",
            "end-set",
        ]
    );
}

#[test]
fn test_sectional_exit_text_parent_level_extcommunity_set() {
    let config_text = "\
extcommunity-set rt TEST_RT
  1:100
  2:200
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "extcommunity-set rt TEST_RT")
        .expect("node not found");

    assert!(tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "extcommunity-set rt TEST_RT",
            "  1:100",
            "  2:200",
            "end-set",
        ]
    );
}

#[test]
fn test_sectional_exit_text_parent_level_template() {
    let config_text = "\
template TEST_TEMPLATE
  description test template
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "template TEST_TEMPLATE")
        .expect("node not found");

    assert!(tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "template TEST_TEMPLATE",
            "  description test template",
            "end-template",
        ]
    );
}

#[test]
fn test_sectional_exit_text_current_level_interface() {
    let config_text = "\
interface GigabitEthernet0/0/0/0
  description test interface
  ipv4 address 192.0.2.1 255.255.255.0
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "interface GigabitEthernet0/0/0/0")
        .expect("node not found");

    assert!(!tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "interface GigabitEthernet0/0/0/0",
            "  description test interface",
            "  ipv4 address 192.0.2.1 255.255.255.0",
            "  root",
        ]
    );
}

#[test]
fn test_sectional_exit_text_current_level_router_bgp() {
    let config_text = "\
router bgp 65000
  bgp router-id 192.0.2.1
  address-family ipv4 unicast
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let node_id = tree
        .get_child_by_text(tree.root, "router bgp 65000")
        .expect("node not found");

    assert!(!tree.sectional_exit_text_parent_level(node_id));
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "router bgp 65000",
            "  bgp router-id 192.0.2.1",
            "  address-family ipv4 unicast",
            "  root",
        ]
    );
}

#[test]
fn test_sectional_exit_text_multiple_sections() {
    let config_text = "\
route-policy TEST1
  pass
!
interface GigabitEthernet0/0/0/0
  description test
!
prefix-set TEST_PREFIX
  192.0.2.0/24
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let route_policy = tree
        .get_child_by_text(tree.root, "route-policy TEST1")
        .expect("route_policy not found");
    let interface = tree
        .get_child_by_text(tree.root, "interface GigabitEthernet0/0/0/0")
        .expect("interface not found");
    let prefix_set = tree
        .get_child_by_text(tree.root, "prefix-set TEST_PREFIX")
        .expect("prefix_set not found");

    assert!(tree.sectional_exit_text_parent_level(route_policy));
    assert!(!tree.sectional_exit_text_parent_level(interface));
    assert!(tree.sectional_exit_text_parent_level(prefix_set));

    assert_eq!(
        tree.dump_simple(true),
        vec![
            "route-policy TEST1",
            "  pass",
            "end-policy",
            "interface GigabitEthernet0/0/0/0",
            "  description test",
            "  root",
            "prefix-set TEST_PREFIX",
            "  192.0.2.0/24",
            "end-set",
        ]
    );
}

#[test]
fn test_indented_bang_section_separators_no_duplicate_child_error() {
    let config_text = "\
telemetry model-driven
 destination-group DEST-GROUP-1
  address-family ipv4 10.0.0.1 port 57000
   encoding self-describing-gpb
   protocol tcp
  !
 !
 destination-group DEST-GROUP-2
  address-family ipv4 10.0.0.2 port 57000
   encoding self-describing-gpb
   protocol tcp
  !
 !
 sensor-group SENSOR-1
  sensor-path openconfig-platform:components/component/cpu
  sensor-path openconfig-platform:components/component/memory
 !
 sensor-group SENSOR-2
  sensor-path openconfig-interfaces:interfaces/interface/state/counters
 !
!
";
    let tree = Tree::from_str(Platform::CiscoXr, config_text).expect("parse failed");
    let telemetry = tree
        .get_child_by_text(tree.root, "telemetry model-driven")
        .expect("telemetry not found");

    let child_texts: Vec<&str> = tree.arena[telemetry]
        .children
        .iter()
        .map(|id| tree.arena[id].text.as_ref())
        .collect();

    assert!(child_texts.contains(&"destination-group DEST-GROUP-1"));
    assert!(child_texts.contains(&"destination-group DEST-GROUP-2"));
    assert!(child_texts.contains(&"sensor-group SENSOR-1"));
    assert!(child_texts.contains(&"sensor-group SENSOR-2"));
}
