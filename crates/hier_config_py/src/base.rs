//! Base class `PyHConfigBase` wrapping a node in the shared configuration tree.

use std::collections::BTreeSet;
use std::sync::Arc;

use hier_config_core::{MatchRule, NodeId, StringPattern, TextStyle};
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyString, PyTuple};

use crate::errors::to_py_err;
use crate::tree::SharedTree;

/// Wraps an already-materialized batch of handles in an immutable Python sequence.
///
/// The results are fully materialized before this is called, so there is nothing to
/// stream. Returning a real sequence lets callers use `len()`, indexing and repeated
/// iteration, and skips the per-call generator frame that the previous implementation
/// paid for on every traversal.
pub(crate) fn items_sequence(py: Python<'_>, items: Vec<PyObject>) -> PyResult<PyObject> {
    Ok(PyTuple::new(py, items)?.into_any().unbind())
}

#[pyclass(subclass, weakref, module = "_hier_config_rust", name = "HConfigBase")]
#[derive(Debug)]
pub struct PyHConfigBase {
    pub tree: Arc<SharedTree>,
    pub node_id: NodeId,
}

impl PyHConfigBase {
    pub fn text(&self) -> String {
        let tree = self.tree.tree.read().unwrap();
        tree.arena
            .get(self.node_id)
            .map_or_else(String::new, |n| n.text.to_string())
    }

    pub fn set_text(&self, text: &str) {
        let mut tree = self.tree.tree.write().unwrap();
        if tree.arena.contains(self.node_id) {
            tree.set_text(self.node_id, text);
        }
    }
}

#[pymethods]
impl PyHConfigBase {
    #[new]
    fn new() -> PyResult<Self> {
        Err(PyTypeError::new_err(
            "HConfigBase is an abstract base class and cannot be instantiated directly",
        ))
    }

    pub fn depth(&self) -> usize {
        let tree = self.tree.tree.read().unwrap();
        tree.depth(self.node_id)
    }

    pub fn path(&self) -> Vec<String> {
        let tree = self.tree.tree.read().unwrap();
        tree.path(self.node_id)
    }

    #[getter]
    pub fn is_leaf(&self) -> bool {
        let tree = self.tree.tree.read().unwrap();
        tree.arena
            .get(self.node_id)
            .is_some_and(hier_config_core::Node::is_leaf)
    }

    #[getter]
    pub fn is_branch(&self) -> bool {
        let tree = self.tree.tree.read().unwrap();
        tree.arena
            .get(self.node_id)
            .is_some_and(hier_config_core::Node::is_branch)
    }

    #[getter]
    pub fn tags(&self, py: Python<'_>) -> PyResult<Py<PyFrozenSet>> {
        let tree = self.tree.tree.read().unwrap();
        let tag_set = tree.tags(self.node_id);
        let py_elements: Vec<Bound<'_, PyString>> =
            tag_set.into_iter().map(|t| PyString::new(py, &t)).collect();
        PyFrozenSet::new(py, &py_elements).map(Bound::unbind)
    }

    #[setter]
    pub fn set_tags(&self, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let tags = extract_strings(value)?;
        let tag_set: BTreeSet<String> = tags.into_iter().collect();
        let mut tree = self.tree.tree.write().unwrap();
        tree.set_tags(self.node_id, tag_set);
        Ok(())
    }

    pub fn tags_add(&self, tag_or_tags: &Bound<'_, PyAny>) -> PyResult<()> {
        let tags = extract_strings(tag_or_tags)?;
        let tag_refs: Vec<&str> = tags.iter().map(String::as_str).collect();
        let mut tree = self.tree.tree.write().unwrap();
        tree.tags_add(self.node_id, &tag_refs);
        Ok(())
    }

    pub fn tags_remove(&self, tag_or_tags: &Bound<'_, PyAny>) -> PyResult<()> {
        let tags = extract_strings(tag_or_tags)?;
        let tag_refs: Vec<&str> = tags.iter().map(String::as_str).collect();
        let mut tree = self.tree.tree.write().unwrap();
        tree.tags_remove(self.node_id, &tag_refs);
        Ok(())
    }

