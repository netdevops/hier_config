//! `PyHConfigChild` representing a single configuration node in Python.

use std::sync::Arc;

use pyo3::IntoPyObjectExt;
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PySet};

use crate::base::PyHConfigBase;
use crate::errors::to_py_err;
use crate::root::PyHConfig;
use crate::tree::{PyRwLockExt, SharedTree, ensure_live};

#[pyclass(extends = PyHConfigBase, subclass, module = "_hier_config_rust", name = "HConfigChild")]
#[derive(Debug)]
pub struct PyHConfigChild {
    pub parent_handle: Option<PyObject>,
}

#[pymethods]
impl PyHConfigChild {
    #[new]
    #[pyo3(signature = (parent, text))]
    fn new(
        _py: Python<'_>,
        parent: &Bound<'_, PyAny>,
        text: &str,
    ) -> PyResult<(Self, PyHConfigBase)> {
        let parent_base = parent.downcast::<PyHConfigBase>()?;
        let parent_node_id = parent_base.borrow().node_id;
        let shared_tree = Arc::clone(&parent_base.borrow().tree);

        let child_id = {
            let mut tree = shared_tree.write_node(parent_node_id)?;
            tree.add_child(parent_node_id, text.trim(), false, true)
                .map_err(to_py_err)?
        };

        Ok((
            Self {
                parent_handle: Some(parent.clone().unbind()),
            },
            PyHConfigBase {
                tree: shared_tree,
                node_id: child_id,
            },
        ))
    }

    #[getter]
    pub fn text(slf: PyRef<'_, Self>) -> PyResult<String> {
        slf.as_ref().text()
    }

    #[setter]
    pub fn set_text(slf: PyRef<'_, Self>, text: &str) -> PyResult<()> {
        slf.as_ref().set_text(text)
    }

    #[getter]
    pub fn indentation(slf: PyRef<'_, Self>) -> PyResult<String> {
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        Ok(tree.indentation(base.node_id))
    }

    #[getter]
    pub fn parent(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        let parent_id = {
            let tree = base.read_tree()?;
            tree.arena.get(base.node_id).and_then(|n| n.parent)
        };
        if let Some(pid) = parent_id {
            if let Some(ref handle) = slf.parent_handle
                && let Ok(parent_base) = handle.extract::<PyRef<'_, PyHConfigBase>>(py)
                && Arc::ptr_eq(&base.tree, &parent_base.tree)
                && parent_base.node_id == pid
            {
                return Ok(handle.clone_ref(py));
            }
            let is_root = {
                let tree_read = base.read_tree()?;
                pid == tree_read.root
            };
            if is_root {
                {
                    let handle = base.tree.root_handle.read_py()?;
                    if let Some(ref root_ref) = *handle {
                        return Ok(root_ref.clone_ref(py));
                    }
                }
                let driver = if let Some(ref drv) = *base.tree.driver_obj.read_py()? {
                    drv.clone_ref(py)
                } else {
                    PyHConfig::get_default_driver(py, base.tree.platform)?
                };
                let root_id = base.read_tree()?.root;
                let hconfig = Py::new(
                    py,
                    (
                        PyHConfig {
                            driver_obj: driver.clone_ref(py),
                        },
                        PyHConfigBase {
                            tree: Arc::clone(&base.tree),
                            node_id: root_id,
                        },
                    ),
                )?;
                let obj = hconfig.into_any();
                *base.tree.root_handle.write_py()? = Some(obj.clone_ref(py));
                return Ok(obj);
            }
            let parent_child = SharedTree::get_or_create_child(&base.tree, py, pid, None)?;
            Ok(parent_child.into_any())
        } else {
            Ok(py.None())
        }
    }

    #[setter]
    pub fn set_parent(slf: &Bound<'_, Self>, new_parent: &Bound<'_, PyAny>) -> PyResult<()> {
        Self::move_(slf, new_parent)
    }

