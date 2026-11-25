use hier_config_core::remediation::{
    children_equal, config_to_get_to_into, future_with_report, overwrite_with,
    strip_acl_sequence_number,
};
use hier_config_core::{Driver, Platform, Tree, parse_tree};
use serde_json::json;

fn generic(text: &str) -> Tree {
    Tree::from_str(Platform::Generic, text).unwrap()
}

#[test]
fn difference_ignores_acl_sequence_numbers_but_preserves_missing_entries() {
    let source = generic(
        "ip access-list extended FILTER\n  10 permit ip any any\n  20 deny tcp any any\nipv4 access-list OTHER\n  100 permit ip any any\nipv6 access-list V6\n  5 permit ipv6 any any\nno logging console\ndefault interface Ethernet1\ninterface Ethernet1\n  description retained\n  shutdown\nremoved section\n  child\n    grandchild",
    );
    let target = generic(
        "ip access-list extended FILTER\n  100 permit ip any any\nipv4 access-list OTHER\n  10 permit ip any any\nipv6 access-list V6\n  99 permit ipv6 any any\ninterface Ethernet1\n  description retained",
    );
    assert_eq!(
        source.difference(&target).unwrap().dump_simple(false),
        [
            "ip access-list extended FILTER",
            "  20 deny tcp any any",
            "interface Ethernet1",
            "  shutdown",
            "removed section",
            "  child",
            "    grandchild",
        ]
    );
    assert!(
        target
            .difference(&source)
            .unwrap()
            .dump_simple(false)
            .is_empty()
    );
    for (input, expected) in [
        ("", ""),
        ("123", ""),
        ("  010   permit ip any any  ", "permit ip any any"),
        ("permit 123 any", "permit 123 any"),
        ("10a permit", "10a permit"),
    ] {
        assert_eq!(strip_acl_sequence_number(input), expected);
    }
}

#[test]
fn unified_diff_renders_nested_added_and_removed_sections_in_order() {
    let source = generic("common\n  unchanged\n  removed\n    grandchild\nold\n  leaf");
    let target = generic("common\n  unchanged\n  added\n    new grandchild\nnew\n  leaf");
    assert_eq!(
        source.unified_diff(&target),
        [
            "common",
            "  - removed",
            "    - grandchild",
            "  + added",
            "    + new grandchild",
            "- old",
            "  - leaf",
            "+ new",
            "  + leaf",
        ]
    );
    assert!(source.unified_diff(&source).is_empty());
}

#[test]
fn remediation_marks_added_descendants_and_deleted_section_size() {
    let source = generic("removed\n  child\n    grandchild");
    let target = generic("added\n  child\n    grandchild");
    let delta = source.config_to_get_to(&target).unwrap();
    let removed = delta.arena[delta.root].children.get("no removed").unwrap();
    assert_eq!(
        delta.arena[removed]
            .comments()
            .iter()
            .map(String::as_str)
            .collect::<Vec<_>>(),
        ["removes 2 lines"]
    );
    assert!(!delta.arena[removed].new_in_config);
    let added = delta.arena[delta.root].children.get("added").unwrap();
    assert!(delta.arena[added].comments().contains("new section"));
    assert!(delta.arena[added].new_in_config);
    for id in delta.all_children(added) {
        assert!(delta.arena[id].new_in_config);
    }
    assert_eq!(
        delta.dump_simple(false),
        ["no removed", "added", "  child", "    grandchild"]
    );
}

#[test]
fn seeded_overwrite_replaces_existing_delta_section() {
    for negate in [true, false] {
        let source = generic("section\n  old");
        let target = generic("section\n  new");
        let mut delta = generic("section\n  pending");
        let source_section = source.arena[source.root].children.get("section").unwrap();
        let target_section = target.arena[target.root].children.get("section").unwrap();
        let root = delta.root;
        overwrite_with(
            &source,
            source_section,
            &target,
            target_section,
            &mut delta,
            root,
            negate,
        )
        .unwrap();
        let new = delta.arena[root].children.get("section").unwrap();
        assert!(delta.arena[new].comments().contains("re-create section"));
        if negate {
            let dropped = delta.arena[root].children.get("no section").unwrap();
            assert!(delta.arena[dropped].comments().contains("dropping section"));
            // Python overwrite_with also retains an existing section's children
            // while renaming it to the negation.
            assert_eq!(
                delta.dump_simple(false),
                ["no section", "  pending", "section", "  new"]
            );
        } else {
            assert_eq!(delta.dump_simple(false), ["section", "  new"]);
        }
        let mut empty = generic("");
        let empty_root = empty.root;
        overwrite_with(
            &source,
            source_section,
            &source,
            source_section,
            &mut empty,
            empty_root,
            negate,
        )
        .unwrap();
        assert!(empty.dump_simple(false).is_empty());
    }
}

