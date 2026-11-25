use hier_config_core::arena::{Arena, NodeId};
use hier_config_core::models::{MatchRule, ParentAllowsDuplicateChildRule, UnusedObjectRule};
use hier_config_core::{Tree, TreeError};
use std::collections::BTreeSet;

const fn missing() -> NodeId {
    NodeId {
        index: 100,
        generation: 1,
    }
}

#[test]
fn arena_clear_never_revives_previous_handles() {
    let mut arena = Arena::new();
    let first = arena.insert("first");
    let second = arena.insert("second");
    arena.remove(first);
    let recycled = arena.insert("recycled");
    arena.clear();
    arena.clear();
    assert!(arena.is_empty());
    let new_ids = [arena.insert("new one"), arena.insert("new two")];
    for stale in [first, second, recycled] {
        assert!(!arena.contains(stale), "clear revived {stale:?}");
        assert_eq!(arena.get(stale), None);
        assert_eq!(arena.get_mut(stale), None);
        assert_eq!(arena.remove(stale), None);
    }
    assert_eq!(arena.len(), 2);
    assert_eq!(arena[new_ids[0]], "new one");
    assert_eq!(arena[new_ids[1]], "new two");
}

#[test]
fn root_count_excludes_unattached_and_replaced_nodes() {
    // Python HConfigBase.__len__ counts all_children(), not allocated objects.
    let mut tree = Tree::default();
    tree.add_children_deep(tree.root, &["section", "old"])
        .unwrap();
    let replacement = tree.create_child_unattached(tree.root, "replacement");
    assert_eq!(tree.node_count(tree.root), tree.len());
    tree.set_child_at(tree.root, 0, replacement).unwrap();
    assert_eq!(tree.dump_simple(false), ["replacement"]);
    assert_eq!(tree.node_count(tree.root), 1);
}

#[test]
fn assigning_an_existing_sibling_preserves_python_list_assignment() {
    // Python HConfigChildren.__setitem__ replaces a slot without removing siblings.
    for (index, replacement_index, expected) in
        [(2, 0, vec!["a", "b", "a"]), (0, 2, vec!["c", "b", "c"])]
    {
        let mut tree = Tree::default();
        let ids = tree.add_children(tree.root, &["a", "b", "c"]).unwrap();
        assert_eq!(
            tree.set_child_at(tree.root, index, ids[replacement_index]),
            Ok(Some(ids[index]))
        );
        assert_eq!(tree.dump_simple(false), expected);
        assert_eq!(tree.arena[tree.root].children.len(), 3);
        assert_eq!(
            tree.get_child_by_text(tree.root, &tree.arena[ids[replacement_index]].text),
            Some(ids[replacement_index])
        );
    }
}

#[test]
fn failed_assignment_is_atomic_for_invalid_index_and_handle() {
    let mut tree = Tree::default();
    let ids = tree.add_children(tree.root, &["a", "b"]).unwrap();
    let before = tree.clone();
    assert_eq!(
        tree.set_child_at(tree.root, 99, ids[0]),
        Err(TreeError::NodeNotFound(ids[0]))
    );
    assert_eq!(tree, before);
    assert_eq!(
        tree.set_child_at(tree.root, 0, missing()),
        Err(TreeError::NodeNotFound(missing()))
    );
    assert_eq!(tree, before);
}

#[test]
fn moving_missing_nodes_returns_errors_without_partial_mutation() {
    let mut tree = Tree::default();
    let child = tree.add_child(tree.root, "child", true, false).unwrap();
    let before = tree.clone();
    assert_eq!(
        tree.move_child(child, missing()),
        Err(TreeError::NodeNotFound(missing()))
    );
    assert_eq!(tree, before);
    assert_eq!(
        tree.move_child(missing(), tree.root),
        Err(TreeError::NodeNotFound(missing()))
    );
    assert_eq!(tree, before);
}

#[test]
fn shallow_copy_missing_source_returns_documented_error() {
    let mut tree = Tree::default();
    let source = Tree::default();
    assert_eq!(
        tree.add_shallow_copy_of(tree.root, &source, missing(), false),
        Err(TreeError::NodeNotFound(missing()))
    );
    assert_eq!(
        tree.add_shallow_copy_within(tree.root, missing(), false),
        Err(TreeError::NodeNotFound(missing()))
    );
    assert!(tree.is_empty());
}

#[test]
fn filtering_preserves_custom_driver_and_duplicate_policy() {
    // Python root.with_tags constructs HConfig(self.driver), not a stock driver.
    let mut tree = Tree::default();
    tree.driver.rules.indentation = 4;
    tree.driver.negation_prefix = "undo ".into();
    tree.driver
        .rules
        .parent_allows_duplicate_child
        .push(ParentAllowsDuplicateChildRule {
            match_rules: vec![],
        });
    for _ in 0..2 {
        let section = tree.add_child(tree.root, "section", true, false).unwrap();
        tree.add_child(section, "leaf", true, false).unwrap();
        tree.tags_add(section, &["keep"]);
    }
    let filtered = tree.with_tags(&BTreeSet::from(["keep".into()])).unwrap();
    assert_eq!(filtered.driver, tree.driver);
    assert_eq!(
        filtered.dump_simple(false),
        ["section", "    leaf", "section", "    leaf"]
    );
}

#[test]
fn unused_object_names_are_deduplicated_per_rule_not_across_namespaces() {
    // Python root.unused_objects creates seen_names inside the rule loop.
    let mut tree = Tree::default();
    let acl = tree
        .add_child(tree.root, "acl shared", true, false)
        .unwrap();
    let policy = tree
        .add_child(tree.root, "policy shared", true, false)
        .unwrap();
    tree.driver.rules.unused_objects = ["acl", "policy"]
        .map(|kind| UnusedObjectRule {
            match_rules: vec![MatchRule::startswith(kind)],
            name_re: format!("^{kind} (?P<name>.+)$"),
            reference_locations: vec![],
        })
        .into();
    assert_eq!(tree.unused_objects(), [acl, policy]);
}

#[test]
fn unused_object_rule_without_named_capture_reports_error_instead_of_hiding_object() {
    // Python root.unused_objects calls match.group("name"), which raises when
    // a matching expression has no such group.
    let mut tree = Tree::default();
    tree.add_child(tree.root, "object one", true, false)
        .unwrap();
    tree.driver.rules.unused_objects.push(UnusedObjectRule {
        match_rules: vec![MatchRule::startswith("object ")],
        name_re: "^object (.+)$".into(),
        reference_locations: vec![],
    });
    assert!(matches!(
        tree.try_unused_objects(),
        Err(TreeError::InvalidRegex(_))
    ));
}
