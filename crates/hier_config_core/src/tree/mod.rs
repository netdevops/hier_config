pub mod children;
pub mod node;

pub use children::Children;
pub use node::Node;

use crate::arena::{Arena, NodeId};
use crate::driver::Driver;
use crate::models::{Dump, DumpLine, Instance, MatchRule, Platform, TagRule, TextStyle};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::sync::Arc;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TreeError {
    EmptyText,
    DuplicateChild(Vec<String>),
    NodeNotFound(NodeId),
    InvalidParent(NodeId),
    UnterminatedBanner(String),
}

impl std::fmt::Display for TreeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EmptyText => write!(f, "text was empty"),
            Self::DuplicateChild(path) => write!(f, "Found a duplicate section: {path:?}"),
            Self::NodeNotFound(id) => write!(f, "Node not found: {id:?}"),
            Self::InvalidParent(id) => write!(f, "Invalid parent: {id:?}"),
            Self::UnterminatedBanner(text) => write!(
                f,
                "Unterminated banner: we are still in a banner for some reason at \
the end of the configuration while parsing {text:?}. Banners must be closed by \
their delimiter or by a '!' line."
            ),
        }
    }
}

impl std::error::Error for TreeError {}

/// An arena-backed hierarchical configuration tree.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Tree {
    pub arena: Arena<Node>,
    pub root: NodeId,
    pub driver: Driver,
}

impl Default for Tree {
    fn default() -> Self {
        Self::new(Driver::default())
    }
}

impl Tree {
    /// Creates a new empty tree with the given platform driver.
    pub fn new(driver: Driver) -> Self {
        let mut arena = Arena::new();
        let root = arena.insert(Node::root());
        Self {
            arena,
            root,
            driver,
        }
    }

    /// Creates a new tree for a specific platform.
    pub fn for_platform(platform: Platform) -> Self {
        Self::new(Driver::for_platform(platform))
    }

    /// Creates a new tree for a specific platform and loads a configuration string into it.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if `config_raw` cannot be parsed into a tree, most
    /// commonly [`TreeError::DuplicateChild`].
    ///
    /// # Example
    ///
    /// ```
    /// use hier_config_core::{Platform, Tree};
    ///
    /// let config = "hostname router1\ninterface GigabitEthernet0/0\n  description WAN\n";
    /// let tree = Tree::from_str(Platform::CiscoIos, config)?;
    ///
    /// assert_eq!(tree.len(), 3);
    /// # Ok::<(), hier_config_core::TreeError>(())
    /// ```
    pub fn from_str(platform: Platform, config_raw: &str) -> Result<Self, TreeError> {
        crate::parser::parse_tree(Driver::for_platform(platform), config_raw)
    }

    /// Creates a new tree for a specific platform and loads a configuration string into it,
    /// running stock post-load callbacks followed additively by the provided custom callbacks.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if `config_raw` cannot be parsed into a tree, most
    /// commonly [`TreeError::DuplicateChild`].
    pub fn from_str_with_callbacks<F>(
        platform: Platform,
        config_raw: &str,
        callbacks: impl IntoIterator<Item = F>,
    ) -> Result<Self, TreeError>
    where
        F: Fn(&mut Self),
    {
        crate::parser::parse_tree_with_callbacks(
            Driver::for_platform(platform),
            config_raw,
            callbacks,
        )
    }

    /// Ingests a JSON document into a config tree for `platform`.
    ///
    /// # Errors
    /// Returns [`crate::formats::FormatError`] if `data` is not valid JSON or cannot be mapped.
    pub fn from_json(
        platform: Platform,
        data: &str,
        list_keys: Option<&[String]>,
    ) -> Result<Self, crate::formats::FormatError> {
        crate::formats::from_json(Driver::for_platform(platform), data, list_keys)
    }

    /// Ingests an XML document into a config tree for `platform`.
    ///
    /// # Errors
    /// Returns [`crate::formats::FormatError`] if `source` is not well-formed XML or cannot be mapped.
    pub fn from_xml(
        platform: Platform,
        source: &str,
        list_keys: Option<&[String]>,
    ) -> Result<Self, crate::formats::FormatError> {
        crate::formats::from_xml(Driver::for_platform(platform), source, list_keys)
    }

    /// Applies a custom callback to mutate this tree.
    pub fn apply_callback<F: FnOnce(&mut Self)>(&mut self, callback: F) {
        callback(self);
    }

    /// Number of all descendant nodes in the tree.
    pub fn len(&self) -> usize {
        self.all_children(self.root).len()
    }

    /// Returns true if the tree has no child nodes.
    pub fn is_empty(&self) -> bool {
        self.arena[self.root].children.is_empty()
    }

    /// Gets an immutable reference to a node.
    pub fn get(&self, id: NodeId) -> Option<&Node> {
        self.arena.get(id)
    }

    /// Gets a mutable reference to a node.
    pub fn get_mut(&mut self, id: NodeId) -> Option<&mut Node> {
        self.arena.get_mut(id)
    }

    /// Distance from `node_id` to the root (root has depth 0, top-level children have depth 1).
    pub fn depth(&self, node_id: NodeId) -> usize {
        if node_id == self.root || !self.arena.contains(node_id) {
            return 0;
        }
        let mut count = 0;
        let mut curr = self.arena[node_id].parent;
        while let Some(parent_id) = curr {
            count += 1;
            if parent_id == self.root {
                break;
            }
            curr = self.arena.get(parent_id).and_then(|p| p.parent);
        }
        count
    }

    /// Yields ancestor `NodeId`s starting from the top-level child down to `node_id`.
    pub fn lineage(&self, node_id: NodeId) -> Vec<NodeId> {
        if node_id == self.root || !self.arena.contains(node_id) {
            return Vec::new();
        }
        let mut chain = Vec::new();
        let mut curr = Some(node_id);
        while let Some(id) = curr {
            if id == self.root {
                break;
            }
            chain.push(id);
            curr = self.arena.get(id).and_then(|n| n.parent);
        }
        chain.reverse();
        chain
    }

    /// Yields configuration texts along the lineage from top-level child down to `node_id`.
    pub fn path(&self, node_id: NodeId) -> Vec<String> {
        self.lineage(node_id)
            .into_iter()
            .filter_map(|id| self.arena.get(id).map(|n| n.text.to_string()))
            .collect()
    }

    /// Checks if a node's lineage matches a sequence of match rules.
    pub fn is_lineage_match(&self, node_id: NodeId, rules: &[MatchRule]) -> bool {
        let lin = self.lineage(node_id);
        if lin.len() != rules.len() {
            return false;
        }
        lin.iter()
            .rev()
            .zip(rules.iter().rev())
            .all(|(&id, rule)| self.arena.get(id).is_some_and(|n| rule.is_match(&n.text)))
    }

    /// Checks if duplicate children are allowed under `parent_id`.
    ///
    /// A rule with empty `match_rules` matches the root's empty lineage, which
    /// is how a driver opts the top level into duplicates (#215).
    pub fn is_duplicate_child_allowed(&self, parent_id: NodeId) -> bool {
        self.driver
            .rules
            .parent_allows_duplicate_child
            .iter()
            .any(|rule| self.is_lineage_match(parent_id, &rule.match_rules))
    }

