use hier_config_core::arena::{Arena, NodeId};
use hier_config_core::models::Instance;
use hier_config_core::tree::{Children, Node};
use std::collections::BTreeSet;
use std::sync::Arc;

#[test]
fn arena_reuses_free_slots_in_lifo_order_and_rejects_stale_generations() {
    let mut arena = Arena::with_capacity(3);
    arena.reserve(8);
    let first = arena.insert(1);
    let second = arena.insert(2);
    let third = arena.insert(3);
    assert_eq!(arena.remove(first), Some(1));
    assert_eq!(arena.remove(third), Some(3));
    assert_eq!(arena.remove(third), None);
    let fourth = arena.insert(4);
    let fifth = arena.insert(5);
    assert_eq!(fourth.index, third.index);
    assert_eq!(fifth.index, first.index);
    assert_eq!(fourth.generation, third.generation + 1);
    assert_eq!(
        arena.iter().map(|(id, n)| (id, *n)).collect::<Vec<_>>(),
        [(fifth, 5), (second, 2), (fourth, 4)]
    );
    for bad in [
        first,
        third,
        NodeId {
            index: 999,
            generation: 1,
        },
    ] {
        assert!(!arena.contains(bad));
        assert_eq!(arena.get_mut(bad), None);
        assert_eq!(arena.remove(bad), None);
    }
}

#[test]
fn arena_mutable_iteration_skips_vacancies_and_clone_survives_clear() {
    let mut arena = Arena::default();
    assert!(arena.is_empty());
    let live = arena.insert(20);
    let dead = arena.insert(30);
    let other = arena.insert(40);
    arena[live] = 20;
    *arena.get_mut(other).unwrap() = 40;
    arena.remove(dead);
    for (id, value) in arena.iter_mut() {
        assert!(id == live || id == other);
        *value += 1;
    }
    assert_eq!(
        arena.iter().map(|(_, value)| *value).collect::<Vec<_>>(),
        [21, 41]
    );
    let cloned = arena.clone();
    assert_eq!(cloned, arena);
    arena.clear();
    assert_eq!(arena.iter().count(), 0);
    assert_eq!(arena.iter_mut().count(), 0);
    assert!(arena.is_empty());
    assert_eq!(cloned.len(), 2);
}

#[test]
#[should_panic(expected = "invalid NodeId in Arena::index:")]
fn arena_index_panics_for_removed_handle() {
    let mut arena = Arena::new();
    let id = arena.insert(1);
    arena.remove(id);
    let _ = arena[id];
}

#[test]
#[should_panic(expected = "invalid NodeId in Arena::index_mut:")]
fn arena_mutable_index_panics_for_removed_handle() {
    let mut arena = Arena::new();
    let id = arena.insert(1);
    arena.remove(id);
    arena[id] = 2;
}

#[test]
fn empty_children_have_no_indexes_or_mapping() {
    let children = Children::new();
    assert!(children.is_empty());
    assert!(!children.contains("a"));
    assert_eq!(children.get("a"), None);
    assert_eq!(children.keys().count(), 0);
}

#[test]
fn children_mapping_preserves_first_duplicate_through_mutations() {
    let mut arena = Arena::new();
    let a = arena.insert(Node::new("a", None));
    let duplicate = arena.insert(Node::new("a", None));
    let b = arena.insert(Node::new("b", None));
    let mut children = Children::new();
    children.append(&arena[a].text, a, true);
    children.append(&arena[duplicate].text, duplicate, false);
    children.append(&arena[b].text, b, true);
    assert_eq!(children.len(), 3);
    assert_eq!(children.iter().collect::<Vec<_>>(), [a, duplicate, b]);
    assert_eq!(children.get("a"), Some(a));
    assert_eq!(children.get_index(1), Some(duplicate));
    assert_eq!(children.get_index(3), None);
    assert_eq!(children.index_of(duplicate), Some(1));
    let missing = NodeId {
        index: 999,
        generation: 1,
    };
    assert_eq!(children.index_of(missing), None);
    children.delete_by_id(a, &arena);
    assert_eq!(children.get("a"), Some(duplicate));
    assert_eq!(children.set_index(0, b, &arena), Some(duplicate));
    assert!(!children.contains("a"));
    assert_eq!(children.get("b"), Some(b));
    children.delete_by_text("b", &arena);
    assert!(children.is_empty());
    assert_eq!(children.keys().count(), 0);
}

