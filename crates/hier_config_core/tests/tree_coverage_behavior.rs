use hier_config_core::arena::NodeId;
use hier_config_core::models::{
    Dump, DumpLine, Instance, MatchRule, OrderingRule, ParentAllowsDuplicateChildRule,
    ReferenceLocation, SectionalExitingRule, SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule, TagRule, TextStyle, UnusedObjectRule,
};
use hier_config_core::{Platform, Tree, TreeError};
use std::collections::BTreeSet;

fn tags(values: &[&str]) -> BTreeSet<String> {
    values.iter().map(|value| (*value).into()).collect()
}

fn add(tree: &mut Tree, parent: NodeId, text: &str) -> NodeId {
    tree.add_child(parent, text, true, false).unwrap()
}

const fn missing() -> NodeId {
    NodeId {
        index: 999,
        generation: 1,
    }
}

#[test]
fn add_validation_duplicate_modes_and_partial_batch_failure() {
    let mut tree = Tree::default();
    let root = tree.root;
    assert!(tree.is_empty());
    assert_eq!(
        tree.add_child(root, " \n ", true, false),
        Err(TreeError::EmptyText)
    );
    assert_eq!(
        tree.add_child(missing(), "a", true, false),
        Err(TreeError::InvalidParent(missing()))
    );
    assert_eq!(tree.add_children_deep(root, &[]), Ok(root));
    let parent = add(&mut tree, root, "  section  ");
    let first = add(&mut tree, parent, " first ");
    assert_eq!(tree.arena[parent].real_indent_level, 0);
    assert_eq!(tree.arena[first].real_indent_level, 1);
    assert_eq!(tree.add_child(parent, "first", true, true), Ok(first));
    assert_eq!(
        tree.add_child(parent, "first", true, false),
        Err(TreeError::DuplicateChild(vec![
            "section".into(),
            "first".into()
        ]))
    );
    assert_eq!(
        tree.add_children_deep(root, &["section", "first"]),
        Ok(first)
    );
    assert!(
        tree.add_children(parent, &["second", "", "not reached"])
            .is_err()
    );
    assert_eq!(tree.arena[parent].children.len(), 2);
    assert_eq!(tree.get_child_by_text(parent, "not reached"), None);
}

#[test]
fn unchecked_and_driver_allowed_duplicates_keep_first_text_mapping() {
    let mut tree = Tree::default();
    let root = tree.root;
    let parent = add(&mut tree, root, "section");
    let first = add(&mut tree, parent, "first");
    let unchecked = tree.add_child(parent, "first", false, false).unwrap();
    assert_ne!(unchecked, first);
    assert_eq!(tree.get_child_by_text(parent, "first"), Some(first));
    tree.driver
        .rules
        .parent_allows_duplicate_child
        .push(ParentAllowsDuplicateChildRule {
            match_rules: vec![MatchRule::equals("section")],
        });
    assert!(tree.is_duplicate_child_allowed(parent));
    let allowed = tree.add_child(parent, "first", true, true).unwrap();
    assert_ne!(allowed, first);
    tree.delete_child(first);
    assert_eq!(tree.get_child_by_text(parent, "first"), Some(unchecked));
    tree.delete_child(unchecked);
    assert_eq!(tree.get_child_by_text(parent, "first"), Some(allowed));
}

#[test]
fn missing_node_accessors_and_traversal_are_empty() {
    let mut tree = Tree::default();
    let root = tree.root;
    assert_eq!(tree.get(missing()), None);
    assert_eq!(tree.get_mut(missing()), None);
    for id in [root, missing()] {
        assert_eq!(tree.depth(id), 0);
        assert!(tree.lineage(id).is_empty());
        assert!(tree.path(id).is_empty());
        assert_eq!(tree.indentation(id), "");
    }
    assert!(tree.all_children(missing()).is_empty());
    assert!(tree.all_children_sorted(missing()).is_empty());
    assert!(tree.sorted_children(missing()).is_empty());
    assert_eq!(tree.node_count(missing()), 0);
    assert_eq!(tree.descendants(missing()).next(), None);
    assert_eq!(tree.descendants_sorted(missing()).next(), None);
}