#[test]
fn sectional_overwrite_modes_and_upstream_no_negate_projection_limitation() {
    for negate in [true, false] {
        let driver = Driver {
            rules: serde_json::from_value(if negate {
                json!({"sectional_overwrite": [{"match_rules": [{"equals": "section"}]}]})
            } else {
                json!({"sectional_overwrite_no_negate": [{"match_rules": [{"equals": "section"}]}]})
            })
            .unwrap(),
            ..Driver::default()
        };
        let source = parse_tree(driver.clone(), "section\n  old\n    grandchild").unwrap();
        let target = parse_tree(driver, "section\n  new\n    grandchild").unwrap();
        let delta = source.config_to_get_to(&target).unwrap();
        let expected = if negate {
            vec!["no section", "section", "  new", "    grandchild"]
        } else {
            vec!["section", "  new", "    grandchild"]
        };
        assert_eq!(delta.dump_simple(false), expected);
        assert!(
            source
                .config_to_get_to(&source)
                .unwrap()
                .dump_simple(false)
                .is_empty()
        );
        if !negate {
            // Upstream compute_future copies the replacement, then copies the
            // original section again without marking it as consumed.
            assert!(
                matches!(source.future(&delta, false), Err(hier_config_core::TreeError::DuplicateChild(path)) if path == ["section"])
            );
            continue;
        }
        let projected = source.future(&delta, false).unwrap();
        assert!(projected.unified_diff(&target).is_empty());
        let rollback = projected.config_to_get_to(&source).unwrap();
        assert_eq!(
            rollback.dump_simple(false),
            if negate {
                vec!["no section", "section", "  old", "    grandchild"]
            } else {
                vec!["section", "  old", "    grandchild"]
            }
        );
        assert!(
            projected
                .future(&rollback, false)
                .unwrap()
                .unified_diff(&source)
                .is_empty()
        );
    }
}

#[test]
fn children_equal_checks_config_and_tags_but_ignores_bookkeeping() {
    let source = generic("parent\n  child\n    grandchild");
    let parent = source.arena[source.root].children.get("parent").unwrap();
    let child = source.arena[parent].children.get("child").unwrap();
    let leaf = source.arena[child].children.get("grandchild").unwrap();
    for mutation in 0..7 {
        let mut target = source.clone();
        match mutation {
            0 => {
                target.set_text(leaf, "different");
            }
            1 => {
                target.arena[leaf].order_weight += 1;
            }
            2 => {
                target.arena[leaf].tags_mut().insert("tag".to_owned());
            }
            3 => {
                target.arena[leaf]
                    .comments_mut()
                    .insert("comment".to_owned());
            }
            4 => {
                target.arena[leaf].new_in_config = true;
            }
            5 => {
                target.add_child(child, "additional", false, false).unwrap();
            }
            _ => {
                target.set_text(parent, "other parent");
            }
        }
        assert_eq!(
            children_equal(&source, parent, &target, parent),
            matches!(mutation, 1 | 3 | 4 | 6),
            "mutation {mutation}"
        );
    }
}

#[test]
fn future_reports_only_unresolved_and_idempotent_negations() {
    let source = Tree::from_str(
        Platform::CiscoIos,
        "logging console warnings\ninterface Ethernet1\n  description old\n  shutdown",
    )
    .unwrap();
    let change = Tree::from_str(
        Platform::CiscoIos,
        "no logging console\nno nonexistent\ninterface Ethernet1\n  no description\n  no shutdown",
    )
    .unwrap();
    let (future, report) = future_with_report(&source, &change, true).unwrap();
    assert_eq!(
        future.dump_simple(false),
        ["no logging console", "no nonexistent"]
    );
    assert_eq!(
        report
            .unresolved_negations
            .iter()
            .map(|id| &*future.arena[*id].text)
            .collect::<Vec<_>>(),
        ["no nonexistent"]
    );
    assert_eq!(
        report
            .idempotency_replacements
            .iter()
            .map(|id| &*future.arena[*id].text)
            .collect::<Vec<_>>(),
        ["no logging console"]
    );
}

#[test]
fn future_prefix_negation_and_pruning_respect_original_empty_sections() {
    let source = generic("outer\n  inner\n    option one\n    option two\nempty");
    let change = generic("outer\n  inner\n    no option\nnew empty");
    let unpruned = source.future(&change, false).unwrap();
    assert_eq!(
        unpruned.dump_simple(false),
        ["outer", "  inner", "new empty", "empty"]
    );
    let (pruned, report) = future_with_report(&source, &change, true).unwrap();
    assert_eq!(pruned.dump_simple(false), ["new empty", "empty"]);
    assert!(report.unresolved_negations.is_empty());
    assert!(report.idempotency_replacements.is_empty());
}

#[test]
fn future_retains_existing_negations_without_reporting_them_again() {
    let source = generic("no absent\n  context\nno shutdown");
    let change = generic("no absent\n  addition\nshutdown");
    let (future, report) = future_with_report(&source, &change, false).unwrap();
    // As in upstream compute_future, a positive command cancels an existing
    // negative counterpart without adding the positive line.
    assert_eq!(
        future.dump_simple(false),
        ["no absent", "  addition", "  context"]
    );
    assert!(report.unresolved_negations.is_empty());
}

#[test]
fn invalid_rules_fail_remediation_and_future_before_populating_output() {
    let source = generic("hostname old");
    let mut invalid = generic("hostname new");
    invalid.driver.rules = serde_json::from_value(json!({
        "negation_sub": [{"match_rules": [], "search": "[", "replace": ""}]
    }))
    .unwrap();
    for (left, right) in [(&source, &invalid), (&invalid, &source)] {
        let mut delta = generic("preserved");
        let error = config_to_get_to_into(left, right, &mut delta).unwrap_err();
        assert!(error.to_string().contains("negation_sub:"), "{error}");
        assert_eq!(delta.dump_simple(false), ["preserved"]);
        let future_error = future_with_report(left, right, false).unwrap_err();
        assert!(
            future_error.to_string().contains("negation_sub:"),
            "{future_error}"
        );
    }
}
