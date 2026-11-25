use hier_config_core::{
    Driver, FullTextSubRule, IdempotentCommandsRule, IndentAdjustRule, MatchRule,
    NegationDefaultWithRule, NegationRule, NegationStrategy, PerLineSubRule, Platform, Tree,
    UnusedObjectRule, parse_fast, parse_tree,
};

#[test]
fn nxos_terminal_replacements_require_explicit_user_rules() {
    for custom_rules in [false, true] {
        let mut driver = Driver::for_platform(Platform::CiscoNxos);
        if custom_rules {
            driver.rules.negation = [
                ("terminal length", "terminal length 24"),
                ("terminal width", "terminal width 80"),
            ]
            .into_iter()
            .map(|(prefix, replacement)| NegationRule {
                strategy: NegationStrategy::Replace,
                match_rules: vec![
                    MatchRule::equals("line console"),
                    MatchRule::startswith(prefix),
                ],
                use_cmd: replacement.into(),
                search: String::new(),
                replace: String::new(),
            })
            .collect();
        }
        let running = parse_fast(
            driver.clone(),
            &[
                "line console",
                "  terminal length 10",
                "  terminal width 100",
            ],
            true,
        )
        .unwrap();
        let intended = parse_fast(driver, &["line console"], true).unwrap();
        let remediation = running.config_to_get_to(&intended).unwrap();
        let expected = if custom_rules {
            vec![
                "line console",
                "  terminal length 24",
                "  terminal width 80",
            ]
        } else {
            vec![
                "line console",
                "  no terminal length 10",
                "  no terminal width 100",
            ]
        };
        assert_eq!(remediation.dump_simple(false), expected);
        let future = running.future(&remediation, false).unwrap();
        let rollback = future.config_to_get_to(&running).unwrap();
        let restored = future.future(&rollback, false).unwrap();
        assert!(restored.unified_diff(&running).is_empty());
    }
}

#[test]
fn substitutions_use_python_templates_in_both_parsers() {
    let mut driver = Driver::default();
    driver.rules.per_line_sub = vec![PerLineSubRule {
        search: r"^(?P<name>port) (\d+)$".into(),
        replace: r"\g<name> \2_suffix $\1 \\1".into(),
    }];
    let expected = vec![r"port 42_suffix $port \1"];
    assert_eq!(
        parse_tree(driver.clone(), "port 42")
            .unwrap()
            .dump_simple(false),
        expected
    );
    assert_eq!(
        parse_fast(driver, &["port 42"], false)
            .unwrap()
            .dump_simple(false),
        expected
    );
}

#[test]
fn full_text_substitutions_use_python_templates() {
    let mut driver = Driver::default();
    driver.rules.full_text_sub = vec![FullTextSubRule {
        search: r"(?m)^(?P<name>port) (\d+)$".into(),
        replace: r"\g<name> \2_suffix $\1".into(),
    }];
    assert_eq!(
        parse_tree(driver, "port 42").unwrap().dump_simple(false),
        vec!["port 42_suffix $port"]
    );
}

#[test]
fn unsupported_substitutions_are_applied_or_rejected_never_dropped() {
    for pattern in [r"foo(?=bar)", r"foobar\Z"] {
        let mut driver = Driver::default();
        driver.rules.per_line_sub = vec![PerLineSubRule {
            search: pattern.into(),
            replace: "changed".into(),
        }];
        if let Ok(tree) = parse_tree(driver, "foobar") {
            assert_ne!(tree.dump_simple(false), vec!["foobar"], "{pattern}");
        }
    }
}

