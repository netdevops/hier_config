//! Regression tests for the PR #302 review findings fixed in the core crate.

use hier_config_core::models::{ReferenceLocation, SectionalExitingRule, UnusedObjectRule};
use hier_config_core::parser::splitlines;
use hier_config_core::tree::MAX_TREE_DEPTH;
use hier_config_core::{
    Driver, MatchRule, Platform, Tree, TreeError, from_xml, load_fast, parse_tree,
};

// MF-2 -----------------------------------------------------------------

#[test]
fn mf2_both_loaders_agree_on_non_space_indentation() {
    for raw in [
        "interface eth0\n\tshutdown",
        "interface eth0\n\u{a0}shutdown",
    ] {
        let slow = parse_tree(Driver::default(), raw).unwrap();
        let slow_dump = slow.dump_simple(false);

        let mut fast = Tree::new(Driver::default());
        let lines: Vec<&str> = splitlines(raw).collect();
        load_fast(&mut fast, &lines, false).unwrap();

        assert_eq!(slow_dump, fast.dump_simple(false), "{raw:?}");
        assert_eq!(
            slow.arena[slow.root].children.len(),
            1,
            "indented line must nest, not land at top level: {raw:?}"
        );
    }
}

#[test]
fn mf2_splitlines_matches_python_boundaries() {
    assert_eq!(
        splitlines("a\rb\u{2028}c\u{b}d\u{85}e\r\nf\ng").collect::<Vec<_>>(),
        ["a", "b", "c", "d", "e", "f", "g"]
    );
    assert_eq!(splitlines("").count(), 0);
    assert_eq!(splitlines("a\n").collect::<Vec<_>>(), ["a"]);
}

// MF-3 -----------------------------------------------------------------

#[test]
fn mf3_python_end_of_string_anchor_is_translated() {
    let tree = parse_tree(Driver::default(), "foo a\nfoo a b").unwrap();
    let matched = tree.get_children(tree.root, &MatchRule::re_search(r"^foo \S+\Z"));
    let texts: Vec<&str> = matched
        .iter()
        .map(|id| tree.arena[*id].text.as_ref())
        .collect();
    assert_eq!(texts, ["foo a"]);
}

#[test]
fn mf3_escaped_backslash_z_is_left_alone() {
    let tree = parse_tree(Driver::default(), r"foo\Z").unwrap();
    assert_eq!(
        tree.get_children(tree.root, &MatchRule::re_search(r"foo\\Z"))
            .len(),
        1
    );
}

// SF-5 -----------------------------------------------------------------
// Covered by `remediation_coverage_regressions.rs`:
//   junos_negation_fallback_propagates_the_swap_error
//   junos_unflattened_command_negation_errors_instead_of_emitting_itself

// SF-7 -----------------------------------------------------------------

#[test]
fn sf7_add_child_rejects_excessive_depth() {
    let mut tree = Tree::new(Driver::default());
    let mut node = tree.add_child(tree.root, "level", false, false).unwrap();
    for _ in 1..MAX_TREE_DEPTH {
        node = tree.add_child(node, "level", false, false).unwrap();
    }
    assert!(matches!(
        tree.add_child(node, "level", false, false),
        Err(TreeError::MaxDepthExceeded(_))
    ));
}

#[test]
fn sf7_deeply_nested_xml_errors_instead_of_crashing() {
    let depth = MAX_TREE_DEPTH + 10;
    let mut xml = String::new();
    for _ in 0..depth {
        xml.push_str("<a>");
    }
    for _ in 0..depth {
        xml.push_str("</a>");
    }
    assert!(from_xml(Driver::default(), &xml, None).is_err());
}

// CF-2 -----------------------------------------------------------------

#[test]
fn cf2_empty_overwrite_source_is_not_negated() {
    let driver = Driver::for_platform(Platform::CiscoXr);
    let running = parse_tree(driver.clone(), "template T\n").unwrap();
    let intended = parse_tree(driver, "template T\n 10.0.0.0/8\n").unwrap();
    let delta = running.config_to_get_to(&intended).unwrap();
    let dumped = delta.dump_simple(false);
    assert!(
        !dumped.iter().any(|line| line.starts_with("no ")),
        "empty running section has nothing to drop: {dumped:?}"
    );
    assert!(dumped.iter().any(|line| line.trim() == "10.0.0.0/8"));
}

#[test]
fn cf2_non_empty_overwrite_source_is_still_negated() {
    let driver = Driver::for_platform(Platform::CiscoXr);
    let running = parse_tree(driver.clone(), "template T\n 10.0.0.0/8\n").unwrap();
    let intended = parse_tree(driver, "template T\n 10.0.0.0/8\n 11.0.0.0/8\n").unwrap();
    let dumped = running
        .config_to_get_to(&intended)
        .unwrap()
        .dump_simple(false);
    assert!(
        dumped.iter().any(|line| line.starts_with("no template")),
        "{dumped:?}"
    );
}

// CF-3 -----------------------------------------------------------------

