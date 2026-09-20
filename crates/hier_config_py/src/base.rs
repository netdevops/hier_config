//! Base class `PyHConfigBase` wrapping a node in the shared configuration tree.

use std::collections::BTreeSet;
use std::sync::Arc;

use hier_config_core::models::Instance;
use hier_config_core::{MatchRule, NodeId, StringPattern, TextStyle};
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PyString, PyTuple};

use crate::errors::to_py_err;
use crate::tree::{PyRwLockExt, SharedTree, ensure_live};

/// Collects an iterable string attribute, ignoring anything that is not a string.
fn collect_str_attr(item: &Bound<'_, PyAny>, name: &str) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    if let Ok(attr) = item.getattr(name) {
        for value in attr.try_iter().into_iter().flatten().flatten() {
            if let Ok(s) = value.extract::<String>() {
                out.insert(s);
            }
        }
    }
    out
}

/// Wraps an already-materialized batch of handles in an immutable Python sequence.
///
/// The results are fully materialized before this is called, so there is nothing to
/// stream. Returning a real sequence lets callers use `len()`, indexing and repeated
/// iteration, and skips the per-call generator frame that the previous implementation
/// paid for on every traversal.
pub(crate) fn items_sequence(py: Python<'_>, items: Vec<Py<PyAny>>) -> PyResult<Py<PyAny>> {
    Ok(PyTuple::new(py, items)?.into_any().unbind())
}

/// Abstract base class for the hierarchical configuration tree.
///
/// Both `HConfig` (the root) and `HConfigChild` (individual nodes) inherit from
/// this class.  It provides the shared tree-manipulation API: adding, searching,
/// and diffing children, as well as the `_future` / `_config_to_get_to` algorithms
/// that power `WorkflowRemediation`.
#[pyo3_stub_gen::derive::gen_stub_pyclass]
#[pyclass(
    subclass,
    weakref,
    module = "hier_config._hier_config_rust",
    name = "HConfigBase"
)]
#[derive(Debug)]
pub struct PyHConfigBase {
    pub tree: Arc<SharedTree>,
    pub node_id: NodeId,
}

impl PyHConfigBase {
    pub(crate) fn read_tree(
        &self,
    ) -> PyResult<std::sync::RwLockReadGuard<'_, hier_config_core::Tree>> {
        self.tree.read_node(self.node_id)
    }

    pub(crate) fn write_tree(
        &self,
    ) -> PyResult<std::sync::RwLockWriteGuard<'_, hier_config_core::Tree>> {
        self.tree.write_node(self.node_id)
    }

    pub(crate) fn ensure_live(&self) -> PyResult<()> {
        drop(self.read_tree()?);
        Ok(())
    }

    /// Copies Python-supplied `instances` into the native tree before rendering.
    ///
    /// Only the subtree actually being rendered is visited, and every Python
    /// call is made with no lock held: arbitrary Python code runs during
    /// `getattr`, and if it reads back from the tree while the tree write lock
    /// were held the call would deadlock.
    pub(crate) fn sync_instances(&self, py: Python<'_>) -> PyResult<()> {
        // Fast path: nothing has ever set `instances`, which is the common case.
        let handles: Vec<(NodeId, Py<PyList>)> = {
            let data_map = self.tree.node_data.read_py()?;
            if data_map.is_empty() {
                return Ok(());
            }
            let scope: Vec<NodeId> = {
                let tree = self.read_tree()?;
                std::iter::once(self.node_id)
                    .chain(tree.all_children(self.node_id))
                    .collect()
            };
            scope
                .into_iter()
                .filter_map(|nid| {
                    data_map
                        .get(&nid)
                        .and_then(|d| d.instances.as_ref())
                        .map(|list| (nid, list.clone_ref(py)))
                })
                .collect()
        };
        if handles.is_empty() {
            return Ok(());
        }

        // No locks are held here, so Python properties may read the tree freely.
        let mut converted: Vec<(NodeId, Vec<Instance>)> = Vec::with_capacity(handles.len());
        for (nid, list) in handles {
            let mut instances = Vec::new();
            for item in list.bind(py).iter() {
                let id: u64 = item.getattr("id").and_then(|v| v.extract()).unwrap_or(0);
                let comments = collect_str_attr(&item, "comments");
                let tags = collect_str_attr(&item, "tags");
                instances.push(Instance { id, comments, tags });
            }
            converted.push((nid, instances));
        }

        let mut tree = self.write_tree()?;
        for (nid, instances) in converted {
            if let Some(node) = tree.arena.get_mut(nid) {
                *node.instances_mut() = instances;
            }
        }
        Ok(())
    }

    pub fn text(&self) -> PyResult<String> {
        let tree = self.read_tree()?;
        Ok(tree
            .arena
            .get(self.node_id)
            .map_or_else(String::new, |n| n.text.to_string()))
    }

    pub fn set_text(&self, text: &str) -> PyResult<()> {
        let mut tree = self.write_tree()?;
        tree.set_text(self.node_id, text);
        Ok(())
    }
}

