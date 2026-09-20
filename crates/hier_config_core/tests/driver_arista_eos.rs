use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_arista_eos_per_line_sub_strips_metadata() {
    let raw = "\
! Last configuration change at Mon Jan 1 00:00:00 2024
Building configuration...
Current configuration : 1234 bytes
! NVRAM config last updated at Mon Jan 1 00:00:00 2024
version 4.28.0F
interface Ethernet1
 description uplink
end
";
    let tree = Tree::from_str(Platform::AristaEos, raw).unwrap();
    let lines = tree.dump_simple(false);
    assert!(
        !lines
            .iter()
            .any(|l| l.contains("Building configuration..."))
    );
    assert!(!lines.iter().any(|l| l.contains("version 4.28.0F")));
    assert!(!lines.iter().any(|l| l.trim() == "end"));
    assert!(lines.contains(&"interface Ethernet1".to_string()));
    assert!(lines.contains(&"  description uplink".to_string()));
}

#[test]
fn test_arista_eos_bgp_sectional_exiting() {
    let raw = "\
router bgp 65001
 address-family ipv4
  neighbor 10.0.0.1 activate
 template peer-policy PEER-POLICY-1
  route-map RM-IN in
 template peer-session PEER-SESSION-1
  password 7 secret
";
    let tree = Tree::from_str(Platform::AristaEos, raw).unwrap();
    for id in tree.all_children(tree.root) {
        let text = tree.arena[id].text.as_ref();
        let exit = tree.sectional_exit(id);
        match text {
            "router bgp 65001" => assert_eq!(exit.as_deref(), Some("exit")),
            "address-family ipv4" => {
                assert_eq!(exit.as_deref(), Some("exit-address-family"));
            }
            "template peer-policy PEER-POLICY-1" => {
                assert_eq!(exit.as_deref(), Some("exit-peer-policy"));
            }
            "template peer-session PEER-SESSION-1" => {
                assert_eq!(exit.as_deref(), Some("exit-peer-session"));
            }
            "neighbor 10.0.0.1 activate" => assert_eq!(exit, None),
            _ => {}
        }
    }
}