    #[getter]
    pub fn root(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        base.ensure_live()?;
        {
            let handle = base.tree.root_handle.read_py()?;
            if let Some(ref root_ref) = *handle {
                return Ok(root_ref.clone_ref(py));
            }
        }
        let driver = if let Some(ref drv) = *base.tree.driver_obj.read_py()? {
            drv.clone_ref(py)
        } else {
            PyHConfig::get_default_driver(py, base.tree.platform)?
        };
        let root_id = base.read_tree()?.root;
        let hconfig = Py::new(
            py,
            (
                PyHConfig {
                    driver_obj: driver.clone_ref(py),
                },
                PyHConfigBase {
                    tree: Arc::clone(&base.tree),
                    node_id: root_id,
                },
            ),
        )?;
        let obj = hconfig.into_any();
        *base.tree.root_handle.write_py()? = Some(obj.clone_ref(py));
        Ok(obj)
    }

    pub fn _default(slf: PyRef<'_, Self>) -> PyResult<PyRef<'_, Self>> {
        let py = slf.py();
        let text_wo_neg = {
            let base = slf.as_ref();
            let text = base.text()?;
            let tree = base.read_tree()?;
            let neg_prefix = &tree.driver.negation_prefix;
            text.strip_prefix(neg_prefix).unwrap_or(&text).to_string()
        };
        let new_text = format!("default {text_wo_neg}");
        let slf_obj = slf.into_py_any(py)?;
        let slf_bound = slf_obj.bind(py);
        slf_bound.setattr("text", new_text)?;
        slf_bound.extract()
    }

    pub fn use_default_for_negation(
        slf: PyRef<'_, Self>,
        config: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let py = slf.py();
        let base = slf.as_ref();
        base.ensure_live()?;
        base.tree.sync_rules(py)?;
        let target_base = config.extract::<PyRef<'_, PyHConfigBase>>()?;
        let target_nid = target_base.node_id;
        let rules = base.read_tree()?.driver.rules.negation_default_when.clone();
        let target_tree = target_base.read_tree()?;
        for rule in &rules {
            if target_tree.is_lineage_match(target_nid, &rule.match_rules) {
                return Ok(true);
            }
        }
        Ok(false)
    }

    pub fn line_inclusion_test(
        slf: PyRef<'_, Self>,
        include_tags: &Bound<'_, PyAny>,
        exclude_tags: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let inc: Vec<String> = crate::base::extract_strings(include_tags)?;
        let exc: Vec<String> = crate::base::extract_strings(exclude_tags)?;
        let base = slf.as_ref();
        let tags = {
            let tree = base.read_tree()?;
            tree.tags(base.node_id)
        };
        let mut include_line = false;
        if !inc.is_empty() {
            include_line = inc.iter().any(|t| tags.contains(t));
        }
        if !exc.is_empty() && (include_line || inc.is_empty()) {
            return Ok(!exc.iter().any(|t| tags.contains(t)));
        }
        Ok(include_line)
    }

    pub fn add_children_deep(slf: PyRef<'_, Self>, lines: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        slf.as_ref().ensure_live()?;
        let py = slf.py();
        let mut curr: PyObject = slf.into_py_any(py)?;
        for line in lines.try_iter()? {
            let l: String = line?.extract()?;
            let curr_bound = curr.bind(py);
            curr = curr_bound
                .call_method1("add_child", (l,))?
                .into_any()
                .unbind();
        }
        Ok(curr)
    }

    #[getter]
    pub fn driver(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let root = Self::root(slf)?;
        root.getattr(py, "driver")
    }

    #[getter]
    pub fn text_without_negation(slf: PyRef<'_, Self>) -> PyResult<String> {
        let base = slf.as_ref();
        let text = base.text()?;
        let tree = base.read_tree()?;
        let neg_prefix = &tree.driver.negation_prefix;
        Ok(text.strip_prefix(neg_prefix).unwrap_or(&text).to_string())
    }

    #[getter]
    pub fn sectional_exit(slf: PyRef<'_, Self>) -> PyResult<Option<String>> {
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        Ok(tree.sectional_exit(base.node_id))
    }

    #[getter]
    pub fn sectional_exit_text_parent_level(slf: PyRef<'_, Self>) -> PyResult<bool> {
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        Ok(tree.sectional_exit_text_parent_level(base.node_id))
    }

    #[getter]
    pub fn real_indent_level(slf: PyRef<'_, Self>) -> PyResult<i32> {
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        Ok(tree
            .arena
            .get(base.node_id)
            .map_or(0, |n| n.real_indent_level))
    }

    #[setter]
    pub fn set_real_indent_level(slf: PyRef<'_, Self>, val: i32) -> PyResult<()> {
        let base = slf.as_ref();
        let mut tree = base.write_tree()?;
        if let Some(node) = tree.arena.get_mut(base.node_id) {
            node.real_indent_level = val;
        }
        Ok(())
    }

    #[getter]
    pub fn order_weight(slf: PyRef<'_, Self>) -> PyResult<i32> {
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        Ok(tree.arena.get(base.node_id).map_or(0, |n| n.order_weight))
    }

    #[setter]
    pub fn set_order_weight(slf: PyRef<'_, Self>, val: i32) -> PyResult<()> {
        let base = slf.as_ref();
        let mut tree = base.write_tree()?;
        if let Some(node) = tree.arena.get_mut(base.node_id) {
            node.order_weight = val;
        }
        Ok(())
    }

    #[getter]
    pub fn new_in_config(slf: PyRef<'_, Self>) -> PyResult<bool> {
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        Ok(tree
            .arena
            .get(base.node_id)
            .is_some_and(|n| n.new_in_config))
    }

    #[setter]
    pub fn set_new_in_config(slf: PyRef<'_, Self>, val: bool) -> PyResult<()> {
        let base = slf.as_ref();
        let mut tree = base.write_tree()?;
        if let Some(node) = tree.arena.get_mut(base.node_id) {
            node.new_in_config = val;
        }
        Ok(())
    }

    #[getter]
    pub fn comments(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        Ok(base.tree.get_node_comments(py, base.node_id)?.into_any())
    }

    #[setter]
    pub fn set_comments(slf: PyRef<'_, Self>, val: &Bound<'_, PyAny>) -> PyResult<()> {
        let py = slf.py();
        let base = slf.as_ref();
        let items: Vec<Bound<'_, PyAny>> = val.try_iter()?.collect::<PyResult<Vec<_>>>()?;
        let set_obj = PySet::new(py, &items)?;
        let _tree = base.read_tree()?;
        let mut data = base.tree.node_data.write_py()?;
        let entry = data.entry(base.node_id).or_default();
        entry.comments = Some(set_obj.unbind());
        Ok(())
    }

    #[getter]
    pub fn instances(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        Ok(base.tree.get_node_instances(py, base.node_id)?.into_any())
    }

    #[setter]
    pub fn set_instances(slf: PyRef<'_, Self>, val: &Bound<'_, PyAny>) -> PyResult<()> {
        let py = slf.py();
        let base = slf.as_ref();
        let items: Vec<Bound<'_, PyAny>> = val.try_iter()?.collect::<PyResult<Vec<_>>>()?;
        let list_obj = PyList::new(py, &items)?;
        let _tree = base.read_tree()?;
        let mut data = base.tree.node_data.write_py()?;
        let entry = data.entry(base.node_id).or_default();
        entry.instances = Some(list_obj.unbind());
        Ok(())
    }

    #[getter]
    pub fn facts(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        Ok(base.tree.get_node_facts(py, base.node_id)?.into_any())
    }

    #[setter]
    pub fn set_facts(slf: PyRef<'_, Self>, val: &Bound<'_, PyDict>) -> PyResult<()> {
        let base = slf.as_ref();
        let _tree = base.read_tree()?;
        let mut data = base.tree.node_data.write_py()?;
        let entry = data.entry(base.node_id).or_default();
        entry.facts = Some(val.clone().unbind());
        Ok(())
    }

    #[getter]
    pub fn instance(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let comments = slf
            .as_ref()
            .tree
            .get_node_comments(py, slf.as_ref().node_id)?;
        let tags = slf.as_ref().tags(py)?;
        let root_obj = Self::root(slf)?;
        let id_val = root_obj.bind(py).as_ptr() as usize;
        let models = py.import("hier_config.models")?;
        let instance_cls = models.getattr("Instance")?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("id", id_val)?;
        kwargs.set_item("comments", PyFrozenSet::new(py, comments.bind(py))?)?;
        kwargs.set_item("tags", tags)?;
        let inst = instance_cls.call((), Some(&kwargs))?;
        Ok(inst.unbind())
    }

    pub fn delete(slf: PyRef<'_, Self>) -> PyResult<()> {
        let base = slf.as_ref();
        let (parent_id, child_id) = {
            let tree = base.read_tree()?;
            (
                tree.arena.get(base.node_id).and_then(|n| n.parent),
                base.node_id,
            )
        };
        if parent_id.is_some() {
            let mut tree = base.write_tree()?;
            tree.delete_child(child_id);
        }
        base.tree.clear_node_cache(child_id)?;
        Ok(())
    }

    #[pyo3(name = "move")]
    pub fn move_(slf: &Bound<'_, Self>, new_parent: &Bound<'_, PyAny>) -> PyResult<()> {
        let (target_tree, target_node_id) =
            if let Ok(root) = new_parent.extract::<PyRef<'_, PyHConfig>>() {
                let base = root.as_ref();
                (Arc::clone(&base.tree), base.node_id)
            } else if let Ok(child) = new_parent.extract::<PyRef<'_, Self>>() {
                let base = child.as_ref();
                (Arc::clone(&base.tree), base.node_id)
            } else {
                return Err(PyTypeError::new_err(
                    "new_parent must be an HConfig or HConfigChild instance",
                ));
            };