#[pyo3_stub_gen::derive::gen_stub_pymethods]
#[pymethods]
impl PyHConfigBase {
    #[new]
    #[gen_stub(override_return_type(type_repr="typing_extensions.Self", imports=("typing_extensions")))]
    fn new() -> PyResult<Self> {
        Err(PyTypeError::new_err(
            "HConfigBase is an abstract base class and cannot be instantiated directly",
        ))
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="int", imports=()))]
    /// Distance from the root of the configuration tree.
    pub fn depth(&self) -> PyResult<usize> {
        let tree = self.read_tree()?;
        Ok(tree.depth(self.node_id))
    }

    #[gen_stub(override_return_type(type_repr="collections.abc.Iterator[str]", imports=("collections.abc")))]
    pub fn path(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let path = self.read_tree()?.path(self.node_id);
        Ok(PyTuple::new(py, path)?.try_iter()?.into_any().unbind())
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="bool", imports=()))]
    /// True if there are no children and is not an instance of `HConfig`.
    pub fn is_leaf(&self) -> PyResult<bool> {
        let tree = self.read_tree()?;
        Ok(tree
            .arena
            .get(self.node_id)
            .is_some_and(hier_config_core::Node::is_leaf))
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="bool", imports=()))]
    /// True if there are children or is an instance of `HConfig`.
    pub fn is_branch(&self) -> PyResult<bool> {
        let tree = self.read_tree()?;
        Ok(tree
            .arena
            .get(self.node_id)
            .is_some_and(hier_config_core::Node::is_branch))
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="frozenset[str]", imports=()))]
    /// Recursive access to tags on all leaf nodes.
    pub fn tags(&self, py: Python<'_>) -> PyResult<Py<PyFrozenSet>> {
        let tree = self.read_tree()?;
        let tag_set = tree.tags(self.node_id);
        let py_elements: Vec<Bound<'_, PyString>> =
            tag_set.into_iter().map(|t| PyString::new(py, &t)).collect();
        PyFrozenSet::new(py, &py_elements).map(Bound::unbind)
    }

    #[setter]
    pub fn set_tags(
        &self,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str]", imports=("collections.abc")))]
        value: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let tags = extract_strings(value)?;
        let tag_set: BTreeSet<String> = tags.into_iter().collect();
        let mut tree = self.write_tree()?;
        tree.set_tags(self.node_id, tag_set);
        Ok(())
    }

    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    /// Add a tag to self._tags on all leaf nodes.
    pub fn tags_add(
        &self,
        #[gen_stub(override_type(type_repr="str | collections.abc.Iterable[str]", imports=("collections.abc")))]
        tag: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let tags = extract_strings(tag)?;
        let tag_refs: Vec<&str> = tags.iter().map(String::as_str).collect();
        let mut tree = self.write_tree()?;
        tree.tags_add(self.node_id, &tag_refs);
        Ok(())
    }

    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    /// Remove a tag from self._tags on all leaf nodes.
    pub fn tags_remove(
        &self,
        #[gen_stub(override_type(type_repr="str | collections.abc.Iterable[str]", imports=("collections.abc")))]
        tag: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let tags = extract_strings(tag)?;
        let tag_refs: Vec<&str> = tags.iter().map(String::as_str).collect();
        let mut tree = self.write_tree()?;
        if let Ok(single_tag) = tag.extract::<String>() {
            let leaves = if tree.arena[self.node_id].is_leaf() && self.node_id != tree.root {
                vec![self.node_id]
            } else {
                tree.all_children(self.node_id)
                    .into_iter()
                    .filter(|&id| tree.arena[id].is_leaf())
                    .collect()
            };
            for id in leaves {
                if !tree.tags(id).contains(&single_tag) {
                    return Err(pyo3::exceptions::PyKeyError::new_err(single_tag));
                }
                tree.tags_remove(id, &tag_refs);
            }
        } else {
            tree.tags_remove(self.node_id, &tag_refs);
        }
        Ok(())
    }

    /// v4 name for `tags_add()`.
    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn add_tags(
        &self,
        #[gen_stub(override_type(type_repr="str | collections.abc.Iterable[str]", imports=("collections.abc")))]
        tag: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        self.tags_add(tag)
    }

    /// v4 name for `tags_remove()`.
    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn remove_tags(
        &self,
        #[gen_stub(override_type(type_repr="str | collections.abc.Iterable[str]", imports=("collections.abc")))]
        tag: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        self.tags_remove(tag)
    }

    /// v4 name for `cisco_style_text()`.
    #[pyo3(signature = (style = None, tag = None))]
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    pub fn indented_text(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="hier_config.models.TextStyle | None", imports=("hier_config.models")))]
        style: Option<&str>,
        #[gen_stub(override_type(type_repr="str | None", imports=()))] tag: Option<&str>,
    ) -> PyResult<String> {
        self.cisco_style_text(py, style, tag)
    }

    #[pyo3(signature = (style = None, tag = None))]
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    /// Return a Cisco style formated line i.e. `indentation_level` + text ! comments.
    pub fn cisco_style_text(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="hier_config.models.TextStyle | None", imports=("hier_config.models")))]
        style: Option<&str>,
        #[gen_stub(override_type(type_repr="str | None", imports=()))] tag: Option<&str>,
    ) -> PyResult<String> {
        self.ensure_live()?;
        self.sync_instances(py)?;
        let parsed_style = match style {
            Some("merged") => TextStyle::Merged,
            Some("with_comments") => TextStyle::WithComments,
            _ => TextStyle::WithoutComments,
        };
        let tree = self.read_tree()?;
        Ok(tree.cisco_style_text(self.node_id, parsed_style, tag))
    }

    #[pyo3(signature = (text, *, return_if_present = false, check_if_present = true))]
    #[gen_stub(override_return_type(type_repr="HConfigChild", imports=()))]
    /// Add a child instance of `HConfigChild`.
    pub fn add_child(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="str", imports=()))] text: &str,
        #[gen_stub(override_type(type_repr="bool", imports=()))] return_if_present: bool,
        #[gen_stub(override_type(type_repr="bool", imports=()))] check_if_present: bool,
    ) -> PyResult<Py<PyAny>> {
        let child_id = {
            let mut tree = self.write_tree()?;
            tree.add_child(self.node_id, text, check_if_present, return_if_present)
                .map_err(to_py_err)?
        };

        let child = SharedTree::get_or_create_child(&self.tree, py, child_id, None)?;
        Ok(child.into_any())
    }

    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    /// Add child instances of `HConfigChild`.
    pub fn add_children(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str]", imports=("collections.abc")))]
        lines: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        self.ensure_live()?;
        for line in lines.try_iter()? {
            let text: String = line?.extract()?;
            self.add_child(py, &text, false, true)?;
        }
        Ok(())
    }

    #[pyo3(signature = (child_to_add, *, merged = false))]
    #[gen_stub(override_return_type(type_repr="HConfigChild", imports=()))]
    /// Add a nested copy of a child to self.
    pub fn add_deep_copy_of(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="HConfigChild", imports=()))] child_to_add: &Bound<
            '_,
            PyAny,
        >,
        #[gen_stub(override_type(type_repr="bool", imports=()))] merged: bool,
    ) -> PyResult<Py<PyAny>> {
        let new_child = self.add_shallow_copy_of(py, child_to_add, merged)?;
        let new_child_bound = new_child.bind(py);
        let children = child_to_add.getattr("children")?;
        for child in children.try_iter()? {
            let child_item = child?;
            let kwargs = PyDict::new(py);
            kwargs.set_item("merged", merged)?;
            new_child_bound.call_method("add_deep_copy_of", (child_item,), Some(&kwargs))?;
        }
        Ok(new_child)
    }

    #[pyo3(signature = (child_to_add, *, merged = false))]
    #[gen_stub(override_return_type(type_repr="HConfigChild", imports=()))]
    /// Add a nested copy of a `child_to_add` to self.children.
    pub fn add_shallow_copy_of(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="HConfigChild", imports=()))] child_to_add: &Bound<
            '_,
            PyAny,
        >,
        #[gen_stub(override_type(type_repr="bool", imports=()))] merged: bool,
    ) -> PyResult<Py<PyAny>> {
        let other_base = child_to_add.extract::<PyRef<'_, Self>>()?;
        let other_node_id = other_base.node_id;
        let other_tree = Arc::clone(&other_base.tree);

        let new_child_id = {
            if Arc::ptr_eq(&self.tree, &other_tree) {
                let mut my_tree = self.write_tree()?;
                ensure_live(&my_tree, other_node_id)?;
                my_tree
                    .add_shallow_copy_within(self.node_id, other_node_id, merged)
                    .map_err(to_py_err)?
            } else {
                let mut my_tree = self.write_tree()?;
                let src_tree = other_tree.read_node(other_node_id)?;
                my_tree
                    .add_shallow_copy_of(self.node_id, &src_tree, other_node_id, merged)
                    .map_err(to_py_err)?
            }
        };

        let child = SharedTree::get_or_create_child(&self.tree, py, new_child_id, None)?;
        let child_bound = child.bind(py);
        if let Ok(src_comments) = child_to_add.getattr("comments")
            && let Ok(dst_comments) = child_bound.getattr("comments")
        {
            let _ = dst_comments.call_method1("update", (src_comments,));
        }
        if merged
            && let Ok(inst) = child_to_add.getattr("instance")
            && let Ok(inst_list) = child_bound.getattr("instances")
        {
            let _ = inst_list.call_method1("append", (inst,));
        }
        Ok(child.into_any())
    }

    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn del_child(
        &self,
        #[gen_stub(override_type(type_repr="HConfigChild", imports=()))] child: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let child_base = child.extract::<PyRef<'_, Self>>()?;
        let child_node_id = child_base.node_id;
        child_base.ensure_live()?;
        if !Arc::ptr_eq(&self.tree, &child_base.tree) {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "child belongs to another configuration",
            ));
        }
        {
            let mut tree = self.write_tree()?;
            ensure_live(&tree, child_node_id)?;
            if tree.arena[child_node_id].parent != Some(self.node_id) {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "node is not a direct child",
                ));
            }
            tree.delete_child(child_node_id);
        }
        self.tree.clear_node_cache(child_node_id)?;
        Ok(())
    }

    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn del_child_by_text(
        &self,
        #[gen_stub(override_type(type_repr="str", imports=()))] text: &str,
    ) -> PyResult<()> {
        let child_to_delete = {
            let tree = self.read_tree()?;
            tree.arena
                .get(self.node_id)
                .and_then(|n| n.children.get(text))
        };
        if let Some(child_id) = child_to_delete {
            let mut tree = self.write_tree()?;
            tree.delete_child(child_id);
            self.tree.clear_node_cache(child_id)?;
        }
        Ok(())
    }

    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn move_child(
        &self,
        #[gen_stub(override_type(type_repr="HConfigChild", imports=()))] child: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let child_base = child.extract::<PyRef<'_, Self>>()?;
        let child_node_id = child_base.node_id;
        child_base.ensure_live()?;
        if !Arc::ptr_eq(&self.tree, &child_base.tree) {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "child belongs to another configuration",
            ));
        }
        let mut tree = self.write_tree()?;
        ensure_live(&tree, child_node_id)?;
        tree.move_child(child_node_id, self.node_id)
            .map_err(to_py_err)
    }

    #[gen_stub(override_return_type(type_repr="HConfigChildren", imports=()))]
    pub fn get_children_object(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        self.ensure_live()?;
        let children = Py::new(
            py,
            crate::children::PyHConfigChildren {
                tree: Arc::clone(&self.tree),
                parent_id: self.node_id,
            },
        )?;
        Ok(children.into_any())
    }

    /// The direct children of this node.
    #[getter(children)]
    #[gen_stub(override_return_type(type_repr="HConfigChildren", imports=()))]
    pub fn children_property(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        self.get_children_object(py)
    }

    #[gen_stub(override_return_type(type_repr="collections.abc.Iterator[HConfigChild]", imports=("collections.abc")))]
    /// Recursively find and yield all children at each hierarchy.
    pub fn all_children(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let node_ids = {
            let tree = self.read_tree()?;
            tree.all_children(self.node_id)
        };
        lazy_children(&self.tree, py, &node_ids)
    }

    #[gen_stub(override_return_type(type_repr="collections.abc.Sequence[HConfigChild]", imports=("collections.abc")))]
    /// Recursively find and yield all children sorted at each hierarchy.
    pub fn all_children_sorted(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let node_ids = {
            let tree = self.read_tree()?;
            tree.all_children_sorted(self.node_id)
        };
        // Sorting has to see every node before the first one can be yielded, so a
        // generator here would only misrepresent the cost. Return the sequence, as
        // `all_children_sorted_by_tags` does.
        let items = SharedTree::get_or_create_children_batch(&self.tree, py, &node_ids)?;
        items_sequence(py, items)
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    #[gen_stub(override_return_type(type_repr="collections.abc.Sequence[HConfigChild]", imports=("collections.abc")))]
    /// Yield all children recursively that match include/exclude tags.
    pub fn all_children_sorted_by_tags(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        include_tags: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        let inc: Vec<String> = include_tags
            .map(extract_strings)
            .transpose()?
            .unwrap_or_default();
        let exc: Vec<String> = exclude_tags
            .map(extract_strings)
            .transpose()?
            .unwrap_or_default();

        let inc_refs: Vec<&str> = inc.iter().map(String::as_str).collect();
        let exc_refs: Vec<&str> = exc.iter().map(String::as_str).collect();

        let node_ids = {
            let tree = self.read_tree()?;
            tree.all_children_sorted_by_tags(self.node_id, &inc_refs, &exc_refs)
        };

        let items = SharedTree::get_or_create_children_batch(&self.tree, py, &node_ids)?;
        items_sequence(py, items)
    }

    #[pyo3(name = "_with_tags")]
    #[gen_stub(override_return_type(type_repr="HConfig | HConfigChild", imports=()))]
    pub fn with_tags_internal(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str]", imports=("collections.abc")))]
        tags: &Bound<'_, PyAny>,
        #[gen_stub(override_type(type_repr="HConfig | HConfigChild", imports=()))]
        new_instance: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        let tag_strings: Vec<String> = extract_strings(tags)?;
        let tag_set: BTreeSet<String> = tag_strings.into_iter().collect();
        let child_ids = {
            let my_tree = self.read_tree()?;
            my_tree
                .arena
                .get(self.node_id)
                .map(|n| n.children.as_slice().to_vec())
                .unwrap_or_default()
        };

        for cid in child_ids {
            let child_tags = {
                let tree = self.tree.read_node(cid)?;
                tree.tags(cid)
            };
            if tag_set.is_subset(&child_tags) {
                let child_obj = SharedTree::get_or_create_child(&self.tree, py, cid, None)?;
                let new_child = new_instance.call_method1("add_shallow_copy_of", (&child_obj,))?;
                let child_bound = child_obj.bind(py);
                child_bound.call_method1("_with_tags", (tags, &new_child))?;
            }
        }
        Ok(new_instance.clone().unbind())
    }

    #[pyo3(signature = (*, equals = None, startswith = None, endswith = None, contains = None, re_search = None))]
    #[gen_stub(override_return_type(type_repr="HConfigChild | None", imports=()))]
    /// Find a child by `text_match` rule. If it is not found, return None.
    pub fn get_child(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="str | (frozenset[str] | set[str]) | None", imports=()))]
        equals: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="str | tuple[str, ...] | None", imports=()))] startswith: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="str | tuple[str, ...] | None", imports=()))]
        endswith: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="str | tuple[str, ...] | None", imports=()))]
        contains: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="str | None", imports=()))] re_search: Option<String>,
    ) -> PyResult<Option<Py<PyAny>>> {
        let rule = parse_match_rule(py, equals, startswith, endswith, contains, re_search)?;
        let child_id = {
            let tree = self.read_tree()?;
            let matches = tree.get_children(self.node_id, &rule);
            matches.into_iter().next()
        };

        if let Some(id) = child_id {
            let child = SharedTree::get_or_create_child(&self.tree, py, id, None)?;
            Ok(Some(child.into_any()))
        } else {
            Ok(None)
        }
    }

    #[pyo3(signature = (*, equals = None, startswith = None, endswith = None, contains = None, re_search = None))]
    #[gen_stub(override_return_type(type_repr="collections.abc.Iterator[HConfigChild]", imports=("collections.abc")))]
    /// Find all children matching a `text_match` rule and return them.
    pub fn get_children(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="str | (frozenset[str] | set[str]) | None", imports=()))]
        equals: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="str | tuple[str, ...] | None", imports=()))] startswith: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="str | tuple[str, ...] | None", imports=()))]
        endswith: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="str | tuple[str, ...] | None", imports=()))]
        contains: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="str | None", imports=()))] re_search: Option<String>,
    ) -> PyResult<Py<PyAny>> {
        let rule = parse_match_rule(py, equals, startswith, endswith, contains, re_search)?;
        let child_ids = {
            let tree = self.read_tree()?;
            tree.get_children(self.node_id, &rule)
        };

        let mut result = Vec::with_capacity(child_ids.len());
        for id in child_ids {
            let child = SharedTree::get_or_create_child(&self.tree, py, id, None)?;
            result.push(child.into_any());
        }
        Ok(PyTuple::new(py, result)?.try_iter()?.into_any().unbind())
    }

    #[gen_stub(override_return_type(type_repr="HConfigChild | None", imports=()))]
    /// Find the first child recursively given a tuple of `MatchRules`.
    pub fn get_child_deep(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="tuple[hier_config.models.MatchRule, ...]", imports=("hier_config.models")))]
        match_rules: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Py<PyAny>>> {
        let parsed_rules = parse_match_rules_seq(py, match_rules)?;
        let child_id = {
            let tree = self.read_tree()?;
            let matches = tree.get_children_deep(self.node_id, &parsed_rules);
            matches.into_iter().next()
        };

        if let Some(id) = child_id {
            let child = SharedTree::get_or_create_child(&self.tree, py, id, None)?;
            Ok(Some(child.into_any()))
        } else {
            Ok(None)
        }
    }

    #[gen_stub(override_return_type(type_repr="collections.abc.Iterator[HConfigChild]", imports=("collections.abc")))]
    /// Find children recursively given a tuple of `MatchRules`.
    pub fn get_children_deep(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="tuple[hier_config.models.MatchRule, ...]", imports=("hier_config.models")))]
        match_rules: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        let parsed_rules = parse_match_rules_seq(py, match_rules)?;
        let child_ids = {
            let tree = self.read_tree()?;
            tree.get_children_deep(self.node_id, &parsed_rules)
        };

        let mut result = Vec::with_capacity(child_ids.len());
        for id in child_ids {
            let child = SharedTree::get_or_create_child(&self.tree, py, id, None)?;
            result.push(child.into_any());
        }
        Ok(PyTuple::new(py, result)?.try_iter()?.into_any().unbind())
    }

    #[gen_stub(override_return_type(type_repr="collections.abc.Iterator[HConfigChild]", imports=("collections.abc")))]
    pub fn lineage(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let lineage_ids = {
            let tree = self.read_tree()?;
            tree.lineage(self.node_id)
        };
        let mut result = Vec::with_capacity(lineage_ids.len());
        for id in lineage_ids {
            let child = SharedTree::get_or_create_child(&self.tree, py, id, None)?;
            result.push(child.into_any());
        }
        Ok(PyTuple::new(py, result)?.try_iter()?.into_any().unbind())
    }

    #[pyo3(signature = (*, sectional_exiting = false))]
    #[gen_stub(override_return_type(type_repr="collections.abc.Iterable[str]", imports=("collections.abc")))]
    pub fn lines(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="bool", imports=()))] sectional_exiting: bool,
    ) -> PyResult<Vec<String>> {
        // Sectional-exit rules may have been reassigned since the parse.
        self.tree.sync_rules_if_stale(py)?;
        let tree = self.read_tree()?;
        Ok(tree.lines(self.node_id, sectional_exiting))
    }

    #[pyo3(signature = (*, sectional_exiting = false))]
    #[gen_stub(override_return_type(type_repr="tuple[str, ...]", imports=()))]
    pub fn dump_simple(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="bool", imports=()))] sectional_exiting: bool,
    ) -> PyResult<Py<PyTuple>> {
        self.tree.sync_rules_if_stale(py)?;
        let tree = self.read_tree()?;
        let lines = tree.lines(self.node_id, sectional_exiting);
        let tuple = PyTuple::new(py, lines)?;
        Ok(tuple.unbind())
    }

    /// v4 name for `dump_simple()`.
    #[pyo3(signature = (*, sectional_exiting = false))]
    #[gen_stub(override_return_type(type_repr="tuple[str, ...]", imports=()))]
    pub fn to_lines(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="bool", imports=()))] sectional_exiting: bool,
    ) -> PyResult<Py<PyTuple>> {
        self.dump_simple(py, sectional_exiting)
    }

    #[gen_stub(override_return_type(type_repr="collections.abc.Iterator[str]", imports=("collections.abc")))]
    /// Yield unified-diff lines comparing self to target.
    ///
    /// Each yielded string is prefixed with ``-`` (present in self but not
    /// target) or ``+`` (present in target but not self), followed by the
    /// appropriate indentation and the command text.
    ///
    /// .. `note::`
    ///     This algorithm does not account for duplicate child differences
    ///     (e.g. two ``endif`` tokens in an IOS-XR route-policy) and does
    ///     not preserve command order where it matters (e.g. ACLs without
    ///     sequence numbers).  Use sequence numbers in ACL entries when
    ///     order is significant.
    ///
    /// Produces output similar to :func:`difflib.unified_diff`.
    pub fn unified_diff(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="HConfig | HConfigChild", imports=()))] target: &Bound<
            '_,
            PyAny,
        >,
    ) -> PyResult<Py<PyAny>> {
        let target_base = target.cast::<Self>()?;
        let lines = {
            let target_base = target_base.borrow();
            let my_tree = self.read_tree()?;
            let other_tree = target_base.read_tree()?;
            my_tree.unified_diff(&other_tree)
        };
        Ok(PyTuple::new(py, lines)?.try_iter()?.into_any().unbind())
    }

    #[gen_stub(override_return_type(type_repr="bool", imports=()))]
    /// Determines if self.text matches a sectional overwrite rule.
    pub fn use_sectional_overwrite(&self) -> PyResult<bool> {
        let tree = self.read_tree()?;
        Ok(tree.use_sectional_overwrite(self.node_id))
    }

    #[gen_stub(override_return_type(type_repr="bool", imports=()))]
    /// Check self's text to see if negation should be handled by
    /// overwriting the section without first negating it.
    pub fn use_sectional_overwrite_without_negation(&self) -> PyResult<bool> {
        let tree = self.read_tree()?;
        Ok(tree.use_sectional_overwrite_without_negation(self.node_id))
    }

    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn delete_sectional_exit(&self) -> PyResult<()> {
        let mut tree = self.write_tree()?;
        tree.delete_sectional_exit(self.node_id);
        Ok(())
    }

    #[gen_stub(override_return_type(type_repr="int", imports=()))]
    /// Return len(self).
    fn __len__(&self) -> PyResult<usize> {
        let tree = self.read_tree()?;
        Ok(tree.node_count(self.node_id))
    }

    #[gen_stub(override_return_type(type_repr="bool", imports=()))]
    /// True if self else False
    fn __bool__(&self) -> PyResult<bool> {
        self.ensure_live()?;
        Ok(true)
    }

    #[gen_stub(override_return_type(type_repr="bool", imports=()))]
    /// Return key in self.
    fn __contains__(
        &self,
        #[gen_stub(override_type(type_repr="str", imports=()))] text: &str,
    ) -> PyResult<bool> {
        let tree = self.read_tree()?;
        Ok(tree
            .arena
            .get(self.node_id)
            .is_some_and(|n| n.children.contains(text)))
    }

    #[gen_stub(override_return_type(type_repr="collections.abc.Iterator[HConfigChild]", imports=("collections.abc")))]
    /// Implement iter(self).
    fn __iter__(&self) -> PyResult<crate::children::PyHConfigChildrenIter> {
        let tree = self.read_tree()?;
        let child_ids = tree
            .arena
            .get(self.node_id)
            .map_or_else(Vec::new, |n| n.children.as_slice().to_vec());
        Ok(crate::children::PyHConfigChildrenIter {
            tree: Arc::clone(&self.tree),
            child_ids,
            index: 0,
        })
    }
}