#[test]
fn accessor_lineage_and_traversal_size_hint_follow_actual_nodes() {
    let mut tree = Tree::default();
    let root = tree.root;
    let branch = add(&mut tree, root, "branch");
    let leaf = add(&mut tree, branch, "leaf");
    assert_eq!(tree.get(leaf).unwrap().text.as_ref(), "leaf");
    tree.get_mut(leaf).unwrap().new_in_config = true;
    assert!(tree.get(leaf).unwrap().new_in_config);
    assert_eq!(tree.descendants(branch).size_hint(), (0, Some(3)));
    assert_eq!(tree.descendants_sorted(branch).size_hint(), (0, Some(3)));
    assert_eq!(tree.all_children(branch), [leaf]);
    assert_eq!(tree.all_children_sorted(branch), [leaf]);
    assert!(tree.is_lineage_match(
        leaf,
        &[MatchRule::equals("branch"), MatchRule::equals("leaf")]
    ));
    assert!(!tree.is_lineage_match(leaf, &[MatchRule::equals("leaf")]));
    assert!(!tree.is_lineage_match(
        leaf,
        &[MatchRule::equals("other"), MatchRule::equals("leaf")]
    ));
}

#[test]
fn deletion_handles_detached_or_missing_nodes_without_deleting_root() {
    let mut tree = Tree::default();
    let root = tree.root;
    tree.add_children_deep(root, &["branch", "leaf"]).unwrap();
    let detached = tree.create_child_unattached(missing(), "orphan");
    assert_eq!(tree.depth(detached), 1);
    assert_eq!(tree.lineage(detached), [missing(), detached]);
    assert_eq!(tree.path(detached), ["orphan"]);
    tree.delete_child(detached);
    assert!(tree.get(detached).is_none());
    tree.delete_child(root);
    tree.delete_child(missing());
    tree.rebuild_children_mapping(missing());
    tree.delete_sectional_exit(missing());
    assert_eq!(tree.len(), 2);
}

#[test]
fn moves_and_text_changes_update_indexes_without_copying_subtrees() {
    let mut tree = Tree::default();
    let root = tree.root;
    let source = add(&mut tree, root, "source");
    let destination = add(&mut tree, root, "destination");
    let branch = add(&mut tree, source, "branch");
    let leaf = add(&mut tree, branch, "leaf");
    tree.tags_add(leaf, &["kept"]);
    tree.move_child(branch, destination).unwrap();
    assert!(tree.arena[source].children.is_empty());
    assert_eq!(tree.get_child_by_text(destination, "branch"), Some(branch));
    assert_eq!(tree.path(leaf), ["destination", "branch", "leaf"]);
    assert_eq!(tree.tags(leaf), tags(&["kept"]));
    assert_eq!(
        tree.move_child(root, destination),
        Err(TreeError::NodeNotFound(root))
    );
    tree.set_text(branch, " renamed ");
    assert_eq!(tree.get_child_by_text(destination, "branch"), None);
    assert_eq!(tree.get_child_by_text(destination, "renamed"), Some(branch));
    tree.arena[branch].text = "manual".into();
    tree.rebuild_children_mapping(destination);
    assert_eq!(tree.get_child_by_text(destination, "manual"), Some(branch));
    tree.set_text(root, "root label");
    assert_eq!(tree.arena[root].text.as_ref(), "root label");
    tree.delete_child(branch);
    assert_eq!(tree.get(branch), None);
    assert_eq!(tree.get(leaf), None);
    assert!(tree.arena[destination].children.is_empty());
    let unattached = tree.create_child_unattached(root, "no parent");
    tree.arena[unattached].parent = None;
    assert_eq!(
        tree.move_child(unattached, destination),
        Err(TreeError::NodeNotFound(unattached))
    );
    tree.delete_child(unattached);
    assert_eq!(tree.get(unattached), None);
}

#[test]
fn replacement_returns_old_handle_and_rebuilds_text_index() {
    let mut tree = Tree::default();
    let root = tree.root;
    let old = add(&mut tree, root, "old");
    let replacement = tree.create_child_unattached(root, "new");
    assert_eq!(tree.set_child_at(root, 0, replacement), Ok(Some(old)));
    assert_eq!(tree.get_child_by_text(root, "old"), None);
    assert_eq!(tree.get_child_by_text(root, "new"), Some(replacement));
    assert_eq!(tree.arena[replacement].parent, Some(root));
    assert_eq!(
        tree.set_child_at(root, 0, replacement),
        Ok(Some(replacement))
    );
    assert_eq!(
        tree.set_child_at(missing(), 0, replacement),
        Err(TreeError::InvalidParent(missing()))
    );
}

