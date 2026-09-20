use hier_config_core::{Driver, DriverRules, MatchRule, Platform, parse_tree};
use serde_json::{Value, json};

fn driver_with_rules(value: Value) -> Driver {
    Driver {
        rules: serde_json::from_value(value).unwrap(),
        ..Driver::default()
    }
}

#[test]
fn idempotency_components_preserve_constraint_identity() {
    let driver = Driver::default();
    let cases = [
        (
            json!({"equals": "shutdown"}),
            "no shutdown",
            "equals|shutdown",
        ),
        (
            json!({"equals": ["shutdown", "no shutdown"]}),
            "no shutdown",
            "equals|no shutdown",
        ),
        (
            json!({"startswith": ["ip ", "ip address "]}),
            "no ip address 10.0.0.1",
            "startswith|ip address ",
        ),
        (
            json!({"endswith": "primary"}),
            "no address primary",
            "endswith|primary",
        ),
        (
            json!({"endswith": ["ary", "primary"]}),
            "address primary",
            "endswith|primary",
        ),
        (
            json!({"contains": "address"}),
            "no ip address primary",
            "contains|address",
        ),
        (
            json!({"contains": ["address", "ip address"]}),
            "ip address primary",
            "contains|ip address",
        ),
        (
            json!({"startswith": "absent", "endswith": "absent", "contains": "absent"}),
            "no shutdown",
            "text|shutdown",
        ),
        (
            json!({"startswith": ["absent"], "endswith": ["absent"], "contains": ["absent"]}),
            "shutdown",
            "text|shutdown",
        ),
        (
            json!({"startswith": "ip ", "endswith": "primary", "contains": "address"}),
            "no ip address primary",
            "startswith|ip ;endswith|primary;contains|address",
        ),
        (
            json!({"re_search": "^no (logging) (console)$"}),
            "no logging console",
            "re|logging|console",
        ),
        (
            json!({"re_search": "^absent$"}),
            "no shutdown",
            "text|shutdown",
        ),
        (
            json!({"re_search": "^description .+$"}),
            "description uplink",
            "re|description",
        ),
        (
            json!({"re_search": ".*"}),
            "description uplink",
            "re|description uplink",
        ),
        (json!({"re_search": r"^(\s*)(x)(z)?$"}), "x", "re||x|"),
        (json!({"re_search": r"^(\s*)x$"}), "x", "re|x"),
        (json!({"re_search": r"^\s*.*$"}), "x", "re|x"),
    ];
    for (rule, text, expected) in cases {
        let rule: MatchRule = serde_json::from_value(rule).unwrap();
        assert_eq!(
            driver.try_idempotency_key(&[text], &[rule]).unwrap(),
            [expected],
            "{text}"
        );
    }
    assert_eq!(
        driver
            .try_idempotency_key(&["one", "two"], &[MatchRule::equals("one")])
            .unwrap(),
        Vec::<String>::new()
    );
    let error = driver
        .try_idempotency_key(&["x"], &[MatchRule::re_search("[")])
        .unwrap_err();
    assert!(error.contains('['), "{error}");
}

#[test]
fn legacy_negation_strategies_and_unified_fallbacks() {
    let driver = driver_with_rules(json!({
        "negation_default_when": [{"match_rules": [{"equals": "no shutdown"}]}]
    }));
    assert_eq!(
        driver
            .try_compute_negation("no shutdown", |_| true)
            .unwrap(),
        "default shutdown"
    );
    assert_eq!(
        driver
            .try_compute_negation("hostname edge", |_| false)
            .unwrap(),
        "no hostname edge"
    );

    for unified in [false, true] {
        let mut rules = json!({
            "negation_sub": [{"match_rules": [{"startswith": "feature "}], "search": "^no (feature) .+$", "replace": "disable \\1"}],
            "negate_with": [{"match_rules": [{"equals": "unused"}], "use": "replacement"}]
        });
        if unified {
            rules["negation"] =
                json!([{"strategy": "default", "match_rules": [{"equals": "unmatched"}]}]);
        }
        let unified_driver = driver_with_rules(rules);
        assert_eq!(
            unified_driver
                .try_compute_negation("feature blue", |matching| matching[0].startswith.is_some())
                .unwrap(),
            "disable feature"
        );
        assert_eq!(
            unified_driver
                .try_compute_negation("feature blue", |_| false)
                .unwrap(),
            "no feature blue"
        );
    }

    let literal_driver = driver_with_rules(json!({
        "negate_with": [{"match_rules": [{"equals": "shutdown"}], "use": "\\g<literal>"}]
    }));
    // A template without a capture-producing regex remains literal.
    literal_driver.rules.validate_regexes().unwrap();
    assert_eq!(
        literal_driver
            .try_compute_negation("shutdown", |_| true)
            .unwrap(),
        r"\g<literal>"
    );
}

