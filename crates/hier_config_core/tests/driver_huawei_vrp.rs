use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;

#[test]
fn test_comments_stripped() {
    let raw = "#\n! this is a comment\ninterface GigabitEthernet0/0/0\n # another comment\n description test\n! yet another comment";
    let tree = Tree::from_str(Platform::HuaweiVrp, raw).unwrap();
    assert_eq!(
        tree.dump_simple(false),
        vec!["interface GigabitEthernet0/0/0", "  description test"]
    );
}

#[test]
fn test_multiple_peer_public_keys_no_duplicate_child_error() {
    let raw = "\
rsa peer-public-key user1 encoding-type openssh
 public-key-code begin
  AAAAB3Nza1
  C1yc2EAAA
 public-key-code end
peer-public-key end
#
rsa peer-public-key user2 encoding-type openssh
 public-key-code begin
  DDDDB3Nza2
 public-key-code end
peer-public-key end
#
";
    let tree = Tree::from_str(Platform::HuaweiVrp, raw).unwrap();
    assert_eq!(
        tree.dump_simple(false),
        vec![
            "rsa peer-public-key user1 encoding-type openssh",
            "  public-key-code begin",
            "    AAAAB3Nza1",
            "    C1yc2EAAA",
            "  public-key-code end",
            "  peer-public-key end",
            "rsa peer-public-key user2 encoding-type openssh",
            "  public-key-code begin",
            "    DDDDB3Nza2",
            "  public-key-code end",
            "  peer-public-key end",
        ]
    );
}

#[test]
fn test_sectional_exit_is_quit() {
    let raw = "interface GigabitEthernet0/0/0\n description test";
    let tree = Tree::from_str(Platform::HuaweiVrp, raw).unwrap();
    assert_eq!(
        tree.dump_simple(true),
        vec![
            "interface GigabitEthernet0/0/0",
            "  description test",
            "  quit"
        ]
    );
}