    #[pyo3(signature = (style = None, tag = None))]
    pub fn cisco_style_text(
        &self,
        py: Python<'_>,
        style: Option<&str>,
        tag: Option<&str>,
    ) -> String {
        // Sync any comments and instances from node_data into the Rust tree
        {
            let data_map = self.tree.node_data.read().unwrap();
            let mut tree = self.tree.tree.write().unwrap();
            for (nid, pdata) in data_map.iter() {
                if let Some(node) = tree.arena.get_mut(*nid) {
                    if let Some(comments) = &pdata.comments {
                        for item in comments.bind(py).iter() {
                            if let Ok(c_str) = item.extract::<String>() {
                                node.comments_mut().insert(c_str);
                            }
                        }
                    }
                    let Some(instances) = &pdata.instances else {
                        continue;
                    };
                    let list_bound = instances.bind(py);
                    node.instances_mut().clear();
                    for item in list_bound.iter() {
                        let id: u64 = item.getattr("id").and_then(|v| v.extract()).unwrap_or(0);
                        let mut inst_comments = BTreeSet::new();
                        if let Ok(c_attr) = item.getattr("comments") {
                            for c in c_attr.try_iter().into_iter().flatten().flatten() {
                                if let Ok(s) = c.extract::<String>() {
                                    inst_comments.insert(s);
                                }
                            }
                        }
                        let mut inst_tags = BTreeSet::new();
                        if let Ok(t_attr) = item.getattr("tags") {
                            for t in t_attr.try_iter().into_iter().flatten().flatten() {
                                if let Ok(s) = t.extract::<String>() {
                                    inst_tags.insert(s);
                                }
                            }
                        }
                        node.instances_mut()
                            .push(hier_config_core::models::Instance {
                                id,
                                comments: inst_comments,
                                tags: inst_tags,
                            });
                    }
                }
            }
        }
        let parsed_style = match style {
            Some("merged") => TextStyle::Merged,
            Some("with_comments") => TextStyle::WithComments,
            _ => TextStyle::WithoutComments,
        };
        let tree = self.tree.tree.read().unwrap();
        tree.cisco_style_text(self.node_id, parsed_style, tag)
    }

    #[pyo3(signature = (text, *, return_if_present = false, check_if_present = true))]
    pub fn add_child(
        &self,
        py: Python<'_>,
        text: &str,
        return_if_present: bool,
        check_if_present: bool,
    ) -> PyResult<PyObject> {
        let child_id = {
            let mut tree = self.tree.tree.write().unwrap();
            tree.add_child(self.node_id, text, check_if_present, return_if_present)
                .map_err(to_py_err)?
        };

        let child = SharedTree::get_or_create_child(&self.tree, py, child_id, None)?;
        Ok(child.into_any())
    }

    pub fn add_children(&self, py: Python<'_>, lines: &Bound<'_, PyAny>) -> PyResult<()> {
        for line in lines.try_iter()? {
            let text: String = line?.extract()?;
            self.add_child(py, &text, false, true)?;
        }
        Ok(())
    }

