use hier_config_core::{
    IdempotentCommandsAvoidRule, IdempotentCommandsRule, MatchRule, NegationDefaultWithRule,
    NegationRule, NegationStrategy, Platform, Tree, TreeError,
};

#[test]
fn generic_idempotency_falls_back_to_other_driver_but_local_rules_take_precedence() {
    let mut local = Tree::default();
    let a = local
        .add_child(local.root, "description new", true, false)
        .unwrap();
    let mut other = Tree::default();
    let children = other
        .add_children(other.root, &["unrelated", "description old"])
        .unwrap();
    other
        .driver
        .rules
        .idempotent_commands
        .push(IdempotentCommandsRule {
            match_rules: vec![MatchRule::startswith("description ")],
        });
    assert_eq!(
        local.idempotent_for(a, &other, &children),
        Some(children[1])
    );
    assert!(local.is_idempotent_command(a, &other, &children));
    other
        .driver
        .rules
        .idempotent_commands_avoid
        .push(IdempotentCommandsAvoidRule {
            match_rules: vec![MatchRule::startswith("description ")],
        });
    assert!(!local.is_idempotent_command(a, &other, &children));
    local
        .driver
        .rules
        .idempotent_commands_avoid
        .push(IdempotentCommandsAvoidRule {
            match_rules: vec![MatchRule::equals("not matched")],
        });
    assert!(local.is_idempotent_command(a, &other, &children));
    local
        .driver
        .rules
        .idempotent_commands
        .push(IdempotentCommandsRule {
            match_rules: vec![MatchRule::equals("not matched")],
        });
    assert_eq!(local.idempotent_for(a, &other, &children), None);
    assert!(!local.is_idempotent_command(a, &other, &children));
    local.driver.rules.idempotent_commands = vec![IdempotentCommandsRule {
        match_rules: vec![MatchRule::re_search(r"^description (\S+)")],
    }];
    assert_eq!(local.idempotent_for(a, &other, &children), None);
    other.set_text(children[1], "description new suffix");
    assert_eq!(
        local.idempotent_for(a, &other, &children),
        Some(children[1])
    );
    assert_eq!(local.idempotent_for(a, &other, &[]), None);
}

#[test]
fn fortios_idempotency_matches_set_key_not_value_and_ignores_non_declarations() {
    for platform in [Platform::Generic, Platform::FortinetFortios] {
        let mut local = Tree::for_platform(platform);
        let a = local
            .add_child(local.root, "set ip new", true, false)
            .unwrap();
        let mut other = Tree::for_platform(Platform::FortinetFortios);
        let children = other
            .add_children(
                other.root,
                &["unset ip", "set", "set gateway old", "set ip old"],
            )
            .unwrap();
        // Clear stock rules so this isolates FortiOS's declaration-key path.
        local.driver.rules.idempotent_commands.clear();
        other.driver.rules.idempotent_commands.clear();
        assert_eq!(
            local.idempotent_for(a, &other, &children),
            Some(children[3])
        );
        assert_eq!(local.idempotent_for(a, &other, &children[..3]), None);
        local.set_text(a, "set ");
        assert_eq!(local.idempotent_for(a, &other, &children), None);
        local.set_text(a, "unset ip");
        assert_eq!(local.idempotent_for(a, &other, &children), None);
        local.driver.declaration_prefix.clear();
        other.driver.declaration_prefix.clear();
        local.set_text(a, "set ip new");
        assert_eq!(local.idempotent_for(a, &other, &children), None);
    }
}

#[test]
fn xr_acl_idempotency_matches_sequence_for_ipv4_and_ipv6_only() {
    for parent in [
        "ipv4 access-list EDGE",
        "ipv6 access-list EDGE",
        "unrelated",
    ] {
        let mut local = Tree::for_platform(Platform::CiscoXr);
        local.driver.rules.idempotent_commands.clear();
        let a = local
            .add_children_deep(local.root, &[parent, "10 permit new"])
            .unwrap();
        let mut other = Tree::for_platform(Platform::CiscoXr);
        other.driver.rules.idempotent_commands.clear();
        let section = other.add_child(other.root, parent, true, false).unwrap();
        let children = other
            .add_children(section, &["20 deny other", "10 deny old"])
            .unwrap();
        let expected = if parent == "unrelated" {
            None
        } else {
            Some(children[1])
        };
        assert_eq!(local.idempotent_for(a, &other, &children), expected);
        assert_eq!(local.idempotent_for(a, &other, &children[..1]), None);
        local.set_text(a, "");
        assert_eq!(local.idempotent_for(a, &other, &children), None);
        local.set_text(a, "10 permit new");
        other.set_text(children[1], "");
        assert_eq!(local.idempotent_for(a, &other, &children), None);
        let top = local
            .add_child(local.root, "10 top-level", true, false)
            .unwrap();
        assert_eq!(local.idempotent_for(top, &other, &children), None);
    }
}

#[test]
fn negation_wrappers_honor_replacement_order_and_propagate_template_errors() {
    let mut tree = Tree::default();
    let id = tree
        .add_child(tree.root, "command 42", true, false)
        .unwrap();
    assert_eq!(tree.negate_with(id), None);
    assert_eq!(tree.compute_negation(id), "no command 42");
    tree.driver.rules.negate_with = vec![
        NegationDefaultWithRule {
            match_rules: vec![MatchRule::equals("absent")],
            use_cmd: "unused".into(),
        },
        NegationDefaultWithRule {
            match_rules: vec![MatchRule::re_search(r"^command (\d+)$")],
            use_cmd: r"legacy \1".into(),
        },
    ];
    assert_eq!(tree.negate_with(id), Some("legacy 42".into()));
    assert_eq!(tree.try_compute_negation(id), Ok("legacy 42".into()));
    tree.driver.rules.negation = vec![NegationRule {
        strategy: NegationStrategy::Replace,
        match_rules: vec![MatchRule::re_search(r"^command (\d+)$")],
        use_cmd: r"unified \1".into(),
        search: String::new(),
        replace: String::new(),
    }];
    assert_eq!(tree.negate_with(id), Some("unified 42".into()));
    tree.driver.rules.negation[0].use_cmd = r"\2".into();
    assert!(matches!(
        tree.try_negate_with(id),
        Err(TreeError::InvalidRegex(_))
    ));
    assert!(matches!(
        tree.try_compute_negation(id),
        Err(TreeError::InvalidRegex(_))
    ));
    tree.driver.rules.negation.clear();
    tree.driver.rules.negate_with[1].use_cmd = r"\2".into();
    assert!(matches!(
        tree.try_negate_with(id),
        Err(TreeError::InvalidRegex(_))
    ));
    tree.driver.rules.negate_with.clear();
    tree.driver.rules.negation = vec![NegationRule {
        strategy: NegationStrategy::RegexSub,
        match_rules: vec![MatchRule::startswith("command")],
        use_cmd: String::new(),
        search: "[".into(),
        replace: String::new(),
    }];
    assert!(matches!(
        tree.try_compute_negation(id),
        Err(TreeError::InvalidRegex(_))
    ));
}