#[test]
fn copies_preserve_only_documented_metadata_and_merge_instances() {
    let mut src = Tree::default();
    let root = src.root;
    let parent = add(&mut src, root, "parent");
    let leaf = add(&mut src, parent, "leaf");
    src.arena[parent]
        .comments_mut()
        .insert("parent comment".into());
    src.arena[leaf].comments_mut().insert("leaf comment".into());
    src.arena[leaf].order_weight = -7;
    src.arena[leaf].new_in_config = true;
    src.arena[leaf]
        .facts_mut()
        .insert("fact".into(), "value".into());
    src.tags_add(leaf, &["leaf tag"]);
    let mut dst = Tree::default();
    let shallow = dst
        .add_shallow_copy_of(dst.root, &src, parent, false)
        .unwrap();
    assert!(dst.arena[shallow].is_leaf());
    assert!(dst.tags(shallow).is_empty());
    assert_eq!(dst.arena[shallow].comments(), &tags(&["parent comment"]));
    let copy = dst.add_deep_copy_of(dst.root, &src, parent, true).unwrap();
    assert_eq!(copy, shallow);
    let copied_leaf = dst.get_child_by_text(copy, "leaf").unwrap();
    assert_eq!(dst.tags(copy), tags(&["leaf tag"]));
    assert_eq!(dst.arena[copied_leaf].order_weight, -7);
    assert!(!dst.arena[copied_leaf].new_in_config);
    assert!(dst.arena[copied_leaf].facts().is_empty());
    assert_eq!(
        dst.arena[copied_leaf].instances(),
        [Instance {
            id: u64::from(leaf.index),
            comments: tags(&["leaf comment"]),
            tags: tags(&["leaf tag"])
        }]
    );
    dst.merge(&src).unwrap();
    assert_eq!(dst.arena[copied_leaf].instances().len(), 2);
    assert_eq!(dst.arena[copied_leaf].comments(), &tags(&["leaf comment"]));
    assert!(dst.add_deep_copy_of(dst.root, &src, parent, false).is_err());
}

#[test]
fn shallow_copy_within_preserves_metadata_and_merges_into_existing_copy() {
    let mut src = Tree::default();
    let root = src.root;
    let parent = add(&mut src, root, "parent");
    let leaf = add(&mut src, parent, "leaf");
    src.arena[leaf].order_weight = -7;
    src.tags_add(leaf, &["leaf tag"]);
    let destination = add(&mut src, root, "destination");
    let within = src
        .add_shallow_copy_within(destination, leaf, false)
        .unwrap();
    assert_eq!(src.arena[within].order_weight, -7);
    assert_eq!(src.tags(within), tags(&["leaf tag"]));
    assert_eq!(
        src.add_shallow_copy_within(destination, leaf, true),
        Ok(within)
    );
    assert_eq!(src.arena[within].instances().len(), 1);
    let copied_branch = src
        .add_shallow_copy_within(destination, parent, true)
        .unwrap();
    assert!(src.tags(copied_branch).is_empty());
    assert_eq!(
        src.arena[copied_branch].instances()[0].tags,
        tags(&["leaf tag"])
    );
}

#[test]
fn ancestor_copy_within_and_between_trees_preserves_lineage() {
    let mut src = Tree::default();
    let leaf = src.add_children_deep(src.root, &["a", "b", "c"]).unwrap();
    src.tags_add(leaf, &["tag"]);
    let mut dst = Tree::default();
    let copied = dst.add_ancestor_copy_of(dst.root, &src, leaf).unwrap();
    assert_eq!(dst.path(copied), ["a", "b", "c"]);
    assert_eq!(dst.tags(copied), tags(&["tag"]));
    assert_eq!(
        dst.add_ancestor_copy_of(dst.root, &src, src.root),
        Ok(dst.root)
    );
    let root = src.root;
    let destination = add(&mut src, root, "destination");
    let within = src.add_ancestor_copy_within(destination, leaf).unwrap();
    assert_eq!(src.path(within), ["destination", "a", "b", "c"]);
    assert_eq!(
        src.add_ancestor_copy_within(destination, root),
        Ok(destination)
    );
    // Original Python root.add_ancestor_copy_of delegates to non-merged
    // shallow copies: existing ancestors raise instead of being reused.
    assert!(src.add_ancestor_copy_within(destination, leaf).is_err());
}

