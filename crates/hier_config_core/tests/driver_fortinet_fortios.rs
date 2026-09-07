use hier_config_core::driver::Driver;
use hier_config_core::models::Platform;

#[test]
fn test_swap_negation_direct() {
    let driver = Driver::for_platform(Platform::FortinetFortios);
    let result = driver.swap_negation("set description 'test value'");
    assert_eq!(result, "unset description");

    let result2 = driver.swap_negation("unset description");
    assert_eq!(result2, "set description");
}

#[test]
fn test_swap_negation_declaration_prefix_with_no_trailing_text() {
    let driver = Driver::for_platform(Platform::FortinetFortios);
    let result = driver.swap_negation("set ");
    // When text is just the declaration prefix "set " with no first word in stripped,
    // it falls through to text.to_string(), which is "set ".
    // (Note: in Python child text was "set ", trimmed was "set", result was "set" or "set ").
    // In Rust driver.swap_negation("set ") -> "set ".
    assert!(result.starts_with("set"));
}
