use hier_config_core::driver::Driver;
use hier_config_core::models::Platform;
use hier_config_core::parser::config_preprocessor;

#[test]
fn test_swap_negation_delete_to_set() {
    let driver = Driver::for_platform(Platform::Vyos);
    let result = driver.swap_negation("delete interfaces ethernet eth0 address 192.168.1.1/24");
    assert_eq!(
        result,
        "set interfaces ethernet eth0 address 192.168.1.1/24"
    );
    assert!(result.starts_with("set "));
}

#[test]
fn test_swap_negation_set_to_delete() {
    let driver = Driver::for_platform(Platform::Vyos);
    let result = driver.swap_negation("set interfaces ethernet eth0 address 192.168.1.1/24");
    assert_eq!(
        result,
        "delete interfaces ethernet eth0 address 192.168.1.1/24"
    );
    assert!(result.starts_with("delete "));
}

#[test]
fn test_swap_negation_no_prefix() {
    let driver = Driver::for_platform(Platform::Vyos);
    let text = "interfaces ethernet eth0 address 192.168.1.1/24";
    let result = driver.swap_negation(text);
    assert_eq!(result, text);
}

#[test]
fn test_swap_negation_no_prefix_python_fallback() {
    let driver = Driver::for_platform(Platform::Vyos);
    let text = "interfaces ethernet eth0 address 192.168.1.1/24";
    let result = driver.swap_negation(text);
    assert_eq!(result, text);
}

#[test]
fn test_declaration_prefix() {
    let driver = Driver::for_platform(Platform::Vyos);
    assert_eq!(driver.declaration_prefix, "set ");
}

#[test]
fn test_negation_prefix() {
    let driver = Driver::for_platform(Platform::Vyos);
    assert_eq!(driver.negation_prefix, "delete ");
}

#[test]
fn test_config_preprocessor() {
    let hierarchical_config = "\
interfaces {
    ethernet eth0 {
        address 192.168.1.1/24
        description \"WAN Interface\"
    }
}
system {
    host-name vyos-router
}";
    let result = config_preprocessor(Platform::Vyos, hierarchical_config);
    assert!(result.contains("set interfaces ethernet eth0 address 192.168.1.1/24"));
    assert!(result.contains("set interfaces ethernet eth0 description"));
    assert!(result.contains("set system host-name vyos-router"));
}