#[test]
fn invalid_rule_regexes_are_rejected_before_parsing() {
    let mut cases = Vec::new();
    let mut per_line = Driver::default();
    per_line.rules.per_line_sub = vec![PerLineSubRule {
        search: "(".into(),
        replace: String::new(),
    }];
    cases.push(per_line);
    let mut full_text = Driver::default();
    full_text.rules.full_text_sub = vec![FullTextSubRule {
        search: "(".into(),
        replace: String::new(),
    }];
    cases.push(full_text);
    for (start, end) in [("(", "end"), ("start", "(")] {
        let mut driver = Driver::default();
        driver.rules.indent_adjust = vec![IndentAdjustRule {
            start_expression: start.into(),
            end_expression: end.into(),
        }];
        cases.push(driver);
    }
    let mut idempotency = Driver::default();
    idempotency.rules.idempotent_commands = vec![IdempotentCommandsRule {
        match_rules: vec![MatchRule::re_search("(")],
    }];
    cases.push(idempotency);
    let mut unused = Driver::default();
    unused.rules.unused_objects = vec![UnusedObjectRule {
        match_rules: vec![MatchRule::startswith("object ")],
        name_re: "(".into(),
        reference_locations: Vec::new(),
    }];
    cases.push(unused);
    let mut negation = Driver::default();
    negation.rules.negation = vec![NegationRule {
        strategy: NegationStrategy::RegexSub,
        match_rules: vec![MatchRule::startswith("foo")],
        search: "(".into(),
        replace: String::new(),
        use_cmd: String::new(),
    }];
    cases.push(negation);
    for driver in cases {
        assert!(parse_tree(driver.clone(), "foo").is_err(), "{driver:?}");
        assert!(parse_fast(driver, &["foo"], false).is_err());
    }
}

#[test]
fn unified_replace_precedes_legacy_negate_with_in_tree() {
    let mut driver = Driver::default();
    driver.rules.negate_with = vec![NegationDefaultWithRule {
        match_rules: vec![MatchRule::equals("shutdown")],
        use_cmd: "legacy".into(),
    }];
    driver.rules.negation = vec![NegationRule {
        strategy: NegationStrategy::Replace,
        match_rules: vec![MatchRule::equals("shutdown")],
        use_cmd: "user override".into(),
        search: String::new(),
        replace: String::new(),
    }];
    let running = parse_fast(driver.clone(), &["shutdown"], false).unwrap();
    let node = running.arena[running.root].children.as_slice()[0];
    assert_eq!(running.negate_with(node), Some("user override".into()));
    assert_eq!(running.compute_negation(node), "user override");
    let intended = Tree::new(driver);
    let remediation = running.config_to_get_to(&intended).unwrap();
    assert_eq!(remediation.dump_simple(false), vec!["user override"]);
    let future = running.future(&remediation, false).unwrap();
    assert!(future.unified_diff(&intended).is_empty());
    let rollback = future.config_to_get_to(&running).unwrap();
    assert_eq!(rollback.dump_simple(false), vec!["shutdown"]);
    assert!(
        future
            .future(&rollback, false)
            .unwrap()
            .unified_diff(&running)
            .is_empty()
    );
}

#[test]
fn negation_template_delimits_numeric_capture_before_suffix() {
    let mut driver = Driver::for_platform(Platform::Generic);
    driver.rules.negate_with = vec![NegationDefaultWithRule {
        match_rules: vec![MatchRule::re_search(r"^port (\d+)$")],
        use_cmd: r"no port \1_suffix $1".into(),
    }];
    assert_eq!(
        driver.compute_negation("port 42", |_| true),
        "no port 42_suffix $1"
    );
}

#[test]
fn negation_regex_sub_replaces_all_occurrences_like_python() {
    let mut driver = Driver::default();
    driver.rules.negation = vec![NegationRule {
        strategy: NegationStrategy::RegexSub,
        match_rules: vec![MatchRule::startswith("ports ")],
        search: r"(\d)".into(),
        replace: r"\1x".into(),
        use_cmd: String::new(),
    }];
    assert_eq!(
        driver.try_compute_negation("ports 12", |_| true).unwrap(),
        "no ports 1x2x"
    );
}