    /// Adds a child to `parent_id`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError::NodeNotFound`] if `parent_id` is not in the arena, or
    /// [`TreeError::DuplicateChild`] if a child with the same text already exists and
    /// the platform driver does not allow duplicates under this parent.
    pub fn add_child(
        &mut self,
        parent_id: NodeId,
        text: &str,
        check_if_present: bool,
        return_if_present: bool,
    ) -> Result<NodeId, TreeError> {
        let trimmed = text.trim();
        if trimmed.is_empty() {
            return Err(TreeError::EmptyText);
        }

        if !self.arena.contains(parent_id) {
            return Err(TreeError::InvalidParent(parent_id));
        }

        if check_if_present && let Some(existing_id) = self.arena[parent_id].children.get(trimmed) {
            if self.is_duplicate_child_allowed(parent_id) {
                let shared: Arc<str> = Arc::from(trimmed);
                let mut node = Node::from_shared_text(Arc::clone(&shared), Some(parent_id));
                let parent_real_indent = self.arena[parent_id].real_indent_level;
                node.real_indent_level = parent_real_indent + 1;
                let child_id = self.arena.insert(node);
                self.arena[parent_id]
                    .children
                    .append(&shared, child_id, false);
                return Ok(child_id);
            }
            if return_if_present {
                return Ok(existing_id);
            }
            let mut path = self.path(parent_id);
            path.push(trimmed.to_string());
            return Err(TreeError::DuplicateChild(path));
        }

        let shared: Arc<str> = Arc::from(trimmed);
        let mut node = Node::from_shared_text(Arc::clone(&shared), Some(parent_id));
        let parent_real_indent = self.arena[parent_id].real_indent_level;
        node.real_indent_level = parent_real_indent + 1;
        let child_id = self.arena.insert(node);
        self.arena[parent_id]
            .children
            .append(&shared, child_id, true);
        Ok(child_id)
    }

    /// Adds multiple children directly under `parent_id`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] under the same conditions as [`Tree::add_child`], for the
    /// first child that cannot be added.
    pub fn add_children(
        &mut self,
        parent_id: NodeId,
        lines: &[&str],
    ) -> Result<Vec<NodeId>, TreeError> {
        let mut ids = Vec::with_capacity(lines.len());
        for line in lines {
            ids.push(self.add_child(parent_id, line, true, false)?);
        }
        Ok(ids)
    }

    /// Adds a nested chain of children under `parent_id`, returning the deepest child.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] under the same conditions as [`Tree::add_child`], for the
    /// first level of the chain that cannot be added.
    pub fn add_children_deep(
        &mut self,
        parent_id: NodeId,
        lines: &[&str],
    ) -> Result<NodeId, TreeError> {
        let mut curr = parent_id;
        for line in lines {
            curr = self.add_child(curr, line, true, true)?;
        }
        Ok(curr)
    }

    /// Adds a shallow copy of a node from `source_tree` under `parent_id`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError::NodeNotFound`] if either node id is missing from its tree,
    /// or [`TreeError::DuplicateChild`] if the copy would duplicate an existing child.
    pub fn add_shallow_copy_of(
        &mut self,
        parent_id: NodeId,
        source_tree: &Self,
        source_id: NodeId,
        merged: bool,
    ) -> Result<NodeId, TreeError> {
        let src_node = &source_tree.arena[source_id];
        let new_id = self.add_child(parent_id, &src_node.text, true, merged)?;

        let (order_weight, comments, is_leaf, tags, instances) = {
            (
                src_node.order_weight,
                src_node.comments().clone(),
                src_node.is_leaf(),
                source_tree.tags(source_id),
                if merged {
                    vec![Instance {
                        id: u64::from(source_id.index),
                        comments: src_node.comments().clone(),
                        tags: source_tree.tags(source_id),
                    }]
                } else {
                    Vec::new()
                },
            )
        };

        let target_node = &mut self.arena[new_id];
        target_node.order_weight = order_weight;
        target_node.comments_mut().extend(comments);
        if merged {
            target_node.instances_mut().extend(instances);
        }
        if is_leaf {
            target_node.tags_mut().extend(tags);
        }

        Ok(new_id)
    }