#[test]
fn cf3_duplicate_negation_in_the_delta_is_rejected() {
    // v3 keys the duplicate check on the pre-negation text, so two running
    // children that share it must raise rather than emit the line twice.
    let driver = Driver::default();
    let mut running = Tree::new(driver.clone());
    running
        .add_child(running.root, "vlan 20", false, false)
        .unwrap();
    running
        .add_child(running.root, "no vlan 20", false, false)
        .unwrap();
    let intended = Tree::new(driver);
    assert!(matches!(
        running.config_to_get_to(&intended),
        Err(TreeError::DuplicateChild(_))
    ));
}

// CF-4 -----------------------------------------------------------------

#[test]
fn cf4_reference_re_unescapes_doubled_braces() {
    let mut driver = Driver::default();
    driver.rules.unused_objects = vec![UnusedObjectRule {
        match_rules: vec![MatchRule::startswith("object ")],
        name_re: r"^object (?P<name>\S+)$".into(),
        reference_locations: vec![ReferenceLocation {
            match_rules: vec![MatchRule::startswith("policy ")],
            reference_re: r"^use \{{{name}\}}$".into(),
        }],
    }];
    let tree = parse_tree(driver, "object A\nobject B\npolicy P\n  use {A}\n").unwrap();
    let unused: Vec<&str> = tree
        .unused_objects()
        .iter()
        .map(|id| tree.arena[*id].text.as_ref())
        .collect();
    assert_eq!(unused, ["object B"]);
}

// CF-6 -----------------------------------------------------------------

#[test]
fn cf6_reversed_port_range_is_deleted() {
    let tree = parse_tree(
        Driver::for_platform(Platform::HpProcurve),
        "vlan 20\n   untagged 5-1\n",
    )
    .unwrap();
    let dumped = tree.dump_simple(false);
    assert!(
        !dumped.iter().any(|line| line.contains("5-1")),
        "reversed range must be dropped: {dumped:?}"
    );
}

#[test]
fn cf6_only_the_first_untagged_child_is_expanded() {
    // v3 uses `get_child(startswith="untagged ")`, which consumes only the
    // first match; iterating every match reordered the interfaces.
    let tree = parse_tree(
        Driver::for_platform(Platform::HpProcurve),
        "vlan 20\n   untagged 5\n   untagged 9\n",
    )
    .unwrap();
    let dumped = tree.dump_simple(false);
    assert!(
        dumped.iter().any(|line| line.trim() == "interface 5"),
        "{dumped:?}"
    );
    assert!(
        dumped.iter().any(|line| line.trim() == "untagged 9"),
        "the second untagged line is left in place: {dumped:?}"
    );
    assert!(
        !dumped.iter().any(|line| line.trim() == "interface 9"),
        "{dumped:?}"
    );
}

// CF-11 ----------------------------------------------------------------

#[test]
fn cf11_text_keyed_child_mapping_still_resolves() {
    let mut tree = Tree::new(Driver::default());
    for text in ["vlan 10", "vlan 20", "vlan 30"] {
        tree.add_child(tree.root, text, false, false).unwrap();
    }
    assert!(tree.arena[tree.root].children.contains("vlan 20"));
    assert!(tree.arena[tree.root].children.get("vlan 30").is_some());
    assert!(tree.arena[tree.root].children.get("vlan 40").is_none());
}

// N-1 ------------------------------------------------------------------

#[test]
fn n1_xr_banner_comment_keeps_the_second_bang() {
    let tree = parse_tree(
        Driver::for_platform(Platform::CiscoXr),
        "!! IOS XR Configuration 7.x\nhostname r1\n",
    )
    .unwrap();
    let hostname = tree.arena[tree.root].children.get("hostname r1").unwrap();
    assert!(
        tree.arena[hostname]
            .comments()
            .iter()
            .any(|c| c == "! IOS XR Configuration 7.x"),
        "{:?}",
        tree.arena[hostname].comments()
    );
}

// N-2 -------------------------------------------------------------------

fn sectional_exit_for(platform: Platform, exit_text: &str) -> Option<String> {
    let mut driver = Driver::for_platform(platform);
    // Insert first so the platform's own built-in rules cannot shadow ours.
    driver.rules.sectional_exiting.insert(
        0,
        SectionalExitingRule {
            match_rules: vec![MatchRule::equals("section")],
            exit_text: exit_text.into(),
            exit_text_parent_level: false,
        },
    );
    driver.sectional_exit(true, |_| true)
}

#[test]
fn n2_explicit_exit_text_maps_to_huawei_platform_default() {
    assert_eq!(
        sectional_exit_for(Platform::HuaweiVrp, "exit"),
        Some("quit".to_string())
    );
}

#[test]
fn n2_non_default_exit_text_is_returned_verbatim() {
    assert_eq!(
        sectional_exit_for(Platform::HuaweiVrp, "return"),
        Some("return".to_string())
    );
}

#[test]
fn n2_empty_exit_text_still_suppresses_the_token() {
    assert_eq!(sectional_exit_for(Platform::HuaweiVrp, ""), None);
}

#[test]
fn n2_other_platforms_keep_the_generic_exit_token() {
    assert_eq!(
        sectional_exit_for(Platform::CiscoIos, "exit"),
        Some("exit".to_string())
    );
}