#[test]
fn tags_propagate_to_leaves_and_empty_sets_release_extras() {
    let mut tree = Tree::default();
    let root = tree.root;
    tree.set_tags(root, tags(&["ignored"]));
    tree.tags_add(root, &["ignored"]);
    tree.tags_remove(root, &["ignored"]);
    assert!(tree.tags(root).is_empty());
    let branch = add(&mut tree, root, "branch");
    let leaves = tree.add_children(branch, &["one", "two"]).unwrap();
    assert!(tree.tags(missing()).is_empty());
    tree.set_tags(leaves[0], BTreeSet::new());
    assert!(tree.arena[leaves[0]].extras().is_none());
    tree.set_tags(branch, tags(&["a", "b"]));
    assert_eq!(tree.tags(root), tags(&["a", "b"]));
    assert!(tree.arena[branch].tags().is_empty());
    tree.tags_add(branch, &["b", "c"]);
    tree.tags_remove(root, &["b", "not present"]);
    for &leaf in &leaves {
        assert_eq!(tree.tags(leaf), tags(&["a", "c"]));
    }
    tree.set_tags(branch, BTreeSet::new());
    for &leaf in &leaves {
        assert!(tree.arena[leaf].extras().is_none());
    }
    tree.arena[leaves[0]].comments_mut().insert("keep".into());
    tree.set_tags(leaves[0], tags(&["remove"]));
    tree.set_tags(leaves[0], BTreeSet::new());
    assert_eq!(tree.arena[leaves[0]].comments(), &tags(&["keep"]));
}

#[test]
fn tag_filtering_uses_leaf_inclusion_and_prunes_empty_branches() {
    let mut tree = Tree::default();
    let root = tree.root;
    let branch = add(&mut tree, root, "branch");
    let leaves = tree.add_children(branch, &["one", "two", "three"]).unwrap();
    let hidden = add(&mut tree, root, "hidden");
    add(&mut tree, hidden, "hidden leaf");
    tree.tags_add(leaves[0], &["a", "b"]);
    tree.tags_add(leaves[1], &["a", "deny"]);
    tree.tags_add(leaves[2], &["b"]);
    assert!(!tree.line_inclusion_test(leaves[0], &[], &[]));
    assert!(tree.line_inclusion_test(leaves[0], &["a"], &[]));
    assert!(!tree.line_inclusion_test(leaves[0], &["x"], &["deny"]));
    assert!(tree.line_inclusion_test(leaves[0], &[], &["deny"]));
    assert!(!tree.line_inclusion_test(leaves[1], &["a"], &["deny"]));
    assert_eq!(
        tree.all_children_sorted_by_tags(root, &["a"], &["deny"]),
        [branch, leaves[0]]
    );
    assert_eq!(
        tree.all_children_sorted_by_tags(branch, &["b"], &[]),
        [branch, leaves[0], leaves[2]]
    );
    assert!(
        tree.all_children_sorted_by_tags(root, &["missing"], &[])
            .is_empty()
    );
    assert_eq!(
        tree.rendered_text_by_tags(&["a"], &["deny"]),
        "branch\n  one"
    );
    assert_eq!(
        tree.rendered_text_by_tags(&[], &[]),
        "branch\n  one\n  two\n  three\nhidden\n  hidden leaf"
    );
    assert_eq!(
        tree.with_tags(&tags(&["a", "b"]))
            .unwrap()
            .dump_simple(false),
        ["branch", "  one"]
    );
    assert!(tree.with_tags(&tags(&["missing"])).unwrap().is_empty());
    assert_eq!(
        tree.with_tags(&BTreeSet::new()).unwrap().dump_simple(false),
        tree.dump_simple(false)
    );
}