pub(crate) fn extract_strings(val: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
    if let Ok(s) = val.extract::<String>() {
        return Ok(vec![s]);
    }
    let mut items = Vec::new();
    for item in val.try_iter()? {
        items.push(item?.extract::<String>()?);
    }
    Ok(items)
}

fn parse_rule_value(val: &Bound<'_, PyAny>) -> PyResult<StringPattern> {
    if let Ok(s) = val.extract::<String>() {
        Ok(StringPattern::Single(s))
    } else {
        let strings = extract_strings(val)?;
        Ok(StringPattern::Multiple(strings))
    }
}

pub(crate) fn parse_match_rule(
    _py: Python<'_>,
    equals: Option<&Bound<'_, PyAny>>,
    startswith: Option<&Bound<'_, PyAny>>,
    endswith: Option<&Bound<'_, PyAny>>,
    contains: Option<&Bound<'_, PyAny>>,
    re_search: Option<String>,
) -> PyResult<MatchRule> {
    fn clean<'a>(opt: Option<&'a Bound<'a, PyAny>>) -> Option<&'a Bound<'a, PyAny>> {
        opt.filter(|&v| !v.is_none())
    }
    Ok(MatchRule {
        equals: clean(equals).map(parse_rule_value).transpose()?,
        startswith: clean(startswith).map(parse_rule_value).transpose()?,
        endswith: clean(endswith).map(parse_rule_value).transpose()?,
        contains: clean(contains).map(parse_rule_value).transpose()?,
        re_search,
    })
}

