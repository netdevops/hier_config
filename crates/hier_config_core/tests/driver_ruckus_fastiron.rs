use hier_config_core::driver::Driver;
use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_negation_and_declaration_prefixes() {
    let driver = Driver::for_platform(Platform::RuckusFastiron);
    assert_eq!(driver.negation_prefix, "no ");
    assert_eq!(driver.declaration_prefix, "");
}

#[test]
fn test_rules_load_with_single_space_indentation() {
    let driver = Driver::for_platform(Platform::RuckusFastiron);
    assert_eq!(driver.rules.indentation, 1);
    assert!(!driver.rules.negation.is_empty());
    assert!(!driver.rules.ordering.is_empty());
}

#[test]
fn test_per_line_sub_strips_capture_artifacts() {
    let raw = "Current configuration:\nver 08.0.30uT7f3\n!\nhostname icx-01\nICX6450-48#\nend";
    let tree = Tree::from_str(Platform::RuckusFastiron, raw).unwrap();

    assert!(
        tree.get_child_by_text(tree.root, "hostname icx-01")
            .is_some()
    );
    for stripped in [
        "Current configuration:",
        "ver 08.0.30uT7f3",
        "ICX6450-48#",
        "end",
    ] {
        assert!(tree.get_child_by_text(tree.root, stripped).is_none());
    }
}

#[test]
fn test_single_space_indentation_nests_children() {
    let raw = "interface ethernet 1/1/1\n port-name uplink\n";
    let tree = Tree::from_str(Platform::RuckusFastiron, raw).unwrap();

    let interface = tree
        .get_child_by_text(tree.root, "interface ethernet 1/1/1")
        .expect("interface ethernet 1/1/1");
    assert!(
        tree.get_child_by_text(interface, "port-name uplink")
            .is_some()
    );
}

#[test]
fn test_port_name_negates_to_bare_no_port_name() {
    let running = "interface ethernet 1/1/1\n port-name uplink\n";
    let intended = "interface ethernet 1/1/1\n";
    let running = Tree::from_str(Platform::RuckusFastiron, running).unwrap();
    let intended = Tree::from_str(Platform::RuckusFastiron, intended).unwrap();

    let lines = running
        .config_to_get_to(&intended)
        .unwrap()
        .dump_simple(false);
    assert_eq!(lines, ["interface ethernet 1/1/1", " no port-name"]);
}

#[test]
fn test_lag_negation_drops_the_trailing_member_syntax() {
    let running = "lag \"UPLINK\" dynamic id 1\n ports ethernet 1/1/1\n";
    let intended = "";
    let running = Tree::from_str(Platform::RuckusFastiron, running).unwrap();
    let intended = Tree::from_str(Platform::RuckusFastiron, intended).unwrap();

    let lines = running
        .config_to_get_to(&intended)
        .unwrap()
        .dump_simple(false);
    assert_eq!(lines, ["no lag \"UPLINK\""]);
}

#[test]
fn test_ordering_puts_an_acl_before_the_interface_that_binds_it() {
    let running = "interface ethernet 1/1/1\n port-name uplink\n";
    let intended = "ip access-list extended GUEST\n permit ip any any\ninterface ethernet 1/1/1\n port-name uplink\n ip access-group GUEST in\n";
    let running = Tree::from_str(Platform::RuckusFastiron, running).unwrap();
    let intended = Tree::from_str(Platform::RuckusFastiron, intended).unwrap();

    let lines = running
        .config_to_get_to(&intended)
        .unwrap()
        .dump_simple(false);
    let acl = lines
        .iter()
        .position(|line| line == "ip access-list extended GUEST")
        .expect("acl line");
    let interface = lines
        .iter()
        .position(|line| line == "interface ethernet 1/1/1")
        .expect("interface line");
    assert!(acl < interface);
}