#[test]
fn tag_rules_and_search_respect_each_lineage_level() {
    let mut tree = Tree::default();
    let root = tree.root;
    let a = tree
        .add_children_deep(root, &["section a", "leaf"])
        .unwrap();
    let b = tree
        .add_children_deep(root, &["section b", "leaf"])
        .unwrap();
    let sections = tree.get_children(root, &MatchRule::startswith("section"));
    assert_eq!(sections.len(), 2);
    assert_eq!(
        tree.get_child(root, &MatchRule::equals("section a")),
        Some(sections[0])
    );
    assert_eq!(tree.get_child(root, &MatchRule::equals("absent")), None);
    assert_eq!(
        tree.get_children_deep(
            root,
            &[MatchRule::startswith("section"), MatchRule::equals("leaf")]
        ),
        [a, b]
    );
    assert!(tree.get_children_deep(root, &[]).is_empty());
    tree.apply_tag_rules(&[
        TagRule {
            match_rules: vec![MatchRule::equals("section a")],
            apply_tags: tags(&["a"]),
        },
        TagRule {
            match_rules: vec![MatchRule::startswith("section"), MatchRule::equals("leaf")],
            apply_tags: tags(&["all"]),
        },
    ]);
    assert_eq!(tree.tags(a), tags(&["a", "all"]));
    assert_eq!(tree.tags(b), tags(&["all"]));
}

#[test]
fn ordering_is_stable_at_each_depth_and_last_matching_rule_wins() {
    let mut tree = Tree::default();
    let root = tree.root;
    let ids = tree.add_children(root, &["late", "first", "tie"]).unwrap();
    let leaves = tree.add_children(ids[0], &["z", "a", "b"]).unwrap();
    tree.driver.rules.ordering = vec![
        OrderingRule {
            match_rules: vec![MatchRule::equals("first")],
            weight: 3,
        },
        OrderingRule {
            match_rules: vec![MatchRule::equals("first")],
            weight: -1,
        },
        OrderingRule {
            match_rules: vec![MatchRule::equals("late"), MatchRule::equals("z")],
            weight: 9,
        },
    ];
    tree.set_order_weight();
    assert_eq!(tree.arena[ids[1]].order_weight, -1);
    assert_eq!(tree.sorted_children(root), [ids[1], ids[0], ids[2]]);
    assert_eq!(
        tree.all_children_sorted(root),
        [ids[1], ids[0], leaves[1], leaves[2], leaves[0], ids[2]]
    );
    assert_eq!(
        tree.all_children(root),
        [ids[0], leaves[0], leaves[1], leaves[2], ids[1], ids[2]]
    );
    let mut iterator = tree.descendants_sorted(root);
    assert_eq!(iterator.by_ref().count(), 6);
    assert_eq!(iterator.next(), None);
    assert_eq!(iterator.next(), None);
    let mut insertion_iterator = tree.descendants(root);
    assert_eq!(insertion_iterator.by_ref().count(), 6);
    assert_eq!(insertion_iterator.next(), None);
    assert_eq!(insertion_iterator.next(), None);
}

#[test]
fn formatting_comments_and_merged_instances_filters_by_tag() {
    let mut tree = Tree::default();
    let leaf = tree
        .add_children_deep(tree.root, &["parent", "leaf"])
        .unwrap();
    tree.arena[leaf].comments_mut().extend(tags(&["z", "a"]));
    tree.arena[leaf].instances_mut().extend([
        Instance {
            id: 1,
            comments: tags(&["one"]),
            tags: tags(&["a"]),
        },
        Instance {
            id: 2,
            comments: tags(&["two", "one"]),
            tags: tags(&["b"]),
        },
    ]);
    assert_eq!(
        tree.cisco_style_text(leaf, TextStyle::WithoutComments, None),
        "  leaf"
    );
    assert_eq!(
        tree.cisco_style_text(leaf, TextStyle::WithComments, None),
        "  leaf !a, z"
    );
    assert_eq!(
        tree.cisco_style_text(leaf, TextStyle::Merged, None),
        "  leaf !2 instances, one, two"
    );
    assert_eq!(
        tree.cisco_style_text(leaf, TextStyle::Merged, Some("a")),
        "  leaf !1 instance, one"
    );
    assert_eq!(
        tree.cisco_style_text(leaf, TextStyle::Merged, Some("missing")),
        "  leaf !0 instances"
    );
    assert_eq!(
        tree.cisco_style_text(missing(), TextStyle::Merged, None),
        ""
    );
    let parent = tree.arena[leaf].parent.unwrap();
    assert_eq!(
        tree.cisco_style_text(parent, TextStyle::WithComments, None),
        "parent"
    );
}

