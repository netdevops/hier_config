use hier_config_core::models::{MatchRule, Platform, TagRule};
use hier_config_core::tree::Tree;
use hier_config_core::workflow::{WorkflowError, WorkflowRemediation};
use std::collections::BTreeSet;

#[test]
fn test_workflow_driver_mismatch() {
    let running = Tree::from_str(Platform::CiscoIos, "hostname r1").unwrap();
    let generated = Tree::from_str(Platform::JuniperJunos, "set system host-name r1").unwrap();

    let err = WorkflowRemediation::new(running, generated).unwrap_err();
    match err {
        WorkflowError::DriverMismatch {
            running: r_plat,
            generated: g_plat,
        } => {
            assert_eq!(r_plat, Platform::CiscoIos);
            assert_eq!(g_plat, Platform::JuniperJunos);
        }
        other => panic!("expected DriverMismatch, got {other:?}"),
    }
}

#[test]
fn test_workflow_remediation_and_rollback() {
    let running_raw = r"
vlan 2
  name test_vlan_2
vlan 3
  name switch_mgmt_10.0.3.0/24
interface Vlan2
  mtu 9000
  ip access-group TEST in
  no shutdown
";
    let generated_raw = r"
vlan 2
  name test_vlan_2
vlan 4
  name switch_mgmt_10.0.4.0/24
interface Vlan2
  no shutdown
interface Vlan4
  description switch_mgmt_10.0.4.0/24
";

    let workflow =
        WorkflowRemediation::from_strings(Platform::CiscoIos, running_raw, generated_raw).unwrap();

    // Check remediation
    let rem_text = workflow.remediation_text(&[], &[]).unwrap();
    assert!(rem_text.contains("no vlan 3"));
    assert!(rem_text.contains("vlan 4"));
    assert!(rem_text.contains("interface Vlan2"));
    assert!(rem_text.contains("no mtu 9000"));
    assert!(rem_text.contains("no ip access-group TEST in"));
    assert!(rem_text.contains("interface Vlan4"));

    // Check rollback
    let roll_text = workflow.rollback_text(&[], &[]).unwrap();
    assert!(roll_text.contains("no vlan 4"));
    assert!(roll_text.contains("vlan 3"));
    assert!(roll_text.contains("interface Vlan2"));
    assert!(roll_text.contains("mtu 9000"));
    assert!(roll_text.contains("ip access-group TEST in"));
}

#[test]
fn test_workflow_tag_rules_and_filtered_text() {
    let running_raw = r"
interface GigabitEthernet0/1
  description Old
  shutdown
interface GigabitEthernet0/2
  description Old
";
    let generated_raw = r"
interface GigabitEthernet0/1
  description New
  no shutdown
interface GigabitEthernet0/2
  description New
";

    let running = Tree::from_str(Platform::CiscoIos, running_raw).unwrap();
    let generated = Tree::from_str(Platform::CiscoIos, generated_raw).unwrap();

    // Test borrowed constructor
    let mut workflow = WorkflowRemediation::from_borrowed(&running, &generated).unwrap();

    // Define tag rule for interface GigabitEthernet0/1
    let tag_rules = vec![TagRule {
        match_rules: vec![
            MatchRule::equals("interface GigabitEthernet0/1"),
            MatchRule::startswith("description"),
        ],
        apply_tags: BTreeSet::from(["safe".to_string(), "interface_desc".to_string()]),
    }];

    workflow.apply_remediation_tag_rules(&tag_rules).unwrap();

    let text_all = workflow.remediation_text(&[], &[]).unwrap();
    let text_safe = workflow.remediation_text(&["safe"], &[]).unwrap();
    let text_excluded = workflow.remediation_text(&[], &["safe"]).unwrap();

    assert!(text_all.contains("description New"));
    assert!(text_safe.contains("interface GigabitEthernet0/1"));
    assert!(text_safe.contains("description New"));
    assert!(!text_safe.contains("interface GigabitEthernet0/2"));

    assert!(!text_excluded.contains("interface GigabitEthernet0/1\n  description New"));
    assert!(text_excluded.contains("interface GigabitEthernet0/2"));
}