#[test]
fn capture_producing_rules_reject_unsupported_patterns_explicitly() {
    // `\Z` is deliberately absent: Python's end-of-string anchor is now
    // translated to `\z` before compiling, so it must succeed.
    for pattern in [r"foo(?=bar)", "("] {
        let mut driver = Driver::default();
        assert!(
            driver
                .try_idempotency_key(&["foobar"], &[MatchRule::re_search(pattern)],)
                .is_err()
        );
        driver.rules.negation = vec![NegationRule {
            strategy: NegationStrategy::RegexSub,
            match_rules: vec![MatchRule::equals("foobar")],
            search: pattern.into(),
            replace: "changed".into(),
            use_cmd: String::new(),
        }];
        assert!(driver.try_compute_negation("foobar", |_| true).is_err());
        driver.rules.negation.clear();
        driver.rules.unused_objects = vec![UnusedObjectRule {
            match_rules: vec![MatchRule::equals("foobar")],
            name_re: pattern.into(),
            reference_locations: Vec::new(),
        }];
        let mut tree = Tree::new(driver);
        tree.add_child(tree.root, "foobar", false, false).unwrap();
        assert!(tree.try_unused_objects().is_err());
    }
}

#[test]
fn python_replacements_support_numbered_named_and_literal_escapes() {
    let re = hier_config_core::regex_cache::rule_regex(r"(?P<first>a)(b)(c)(d)(e)(f)(g)(h)(i)(j)")
        .unwrap();
    for (template, expected) in [
        (r"\1_suffix", "a_suffix"),
        (r"\10_suffix", "j_suffix"),
        (r"\g<first>_\g<0>", "a_abcdefghij"),
        (r"$1 ${first} $$", "$1 ${first} $$"),
        (r"\\1", r"\1"),
        (r"\101\077", "A?"),
        (r"\n\t\r\a\b\f\v", "\n\t\r\x07\x08\x0c\x0b"),
        (r"\$", r"\$"),
    ] {
        let replacement = hier_config_core::regex_cache::python_replacement(&re, template).unwrap();
        assert_eq!(
            re.replace_all("abcdefghij", replacement.as_str()),
            expected,
            "{template}"
        );
    }
    for template in [
        r"\20",
        r"\g<missing>",
        r"\g<>",
        r"\g<first",
        r"\gfirst",
        r"\q",
        "\\",
        r"\777",
    ] {
        assert!(
            hier_config_core::regex_cache::python_replacement(&re, template).is_err(),
            "{template}"
        );
    }
}

#[test]
fn invalid_replacement_templates_are_rejected_even_without_a_match() {
    for replacement in [r"\2", r"\g<missing>", r"\q", "\\"] {
        let mut driver = Driver::default();
        driver.rules.per_line_sub = vec![PerLineSubRule {
            search: "(foo)".into(),
            replace: replacement.into(),
        }];
        assert!(parse_tree(driver.clone(), "unrelated").is_err());
        assert!(parse_fast(driver, &["unrelated"], false).is_err());
    }
}

#[test]
fn indent_rules_support_lookaround_at_both_boundaries() {
    let mut driver = Driver::default();
    driver.rules.indent_adjust = vec![IndentAdjustRule {
        start_expression: r"^template(?! timeout)".into(),
        end_expression: r"^end(?=-template)".into(),
    }];
    let tree = parse_tree(
        driver,
        "template PORT\ndescription edge\nend-template\nhostname switch",
    )
    .unwrap();
    assert_eq!(
        tree.dump_simple(false),
        vec![
            "template PORT",
            "  description edge",
            "  end-template",
            "hostname switch"
        ],
    );
}

#[test]
fn cisco_xr_template_negative_lookahead_rule_round_trip() {
    let driver = Driver::for_platform(Platform::CiscoXr);
    let running = parse_tree(
        driver.clone(),
        "template PORT\ndescription old\nend-template",
    )
    .unwrap();
    let intended = parse_tree(driver, "template PORT\ndescription new\nend-template").unwrap();
    let remediation = running.config_to_get_to(&intended).unwrap();
    assert_eq!(
        remediation.dump_simple(false),
        vec!["no template PORT", "template PORT", "  description new"],
    );
    let future = running.future(&remediation, false).unwrap();
    assert!(future.unified_diff(&intended).is_empty());
    let rollback = future.config_to_get_to(&running).unwrap();
    assert_eq!(
        rollback.dump_simple(false),
        vec!["no template PORT", "template PORT", "  description old"]
    );
    assert!(
        future
            .future(&rollback, false)
            .unwrap()
            .unified_diff(&running)
            .is_empty()
    );
}