#[test]
fn sectional_rules_render_both_exit_indents_and_delete_only_trailing_exit() {
    for parent_level in [false, true] {
        let mut tree = Tree::default();
        let root = tree.root;
        let section = add(&mut tree, root, "section");
        let other = add(&mut tree, root, "other");
        let exit = add(&mut tree, section, "exit");
        let leaf = add(&mut tree, section, "leaf");
        tree.driver
            .rules
            .sectional_exiting
            .push(SectionalExitingRule {
                match_rules: vec![MatchRule::equals("section")],
                exit_text: "exit".into(),
                exit_text_parent_level: parent_level,
            });
        tree.driver
            .rules
            .sectional_overwrite
            .push(SectionalOverwriteRule {
                match_rules: vec![MatchRule::equals("section")],
            });
        tree.driver
            .rules
            .sectional_overwrite_no_negate
            .push(SectionalOverwriteNoNegateRule {
                match_rules: vec![MatchRule::equals("other")],
            });
        assert!(tree.use_sectional_overwrite(section));
        assert!(!tree.use_sectional_overwrite(other));
        assert!(tree.use_sectional_overwrite_without_negation(other));
        assert!(!tree.use_sectional_overwrite_without_negation(section));
        assert_eq!(tree.sectional_exit(section), Some("exit".into()));
        assert_eq!(tree.sectional_exit(other), None);
        assert_eq!(tree.sectional_exit(missing()), None);
        assert_eq!(
            (
                tree.sectional_exit_text_parent_level(missing()),
                tree.sectional_exit_text_parent_level(other)
            ),
            (false, false)
        );
        tree.delete_sectional_exit(other);
        tree.delete_sectional_exit(section);
        assert!(tree.get(exit).is_some());
        tree.delete_child(leaf);
        tree.delete_sectional_exit(section);
        assert!(tree.get(exit).is_none());
        add(&mut tree, section, "leaf");
        let expected_exit = if parent_level { "exit" } else { "  exit" };
        assert_eq!(
            tree.lines(section, true),
            ["section", "  leaf", expected_exit]
        );
        assert_eq!(tree.lines(section, false), ["section", "  leaf"]);
    }
}

#[test]
fn dump_load_preserves_metadata_skips_zero_depth_and_reports_duplicates() {
    let dump = Dump {
        lines: vec![
            DumpLine {
                depth: 0,
                text: "ignored".into(),
                tags: tags(&["ignored"]),
                comments: BTreeSet::new(),
                new_in_config: false,
            },
            DumpLine {
                depth: 1,
                text: "parent".into(),
                tags: tags(&["aggregate"]),
                comments: tags(&["parent comment"]),
                new_in_config: true,
            },
            DumpLine {
                depth: 2,
                text: "leaf".into(),
                tags: tags(&["aggregate"]),
                comments: tags(&["leaf comment"]),
                new_in_config: true,
            },
            DumpLine {
                depth: 1,
                text: "plain".into(),
                tags: BTreeSet::new(),
                comments: BTreeSet::new(),
                new_in_config: false,
            },
        ],
    };
    let mut tree = Tree::default();
    tree.load_from_dump(&dump).unwrap();
    assert_eq!(tree.dump().lines, dump.lines[1..]);
    let plain = tree.get_child_by_text(tree.root, "plain").unwrap();
    assert!(tree.arena[plain].extras().is_none());
    assert!(tree.load_from_dump(&dump).is_err());
    let mut reloaded = Tree::default();
    reloaded.load_from_dump(&tree.dump()).unwrap();
    assert!(tree.node_eq(tree.root, &reloaded, reloaded.root));
}

