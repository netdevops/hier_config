//! Ports the upstream/next `_idempotency_key` cases and `FortiOS` #225 crash guard.

use hier_config_core::{Driver, MatchRule, Platform, StringPattern, Tree, parse_fast};

#[test]
fn idempotency_key_string_predicates_and_fallbacks() {
    let driver = Driver::for_platform(Platform::CiscoIos);
    let cases = [
        (
            MatchRule::equals("logging console"),
            "equals|logging console",
        ),
        (
            MatchRule {
                equals: Some(StringPattern::Multiple(vec![
                    "logging console".into(),
                    "other".into(),
                ])),
                ..MatchRule::default()
            },
            "equals|logging console",
        ),
        (MatchRule::default(), "text|logging console"),
        (MatchRule::startswith("interface"), "text|logging console"),
        (MatchRule::endswith("emergency"), "text|logging console"),
        (MatchRule::contains("interface"), "text|logging console"),
        (MatchRule::endswith("console"), "endswith|console"),
        (MatchRule::contains("console"), "contains|console"),
        (MatchRule::re_search("^interface"), "text|logging console"),
        (MatchRule::re_search("interface.*"), "text|logging console"),
    ];
    for (rule, expected) in cases {
        assert_eq!(
            driver.idempotency_key(&["logging console"], &[rule]),
            vec![expected]
        );
    }
}

#[test]
fn idempotency_key_multiple_predicates_choose_longest_or_fall_back() {
    let driver = Driver::default();
    for values in [
        vec!["interface", "router", "vlan"],
        vec!["log", "logging", "logging console"],
    ] {
        let pattern = StringPattern::Multiple(values.iter().map(ToString::to_string).collect());
        let rule = MatchRule {
            startswith: Some(pattern),
            ..MatchRule::default()
        };
        let expected = if values[0] == "log" {
            "startswith|logging console"
        } else {
            "text|logging console"
        };
        assert_eq!(
            driver.idempotency_key(&["logging console"], &[rule]),
            vec![expected]
        );
    }
    for (values, expected) in [
        (
            vec!["emergency", "alert", "critical"],
            "text|logging console",
        ),
        (vec!["ole", "sole", "console"], "endswith|console"),
    ] {
        let rule = MatchRule {
            endswith: Some(StringPattern::Multiple(
                values.iter().map(ToString::to_string).collect(),
            )),
            ..MatchRule::default()
        };
        assert_eq!(
            driver.idempotency_key(&["logging console"], &[rule]),
            vec![expected]
        );
    }
    for (values, expected) in [
        (vec!["interface", "router", "vlan"], "text|logging console"),
        (
            vec!["log", "console", "logging console"],
            "contains|logging console",
        ),
    ] {
        let rule = MatchRule {
            contains: Some(StringPattern::Multiple(
                values.iter().map(ToString::to_string).collect(),
            )),
            ..MatchRule::default()
        };
        assert_eq!(
            driver.idempotency_key(&["logging console"], &[rule]),
            vec![expected]
        );
    }
}

#[test]
fn idempotency_key_capture_groups_greedy_suffixes_and_negation() {
    let driver = Driver::default();
    for (text, regex, expected) in [
        ("logging console", r"logging ()?(console)", "re|console"),
        ("logging console", r"logging (none)?()", "re|logging"),
        (
            "logging console emergency",
            r"logging console.*",
            "re|logging console",
        ),
        (
            "logging console emergency",
            r"logging console.*$",
            "re|logging console",
        ),
        ("logging console", r".*", "re|logging console"),
        (
            "interface GigabitEthernet1",
            r"interface .+",
            "re|interface",
        ),
        ("no logging console", r"^no logging", "re|no logging"),
    ] {
        assert_eq!(
            driver.idempotency_key(&[text], &[MatchRule::re_search(regex)]),
            vec![expected]
        );
    }
    assert_eq!(
        driver.idempotency_key(&["no logging console"], &[MatchRule::startswith("logging")]),
        vec!["startswith|logging"]
    );
    assert_eq!(
        driver.idempotency_key(
            &["router bgp 1", "neighbor 10.1.1.1 description peer1"],
            &[
                MatchRule::startswith("router bgp"),
                MatchRule::re_search(r"neighbor (\S+) description")
            ],
        ),
        vec!["startswith|router bgp", "re|10.1.1.1"]
    );
    assert!(
        driver
            .idempotency_key(
                &["interface GigabitEthernet1", "description test"],
                &[MatchRule::startswith("description")],
            )
            .is_empty()
    );
}

#[test]
fn fortios_idempotent_for_preserves_attribute_identity_and_bare_set_guard_225() {
    for (text, other_text, matched) in [
        ("set primary 192.0.2.1", "set primary 192.0.2.3", true),
        ("set primary 192.0.2.1", "set secondary 192.0.2.3", false),
        ("set", "set", false),
        ("set", "set primary 192.0.2.3", false),
        ("set primary 192.0.2.1", "set", false),
    ] {
        let mut tree = Tree::for_platform(Platform::FortinetFortios);
        let node = tree.add_child(tree.root, text, false, false).unwrap();
        let mut other = Tree::for_platform(Platform::FortinetFortios);
        let other_node = other
            .add_child(other.root, other_text, false, false)
            .unwrap();
        assert_eq!(
            tree.idempotent_for(node, &other, &[other_node]),
            matched.then_some(other_node)
        );
    }
    let driver = Driver::for_platform(Platform::FortinetFortios);
    assert_eq!(driver.swap_negation("set"), "set");
    assert_eq!(
        driver.swap_negation(r#"set description "Port 1""#),
        "unset description"
    );
}

#[test]
fn fortios_idempotent_attribute_round_trip_225() {
    let driver = Driver::for_platform(Platform::FortinetFortios);
    let running = parse_fast(
        driver.clone(),
        &["config system dns", " set primary 192.0.2.1"],
        true,
    )
    .unwrap();
    let intended = parse_fast(
        driver,
        &["config system dns", " set primary 192.0.2.3"],
        true,
    )
    .unwrap();
    let remediation = running.config_to_get_to(&intended).unwrap();
    assert_eq!(
        remediation.dump_simple(false),
        vec!["config system dns", "  set primary 192.0.2.3"]
    );
    let future = running.future(&remediation, false).unwrap();
    assert!(
        future.unified_diff(&intended).is_empty(),
        "{:?}",
        future.dump_simple(false)
    );
    let rollback = future.config_to_get_to(&running).unwrap();
    assert_eq!(
        rollback.dump_simple(false),
        vec!["config system dns", "  set primary 192.0.2.1"]
    );
    assert!(
        future
            .future(&rollback, false)
            .unwrap()
            .unified_diff(&running)
            .is_empty()
    );
}
