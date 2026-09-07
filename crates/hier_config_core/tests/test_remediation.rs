use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_remediation_addition_and_deletion() {
    let running_raw = r"
interface GigabitEthernet0/1
  description Old Description
  shutdown
";
    let generated_raw = r"
interface GigabitEthernet0/1
  description New Description
  no shutdown
interface GigabitEthernet0/2
  description Interface Two
";

    let running = Tree::from_str(Platform::CiscoIos, running_raw).unwrap();
    let generated = Tree::from_str(Platform::CiscoIos, generated_raw).unwrap();

    let remediation = running.config_to_get_to(&generated).unwrap();
    let lines = remediation.dump_simple(false);

    // description is idempotent command in Cisco IOS, so Old Description is replaced by New Description without "no description"
    // shutdown -> no shutdown
    // interface GigabitEthernet0/2 added
    assert!(lines.contains(&"interface GigabitEthernet0/1".to_string()));
    assert!(lines.contains(&"  description New Description".to_string()));
    assert!(lines.contains(&"  no shutdown".to_string()));
    assert!(lines.contains(&"interface GigabitEthernet0/2".to_string()));
    assert!(lines.contains(&"  description Interface Two".to_string()));
}

#[test]
fn test_remediation_deletion_only() {
    let running_raw = r"
vlan 10
  name Marketing
vlan 20
  name Engineering
";
    let generated_raw = r"
vlan 10
  name Marketing
";

    let running = Tree::from_str(Platform::CiscoIos, running_raw).unwrap();
    let generated = Tree::from_str(Platform::CiscoIos, generated_raw).unwrap();

    let remediation = running.config_to_get_to(&generated).unwrap();
    let lines = remediation.dump_simple(false);

    assert_eq!(lines, vec!["no vlan 20"]);
}

#[test]
fn test_future_application() {
    let running_raw = r"
interface GigabitEthernet0/1
  shutdown
";
    let remediation_raw = r"
interface GigabitEthernet0/1
  no shutdown
  description Production Link
";

    let running = Tree::from_str(Platform::CiscoIos, running_raw).unwrap();
    let remediation = Tree::from_str(Platform::CiscoIos, remediation_raw).unwrap();

    let future = running.future(&remediation, true).unwrap();
    let lines = future.dump_simple(false);

    assert_eq!(
        lines,
        vec![
            "interface GigabitEthernet0/1",
            "  description Production Link",
        ]
    );
}

#[test]
fn test_difference() {
    let running_raw = r"
interface GigabitEthernet0/1
  shutdown
  description Link
";
    let target_raw = r"
interface GigabitEthernet0/1
  description Link
";

    let running = Tree::from_str(Platform::CiscoIos, running_raw).unwrap();
    let target = Tree::from_str(Platform::CiscoIos, target_raw).unwrap();

    let diff = running.difference(&target).unwrap();
    let lines = diff.dump_simple(false);

    assert_eq!(lines, vec!["interface GigabitEthernet0/1", "  shutdown",]);
}

#[test]
fn test_unified_diff() {
    let a_raw = r"
interface GigabitEthernet0/1
  shutdown
";
    let b_raw = r"
interface GigabitEthernet0/1
  no shutdown
";

    let a = Tree::from_str(Platform::CiscoIos, a_raw).unwrap();
    let b = Tree::from_str(Platform::CiscoIos, b_raw).unwrap();

    let udiff = a.unified_diff(&b);
    assert!(!udiff.is_empty());
}
