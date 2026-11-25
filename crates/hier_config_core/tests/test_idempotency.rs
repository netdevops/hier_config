use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_cisco_ios_description_idempotent() {
    let running_raw = r"
interface GigabitEthernet0/1
  description Old Description
";
    let generated_raw = r"
interface GigabitEthernet0/1
  description New Description
";

    let running = Tree::from_str(Platform::CiscoIos, running_raw).unwrap();
    let generated = Tree::from_str(Platform::CiscoIos, generated_raw).unwrap();

    let remediation = running.config_to_get_to(&generated).unwrap();
    let lines = remediation.dump_simple(false);

    assert_eq!(
        lines,
        vec![
            "interface GigabitEthernet0/1",
            "  description New Description",
        ]
    );
}

#[test]
fn test_cisco_xr_bgp_neighbor_idempotent() {
    let running_raw = r"
router bgp 65000
  neighbor 192.0.2.1 remote-as 65001
  neighbor 192.0.2.2 remote-as 65002
";
    let generated_raw = r"
router bgp 65000
  neighbor 192.0.2.1 remote-as 65010
";

    let running = Tree::from_str(Platform::CiscoXr, running_raw).unwrap();
    let generated = Tree::from_str(Platform::CiscoXr, generated_raw).unwrap();

    let remediation = running.config_to_get_to(&generated).unwrap();
    let lines = remediation.dump_simple(false);

    // neighbor 192.0.2.1 is updated; neighbor 192.0.2.2 is removed
    assert!(lines.contains(&"  no neighbor 192.0.2.2 remote-as 65002".to_string()));
    assert!(lines.contains(&"  neighbor 192.0.2.1 remote-as 65010".to_string()));
}

#[test]
fn test_fortinet_fortios_set_unset() {
    let running_raw = r"
config system interface
  edit port1
    set ip 192.168.1.1 255.255.255.0
    set allowaccess ping
";
    let generated_raw = r"
config system interface
  edit port1
    set ip 10.0.0.1 255.255.255.0
";

    let running = Tree::from_str(Platform::FortinetFortios, running_raw).unwrap();
    let generated = Tree::from_str(Platform::FortinetFortios, generated_raw).unwrap();

    let remediation = running.config_to_get_to(&generated).unwrap();
    let lines = remediation.dump_simple(false);

    // FortiOS negation: set allowaccess -> unset allowaccess
    // set ip is idempotent: set ip 10.0.0.1 replaces set ip 192.168.1.1
    assert!(lines.contains(&"    unset allowaccess".to_string()));
    assert!(lines.contains(&"    set ip 10.0.0.1 255.255.255.0".to_string()));
}

#[test]
fn test_hp_procurve_aaa_port_access_idempotent() {
    let running_raw = r"
aaa port-access authenticator 1/1 tx-period 3
aaa port-access authenticator 1/1 client-limit 4
";
    let generated_raw = r"
aaa port-access authenticator 1/1 tx-period 4
";

    let running = Tree::from_str(Platform::HpProcurve, running_raw).unwrap();
    let generated = Tree::from_str(Platform::HpProcurve, generated_raw).unwrap();

    let remediation = running.config_to_get_to(&generated).unwrap();
    let lines = remediation.dump_simple(false);

    // client-limit negated via custom rule: "no aaa port-access authenticator 1/1 client-limit"
    assert!(lines.contains(&"no aaa port-access authenticator 1/1 client-limit".to_string()));
    assert!(lines.contains(&"aaa port-access authenticator 1/1 tx-period 4".to_string()));
}
