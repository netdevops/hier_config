use hier_config_core::driver::Driver;
use hier_config_core::models::Platform;
use hier_config_core::parser::config_preprocessor;

#[test]
fn test_swap_negation_delete_to_set() {
    let driver = Driver::for_platform(Platform::NokiaSrl);
    let result = driver
        .swap_negation("delete interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24");
    assert_eq!(
        result,
        "set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    );
    assert!(result.starts_with("set "));
}

#[test]
fn test_swap_negation_set_to_delete() {
    let driver = Driver::for_platform(Platform::NokiaSrl);
    let result = driver
        .swap_negation("set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24");
    assert_eq!(
        result,
        "delete interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24"
    );
    assert!(result.starts_with("delete "));
}

#[test]
fn test_swap_negation_no_prefix() {
    let driver = Driver::for_platform(Platform::NokiaSrl);
    let text = "interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24";
    let result = driver.swap_negation(text);
    assert_eq!(result, text);
}

#[test]
fn test_declaration_prefix() {
    let driver = Driver::for_platform(Platform::NokiaSrl);
    assert_eq!(driver.declaration_prefix, "set ");
}

#[test]
fn test_negation_prefix() {
    let driver = Driver::for_platform(Platform::NokiaSrl);
    assert_eq!(driver.negation_prefix, "delete ");
}

#[test]
fn test_config_preprocessor() {
    let hierarchical_config = "\
interface {
    ethernet-1/1 {
        subinterface 0 {
            ipv4 {
                admin-state enable
                address 192.168.1.1/24
            }
        }
    }
}
system {
    name {
        host-name srl-router
    }
}";
    let result = config_preprocessor(Platform::NokiaSrl, hierarchical_config);
    assert!(result.contains("set interface ethernet-1/1 subinterface 0 ipv4 admin-state enable"));
    assert!(
        result.contains("set interface ethernet-1/1 subinterface 0 ipv4 address 192.168.1.1/24")
    );
    assert!(result.contains("set system name host-name srl-router"));
}