pub(crate) fn parse_match_rules_seq(
    py: Python<'_>,
    rules: &Bound<'_, PyAny>,
) -> PyResult<Vec<MatchRule>> {
    let mut list = Vec::new();
    for rule in rules.try_iter()? {
        let r = rule?;
        let clean_attr = |name: &str| -> Option<Bound<'_, PyAny>> {
            r.getattr(name).ok().filter(|v| !v.is_none())
        };
        let equals = clean_attr("equals");
        let startswith = clean_attr("startswith");
        let endswith = clean_attr("endswith");
        let contains = clean_attr("contains");
        let re_search = clean_attr("re_search").and_then(|v| v.extract().ok());

        list.push(parse_match_rule(
            py,
            equals.as_ref(),
            startswith.as_ref(),
            endswith.as_ref(),
            contains.as_ref(),
            re_search,
        )?);
    }
    Ok(list)
}

/// Wraps `node_ids` as interned children handed back through a real
/// Python generator, matching the documented iterator contract.
fn lazy_children(
    tree: &Arc<SharedTree>,
    py: Python<'_>,
    node_ids: &[NodeId],
) -> PyResult<Py<PyAny>> {
    // Bulk traversal, so take the uncached materializer: interning costs a lock, a
    // hash and a weakref per node, and nothing about a whole-tree walk needs handle
    // identity. See `SharedTree::get_or_create_children_batch`.
    let children = SharedTree::get_or_create_children_batch(tree, py, node_ids)?;
    py.import("hier_config._iterators")?
        .getattr("as_generator")?
        .call1((PyTuple::new(py, children)?,))
        .map(Bound::unbind)
}