    /// Adds a shallow copy of a node that lives in the *same* tree.
    ///
    /// This is the aliased counterpart of [`Tree::add_shallow_copy_of`]: it takes a
    /// single mutable borrow instead of a separate source tree, which is required when
    /// the source and destination are the same tree (otherwise the caller would have to
    /// hold a write and a read lock on one `RwLock` simultaneously and deadlock).
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] under the same conditions as [`Tree::add_shallow_copy_of`].
    pub fn add_shallow_copy_within(
        &mut self,
        parent_id: NodeId,
        source_id: NodeId,
        merged: bool,
    ) -> Result<NodeId, TreeError> {
        let (text, order_weight, comments, is_leaf) = {
            let src_node = &self.arena[source_id];
            (
                Arc::<str>::clone(&src_node.text),
                src_node.order_weight,
                src_node.comments().clone(),
                src_node.is_leaf(),
            )
        };
        let tags = self.tags(source_id);
        let instances = if merged {
            vec![Instance {
                id: u64::from(source_id.index),
                comments: comments.clone(),
                tags: tags.clone(),
            }]
        } else {
            Vec::new()
        };

        let new_id = self.add_child(parent_id, &text, true, merged)?;

        let target_node = &mut self.arena[new_id];
        target_node.order_weight = order_weight;
        target_node.comments_mut().extend(comments);
        if merged {
            target_node.instances_mut().extend(instances);
        }
        if is_leaf {
            target_node.tags_mut().extend(tags);
        }

        Ok(new_id)
    }

    /// Recursively adds a deep copy of a node and all its children.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] under the same conditions as [`Tree::add_shallow_copy_of`],
    /// for the first node in the subtree that cannot be copied.
    pub fn add_deep_copy_of(
        &mut self,
        parent_id: NodeId,
        source_tree: &Self,
        source_id: NodeId,
        merged: bool,
    ) -> Result<NodeId, TreeError> {
        let new_child = self.add_shallow_copy_of(parent_id, source_tree, source_id, merged)?;
        for child_id in source_tree.arena[source_id].children.iter() {
            self.add_deep_copy_of(new_child, source_tree, child_id, merged)?;
        }
        Ok(new_child)
    }

    /// Copies all ancestors in `source_tree` along the lineage down to `source_id`
    /// into this tree under `parent_id`, reusing existing matching children where present.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if any ancestor cannot be added or copied.
    pub fn add_ancestor_copy_of(
        &mut self,
        parent_id: NodeId,
        source_tree: &Self,
        source_id: NodeId,
    ) -> Result<NodeId, TreeError> {
        let lineage = source_tree.lineage(source_id);
        let mut curr = parent_id;
        for ancestor in lineage {
            curr = self.add_shallow_copy_of(curr, source_tree, ancestor, false)?;
        }
        Ok(curr)
    }

    /// Copies all ancestors in this tree along the lineage down to `source_id`
    /// under `parent_id`, reusing existing matching children where present.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if any ancestor cannot be added or copied.
    pub fn add_ancestor_copy_within(
        &mut self,
        parent_id: NodeId,
        source_id: NodeId,
    ) -> Result<NodeId, TreeError> {
        let lineage = self.lineage(source_id);
        let mut curr = parent_id;
        for ancestor in lineage {
            curr = self.add_shallow_copy_within(curr, ancestor, false)?;
        }
        Ok(curr)
    }

    /// Merges all top-level children from `other` into this tree with `merged: true`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if copying any node fails.
    pub fn merge(&mut self, other: &Self) -> Result<(), TreeError> {
        let child_ids: Vec<NodeId> = other.arena[other.root].children.iter().collect();
        for child_id in child_ids {
            self.add_deep_copy_of(self.root, other, child_id, true)?;
        }
        Ok(())
    }

    /// Moves a child from its current parent to `new_parent_id`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError::NodeNotFound`] if `child_id` is the root or either node is
    /// missing from the arena.
    pub fn move_child(&mut self, child_id: NodeId, new_parent_id: NodeId) -> Result<(), TreeError> {
        if child_id == self.root {
            return Err(TreeError::NodeNotFound(child_id));
        }
        let old_parent = self.arena[child_id]
            .parent
            .ok_or(TreeError::NodeNotFound(child_id))?;

        let text = Arc::<str>::clone(&self.arena[child_id].text);
        let mut old_children = std::mem::take(&mut self.arena[old_parent].children);
        old_children.delete_by_id(child_id, &self.arena);
        self.arena[old_parent].children = old_children;

        self.arena[child_id].parent = Some(new_parent_id);
        self.arena[new_parent_id]
            .children
            .append(&text, child_id, true);
        Ok(())
    }

    /// Deletes a child and all its descendants.
    pub fn delete_child(&mut self, child_id: NodeId) {
        if child_id == self.root || !self.arena.contains(child_id) {
            return;
        }
        if let Some(parent_id) = self.arena[child_id].parent
            && self.arena.contains(parent_id)
        {
            let mut parent_children = std::mem::take(&mut self.arena[parent_id].children);
            parent_children.delete_by_id(child_id, &self.arena);
            self.arena[parent_id].children = parent_children;
        }
        self.delete_subtree(child_id);
    }

    fn delete_subtree(&mut self, node_id: NodeId) {
        if !self.arena.contains(node_id) {
            return;
        }
        let children: Vec<NodeId> = self.arena[node_id].children.iter().collect();
        for child_id in children {
            self.delete_subtree(child_id);
        }
        self.arena.remove(node_id);
    }

    /// Rebuilds the text->NodeId mapping for children of `parent_id`.
    pub fn rebuild_children_mapping(&mut self, parent_id: NodeId) {
        if !self.arena.contains(parent_id) {
            return;
        }
        let mut children = std::mem::take(&mut self.arena[parent_id].children);
        children.rebuild_mapping(&self.arena);
        self.arena[parent_id].children = children;
    }

    /// Creates a child node unattached to `parent_id`'s children collection.
    pub fn create_child_unattached(&mut self, parent_id: NodeId, text: &str) -> NodeId {
        let node = Node::new(text, Some(parent_id));
        self.arena.insert(node)
    }

    /// Sets the child at `index` under `parent_id` to `new_child_id`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError::NodeNotFound`] if `parent_id` or `new_child_id` is missing,
    /// or if `index` is out of range for the parent's children.
    pub fn set_child_at(
        &mut self,
        parent_id: NodeId,
        index: usize,
        new_child_id: NodeId,
    ) -> Result<Option<NodeId>, TreeError> {
        if !self.arena.contains(parent_id) {
            return Err(TreeError::InvalidParent(parent_id));
        }
        let old_pos = self.arena[parent_id].children.index_of(new_child_id);
        if let Some(pos) = old_pos
            && pos != index
        {
            let mut children = std::mem::take(&mut self.arena[parent_id].children);
            children.delete_by_id(new_child_id, &self.arena);
            self.arena[parent_id].children = children;
        }
        let mut children = std::mem::take(&mut self.arena[parent_id].children);
        let old_id = children.set_index(index, new_child_id, &self.arena);
        self.arena[parent_id].children = children;
        if let Some(old) = old_id {
            if let Some(node) = self.arena.get_mut(new_child_id) {
                node.parent = Some(parent_id);
            }
            Ok(Some(old))
        } else {
            Err(TreeError::NodeNotFound(new_child_id))
        }
    }

    /// Compares two nodes for equality based on text, tags, and recursively sorted children.
    pub fn node_equals(&self, a: NodeId, other_tree: &Self, b: NodeId) -> bool {
        let (node_a, node_b) = match (self.arena.get(a), other_tree.arena.get(b)) {
            (Some(na), Some(nb)) => (na, nb),
            (None, None) => return true,
            _ => return false,
        };
        if node_a.text != node_b.text {
            return false;
        }
        if self.tags(a) != other_tree.tags(b) {
            return false;
        }
        let a_children = self.sorted_children(a);
        let b_children = other_tree.sorted_children(b);
        if a_children.len() != b_children.len() {
            return false;
        }
        for (&ca, &cb) in a_children.iter().zip(b_children.iter()) {
            if !self.node_equals(ca, other_tree, cb) {
                return false;
            }
        }
        true
    }

    /// Returns the number of descendant nodes under `node_id`.
    pub fn node_count(&self, node_id: NodeId) -> usize {
        if !self.arena.contains(node_id) {
            0
        } else if node_id == self.root {
            self.arena.len().saturating_sub(1)
        } else {
            self.descendants(node_id).count()
        }
    }

    /// Returns an iterator over all descendant `NodeId`s in pre-order insertion order.
    pub fn descendants(&self, node_id: NodeId) -> Descendants<'_> {
        Descendants::new(self, node_id)
    }

    /// Returns an iterator over all descendant `NodeId`s in pre-order, sorted by `order_weight` at each level.
    pub fn descendants_sorted(&self, node_id: NodeId) -> DescendantsSorted<'_> {
        DescendantsSorted::new(self, node_id)
    }

    /// Returns all descendant `NodeId`s recursively in insertion order.
    pub fn all_children(&self, node_id: NodeId) -> Vec<NodeId> {
        let mut result = Vec::new();
        if self.arena.contains(node_id) {
            result.reserve(self.traversal_size_hint(node_id));
            result.extend(self.descendants(node_id));
        }
        result
    }

    /// Returns sorted children for a node based on `order_weight` (stable sort).
    pub fn sorted_children(&self, node_id: NodeId) -> Vec<NodeId> {
        if let Some(node) = self.arena.get(node_id) {
            let mut list: Vec<NodeId> = node.children.iter().collect();
            list.sort_by_key(|&id| self.arena.get(id).map_or(0, |n| n.order_weight));
            list
        } else {
            Vec::new()
        }
    }

    /// Estimates how many descendants a full traversal of `node_id` will yield.
    ///
    /// A whole-tree walk visits every node, so the arena length is exact there. For a
    /// subtree we only use the direct child count, because reserving the whole arena
    /// would over-allocate badly for the many small-subtree traversals that
    /// remediation performs.
    fn traversal_size_hint(&self, node_id: NodeId) -> usize {
        if node_id == self.root {
            self.arena.len()
        } else {
            self.arena
                .get(node_id)
                .map_or(0, |n| n.children.as_slice().len())
        }
    }

    /// Returns true when `children` is already in non-decreasing `order_weight` order.
    ///
    /// `order_weight` is left at its default on the overwhelming majority of nodes, so
    /// this lets the recursive walk iterate the existing slice instead of building and
    /// sorting a throwaway `Vec` at every level.
    fn children_already_ordered(&self, children: &[NodeId]) -> bool {
        let mut previous = i32::MIN;
        for &id in children {
            let weight = self.arena.get(id).map_or(0, |n| n.order_weight);
            if weight < previous {
                return false;
            }
            previous = weight;
        }
        true
    }

    /// Returns all descendant `NodeId`s recursively, sorted by `order_weight` at each level.
    pub fn all_children_sorted(&self, node_id: NodeId) -> Vec<NodeId> {
        let mut result = Vec::new();
        if self.arena.contains(node_id) {
            result.reserve(self.traversal_size_hint(node_id));
            result.extend(self.descendants_sorted(node_id));
        }
        result
    }

    /// Computes the union of tags on all leaf nodes under `node_id`.
    pub fn tags(&self, node_id: NodeId) -> BTreeSet<String> {
        if let Some(node) = self.arena.get(node_id) {
            if node.is_leaf() && node_id != self.root {
                return node.tags().clone();
            }
            let mut all_tags = BTreeSet::new();
            for child_id in node.children.iter() {
                all_tags.extend(self.tags(child_id));
            }
            all_tags
        } else {
            BTreeSet::new()
        }
    }

    /// Sets tags on leaf nodes under `node_id`.
    pub fn set_tags(&mut self, node_id: NodeId, tags: BTreeSet<String>) {
        if self.arena[node_id].is_leaf() && node_id != self.root {
            let node = &mut self.arena[node_id];
            if tags.is_empty() {
                // Avoid materialising an extras block just to store nothing.
                if node.extras().is_some() {
                    node.tags_mut().clear();
                    node.shrink_extras();
                }
            } else {
                *node.tags_mut() = tags;
            }
        } else {
            let children: Vec<NodeId> = self.arena[node_id].children.iter().collect();
            for child_id in children {
                self.set_tags(child_id, tags.clone());
            }
        }
    }

    /// Adds tags to all leaf nodes under `node_id`.
    pub fn tags_add(&mut self, node_id: NodeId, tags: &[&str]) {
        if self.arena[node_id].is_leaf() && node_id != self.root {
            for tag in tags {
                self.arena[node_id].tags_mut().insert((*tag).to_string());
            }
        } else {
            let children: Vec<NodeId> = self.arena[node_id].children.iter().collect();
            for child_id in children {
                self.tags_add(child_id, tags);
            }
        }
    }

    /// Removes tags from all leaf nodes under `node_id`.
    pub fn tags_remove(&mut self, node_id: NodeId, tags: &[&str]) {
        if self.arena[node_id].is_leaf() && node_id != self.root {
            for tag in tags {
                self.arena[node_id].tags_mut().remove(*tag);
            }
        } else {
            let children: Vec<NodeId> = self.arena[node_id].children.iter().collect();
            for child_id in children {
                self.tags_remove(child_id, tags);
            }
        }
    }

    /// Returns a new `Tree` containing only nodes matching the given tags.
    ///
    /// For each child of a node, if `tags` is a subset of the child's aggregated tags,
    /// that child is shallow-copied into the new tree and recursion continues.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if copying any node fails.
    pub fn with_tags(&self, tags: &BTreeSet<String>) -> Result<Self, TreeError> {
        let mut new_tree = Self::for_platform(self.driver.platform);
        let new_root = new_tree.root;
        self.with_tags_recursive(self.root, &mut new_tree, new_root, tags)?;
        Ok(new_tree)
    }

    fn with_tags_recursive(
        &self,
        src_parent: NodeId,
        dst_tree: &mut Self,
        dst_parent: NodeId,
        tags: &BTreeSet<String>,
    ) -> Result<(), TreeError> {
        let child_ids: Vec<NodeId> = self.arena[src_parent].children.iter().collect();
        for cid in child_ids {
            let child_tags = self.tags(cid);
            if tags.is_subset(&child_tags) {
                let new_child = dst_tree.add_shallow_copy_of(dst_parent, self, cid, false)?;
                self.with_tags_recursive(cid, dst_tree, new_child, tags)?;
            }
        }
        Ok(())
    }

    /// Tests whether a node should be included according to include/exclude tags.
    pub fn line_inclusion_test(
        &self,
        node_id: NodeId,
        include_tags: &[&str],
        exclude_tags: &[&str],
    ) -> bool {
        let tags = self.tags(node_id);
        let mut include_line = false;

        if !include_tags.is_empty() {
            include_line = include_tags.iter().any(|t| tags.contains(*t));
        }

        if !exclude_tags.is_empty() && (include_line || include_tags.is_empty()) {
            return !exclude_tags.iter().any(|t| tags.contains(*t));
        }

        include_line
    }

    /// Yields all children recursively that match include/exclude tags.
    pub fn all_children_sorted_by_tags(
        &self,
        node_id: NodeId,
        include_tags: &[&str],
        exclude_tags: &[&str],
    ) -> Vec<NodeId> {
        let mut result = Vec::new();
        if node_id == self.root {
            for child_id in self.sorted_children(self.root) {
                self.collect_children_by_tags(child_id, include_tags, exclude_tags, &mut result);
            }
        } else {
            self.collect_children_by_tags(node_id, include_tags, exclude_tags, &mut result);
        }
        result
    }

    fn collect_children_by_tags(
        &self,
        node_id: NodeId,
        include_tags: &[&str],
        exclude_tags: &[&str],
        out: &mut Vec<NodeId>,
    ) -> bool {
        let node = &self.arena[node_id];
        if node.is_leaf() {
            if self.line_inclusion_test(node_id, include_tags, exclude_tags) {
                out.push(node_id);
                true
            } else {
                false
            }
        } else {
            let start_len = out.len();
            // placeholder for branch node
            out.push(node_id);
            let mut any_included = false;
            for child_id in self.sorted_children(node_id) {
                if self.collect_children_by_tags(child_id, include_tags, exclude_tags, out) {
                    any_included = true;
                }
            }
            if any_included {
                true
            } else {
                // If no children were included, prune branch
                out.truncate(start_len);
                false
            }
        }
    }

    /// Applies tag rules to descendant nodes matching each rule's match criteria.
    pub fn apply_tag_rules(&mut self, rules: &[TagRule]) {
        for rule in rules {
            let matching_ids = self.get_children_deep(self.root, &rule.match_rules);
            let tag_refs: Vec<&str> = rule.apply_tags.iter().map(String::as_str).collect();
            for node_id in matching_ids {
                self.tags_add(node_id, &tag_refs);
            }
        }
    }

    /// Formats all children (or filtered by tags) into a single Cisco-style text string.
    pub fn rendered_text_by_tags(&self, include_tags: &[&str], exclude_tags: &[&str]) -> String {
        let node_ids = if include_tags.is_empty() && exclude_tags.is_empty() {
            self.all_children_sorted(self.root)
        } else {
            self.all_children_sorted_by_tags(self.root, include_tags, exclude_tags)
        };
        let mut buffer = String::with_capacity(node_ids.len() * 32);
        for (i, &node_id) in node_ids.iter().enumerate() {
            if i > 0 {
                buffer.push('\n');
            }
            buffer.push_str(&self.cisco_style_text(node_id, TextStyle::WithoutComments, None));
        }
        buffer
    }

    /// Looks up a direct child of `parent_id` by its exact text.
    pub fn get_child_by_text(&self, parent_id: NodeId, text: &str) -> Option<NodeId> {
        self.arena[parent_id].children.get(text)
    }

    /// Finds children of `parent_id` matching a `MatchRule`.
    pub fn get_children(&self, parent_id: NodeId, rule: &MatchRule) -> Vec<NodeId> {
        self.arena[parent_id]
            .children
            .iter()
            .filter(|&id| rule.is_match(&self.arena[id].text))
            .collect()
    }

    /// Finds the first child of `parent_id` matching a `MatchRule`.
    pub fn get_child(&self, parent_id: NodeId, rule: &MatchRule) -> Option<NodeId> {
        self.arena[parent_id]
            .children
            .iter()
            .find(|&id| rule.is_match(&self.arena[id].text))
    }

    /// Recursively finds children matching a sequence of `MatchRule`s.
    pub fn get_children_deep(&self, parent_id: NodeId, rules: &[MatchRule]) -> Vec<NodeId> {
        if rules.is_empty() {
            return Vec::new();
        }
        let first_rule = &rules[0];
        let remaining_rules = &rules[1..];
        let mut result = Vec::new();

        for child_id in self.get_children(parent_id, first_rule) {
            if remaining_rules.is_empty() {
                result.push(child_id);
            } else {
                result.extend(self.get_children_deep(child_id, remaining_rules));
            }
        }

        result
    }

    /// Returns indentation spaces for `node_id`.
    pub fn indentation(&self, node_id: NodeId) -> String {
        let depth = self.depth(node_id);
        if depth == 0 {
            String::new()
        } else {
            " ".repeat(self.driver.rules.indentation * (depth - 1))
        }
    }

    /// Sets the text of a node and rebuilds its parent's text mapping.
    pub fn set_text(&mut self, node_id: NodeId, new_text: &str) {
        let trimmed = new_text.trim();
        self.arena[node_id].text = Arc::from(trimmed);
        if let Some(parent_id) = self.arena[node_id].parent {
            let mut parent_children = std::mem::take(&mut self.arena[parent_id].children);
            parent_children.rebuild_mapping(&self.arena);
            self.arena[parent_id].children = parent_children;
        }
    }

    /// Sets `order_weight` on all descendant nodes based on driver ordering rules.
    pub fn set_order_weight(&mut self) {
        let all_nodes = self.all_children(self.root);
        for node_id in all_nodes {
            for rule in &self.driver.rules.ordering {
                if self.is_lineage_match(node_id, &rule.match_rules) {
                    self.arena[node_id].order_weight = rule.weight;
                }
            }
        }
    }

    /// Finds top-level children that are defined objects with no references across the config.
    pub fn unused_objects(&self) -> Vec<NodeId> {
        let mut unused = Vec::new();
        let mut seen_names = std::collections::HashSet::new();

        for rule in &self.driver.rules.unused_objects {
            let Some(re) = crate::regex_cache::regex(&rule.name_re) else {
                continue;
            };
            for definition_id in self.get_children_deep(self.root, &rule.match_rules) {
                let text = &self.arena[definition_id].text;
                let Some(caps) = re.captures(text) else {
                    continue;
                };
                let Some(name) = caps.name("name").map(|m| m.as_str()) else {
                    continue;
                };
                if !seen_names.insert(name.to_string()) {
                    continue;
                }

                if !self.is_object_referenced(name, &rule.reference_locations) {
                    unused.push(definition_id);
                }
            }
        }

        unused
    }

    /// Checks whether an object name is referenced anywhere matching the given reference locations.
    pub fn is_object_referenced(
        &self,
        name: &str,
        locations: &[crate::models::ReferenceLocation],
    ) -> bool {
        let escaped = regex::escape(name);
        for loc in locations {
            let pattern = loc.reference_re.replace("{name}", &escaped);
            // The object name is interpolated into the pattern, so each distinct name
            // yields a unique pattern that would never be a cache hit. Routing these
            // through the process-wide, never-evicting `regex_cache` would leak memory
            // monotonically on input-controlled strings, so compile without caching.
            let Some(re) = crate::regex_cache::compile_uncached(&pattern) else {
                continue;
            };
            for section_id in self.get_children_deep(self.root, &loc.match_rules) {
                for child_id in self.all_children(section_id) {
                    if re.is_match(&self.arena[child_id].text) {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// Determines if self.text is an idempotent command change.
    pub fn is_idempotent_command(
        &self,
        node_id: NodeId,
        other_tree: &Self,
        other_children: &[NodeId],
    ) -> bool {
        let avoid_rules = if self.driver.rules.idempotent_commands_avoid.is_empty() {
            &other_tree.driver.rules.idempotent_commands_avoid
        } else {
            &self.driver.rules.idempotent_commands_avoid
        };
        for rule in avoid_rules {
            if self.is_lineage_match(node_id, &rule.match_rules) {
                return false;
            }
        }

        self.idempotent_for(node_id, other_tree, other_children)
            .is_some()
    }

    fn fortios_idempotent_for(
        &self,
        node_id: NodeId,
        other_tree: &Self,
        other_children: &[NodeId],
    ) -> Option<NodeId> {
        let text = &self.arena[node_id].text;
        let decl = if self.driver.declaration_prefix.is_empty() {
            &other_tree.driver.declaration_prefix
        } else {
            &self.driver.declaration_prefix
        };
        if !decl.is_empty() && text.starts_with(decl) {
            let parts: Vec<&str> = text.split_whitespace().collect();
            if parts.len() > 1 {
                for &other_id in other_children {
                    let other_text = &other_tree.arena[other_id].text;
                    if other_text.starts_with(decl) {
                        let other_parts: Vec<&str> = other_text.split_whitespace().collect();
                        if other_parts.len() > 1 && parts[1] == other_parts[1] {
                            return Some(other_id);
                        }
                    }
                }
            }
        }
        None
    }

    fn ciscoxr_idempotent_for(
        &self,
        node_id: NodeId,
        other_tree: &Self,
        other_children: &[NodeId],
    ) -> Option<NodeId> {
        let text = &self.arena[node_id].text;
        if let Some(parent_id) = self.arena[node_id].parent
            && parent_id != self.root
        {
            let parent_text = &self.arena[parent_id].text;
            if (parent_text.starts_with("ipv4 access-list ")
                || parent_text.starts_with("ipv6 access-list "))
                && let Some(self_sn) = text.split_whitespace().next()
            {
                for &other_id in other_children {
                    let other_text = &other_tree.arena[other_id].text;
                    if let Some(other_sn) = other_text.split_whitespace().next()
                        && self_sn == other_sn
                    {
                        return Some(other_id);
                    }
                }
            }
        }
        None
    }

    /// Finds matching child in `other_children` that is idempotent for `node_id`.
    pub fn idempotent_for(
        &self,
        node_id: NodeId,
        other_tree: &Self,
        other_children: &[NodeId],
    ) -> Option<NodeId> {
        let platform = if self.driver.platform == Platform::Generic {
            other_tree.driver.platform
        } else {
            self.driver.platform
        };
        match platform {
            Platform::FortinetFortios => {
                if let Some(found) =
                    self.fortios_idempotent_for(node_id, other_tree, other_children)
                {
                    return Some(found);
                }
            }
            Platform::CiscoXr => {
                if let Some(found) =
                    self.ciscoxr_idempotent_for(node_id, other_tree, other_children)
                {
                    return Some(found);
                }
            }
            _ => {}
        }

        self.base_idempotent_for(node_id, other_tree, other_children)
    }

    fn base_idempotent_for(
        &self,
        node_id: NodeId,
        other_tree: &Self,
        other_children: &[NodeId],
    ) -> Option<NodeId> {
        let self_path = self.path(node_id);
        let self_path_refs: Vec<&str> = self_path.iter().map(String::as_str).collect();
        let (rules, driver) = if self.driver.rules.idempotent_commands.is_empty() {
            (
                &other_tree.driver.rules.idempotent_commands,
                &other_tree.driver,
            )
        } else {
            (&self.driver.rules.idempotent_commands, &self.driver)
        };
        for rule in rules {
            if !self.is_lineage_match(node_id, &rule.match_rules) {
                continue;
            }

            let self_key = driver.idempotency_key(&self_path_refs, &rule.match_rules);

            for &other_id in other_children {
                if !other_tree.is_lineage_match(other_id, &rule.match_rules) {
                    continue;
                }
                let other_path = other_tree.path(other_id);
                let other_path_refs: Vec<&str> = other_path.iter().map(String::as_str).collect();
                let other_key = driver.idempotency_key(&other_path_refs, &rule.match_rules);

                if !self_key.is_empty() && self_key == other_key {
                    return Some(other_id);
                }
            }
        }
        None
    }

    /// Computes the negation string for a node.
    pub fn compute_negation(&self, node_id: NodeId) -> String {
        if let Some(with_cmd) = self.negate_with(node_id) {
            return with_cmd;
        }
        let text = &self.arena[node_id].text;
        self.driver
            .compute_negation(text, |rules| self.is_lineage_match(node_id, rules))
    }

    /// Returns the custom negation string if defined by a `negate_with` rule.
    pub fn negate_with(&self, node_id: NodeId) -> Option<String> {
        for rule in &self.driver.rules.negate_with {
            if self.is_lineage_match(node_id, &rule.match_rules) {
                return Some(Driver::expand_negate_with(&self.arena[node_id].text, rule));
            }
        }

        None
    }

    /// Checks if a node should use sectional overwrite with negation.
    pub fn use_sectional_overwrite(&self, node_id: NodeId) -> bool {
        for rule in &self.driver.rules.sectional_overwrite {
            if self.is_lineage_match(node_id, &rule.match_rules) {
                return true;
            }
        }
        false
    }

    /// Checks if a node should use sectional overwrite without negation.
    pub fn use_sectional_overwrite_without_negation(&self, node_id: NodeId) -> bool {
        for rule in &self.driver.rules.sectional_overwrite_no_negate {
            if self.is_lineage_match(node_id, &rule.match_rules) {
                return true;
            }
        }
        false
    }

    /// Formats a node's line in Cisco-style.
    pub fn cisco_style_text(&self, node_id: NodeId, style: TextStyle, tag: Option<&str>) -> String {
        let Some(node) = self.arena.get(node_id) else {
            return String::new();
        };
        let mut comments = Vec::new();

        match style {
            TextStyle::WithoutComments => {}
            TextStyle::Merged => {
                let mut instance_count = 0;
                let mut instance_comments = BTreeSet::new();
                for instance in node.instances() {
                    if tag.is_none_or(|t| instance.tags.contains(t)) {
                        instance_count += 1;
                        instance_comments.extend(instance.comments.clone());
                    }
                }
                let word = if instance_count == 1 {
                    "instance"
                } else {
                    "instances"
                };
                comments.push(format!("{instance_count} {word}"));
                comments.extend(instance_comments);
            }
            TextStyle::WithComments => {
                comments.extend(node.comments().clone());
            }
        }

        let comments_str = if comments.is_empty() {
            String::new()
        } else {
            comments.sort();
            format!(" !{}", comments.join(", "))
        };

        format!("{}{}{}", self.indentation(node_id), node.text, comments_str)
    }

    /// Returns the sectional exit text for a node if configured.
    pub fn sectional_exit(&self, node_id: NodeId) -> Option<String> {
        let node = self.arena.get(node_id)?;
        let has_children = !node.children.is_empty();
        self.driver
            .sectional_exit(has_children, |rules| self.is_lineage_match(node_id, rules))
    }

    /// Checks if the exit command should be at parent indentation level.
    pub fn sectional_exit_text_parent_level(&self, node_id: NodeId) -> bool {
        if !self.arena.contains(node_id) {
            return false;
        }
        for rule in &self.driver.rules.sectional_exiting {
            if self.is_lineage_match(node_id, &rule.match_rules) {
                return rule.exit_text_parent_level;
            }
        }
        false
    }

    /// Deletes a potential redundant sectional exit node at the end of `node_id`'s children.
    pub fn delete_sectional_exit(&mut self, node_id: NodeId) {
        if !self.arena.contains(node_id) {
            return;
        }
        if let Some(last_id) = self.arena[node_id].children.as_slice().last().copied()
            && let Some(exit_text) = self.sectional_exit(node_id)
            && self.arena.contains(last_id)
            && self.arena[last_id].text.as_ref() == exit_text
        {
            self.delete_child(last_id);
        }
    }

    /// Generates rendered configuration lines.
    pub fn lines(&self, node_id: NodeId, sectional_exiting: bool) -> Vec<String> {
        let mut out = Vec::new();
        self.collect_lines(node_id, sectional_exiting, &mut out);
        out
    }

    fn collect_lines(&self, node_id: NodeId, sectional_exiting: bool, out: &mut Vec<String>) {
        if node_id != self.root {
            out.push(self.cisco_style_text(node_id, TextStyle::WithoutComments, None));
        }

        for child_id in self.sorted_children(node_id) {
            self.collect_lines(child_id, sectional_exiting, out);
        }

        if node_id != self.root
            && sectional_exiting
            && let Some(exit_text) = self.sectional_exit(node_id)
        {
            let depth = if self.sectional_exit_text_parent_level(node_id) {
                self.depth(node_id).saturating_sub(1)
            } else {
                self.depth(node_id)
            };
            let indent = " ".repeat(self.driver.rules.indentation * depth);
            out.push(format!("{indent}{exit_text}"));
        }
    }

    /// Computes the remediation configuration to get from `self` to `target`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if the remediation tree cannot be assembled.
    ///
    /// # Example
    ///
    /// ```
    /// use hier_config_core::{Platform, Tree};
    ///
    /// let running = Tree::from_str(
    ///     Platform::CiscoIos,
    ///     "vlan 10\n  name Marketing\nvlan 20\n  name Engineering\n",
    /// )?;
    /// let intended = Tree::from_str(
    ///     Platform::CiscoIos,
    ///     "vlan 10\n  name Marketing\n",
    /// )?;
    ///
    /// let remediation = running.config_to_get_to(&intended)?;
    /// assert_eq!(remediation.dump_simple(false), vec!["no vlan 20"]);
    /// # Ok::<(), hier_config_core::TreeError>(())
    /// ```
    pub fn config_to_get_to(&self, target: &Self) -> Result<Self, TreeError> {
        crate::remediation::config_to_get_to(self, target)
    }

    /// Computes the future configuration after applying `config` to `self`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if the predicted tree cannot be assembled.
    ///
    /// # Example
    ///
    /// ```
    /// use hier_config_core::{Platform, Tree};
    ///
    /// let running = Tree::from_str(
    ///     Platform::CiscoIos,
    ///     "interface GigabitEthernet0/1\n  shutdown\n",
    /// )?;
    /// let remediation = Tree::from_str(
    ///     Platform::CiscoIos,
    ///     "interface GigabitEthernet0/1\n  no shutdown\n  description Production Link\n",
    /// )?;
    ///
    /// let future = running.future(&remediation, true)?;
    /// assert_eq!(
    ///     future.dump_simple(false),
    ///     vec![
    ///         "interface GigabitEthernet0/1",
    ///         "  description Production Link",
    ///     ]
    /// );
    /// # Ok::<(), hier_config_core::TreeError>(())
    /// ```
    pub fn future(&self, config: &Self, prune_empty_branches: bool) -> Result<Self, TreeError> {
        crate::remediation::future(self, config, prune_empty_branches)
    }

    /// Computes the difference between `self` and `target`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if the difference tree cannot be assembled.
    pub fn difference(&self, target: &Self) -> Result<Self, TreeError> {
        crate::remediation::difference(self, target)
    }

    /// Computes unified diff lines between `self` and `target`.
    ///
    /// # Example
    ///
    /// ```
    /// use hier_config_core::{Platform, Tree};
    ///
    /// let running = Tree::from_str(
    ///     Platform::CiscoIos,
    ///     "interface GigabitEthernet0/1\n  shutdown\n",
    /// )?;
    /// let intended = Tree::from_str(
    ///     Platform::CiscoIos,
    ///     "interface GigabitEthernet0/1\n  no shutdown\n",
    /// )?;
    ///
    /// let diff = running.unified_diff(&intended);
    /// assert!(!diff.is_empty());
    /// # Ok::<(), hier_config_core::TreeError>(())
    /// ```
    pub fn unified_diff(&self, target: &Self) -> Vec<String> {
        crate::remediation::unified_diff(self, target)
    }

    /// Serializes configuration tree to `Dump`.
    pub fn dump(&self) -> Dump {
        let lines = self
            .all_children_sorted(self.root)
            .into_iter()
            .map(|id| {
                let node = &self.arena[id];
                DumpLine {
                    depth: self.depth(id),
                    text: node.text.to_string(),
                    tags: self.tags(id),
                    comments: node.comments().clone(),
                    new_in_config: node.new_in_config,
                }
            })
            .collect();

        Dump { lines }
    }

    /// Reconstructs the tree structure from a [`Dump`].
    ///
    /// Rebuilds nodes and parent-child hierarchy in O(N) using the dump's
    /// depth numbers and a stack of ancestor [`NodeId`]s.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if a node cannot be created or has an invalid parent.
    pub fn load_from_dump(&mut self, dump: &Dump) -> Result<(), TreeError> {
        let mut stack = vec![self.root];
        for line in &dump.lines {
            if line.depth == 0 {
                continue;
            }
            if line.depth <= stack.len() {
                stack.truncate(line.depth);
            }
            let parent_id = *stack.last().unwrap_or(&self.root);
            let child_id = self.add_child(parent_id, &line.text, true, false)?;
            {
                let node = &mut self.arena[child_id];
                if !line.tags.is_empty() {
                    node.tags_mut().clone_from(&line.tags);
                }
                if !line.comments.is_empty() {
                    node.comments_mut().clone_from(&line.comments);
                }
                node.new_in_config = line.new_in_config;
                node.shrink_extras();
            }
            stack.push(child_id);
        }
        Ok(())
    }

    /// Returns rendered lines without comments.
    ///
    /// # Example
    ///
    /// ```
    /// use hier_config_core::{Platform, Tree};
    ///
    /// let tree = Tree::from_str(
    ///     Platform::CiscoIos,
    ///     "interface GigabitEthernet0/1\n  description Uplink\n",
    /// )?;
    ///
    /// assert_eq!(
    ///     tree.dump_simple(false),
    ///     vec!["interface GigabitEthernet0/1", "  description Uplink"]
    /// );
    /// # Ok::<(), hier_config_core::TreeError>(())
    /// ```
    pub fn dump_simple(&self, sectional_exiting: bool) -> Vec<String> {
        self.lines(self.root, sectional_exiting)
    }

    /// Deep structural equality comparison between two subtrees across trees.
    pub fn node_eq(&self, id_a: NodeId, other_tree: &Self, id_b: NodeId) -> bool {
        let node_a = &self.arena[id_a];
        let node_b = &other_tree.arena[id_b];

        if node_a.text != node_b.text || self.tags(id_a) != other_tree.tags(id_b) {
            return false;
        }

        self.children_eq(id_a, other_tree, id_b)
    }

    /// Structural equality comparison for children of two nodes.
    pub fn children_eq(&self, id_a: NodeId, other_tree: &Self, id_b: NodeId) -> bool {
        let children_a = &self.arena[id_a].children;
        let children_b = &other_tree.arena[id_b].children;

        if children_a.is_empty() && children_b.is_empty() {
            return true;
        }
        if children_a.len() != children_b.len() {
            return false;
        }

        // Compare key sets
        let keys_a: BTreeSet<&str> = children_a.keys().collect();
        let keys_b: BTreeSet<&str> = children_b.keys().collect();
        if keys_a != keys_b {
            return false;
        }

        let sorted_a = self.sorted_children(id_a);
        let sorted_b = other_tree.sorted_children(id_b);

        sorted_a
            .into_iter()
            .zip(sorted_b)
            .all(|(ca, cb)| self.node_eq(ca, other_tree, cb))
    }
}

/// Pre-order depth-first iterator over descendant [`NodeId`]s in insertion order.
#[derive(Debug)]
pub struct Descendants<'a> {
    tree: &'a Tree,
    stack: Vec<std::slice::Iter<'a, NodeId>>,
}

impl<'a> Descendants<'a> {
    pub(crate) fn new(tree: &'a Tree, root: NodeId) -> Self {
        let mut stack = Vec::with_capacity(8);
        if let Some(node) = tree.arena.get(root) {
            let slice = node.children.as_slice();
            if !slice.is_empty() {
                stack.push(slice.iter());
            }
        }
        Self { tree, stack }
    }
}

impl Iterator for Descendants<'_> {
    type Item = NodeId;

    fn next(&mut self) -> Option<Self::Item> {
        while let Some(top) = self.stack.last_mut() {
            if let Some(&child_id) = top.next() {
                if let Some(child_node) = self.tree.arena.get(child_id) {
                    let child_slice = child_node.children.as_slice();
                    if !child_slice.is_empty() {
                        self.stack.push(child_slice.iter());
                    }
                }
                return Some(child_id);
            }
            self.stack.pop();
        }
        None
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        (0, Some(self.tree.arena.len()))
    }
}

#[derive(Debug)]
enum SortedFrame<'a> {
    Slice(std::slice::Iter<'a, NodeId>),
    Vec(std::vec::IntoIter<NodeId>),
}

/// Pre-order depth-first iterator over descendant [`NodeId`]s sorted by `order_weight` at each level.
#[derive(Debug)]
pub struct DescendantsSorted<'a> {
    tree: &'a Tree,
    stack: Vec<SortedFrame<'a>>,
}

impl<'a> DescendantsSorted<'a> {
    pub(crate) fn new(tree: &'a Tree, root: NodeId) -> Self {
        let mut stack = Vec::with_capacity(8);
        if let Some(frame) = Self::frame_for_node(tree, root) {
            stack.push(frame);
        }
        Self { tree, stack }
    }

    fn frame_for_node(tree: &'a Tree, node_id: NodeId) -> Option<SortedFrame<'a>> {
        let node = tree.arena.get(node_id)?;
        let children = node.children.as_slice();
        if children.is_empty() {
            None
        } else if tree.children_already_ordered(children) {
            Some(SortedFrame::Slice(children.iter()))
        } else {
            Some(SortedFrame::Vec(tree.sorted_children(node_id).into_iter()))
        }
    }
}

impl Iterator for DescendantsSorted<'_> {
    type Item = NodeId;

    fn next(&mut self) -> Option<Self::Item> {
        while let Some(top) = self.stack.last_mut() {
            let next_id = match top {
                SortedFrame::Slice(it) => it.next().copied(),
                SortedFrame::Vec(it) => it.next(),
            };
            if let Some(child_id) = next_id {
                if let Some(child_frame) = Self::frame_for_node(self.tree, child_id) {
                    self.stack.push(child_frame);
                }
                return Some(child_id);
            }
            self.stack.pop();
        }
        None
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        (0, Some(self.tree.arena.len()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_duplicate_children_allowed_at_root_by_empty_rule() {
        // A rule with no match_rules describes root's (empty) lineage, so it
        // must permit duplicates directly under root. See netdevops/hier_config#215.
        let mut tree = Tree::for_platform(Platform::Generic);
        tree.driver.rules.parent_allows_duplicate_child.push(
            crate::models::ParentAllowsDuplicateChildRule {
                match_rules: Vec::new(),
            },
        );

        assert!(tree.is_duplicate_child_allowed(tree.root));
        tree.add_child(tree.root, "vlan 10", true, false).unwrap();
        tree.add_child(tree.root, "vlan 10", true, false).unwrap();
        assert_eq!(tree.arena[tree.root].children.len(), 2);
    }

    #[test]
    fn test_duplicate_children_rejected_at_root_without_a_rule() {
        let mut tree = Tree::for_platform(Platform::Generic);
        assert!(!tree.is_duplicate_child_allowed(tree.root));
        tree.add_child(tree.root, "vlan 10", true, false).unwrap();
        assert!(matches!(
            tree.add_child(tree.root, "vlan 10", true, false),
            Err(TreeError::DuplicateChild { .. })
        ));
    }

    #[test]
    fn test_tree_add_child_and_hierarchy() {
        let mut tree = Tree::for_platform(Platform::Generic);
        let iface = tree
            .add_child(tree.root, "interface GigabitEthernet0/1", true, false)
            .unwrap();
        let ip = tree
            .add_child(iface, "ip address 192.168.1.1 255.255.255.0", true, false)
            .unwrap();

        assert_eq!(tree.depth(iface), 1);
        assert_eq!(tree.depth(ip), 2);
        assert_eq!(
            tree.path(ip),
            vec![
                "interface GigabitEthernet0/1",
                "ip address 192.168.1.1 255.255.255.0"
            ]
        );

        let rendered = tree.dump_simple(false);
        assert_eq!(
            rendered,
            vec![
                "interface GigabitEthernet0/1",
                "  ip address 192.168.1.1 255.255.255.0",
            ]
        );
    }

    #[test]
    fn test_tree_duplicate_child_error() {
        let mut tree = Tree::for_platform(Platform::Generic);
        tree.add_child(tree.root, "hostname Router1", true, false)
            .unwrap();
        let err = tree.add_child(tree.root, "hostname Router1", true, false);
        assert!(err.is_err());
        match err.unwrap_err() {
            TreeError::DuplicateChild(path) => assert_eq!(path, vec!["hostname Router1"]),
            other => panic!("unexpected error: {other:?}"),
        }
    }

    #[test]
    fn test_load_from_dump_round_trip() {
        let mut tree = Tree::for_platform(Platform::CiscoIos);
        let iface = tree
            .add_child(tree.root, "interface GigabitEthernet0/1", true, false)
            .unwrap();
        let ip = tree
            .add_child(iface, "ip address 192.168.1.1 255.255.255.0", true, false)
            .unwrap();
        tree.arena[ip].tags_mut().insert("safe".to_string());
        tree.arena[ip]
            .comments_mut()
            .insert("configured by automation".to_string());
        tree.arena[ip].new_in_config = true;

        let dump = tree.dump();
        assert_eq!(dump.lines.len(), 2);
        assert_eq!(dump.lines[0].depth, 1);
        assert_eq!(dump.lines[1].depth, 2);

        let mut restored = Tree::for_platform(Platform::CiscoIos);
        restored.load_from_dump(&dump).unwrap();

        assert_eq!(restored.dump(), dump);
        assert_eq!(restored.dump_simple(false), tree.dump_simple(false));
    }

    #[test]
    fn test_descendants_iterators_and_node_count() {
        let mut tree = Tree::for_platform(Platform::CiscoIos);
        assert_eq!(tree.node_count(tree.root), 0);
        assert_eq!(tree.descendants(tree.root).count(), 0);
        assert_eq!(tree.descendants_sorted(tree.root).count(), 0);

        let iface = tree
            .add_child(tree.root, "interface GigabitEthernet0/1", true, false)
            .unwrap();
        let ip = tree
            .add_child(iface, "ip address 192.168.1.1 255.255.255.0", true, false)
            .unwrap();
        let desc = tree
            .add_child(iface, "description Test Link", true, false)
            .unwrap();
        let vlan = tree.add_child(tree.root, "vlan 10", true, false).unwrap();

        assert_eq!(tree.node_count(tree.root), 4);
        assert_eq!(tree.node_count(iface), 2);
        assert_eq!(tree.node_count(ip), 0);

        let desc_ids: Vec<NodeId> = tree.descendants(tree.root).collect();
        assert_eq!(desc_ids, tree.all_children(tree.root));
        assert_eq!(desc_ids, vec![iface, ip, desc, vlan]);

        let desc_sorted_ids: Vec<NodeId> = tree.descendants_sorted(tree.root).collect();
        assert_eq!(desc_sorted_ids, tree.all_children_sorted(tree.root));

        // Test non-trivial ordering
        tree.arena[desc].order_weight = -10;
        let desc_sorted_weighted: Vec<NodeId> = tree.descendants_sorted(tree.root).collect();
        assert_eq!(desc_sorted_weighted, tree.all_children_sorted(tree.root));
        assert_eq!(desc_sorted_weighted, vec![iface, desc, ip, vlan]);
    }

    #[test]
    fn test_tree_merge() {
        let mut tree1 = Tree::for_platform(Platform::CiscoIos);
        tree1
            .add_children_deep(tree1.root, &["interface GigabitEthernet0/1", "shutdown"])
            .unwrap();

        let mut tree2 = Tree::for_platform(Platform::CiscoIos);
        tree2
            .add_children_deep(
                tree2.root,
                &["interface GigabitEthernet0/1", "description uplink"],
            )
            .unwrap();
        tree2
            .add_children_deep(tree2.root, &["vlan 10", "name USERS"])
            .unwrap();

        tree1.merge(&tree2).unwrap();

        let dumped = tree1.dump_simple(false);
        assert_eq!(
            dumped,
            vec![
                "interface GigabitEthernet0/1",
                "  shutdown",
                "  description uplink",
                "vlan 10",
                "  name USERS",
            ]
        );
    }

    #[test]
    fn test_tree_with_tags() {
        let mut tree = Tree::for_platform(Platform::CiscoIos);
        let iface = tree
            .add_child(tree.root, "interface GigabitEthernet0/1", true, false)
            .unwrap();
        tree.arena[iface].tags_mut().insert("prod".to_string());
        let desc = tree
            .add_child(iface, "description link", true, false)
            .unwrap();
        tree.arena[desc].tags_mut().insert("prod".to_string());
        let shut = tree.add_child(iface, "shutdown", true, false).unwrap();
        tree.arena[shut].tags_mut().insert("maint".to_string());

        let mut tags = BTreeSet::new();
        tags.insert("prod".to_string());

        let filtered = tree.with_tags(&tags).unwrap();
        let dumped = filtered.dump_simple(false);
        assert_eq!(
            dumped,
            vec!["interface GigabitEthernet0/1", "  description link"]
        );
    }

    #[test]
    fn test_tree_add_ancestor_copy_of() {
        let mut src = Tree::for_platform(Platform::CiscoIos);
        let ip = src
            .add_children_deep(
                src.root,
                &["interface Vlan2", "ip address 192.168.1.1 255.255.255.0"],
            )
            .unwrap();

        let mut dst = Tree::for_platform(Platform::CiscoIos);
        let copied = dst.add_ancestor_copy_of(dst.root, &src, ip).unwrap();

        assert_eq!(dst.depth(copied), 2);
        assert_eq!(
            dst.dump_simple(false),
            vec!["interface Vlan2", "  ip address 192.168.1.1 255.255.255.0"]
        );
    }
}