#[test]
fn equality_detects_text_tags_child_counts_and_keys() {
    let mut a = Tree::default();
    let root = a.root;
    let leaf = add(&mut a, root, "leaf");
    let mut b = a.clone();
    assert!(a.node_equals(root, &b, b.root));
    assert!(a.node_eq(root, &b, b.root));
    assert!(a.node_equals(missing(), &b, missing()));
    assert!(!a.node_equals(root, &b, missing()));
    assert!(!a.node_equals(missing(), &b, root));
    b.set_text(leaf, "other");
    assert!(!a.node_equals(leaf, &b, leaf));
    assert!(!a.children_eq(root, &b, root));
    assert!(!a.node_eq(leaf, &b, leaf));
    b.set_text(leaf, "leaf");
    b.tags_add(leaf, &["different"]);
    assert!(!a.node_equals(root, &b, root));
    assert!(!a.node_eq(leaf, &b, leaf));
    b.set_tags(leaf, BTreeSet::new());
    add(&mut b, root, "extra");
    assert!(!a.children_eq(root, &b, root));
    assert!(!a.node_equals(root, &b, root));
    let mut c = a.clone();
    add(&mut c, leaf, "nested");
    assert!(!a.node_equals(root, &c, root));
    assert!(!a.children_eq(root, &c, root));
}

#[test]
fn unused_objects_skip_nonmatching_names_and_duplicate_names() {
    let mut tree = Tree::default();
    let root = tree.root;
    let used = add(&mut tree, root, "object used");
    let unused = add(&mut tree, root, "object a.b");
    add(&mut tree, root, "object ignored");
    tree.add_child(root, "object a.b", false, false).unwrap();
    let section = add(&mut tree, root, "section");
    add(&mut tree, section, "use used");
    add(&mut tree, section, "use axb");
    let location = ReferenceLocation {
        match_rules: vec![MatchRule::equals("section")],
        reference_re: "^use {name}$".into(),
    };
    tree.driver.rules.unused_objects = vec![
        UnusedObjectRule {
            match_rules: vec![MatchRule::startswith("object")],
            name_re: "^object (?P<name>used|a\\.b)$".into(),
            reference_locations: vec![location.clone()],
        },
        UnusedObjectRule {
            match_rules: vec![MatchRule::equals("object ignored")],
            name_re: "^not matched (.+)$".into(),
            reference_locations: vec![],
        },
    ];
    assert_eq!(tree.unused_objects(), [unused]);
    assert_ne!(used, unused);
    assert!(tree.is_object_referenced("used", std::slice::from_ref(&location)));
    assert!(!tree.is_object_referenced("a.b", &[location]));
    assert!(!tree.is_object_referenced("used", &[]));
    tree.driver.rules.unused_objects[0].name_re = "[".into();
    assert!(matches!(
        tree.try_unused_objects(),
        Err(TreeError::InvalidRegex(_))
    ));
    assert!(matches!(
        tree.try_is_object_referenced(
            "used",
            &[ReferenceLocation {
                match_rules: vec![],
                reference_re: "[".into()
            }]
        ),
        Err(TreeError::InvalidRegex(_))
    ));
}

#[test]
fn public_constructors_and_callback_mutations_produce_real_tree_content() {
    fn callback(tree: &mut Tree) {
        tree.add_child(tree.root, "from callback", true, false)
            .unwrap();
    }
    let mut tree =
        Tree::from_str_with_callbacks(Platform::Generic, "original", [callback]).unwrap();
    tree.apply_callback(|tree| {
        tree.set_text(
            tree.get_child_by_text(tree.root, "original").unwrap(),
            "renamed",
        );
    });
    assert_eq!(tree.dump_simple(false), ["renamed", "from callback"]);
    assert!(Tree::from_json(Platform::Generic, "{", None).is_err());
    assert!(Tree::from_xml(Platform::Generic, "<broken>", None).is_err());
}

#[test]
fn tree_error_messages_identify_context() {
    for (error, expected) in [
        (TreeError::EmptyText, "text was empty".to_string()),
        (
            TreeError::DuplicateChild(vec!["a".into(), "b".into()]),
            "Found a duplicate section: [\"a\", \"b\"]".into(),
        ),
        (
            TreeError::NodeNotFound(missing()),
            format!("Node not found: {:?}", missing()),
        ),
        (
            TreeError::InvalidParent(missing()),
            format!("Invalid parent: {:?}", missing()),
        ),
        (
            TreeError::InvalidRegex("bad".into()),
            "Invalid regex rule: bad".into(),
        ),
    ] {
        assert_eq!(error.to_string(), expected);
    }
    let banner = TreeError::UnterminatedBanner("banner motd ^".into()).to_string();
    assert!(banner.starts_with("Unterminated banner:"));
    assert!(banner.contains("banner motd ^"));
    assert!(banner.ends_with("their delimiter or by a '!' line."));
}