        let (my_node_id, my_tree) = {
            let borrow = slf.borrow();
            let base = borrow.as_ref();
            (base.node_id, Arc::clone(&base.tree))
        };

        if Arc::ptr_eq(&target_tree, &my_tree) {
            let mut tree = my_tree.write_node(my_node_id)?;
            ensure_live(&tree, target_node_id)?;
            tree.move_child(my_node_id, target_node_id)
                .map_err(to_py_err)?;
            slf.borrow_mut().parent_handle = Some(new_parent.clone().unbind());
            Ok(())
        } else {
            // Cross-tree move
            let new_node_id = {
                let src_tree = my_tree.read_node(my_node_id)?;
                let mut dst_tree = target_tree.write_node(target_node_id)?;
                dst_tree
                    .add_deep_copy_of(target_node_id, &src_tree, my_node_id, false)
                    .map_err(to_py_err)?
            };

            // Move node_data
            {
                let mut src_data = my_tree.node_data.write_py()?;
                if let Some(nd) = src_data.remove(&my_node_id) {
                    let mut dst_data = target_tree.node_data.write_py()?;
                    dst_data.insert(new_node_id, nd);
                }
            }

            // Delete from source tree
            {
                let mut src_tree = my_tree.write_node(my_node_id)?;
                src_tree.delete_child(my_node_id);
            }
            my_tree.clear_node_cache(my_node_id)?;

            // Update this child handle to point to target tree and new node id
            {
                let mut borrow = slf.borrow_mut();
                let base_mut = borrow.as_mut();
                base_mut.tree = Arc::clone(&target_tree);
                base_mut.node_id = new_node_id;
                borrow.parent_handle = Some(new_parent.clone().unbind());
            }

            // Register in target tree's intern_cache
            let weak_ref = pyo3::types::PyWeakrefReference::new(slf)?;
            target_tree
                .intern_cache
                .write_py()?
                .insert(new_node_id, weak_ref.unbind());

            Ok(())
        }
    }

    pub fn negate(slf: PyRef<'_, Self>) -> PyResult<PyRef<'_, Self>> {
        let py = slf.py();
        let base = slf.as_ref();
        base.ensure_live()?;
        base.tree.sync_rules(py)?;
        let new_text = {
            let tree = base.read_tree()?;
            tree.try_compute_negation(base.node_id).map_err(to_py_err)?
        };
        {
            let mut tree = base.write_tree()?;
            tree.set_text(base.node_id, &new_text);
        }
        Ok(slf)
    }

    #[pyo3(signature = (*, equals = None, startswith = None, endswith = None, contains = None, re_search = None))]
    pub fn is_match(
        slf: PyRef<'_, Self>,
        equals: Option<&Bound<'_, PyAny>>,
        startswith: Option<&Bound<'_, PyAny>>,
        endswith: Option<&Bound<'_, PyAny>>,
        contains: Option<&Bound<'_, PyAny>>,
        re_search: Option<String>,
    ) -> PyResult<bool> {
        let py = slf.py();
        let rule =
            crate::base::parse_match_rule(py, equals, startswith, endswith, contains, re_search)?;
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        let text = tree.arena.get(base.node_id).map_or("", |n| n.text.as_ref());
        Ok(rule.is_match(text))
    }

    pub fn is_lineage_match(slf: PyRef<'_, Self>, rules: &Bound<'_, PyAny>) -> PyResult<bool> {
        let py = slf.py();
        let match_rules = crate::base::parse_match_rules_seq(py, rules)?;
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        Ok(tree.is_lineage_match(base.node_id, &match_rules))
    }

    pub fn is_idempotent_command(
        slf: PyRef<'_, Self>,
        other_children: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let base = slf.as_ref();
        base.ensure_live()?;
        base.tree.sync_rules(slf.py())?;
        let mut other_ids = Vec::new();
        let mut other_tree_arc: Option<Arc<SharedTree>> = None;
        for child in other_children.try_iter()? {
            let c = child?;
            if let Ok(b) = c.downcast::<PyHConfigBase>() {
                b.borrow().ensure_live()?;
                if let Some(ref other_tree) = other_tree_arc
                    && !Arc::ptr_eq(other_tree, &b.borrow().tree)
                {
                    return Err(pyo3::exceptions::PyValueError::new_err(
                        "children belong to different configurations",
                    ));
                }
                other_ids.push(b.borrow().node_id);
                if other_tree_arc.is_none() {
                    other_tree_arc = Some(Arc::clone(&b.borrow().tree));
                }
            }
        }
        if let Some(ref target_tree) = other_tree_arc
            && !Arc::ptr_eq(&base.tree, target_tree)
        {
            target_tree.sync_rules(slf.py())?;
        }
        let my_tree = base.read_tree()?;
        if let Some(target_tree_arc) = other_tree_arc {
            let other_tree = target_tree_arc.tree.read_py()?;
            for id in &other_ids {
                ensure_live(&other_tree, *id)?;
            }
            Ok(my_tree.is_idempotent_command(base.node_id, &other_tree, &other_ids))
        } else {
            Ok(false)
        }
    }

    #[pyo3(signature = (target, delta, *, negate = true))]
    pub fn overwrite_with(
        slf: PyRef<'_, Self>,
        target: &Bound<'_, PyAny>,
        delta: &Bound<'_, PyAny>,
        negate: bool,
    ) -> PyResult<()> {
        let base = slf.as_ref();
        let target_base = target.downcast::<PyHConfigBase>()?;
        let delta_base = delta.downcast::<PyHConfigBase>()?;

        let target_node_id = target_base.borrow().node_id;
        let delta_node_id = delta_base.borrow().node_id;

        let target_tree_arc = Arc::clone(&target_base.borrow().tree);
        let delta_tree_arc = Arc::clone(&delta_base.borrow().tree);

        let mut delta_tree = delta_tree_arc.write_node(delta_node_id)?;

        // When a source aliases the delta tree, read-locking the same `RwLock` on this
        // thread while the write lock is held above would deadlock. In that (rare) case
        // clone the source from the write guard we already hold; otherwise read-lock it.
        let delta_is_self = Arc::ptr_eq(&delta_tree_arc, &base.tree);
        let delta_is_target = Arc::ptr_eq(&delta_tree_arc, &target_tree_arc);
        let my_clone: Option<hier_config_core::Tree> = delta_is_self.then(|| delta_tree.clone());
        let target_clone: Option<hier_config_core::Tree> =
            delta_is_target.then(|| delta_tree.clone());
        let my_guard = (!delta_is_self).then(|| base.read_tree()).transpose()?;
        let target_guard = (!delta_is_target)
            .then(|| target_tree_arc.read_node(target_node_id))
            .transpose()?;
        let my_tree: &hier_config_core::Tree = my_clone
            .as_ref()
            .unwrap_or_else(|| my_guard.as_deref().unwrap());
        let target_tree: &hier_config_core::Tree = target_clone
            .as_ref()
            .unwrap_or_else(|| target_guard.as_deref().unwrap());
        ensure_live(my_tree, base.node_id)?;
        ensure_live(target_tree, target_node_id)?;

        hier_config_core::remediation::overwrite_with(
            my_tree,
            base.node_id,
            target_tree,
            target_node_id,
            &mut delta_tree,
            delta_node_id,
            negate,
        )
        .map_err(to_py_err)?;

        Ok(())
    }

    pub fn __deepcopy__(slf: PyRef<'_, Self>, memo: &Bound<'_, PyDict>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        base.ensure_live()?;
        let node_id = base.node_id;
        let identity = slf.as_ptr() as usize;
        let root = Self::root(slf)?;
        let copied_root = py
            .import("copy")?
            .getattr("deepcopy")?
            .call1((root, memo))?;
        let copied_base = copied_root.extract::<PyRef<'_, PyHConfigBase>>()?;
        let child = SharedTree::get_or_create_child(&copied_base.tree, py, node_id, None)?;
        memo.set_item(identity, child.bind(py))?;
        Ok(child.into_any())
    }

    fn __repr__(slf: PyRef<'_, Self>) -> PyResult<String> {
        let base = slf.as_ref();
        let tree = base.read_tree()?;
        if let Some(node) = tree.arena.get(base.node_id) {
            let is_root_parent = node.parent == Some(tree.root);
            let parent_str = if is_root_parent {
                "HConfig"
            } else {
                "HConfigChild"
            };
            Ok(format!("HConfigChild({}, {})", parent_str, node.text))
        } else {
            unreachable!("read_tree validates the node")
        }
    }

    fn __str__(slf: PyRef<'_, Self>) -> PyResult<String> {
        let base = slf.as_ref();
        Ok(base.lines(true)?.join("\n"))
    }

    fn __lt__(slf: PyRef<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        slf.as_ref().ensure_live()?;
        let py = slf.py();
        let Ok(other_child) = other.extract::<PyRef<'_, Self>>() else {
            // Return NotImplemented (not a TypeError) so Python can try the reflected
            // comparison, consistent with __eq__/__ne__ in this file.
            return Ok(py.NotImplemented());
        };
        let base = slf.as_ref();
        let other_base = other_child.as_ref();
        let my_tree = base.read_tree()?;
        let other_tree = other_base.read_tree()?;
        let my_weight = my_tree
            .arena
            .get(base.node_id)
            .map_or(0, |n| n.order_weight);
        let other_weight = other_tree
            .arena
            .get(other_base.node_id)
            .map_or(0, |n| n.order_weight);
        (my_weight < other_weight).into_py_any(py)
    }

    fn __eq__(slf: PyRef<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        slf.as_ref().ensure_live()?;
        let py = slf.py();
        if let Ok(other_child) = other.extract::<PyRef<'_, Self>>() {
            let base = slf.as_ref();
            let other_base = other_child.as_ref();
            let my_tree = base.read_tree()?;
            let other_tree = other_base.read_tree()?;
            let eq = my_tree.node_equals(base.node_id, &other_tree, other_base.node_id);
            return eq.into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    fn __ne__(slf: PyRef<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        slf.as_ref().ensure_live()?;
        let py = slf.py();
        if let Ok(other_child) = other.extract::<PyRef<'_, Self>>() {
            let base = slf.as_ref();
            let other_base = other_child.as_ref();
            let my_tree = base.read_tree()?;
            let other_tree = other_base.read_tree()?;
            let eq = my_tree.node_equals(base.node_id, &other_tree, other_base.node_id);
            return (!eq).into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    fn __hash__(slf: PyRef<'_, Self>) -> PyResult<isize> {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let base = slf.as_ref();
        let mut hasher = DefaultHasher::new();
        base.text()?.hash(&mut hasher);
        let tree = base.read_tree()?;
        let tags = tree.tags(base.node_id);
        for t in tags {
            t.hash(&mut hasher);
        }
        if let Some(node) = tree.arena.get(base.node_id) {
            for &c in node.children.as_slice() {
                if let Some(c_node) = tree.arena.get(c) {
                    c_node.text.hash(&mut hasher);
                }
            }
        }
        // Python's __hash__ contract is a machine-word-sized int; truncating the
        // 64-bit hash to isize is the intended behaviour, exactly as CPython does.
        let bytes = hasher.finish().to_ne_bytes();
        let mut isize_bytes = [0u8; size_of::<isize>()];
        isize_bytes.copy_from_slice(&bytes[..size_of::<isize>()]);
        Ok(isize::from_ne_bytes(isize_bytes))
    }
}