#[test]
fn test_workflow_take_remediation_and_rollback() {
    let mut workflow = WorkflowRemediation::from_strings(
        Platform::CiscoIos,
        "hostname r1\nvlan 10",
        "hostname r1\nvlan 20",
    )
    .unwrap();

    let rem_tree = workflow.take_remediation().unwrap();
    assert_eq!(rem_tree.driver.platform, Platform::CiscoIos);
    let dump = rem_tree.dump_simple(false);
    assert!(dump.contains(&"no vlan 10".to_string()));
    assert!(dump.contains(&"vlan 20".to_string()));

    let roll_tree = workflow.take_rollback().unwrap();
    assert_eq!(roll_tree.driver.platform, Platform::CiscoIos);
    let roll_dump = roll_tree.dump_simple(false);
    assert!(roll_dump.contains(&"no vlan 20".to_string()));
    assert!(roll_dump.contains(&"vlan 10".to_string()));
}

#[test]
fn test_workflow_immutable_concurrent_queries() {
    let workflow = WorkflowRemediation::from_strings(
        Platform::CiscoIos,
        "hostname r1\nvlan 10",
        "hostname r1\nvlan 20",
    )
    .unwrap();

    std::thread::scope(|s| {
        let t1 = s.spawn(|| workflow.remediation_text(&[], &[]).unwrap());
        let t2 = s.spawn(|| workflow.rollback_text(&[], &[]).unwrap());
        let t3 = s.spawn(|| {
            let rem = workflow.remediation_config().unwrap();
            rem.len()
        });

        let rem_text = t1.join().unwrap();
        let roll_text = t2.join().unwrap();
        let rem_len = t3.join().unwrap();

        assert!(rem_text.contains("vlan 20"));
        assert!(roll_text.contains("vlan 10"));
        assert!(rem_len > 0);
    });
}

#[test]
fn test_idempotent_hp_procurve_future() {
    let running = Tree::from_str(Platform::HpProcurve, "aaa accounting update periodic 1").unwrap();
    let incoming = Tree::from_str(Platform::Generic, "aaa accounting update periodic 5").unwrap();
    let (future, _) =
        hier_config_core::remediation::future_with_report(&running, &incoming, false).unwrap();
    let lines: Vec<String> = future.lines(future.root, false);
    assert_eq!(lines, vec!["aaa accounting update periodic 5"]);
}

#[test]
fn test_workflow_remediation_netconf_xml() {
    let running_xml = "<config><interface><name>GigabitEthernet0/1</name><description>old</description></interface></config>";
    let generated_xml = "<config><interface><name>GigabitEthernet0/1</name><description>new</description></interface></config>";

    let running = Tree::from_xml(Platform::Generic, running_xml, None).unwrap();
    let generated = Tree::from_xml(Platform::Generic, generated_xml, None).unwrap();

    let workflow = WorkflowRemediation::new(running, generated).unwrap();
    let xml = workflow.remediation_netconf_xml(None).unwrap();
    assert!(xml.contains("<description>new</description>"));
}

#[test]
fn test_workflow_remediation_gnmi() {
    let running_json = r#"{"interfaces": {"interface": [{"name": "eth0", "description": "old"}]}}"#;
    let generated_json =
        r#"{"interfaces": {"interface": [{"name": "eth0", "description": "new"}]}}"#;

    let running = Tree::from_json(Platform::Generic, running_json, None).unwrap();
    let generated = Tree::from_json(Platform::Generic, generated_json, None).unwrap();

    let workflow = WorkflowRemediation::new(running, generated).unwrap();
    let gnmi = workflow.remediation_gnmi(None).unwrap();
    assert!(!gnmi.update.is_empty());
}
