use hier_config_core::driver::Driver;
use hier_config_core::models::Platform;

#[test]
fn test_swap_negation_delete_to_set() {
    let driver = Driver::for_platform(Platform::JuniperJunos);
    let result = driver
        .try_swap_negation("delete vlans test_vlan vlan-id 100")
        .unwrap();
    assert_eq!(result, "set vlans test_vlan vlan-id 100");
    assert!(result.starts_with("set "));
}

#[test]
fn test_swap_negation_set_to_delete() {
    let driver = Driver::for_platform(Platform::JuniperJunos);
    let result = driver
        .try_swap_negation("set vlans test_vlan vlan-id 100")
        .unwrap();
    assert_eq!(result, "delete vlans test_vlan vlan-id 100");
    assert!(result.starts_with("delete "));
}

#[test]
fn test_swap_negation_invalid_prefix() {
    let driver = Driver::for_platform(Platform::JuniperJunos);
    let err = driver
        .try_swap_negation("vlans test_vlan vlan-id 100")
        .unwrap_err();
    assert!(err.contains("did not start with"));
    assert!(err.contains("delete "));
    assert!(err.contains("set "));
}

#[test]
fn test_junos_uses_set_and_delete_prefixes() {
    let driver = Driver::for_platform(Platform::JuniperJunos);
    assert_eq!(driver.declaration_prefix, "set ");
    assert_eq!(driver.negation_prefix, "delete ");
}
