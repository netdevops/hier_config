use crate::arena::{Arena, NodeId};
use crate::tree::node::Node;
use rustc_hash::FxHashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// Text-keyed index from a child's text to the *first* child that carries it.
type Mapping = FxHashMap<Arc<str>, NodeId>;

/// Ordered collection of child `NodeId`s with fast text-keyed lookup.
///
/// Preserves insertion order in a `Vec<NodeId>` while mapping `child.text` to the
/// *first* occurrence of a child with that text.
///
/// Two details keep this cheap on large configurations. The map is boxed and only
/// allocated once a child is appended with mapping enabled, so the leaf nodes that
/// make up most of a parsed tree carry a single null pointer rather than an empty
/// hash table. Its keys are `Arc<str>` shared with the node itself, so indexing a
/// child is a reference-count bump instead of a second copy of every configuration
/// line.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct Children {
    data: Vec<NodeId>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    mapping: Option<Box<Mapping>>,
}

impl Children {
    /// Creates an empty Children container.
    pub const fn new() -> Self {
        Self {
            data: Vec::new(),
            mapping: None,
        }
    }

    /// Number of children in the collection.
    pub const fn len(&self) -> usize {
        self.data.len()
    }

    /// Returns true if there are no children.
    pub const fn is_empty(&self) -> bool {
        self.data.is_empty()
    }

    /// Looks up a child by exact text match (returns the first matching child).
    pub fn get(&self, text: &str) -> Option<NodeId> {
        self.mapping.as_ref()?.get(text).copied()
    }

    /// Checks if a child with `text` exists.
    pub fn contains(&self, text: &str) -> bool {
        self.mapping
            .as_ref()
            .is_some_and(|mapping| mapping.contains_key(text))
    }

    /// Retrieves a child by index.
    pub fn get_index(&self, index: usize) -> Option<NodeId> {
        self.data.get(index).copied()
    }

    /// Returns the index of a child in the ordered list.
    pub fn index_of(&self, id: NodeId) -> Option<usize> {
        self.data.iter().position(|&x| x == id)
    }

    /// Returns a slice of the child `NodeId`s in insertion order.
    pub fn as_slice(&self) -> &[NodeId] {
        &self.data
    }

    /// Iterates over all child `NodeId`s in insertion order.
    pub fn iter(&self) -> impl Iterator<Item = NodeId> + '_ {
        self.data.iter().copied()
    }

    /// Appends a child to the collection.
    ///
    /// Only the first child with a given `text` is recorded in the mapping. Pass the
    /// child's own `Arc<str>` so the index shares that allocation.
    pub fn append(&mut self, text: &Arc<str>, child_id: NodeId, update_mapping: bool) {
        self.data.push(child_id);
        if update_mapping {
            self.mapping
                .get_or_insert_with(|| Box::new(Mapping::default()))
                .entry(Arc::clone(text))
                .or_insert(child_id);
        }
    }

    /// Replaces child at `index` and rebuilds the text mapping.
    pub fn set_index(
        &mut self,
        index: usize,
        new_id: NodeId,
        arena: &Arena<Node>,
    ) -> Option<NodeId> {
        if index < self.data.len() {
            let old_id = self.data[index];
            self.data[index] = new_id;
            self.rebuild_mapping(arena);
            Some(old_id)
        } else {
            None
        }
    }

    /// Clears all children.
    pub fn clear(&mut self) {
        self.data.clear();
        self.mapping = None;
    }

    /// Removes a specific child `NodeId` and rebuilds the text mapping.
    pub fn delete_by_id(&mut self, id: NodeId, arena: &Arena<Node>) {
        let old_len = self.data.len();
        self.data.retain(|&x| x != id);
        if self.data.len() != old_len {
            self.rebuild_mapping(arena);
        }
    }

    /// Removes all children with the given text and rebuilds the text mapping.
    pub fn delete_by_text(&mut self, text: &str, arena: &Arena<Node>) {
        if self.contains(text) {
            self.data.retain(|&id| {
                if let Some(node) = arena.get(id) {
                    node.text.as_ref() != text
                } else {
                    false
                }
            });
            self.rebuild_mapping(arena);
        }
    }

    /// Rebuilds the text -> `NodeId` mapping from current `data`.
    pub fn rebuild_mapping(&mut self, arena: &Arena<Node>) {
        if self.data.is_empty() {
            self.mapping = None;
            return;
        }
        let mapping = self
            .mapping
            .get_or_insert_with(|| Box::new(Mapping::default()));
        mapping.clear();
        for &id in &self.data {
            if let Some(node) = arena.get(id) {
                mapping.entry(Arc::clone(&node.text)).or_insert(id);
            }
        }
    }

    /// Returns an iterator over all keys in the mapping.
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.mapping
            .iter()
            .flat_map(|mapping| mapping.keys().map(Arc::as_ref))
    }
}