#[test]
fn children_missing_mutations_leave_collection_unchanged() {
    let mut arena = Arena::new();
    let id = arena.insert(Node::new("child", None));
    let mut children = Children::new();
    children.append(&arena[id].text, id, true);
    let before = children.clone();
    children.delete_by_id(
        NodeId {
            index: 999,
            generation: 1,
        },
        &arena,
    );
    children.delete_by_text("absent", &arena);
    assert_eq!(children.set_index(9, id, &arena), None);
    assert_eq!(children, before);
}

#[test]
fn children_rebuild_skips_dead_handles_and_clear_discards_mapping() {
    let mut arena = Arena::new();
    let alive = arena.insert(Node::new("alive", None));
    let dead = arena.insert(Node::new("dead", None));
    let mut children = Children::default();
    children.append(&arena[alive].text, alive, false);
    children.append(&arena[dead].text, dead, true);
    arena.remove(dead);
    children.rebuild_mapping(&arena);
    assert_eq!(children.as_slice(), [alive, dead]);
    assert_eq!(children.keys().collect::<Vec<_>>(), ["alive"]);
    children.delete_by_text("alive", &arena);
    assert!(children.is_empty());
    children.append(&arena[alive].text, alive, true);
    children.clear();
    assert_eq!(children.get_index(0), None);
    assert_eq!(children.get("alive"), None);
    children.rebuild_mapping(&arena);
    assert_eq!(children, Children::new());
}

#[test]
fn node_extras_reads_and_empty_shrink_do_not_allocate() {
    let mut node = Node::new("  command \n", None);
    assert_eq!(node.text.as_ref(), "command");
    assert!(node.is_leaf());
    assert!(!node.is_branch());
    assert!(node.tags().is_empty());
    assert!(node.comments().is_empty());
    assert!(node.instances().is_empty());
    assert!(node.facts().is_empty());
    node.shrink_extras();
    assert!(node.extras().is_none());
}

#[test]
fn node_extras_shrink_only_when_every_collection_is_empty() {
    let mut node = Node::new("command", None);
    let blank = node.clone();
    node.tags_mut().insert("tag".into());
    node.comments_mut().insert("comment".into());
    node.instances_mut().push(Instance {
        id: 7,
        tags: BTreeSet::from(["instance tag".into()]),
        comments: BTreeSet::new(),
    });
    node.facts_mut().insert("fact".into(), "value".into());
    assert_ne!(node, blank);
    node.tags_mut().clear();
    node.shrink_extras();
    assert!(node.extras().is_some());
    node.comments_mut().clear();
    node.shrink_extras();
    assert!(node.extras().is_some());
    node.instances_mut().clear();
    node.shrink_extras();
    assert_eq!(node.facts().get("fact").map(String::as_str), Some("value"));
    node.facts_mut().clear();
    assert_eq!(node, blank);
    node.shrink_extras();
    assert!(node.extras().is_none());
    assert_eq!(node, blank);
}

#[test]
fn node_equality_compares_effective_fields_and_clone_metadata_is_independent() {
    let node = Node::new("command", None);
    for mutate in [
        |n: &mut Node| n.text = Arc::from("other"),
        |n: &mut Node| n.order_weight = 1,
        |n: &mut Node| n.new_in_config = true,
        |n: &mut Node| {
            n.parent = Some(NodeId {
                index: 0,
                generation: 1,
            });
        },
        |n: &mut Node| n.real_indent_level = 3,
        |n: &mut Node| {
            n.tags_mut().insert("tag".into());
        },
        |n: &mut Node| {
            n.comments_mut().insert("comment".into());
        },
        |n: &mut Node| {
            n.instances_mut().push(Instance {
                id: 1,
                tags: BTreeSet::new(),
                comments: BTreeSet::new(),
            });
        },
        |n: &mut Node| {
            n.facts_mut().insert("key".into(), "value".into());
        },
        |n: &mut Node| {
            n.children.append(
                &Arc::from("child"),
                NodeId {
                    index: 0,
                    generation: 1,
                },
                true,
            );
        },
    ] {
        let mut changed = node.clone();
        mutate(&mut changed);
        assert_ne!(node, changed);
    }
    let shared: Arc<str> = Arc::from("already trimmed");
    let from_shared = Node::from_shared_text(Arc::clone(&shared), None);
    assert!(Arc::ptr_eq(&shared, &from_shared.text));
    let root = Node::root();
    assert_eq!(root.real_indent_level, -1);
    assert_eq!(root.parent, None);
    assert_eq!(root.text.as_ref(), "");
    let mut decorated = node;
    decorated.tags_mut().insert("a".into());
    let mut clone = decorated.clone();
    clone.tags_mut().insert("b".into());
    assert_eq!(decorated.tags(), &BTreeSet::from(["a".into()]));
    assert_eq!(clone.tags(), &BTreeSet::from(["a".into(), "b".into()]));
}