    #[pyo3(signature = (child_to_add, *, merged = false))]
    pub fn add_deep_copy_of(
        &self,
        py: Python<'_>,
        child_to_add: &Bound<'_, PyAny>,
        merged: bool,
    ) -> PyResult<PyObject> {
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
    pub fn add_shallow_copy_of(
        &self,
        py: Python<'_>,
        child_to_add: &Bound<'_, PyAny>,
        merged: bool,
    ) -> PyResult<PyObject> {
        let other_base = child_to_add.extract::<PyRef<'_, Self>>()?;
        let other_node_id = other_base.node_id;
        let other_tree = Arc::clone(&other_base.tree);

        let new_child_id = {
            if Arc::ptr_eq(&self.tree, &other_tree) {
                let mut my_tree = self.tree.tree.write().unwrap();
                my_tree
                    .add_shallow_copy_within(self.node_id, other_node_id, merged)
                    .map_err(to_py_err)?
            } else {
                let mut my_tree = self.tree.tree.write().unwrap();
                let src_tree = other_tree.tree.read().unwrap();
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

    pub fn del_child(&self, child: &Bound<'_, PyAny>) -> PyResult<()> {
        let child_base = child.extract::<PyRef<'_, Self>>()?;
        let child_node_id = child_base.node_id;
        {
            let mut tree = self.tree.tree.write().unwrap();
            tree.delete_child(child_node_id);
        }
        self.tree.clear_node_cache(child_node_id);
        Ok(())
    }

    pub fn del_child_by_text(&self, text: &str) {
        let child_to_delete = {
            let tree = self.tree.tree.read().unwrap();
            tree.arena
                .get(self.node_id)
                .and_then(|n| n.children.get(text))
        };
        if let Some(child_id) = child_to_delete {
            let mut tree = self.tree.tree.write().unwrap();
            tree.delete_child(child_id);
            self.tree.clear_node_cache(child_id);
        }
    }

    pub fn move_child(&self, child: &Bound<'_, PyAny>) -> PyResult<()> {
        let child_base = child.extract::<PyRef<'_, Self>>()?;
        let child_node_id = child_base.node_id;
        let mut tree = self.tree.tree.write().unwrap();
        tree.move_child(child_node_id, self.node_id)
            .map_err(to_py_err)
    }

    pub fn get_children_object(&self, py: Python<'_>) -> PyResult<PyObject> {
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
    pub fn children_property(&self, py: Python<'_>) -> PyResult<PyObject> {
        self.get_children_object(py)
    }

    pub fn all_children(&self, py: Python<'_>) -> PyResult<PyObject> {
        let node_ids = {
            let tree = self.tree.tree.read().unwrap();
            tree.all_children(self.node_id)
        };
        let result = SharedTree::get_or_create_children_batch(&self.tree, py, &node_ids)?;
        items_sequence(py, result)
    }

    pub fn all_children_sorted(&self, py: Python<'_>) -> PyResult<PyObject> {
        let node_ids = {
            let tree = self.tree.tree.read().unwrap();
            tree.all_children_sorted(self.node_id)
        };
        let result = SharedTree::get_or_create_children_batch(&self.tree, py, &node_ids)?;
        items_sequence(py, result)
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    pub fn all_children_sorted_by_tags(
        &self,
        py: Python<'_>,
        include_tags: Option<&Bound<'_, PyAny>>,
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyObject> {
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
            let tree = self.tree.tree.read().unwrap();
            tree.all_children_sorted_by_tags(self.node_id, &inc_refs, &exc_refs)
        };

        let items = SharedTree::get_or_create_children_batch(&self.tree, py, &node_ids)?;
        items_sequence(py, items)
    }

    #[pyo3(name = "_with_tags")]
    pub fn with_tags_internal(
        &self,
        py: Python<'_>,
        tags: &Bound<'_, PyAny>,
        new_instance: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let tag_strings: Vec<String> = extract_strings(tags)?;
        let tag_set: BTreeSet<String> = tag_strings.into_iter().collect();
        let child_ids = {
            let my_tree = self.tree.tree.read().unwrap();
            my_tree
                .arena
                .get(self.node_id)
                .map(|n| n.children.as_slice().to_vec())
                .unwrap_or_default()
        };

        for cid in child_ids {
            let child_tags = {
                let tree = self.tree.tree.read().unwrap();
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
    pub fn get_child(
        &self,
        py: Python<'_>,
        equals: Option<&Bound<'_, PyAny>>,
        startswith: Option<&Bound<'_, PyAny>>,
        endswith: Option<&Bound<'_, PyAny>>,
        contains: Option<&Bound<'_, PyAny>>,
        re_search: Option<String>,
    ) -> PyResult<Option<PyObject>> {
        let rule = parse_match_rule(py, equals, startswith, endswith, contains, re_search)?;
        let child_id = {
            let tree = self.tree.tree.read().unwrap();
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
    pub fn get_children(
        &self,
        py: Python<'_>,
        equals: Option<&Bound<'_, PyAny>>,
        startswith: Option<&Bound<'_, PyAny>>,
        endswith: Option<&Bound<'_, PyAny>>,
        contains: Option<&Bound<'_, PyAny>>,
        re_search: Option<String>,
    ) -> PyResult<Vec<PyObject>> {
        let rule = parse_match_rule(py, equals, startswith, endswith, contains, re_search)?;
        let child_ids = {
            let tree = self.tree.tree.read().unwrap();
            tree.get_children(self.node_id, &rule)
        };

        let mut result = Vec::with_capacity(child_ids.len());
        for id in child_ids {
            let child = SharedTree::get_or_create_child(&self.tree, py, id, None)?;
            result.push(child.into_any());
        }
        Ok(result)
    }

    pub fn get_child_deep(
        &self,
        py: Python<'_>,
        rules: &Bound<'_, PyAny>,
    ) -> PyResult<Option<PyObject>> {
        let parsed_rules = parse_match_rules_seq(py, rules)?;
        let child_id = {
            let tree = self.tree.tree.read().unwrap();
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

    pub fn get_children_deep(
        &self,
        py: Python<'_>,
        rules: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<PyObject>> {
        let parsed_rules = parse_match_rules_seq(py, rules)?;
        let child_ids = {
            let tree = self.tree.tree.read().unwrap();
            tree.get_children_deep(self.node_id, &parsed_rules)
        };

        let mut result = Vec::with_capacity(child_ids.len());
        for id in child_ids {
            let child = SharedTree::get_or_create_child(&self.tree, py, id, None)?;
            result.push(child.into_any());
        }
        Ok(result)
    }

    pub fn lineage(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let lineage_ids = {
            let tree = self.tree.tree.read().unwrap();
            tree.lineage(self.node_id)
        };
        let mut result = Vec::with_capacity(lineage_ids.len());
        for id in lineage_ids {
            let child = SharedTree::get_or_create_child(&self.tree, py, id, None)?;
            result.push(child.into_any());
        }
        Ok(result)
    }

    #[pyo3(signature = (*, sectional_exiting = false))]
    pub fn lines(&self, sectional_exiting: bool) -> Vec<String> {
        let tree = self.tree.tree.read().unwrap();
        tree.lines(self.node_id, sectional_exiting)
    }

    #[pyo3(signature = (*, sectional_exiting = false))]
    pub fn dump_simple(&self, py: Python<'_>, sectional_exiting: bool) -> PyResult<Py<PyTuple>> {
        let tree = self.tree.tree.read().unwrap();
        let lines = tree.lines(self.node_id, sectional_exiting);
        let tuple = PyTuple::new(py, lines)?;
        Ok(tuple.unbind())
    }

    pub fn unified_diff(&self, target: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
        let target_base = target.downcast::<Self>()?;
        let target_tree = Arc::clone(&target_base.borrow().tree);

        let my_tree = self.tree.tree.read().unwrap();
        let other_tree = target_tree.tree.read().unwrap();

        Ok(my_tree.unified_diff(&other_tree))
    }

    pub fn use_sectional_overwrite(&self) -> bool {
        let tree = self.tree.tree.read().unwrap();
        tree.use_sectional_overwrite(self.node_id)
    }

    pub fn use_sectional_overwrite_without_negation(&self) -> bool {
        let tree = self.tree.tree.read().unwrap();
        tree.use_sectional_overwrite_without_negation(self.node_id)
    }

    pub fn delete_sectional_exit(&self) {
        let mut tree = self.tree.tree.write().unwrap();
        tree.delete_sectional_exit(self.node_id);
    }

    fn __len__(&self) -> usize {
        let tree = self.tree.tree.read().unwrap();
        tree.all_children(self.node_id).len()
    }

    const fn __bool__(&self) -> bool {
        _ = self.node_id;
        true
    }

    fn __contains__(&self, text: &str) -> bool {
        let tree = self.tree.tree.read().unwrap();
        tree.arena
            .get(self.node_id)
            .is_some_and(|n| n.children.contains(text))
    }

    fn __iter__(&self) -> crate::children::PyHConfigChildrenIter {
        let tree = self.tree.tree.read().unwrap();
        let child_ids = tree
            .arena
            .get(self.node_id)
            .map_or_else(Vec::new, |n| n.children.as_slice().to_vec());
        crate::children::PyHConfigChildrenIter {
            tree: Arc::clone(&self.tree),
            child_ids,
            index: 0,
        }
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
