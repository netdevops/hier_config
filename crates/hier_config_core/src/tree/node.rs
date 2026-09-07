use crate::arena::NodeId;
use crate::models::Instance;
use crate::tree::children::Children;
use rustc_hash::{FxBuildHasher, FxHashMap as HashMap};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::sync::Arc;

/// Per-node state that is empty for the overwhelming majority of nodes.
///
/// Tags, comments, facts and instances are populated on a small fraction of a
/// real configuration's lines, but as inline fields every node paid for their
/// empty headers whether or not it used them. Collecting them here lets [`Node`]
/// store a single `Option<Box<NodeExtras>>`, so an unadorned node costs one
/// pointer instead of four collection headers. That shrinks arena inserts,
/// makes `clone` cheaper, and improves cache locality during traversal, which
/// is dominated by nodes carrying none of this.
///
/// Reach it through the accessors on [`Node`] rather than directly; they handle
/// the unset case and allocate lazily on first write.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct NodeExtras {
    pub tags: BTreeSet<String>,
    pub comments: BTreeSet<String>,
    pub instances: Vec<Instance>,
    pub facts: HashMap<String, String>,
}

impl NodeExtras {
    /// Returns true when nothing is populated, so the box can be released.
    fn is_empty(&self) -> bool {
        self.tags.is_empty()
            && self.comments.is_empty()
            && self.instances.is_empty()
            && self.facts.is_empty()
    }
}

static EMPTY_STRINGS: BTreeSet<String> = BTreeSet::new();
static EMPTY_INSTANCES: Vec<Instance> = Vec::new();
static EMPTY_FACTS: HashMap<String, String> = HashMap::with_hasher(FxBuildHasher);

/// A single node in the configuration tree.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Node {
    /// The node's configuration line.
    ///
    /// Shared via `Arc` so that indexing a node under its parent, and cloning a
    /// whole tree, cost a reference-count bump instead of copying every line.
    pub text: Arc<str>,
    pub order_weight: i32,
    pub new_in_config: bool,
    pub parent: Option<NodeId>,
    pub children: Children,
    pub real_indent_level: i32,
    /// Lazily allocated rarely-populated state. Reach it via the accessors.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    extras: Option<Box<NodeExtras>>,
}

/// Compares the *effective* value of every field.
///
/// Hand-written rather than derived because `extras` has two representations
/// for an unadorned node — `None`, and `Some` holding empty collections after
/// something was added and then removed. Those must compare equal, which a
/// derive would get wrong.
impl PartialEq for Node {
    fn eq(&self, other: &Self) -> bool {
        self.text == other.text
            && self.order_weight == other.order_weight
            && self.new_in_config == other.new_in_config
            && self.parent == other.parent
            && self.real_indent_level == other.real_indent_level
            && self.children == other.children
            && self.tags() == other.tags()
            && self.comments() == other.comments()
            && self.instances() == other.instances()
            && self.facts() == other.facts()
    }
}

impl Eq for Node {}

impl Node {
    /// Creates a new Node with given text and parent.
    ///
    /// The text is trimmed before it is shared, so callers never need to trim first.
    pub fn new(text: &str, parent: Option<NodeId>) -> Self {
        Self::from_shared_text(Arc::from(text.trim()), parent)
    }

    /// Creates a new Node from an already-trimmed shared text buffer.
    ///
    /// Use this when the caller also needs the `Arc` (for example to index the node
    /// under its parent) so the line is allocated exactly once.
    pub const fn from_shared_text(text: Arc<str>, parent: Option<NodeId>) -> Self {
        Self {
            text,
            order_weight: 0,
            new_in_config: false,
            parent,
            children: Children::new(),
            real_indent_level: 0,
            extras: None,
        }
    }

    /// Creates a root node (parent = None, `real_indent_level` = -1).
    pub fn root() -> Self {
        Self {
            text: Arc::from(""),
            order_weight: 0,
            new_in_config: false,
            parent: None,
            children: Children::new(),
            real_indent_level: -1,
            extras: None,
        }
    }

    /// Returns true if this node has no children.
    pub const fn is_leaf(&self) -> bool {
        self.children.is_empty()
    }

    /// Returns true if this node has children.
    pub const fn is_branch(&self) -> bool {
        !self.children.is_empty()
    }

    /// Returns the extras block, if anything has ever been written to it.
    pub fn extras(&self) -> Option<&NodeExtras> {
        self.extras.as_deref()
    }

    /// Returns the extras block, allocating it if this is the first write.
    ///
    /// Prefer the field-specific `_mut` accessors; this exists for callers that
    /// need to touch several fields at once.
    pub fn extras_mut(&mut self) -> &mut NodeExtras {
        self.extras.get_or_insert_with(Box::default)
    }

    /// Releases the extras allocation if every field is now empty.
    ///
    /// Call after bulk removals so an emptied node returns to the one-pointer
    /// representation. Correctness never depends on this — [`PartialEq`] treats
    /// `None` and an all-empty block as equal — it only reclaims memory.
    pub fn shrink_extras(&mut self) {
        if self.extras.as_ref().is_some_and(|extras| extras.is_empty()) {
            self.extras = None;
        }
    }

    pub fn tags(&self) -> &BTreeSet<String> {
        self.extras
            .as_ref()
            .map_or(&EMPTY_STRINGS, |extras| &extras.tags)
    }

    pub fn tags_mut(&mut self) -> &mut BTreeSet<String> {
        &mut self.extras_mut().tags
    }

    pub fn comments(&self) -> &BTreeSet<String> {
        self.extras
            .as_ref()
            .map_or(&EMPTY_STRINGS, |extras| &extras.comments)
    }

    pub fn comments_mut(&mut self) -> &mut BTreeSet<String> {
        &mut self.extras_mut().comments
    }

    pub fn instances(&self) -> &[Instance] {
        self.extras
            .as_ref()
            .map_or(&EMPTY_INSTANCES, |extras| &extras.instances)
    }

    pub fn instances_mut(&mut self) -> &mut Vec<Instance> {
        &mut self.extras_mut().instances
    }

    pub fn facts(&self) -> &HashMap<String, String> {
        self.extras
            .as_ref()
            .map_or(&EMPTY_FACTS, |extras| &extras.facts)
    }

    pub fn facts_mut(&mut self) -> &mut HashMap<String, String> {
        &mut self.extras_mut().facts
    }
}
