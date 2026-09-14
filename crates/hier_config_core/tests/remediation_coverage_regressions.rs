use hier_config_core::models::IdempotentCommandsRule;
use hier_config_core::{Driver, MatchRule, Platform, parse_tree};

#[test]
fn junos_native_negation_fallback_is_permissive_but_swap_is_strict() {
    // upstream/next@0866dc2 juniper_junos/driver.py:swap_negation raises
    // ValueError without a set/delete prefix. The native-v1 structured-format
    // snapshots deliberately preserve a permissive compute_negation fallback.
    for rules in [serde_json::json!({}), serde_json::json!({"negation": []})] {
        let driver = Driver {
            rules: serde_json::from_value(rules).unwrap(),
            ..Driver::for_platform(Platform::JuniperJunos)
        };
        for text in [
            "",
            "system host-name router",
            "setting hostname",
            "delete",
            "@b \"two\"",
            "vlans 20",
        ] {
            let error = driver.try_swap_negation(text).unwrap_err();
            assert!(error.contains("did not start with"), "{error}");
            assert_eq!(
                driver.try_compute_negation(text, |_| false),
                Ok(text.to_owned())
            );
        }
        assert_eq!(
            driver.try_compute_negation("set system host-name router", |_| false),
            Ok("delete system host-name router".to_owned())
        );
        assert_eq!(
            driver.try_compute_negation("delete system host-name router", |_| false),
            Ok("set system host-name router".to_owned())
        );
    }
}

#[test]
fn junos_native_remediation_preserves_unflattened_command_fallback() {
    let mut running = parse_tree(Driver::for_platform(Platform::JuniperJunos), "").unwrap();
    let node = running
        .add_child(running.root, "system host-name router", false, false)
        .unwrap();
    let intended = parse_tree(Driver::for_platform(Platform::JuniperJunos), "").unwrap();
    assert!(
        running
            .driver
            .try_swap_negation("system host-name router")
            .is_err()
    );
    assert_eq!(
        running.try_compute_negation(node).unwrap(),
        "system host-name router"
    );
    assert_eq!(
        running
            .config_to_get_to(&intended)
            .unwrap()
            .dump_simple(false),
        ["system host-name router"]
    );
    assert_eq!(running.dump_simple(false), ["system host-name router"]);
}

#[test]
fn optional_capture_positions_are_part_of_idempotency_identity() {
    // upstream/next@0866dc2 driver_base.py:_normalize_regex_key keeps empty
    // capture positions; collapsing them aliases distinct command families.
    let mut driver = Driver::for_platform(Platform::Generic);
    let rule = MatchRule::re_search(r"^(?:foo (x)|bar (x)) .+$");
    driver
        .rules
        .idempotent_commands
        .push(IdempotentCommandsRule {
            match_rules: vec![rule.clone()],
        });
    assert_eq!(
        driver.idempotency_key(&["foo x old"], std::slice::from_ref(&rule)),
        ["re|x|"]
    );
    assert_eq!(driver.idempotency_key(&["bar x new"], &[rule]), ["re||x"]);

    let running = parse_tree(driver.clone(), "foo x old").unwrap();
    let intended = parse_tree(driver, "bar x new").unwrap();
    let delta = running.config_to_get_to(&intended).unwrap();
    assert_eq!(delta.dump_simple(false), ["no foo x old", "bar x new"]);
    let future = running.future(&delta, false).unwrap();
    assert!(future.unified_diff(&intended).is_empty());
    let rollback = future.config_to_get_to(&running).unwrap();
    assert_eq!(rollback.dump_simple(false), ["no bar x new", "foo x old"]);
    assert!(
        future
            .future(&rollback, false)
            .unwrap()
            .unified_diff(&running)
            .is_empty()
    );
}

#[test]
fn capture_identity_retains_upstream_empty_and_delimiter_normalization() {
    // Executed against upstream/next@0866dc2:_normalize_regex_key. Python
    // replaces None with "" and joins with "|": these collisions predate Rust.
    // A lossless encoding would be a separate, intentional behavior change.
    let driver = Driver::default();
    for (text, regex, expected) in [
        ("x", r"^()(x)$", "re||x"),
        ("x", r"^(z)?(x)$", "re||x"),
        ("a|b/c", r"^(.*)/(.*)$", "re|a|b|c"),
        ("a/b|c", r"^(.*)/(.*)$", "re|a|b|c"),
    ] {
        assert_eq!(
            driver.idempotency_key(&[text], &[MatchRule::re_search(regex)]),
            [expected]
        );
    }
}

#[test]
fn negation_can_already_be_an_unchanged_target_leaf() {
    // upstream/next@0866dc2 tree_algorithms.py:_remediation_right skips
    // matched leaves rather than inserting an empty subtree into the delta.
    let running = parse_tree(Driver::default(), "no shutdown\nshutdown").unwrap();
    let intended = parse_tree(Driver::default(), "shutdown").unwrap();
    assert_eq!(
        running
            .config_to_get_to(&intended)
            .unwrap()
            .dump_simple(false),
        ["shutdown"]
    );
}

#[test]
fn sectional_overwrite_ignores_nonsemantic_child_metadata() {
    // upstream/next@0866dc2 HConfigChild.__eq__ explicitly excludes comments,
    // order_weight and new_in_config, so bookkeeping must not drop ACLs.
    let driver = Driver {
        rules: serde_json::from_value(serde_json::json!({
            "sectional_overwrite": [{"match_rules": [{"equals": "ip access-list extended FILTER"}]}]
        }))
        .unwrap(),
        ..Driver::default()
    };
    let running = parse_tree(
        driver,
        "ip access-list extended FILTER\n  permit ip any any",
    )
    .unwrap();
    let mut intended = running.clone();
    let section = intended.arena[intended.root]
        .children
        .get("ip access-list extended FILTER")
        .unwrap();
    let leaf = intended.arena[section]
        .children
        .get("permit ip any any")
        .unwrap();
    intended.arena[leaf]
        .comments_mut()
        .insert("audited".to_owned());
    intended.arena[leaf].order_weight = 100;
    intended.arena[leaf].new_in_config = true;
    assert_eq!(
        running
            .config_to_get_to(&intended)
            .unwrap()
            .dump_simple(false),
        Vec::<String>::new()
    );
}