#[test]
fn replacement_uses_last_regex_and_does_not_leak_unmatched_text() {
    let driver = driver_with_rules(json!({
        "negation": [{
            "strategy": "replace",
            "match_rules": [{"re_search": "(ancestor)"}, {"re_search": "(?P<setting>timer) ([0-9]+)"}],
            "use": "reset \\g<setting> \\2"
        }]
    }));
    assert_eq!(
        driver
            .try_compute_negation("prefix timer 30 suffix", |_| true)
            .unwrap(),
        "reset timer 30"
    );
    assert_eq!(
        driver.try_compute_negation("unmatched", |_| true).unwrap(),
        r"reset \g<setting> \2"
    );
}

#[test]
fn malformed_rule_fields_report_their_origin() {
    let cases = [
        (
            json!({"per_line_sub": [{"search": "[", "replace": ""}]}),
            "per_line_sub:",
        ),
        (
            json!({"full_text_sub": [{"search": "(x)", "replace": "\\2"}]}),
            "full_text_sub replacement:",
        ),
        (
            json!({"negation_sub": [{"match_rules": [], "search": "[", "replace": ""}]}),
            "negation_sub:",
        ),
        (
            json!({"negation": [{"strategy": "regex_sub", "match_rules": [], "search": "[", "replace": ""}]}),
            "negation REGEX_SUB:",
        ),
        (
            json!({"negation": [{"strategy": "replace", "match_rules": [{"re_search": "(x)"}], "use": "\\2"}]}),
            "negate_with replacement:",
        ),
        (
            json!({"negate_with": [{"match_rules": [{"re_search": "["}], "use": "\\1"}]}),
            "negate_with:",
        ),
        (
            json!({"idempotent_commands": [{"match_rules": [{"re_search": "["}]}]}),
            "idempotent_commands:",
        ),
        (
            json!({"indent_adjust": [{"start_expression": "[", "end_expression": "end"}]}),
            "indent_adjust.start_expression:",
        ),
        (
            json!({"indent_adjust": [{"start_expression": "begin", "end_expression": "["}]}),
            "indent_adjust.end_expression:",
        ),
        (
            json!({"unused_objects": [{"name": "test", "name_re": "[", "match_rules": [], "reference_locations": []}]}),
            "unused_objects.name_re:",
        ),
    ];
    for (rules, expected) in cases {
        let driver = driver_with_rules(rules);
        let error = driver.rules.validate_regexes().unwrap_err();
        assert!(error.starts_with(expected), "{expected}: {error}");
        let parse_error = parse_tree(driver, "hostname edge").unwrap_err();
        assert!(parse_error.to_string().contains(expected), "{parse_error}");
    }
}

#[test]
fn sectional_exit_rules_can_suppress_or_override_default_tokens() {
    let driver = driver_with_rules(json!({
        "sectional_exiting": [
            {"match_rules": [{"equals": "suppress"}], "exit_text": ""},
            {"match_rules": [{"equals": "special"}], "exit_text": "end-policy"}
        ]
    }));
    assert_eq!(
        driver.sectional_exit(true, |rules| rules[0] == MatchRule::equals("suppress")),
        None
    );
    assert_eq!(
        driver.sectional_exit(false, |rules| rules[0] == MatchRule::equals("special")),
        Some("end-policy".to_owned())
    );
    assert_eq!(
        driver.sectional_exit(true, |_| false),
        Some("exit".to_owned())
    );
    assert_eq!(driver.sectional_exit(false, |_| false), None);
    assert_eq!(
        Driver::for_platform(Platform::FortinetFortios).sectional_exit(true, |_| false),
        Some("exit".to_owned())
    );
}

#[test]
fn default_rules_serialize_without_overrides_and_restore_defaults() {
    assert_eq!(
        serde_json::to_value(DriverRules::default()).unwrap(),
        json!({})
    );
    assert_eq!(
        serde_json::from_value::<DriverRules>(json!({})).unwrap(),
        DriverRules::default()
    );
    let driver = driver_with_rules(json!({"indentation": 4, "enabled_post_load": []}));
    assert_eq!(
        serde_json::to_value(&driver.rules).unwrap(),
        json!({"indentation": 4, "enabled_post_load": []})
    );
}
