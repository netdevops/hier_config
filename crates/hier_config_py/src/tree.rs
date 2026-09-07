//! Shared tree state and handle interning cache.

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use hier_config_core::{NodeId, Platform, Tree};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PySet, PyWeakrefMethods, PyWeakrefReference};

/// Per-node Python-visible mutable state.
///
/// Every field is created on first access. Iterating a large configuration
/// materializes a handle per node but almost never touches these, so allocating
/// them eagerly would cost three Python objects per node for nothing.
#[derive(Debug, Default)]
pub struct NodePyData {
    pub facts: Option<Py<PyDict>>,
    pub comments: Option<Py<PySet>>,
    pub instances: Option<Py<PyList>>,
}

#[derive(Debug)]
pub struct SharedTree {
    pub tree: RwLock<Tree>,
    pub platform: Platform,
    pub node_data: RwLock<HashMap<NodeId, NodePyData>>,
    pub intern_cache: RwLock<HashMap<NodeId, Py<PyWeakrefReference>>>,
    pub root_handle: RwLock<Option<PyObject>>,
    pub driver_obj: RwLock<Option<PyObject>>,
}

impl SharedTree {
    pub fn new(tree: Tree, platform: Platform) -> Self {
        Self {
            tree: RwLock::new(tree),
            platform,
            node_data: RwLock::new(HashMap::new()),
            intern_cache: RwLock::new(HashMap::new()),
            root_handle: RwLock::new(None),
            driver_obj: RwLock::new(None),
        }
    }

    pub fn set_driver(&self, driver: PyObject) {
        *self.driver_obj.write().unwrap() = Some(driver);
    }

    pub fn sync_rules(&self, py: Python<'_>) -> PyResult<()> {
        let driver_opt = {
            let guard = self.driver_obj.read().unwrap();
            guard.as_ref().map(|d| d.clone_ref(py))
        };
        let Some(driver) = driver_opt else {
            return Ok(());
        };
        let driver_bound = driver.bind(py);

        let np_str = driver_bound
            .getattr("negation_prefix")?
            .extract::<String>()?;
        let dp_str = driver_bound
            .getattr("declaration_prefix")?
            .extract::<String>()?;
        {
            let mut tree = self.tree.write().unwrap();
            tree.driver.negation_prefix = np_str;
            tree.driver.declaration_prefix = dp_str;
        }

        let rules_obj = driver_bound.getattr("rules")?;
        let kwargs = PyDict::new(py);
        let exclude_set = PySet::new(
            py,
            ["post_load_callbacks", "remediation_transform_callbacks"],
        )?;
        kwargs.set_item("exclude", exclude_set)?;
        let json_str = rules_obj
            .getattr("model_dump_json")?
            .call((), Some(&kwargs))?
            .extract::<String>()?;
        let mut driver_rules = serde_json::from_str::<hier_config_core::DriverRules>(&json_str)
            .map_err(|e| {
                pyo3::exceptions::PyValueError::new_err(format!(
                    "failed to sync driver rules from Python driver: {e}"
                ))
            })?;
        // `post_load_callbacks` is excluded from the JSON above because it holds
        // Python callables, so carry the surviving names across separately: the
        // core skips any callback the caller removed on the Python side (#286).
        driver_rules.enabled_post_load = Some(callback_names(&rules_obj)?);
        {
            let mut tree = self.tree.write().unwrap();
            tree.driver.rules = driver_rules;
        }
        Ok(())
    }

    /// Retrieves an existing cached `PyHConfigChild` handle or instantiates and caches a new one.
    pub fn get_or_create_child(
        self_arc: &Arc<Self>,
        py: Python<'_>,
        node_id: NodeId,
        parent_handle: Option<PyObject>,
    ) -> PyResult<Py<crate::child::PyHConfigChild>> {
        // 1. Check intern cache. `upgrade` is a C-level dereference; going through
        //    Python's `weakref.ref.__call__` here would cost a full interpreter
        //    call on a path that runs once per node per traversal.
        {
            let cache = self_arc.intern_cache.read().unwrap();
            if let Some(weak) = cache.get(&node_id)
                && let Some(alive) = weak.bind(py).upgrade()
                && let Ok(child) = alive.extract::<Py<crate::child::PyHConfigChild>>()
            {
                return Ok(child);
            }
        }

        // 2. Create new PyHConfigChild
        let child = Py::new(
            py,
            (
                crate::child::PyHConfigChild { parent_handle },
                crate::base::PyHConfigBase {
                    tree: Arc::clone(self_arc),
                    node_id,
                },
            ),
        )?;

        // 3. Store weakref in cache
        let weak_ref = PyWeakrefReference::new(child.bind(py))?;
        {
            let mut cache = self_arc.intern_cache.write().unwrap();
            cache.insert(node_id, weak_ref.unbind());
        }

        Ok(child)
    }

    /// Materializes handles for many nodes at once.
    ///
    /// Bulk traversals deliberately bypass the intern cache. Interning costs a lock,
    /// a hash, a weakref allocation and an upgrade per node, and whole-tree walks are
    /// the dominant iteration cost. Handles are value-comparable (`__eq__`/`__hash__`
    /// are derived from the node, not the wrapper) and all mutable state lives in the
    /// shared tree keyed by `NodeId`, so equality, hashing, set/dict membership and
    /// mutation visibility are unaffected.
    ///
    /// The trade-off is that two handles for the same node obtained from *different*
    /// bulk traversals are no longer the same Python object, so `is` / `id()` no
    /// longer match across traversals. Single-node lookups such as
    /// [`Self::get_or_create_child`] still intern, which keeps the identity guarantees
    /// that `children.get()`, `get_or_create_child` and the config views rely on.
    pub fn get_or_create_children_batch(
        self_arc: &Arc<Self>,
        py: Python<'_>,
        node_ids: &[NodeId],
    ) -> PyResult<Vec<PyObject>> {
        let mut out = Vec::with_capacity(node_ids.len());
        for &node_id in node_ids {
            out.push(Self::new_child_handle(self_arc, py, node_id)?.into_any());
        }
        Ok(out)
    }

    /// Builds an uncached Python handle for `node_id`.
    fn new_child_handle(
        self_arc: &Arc<Self>,
        py: Python<'_>,
        node_id: NodeId,
    ) -> PyResult<Py<crate::child::PyHConfigChild>> {
        Py::new(
            py,
            (
                crate::child::PyHConfigChild {
                    parent_handle: None,
                },
                crate::base::PyHConfigBase {
                    tree: Arc::clone(self_arc),
                    node_id,
                },
            ),
        )
    }

    pub fn get_node_facts(&self, py: Python<'_>, node_id: NodeId) -> Py<PyDict> {
        let mut data_map = self.node_data.write().unwrap();
        let entry = data_map.entry(node_id).or_default();
        entry
            .facts
            .get_or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py)
    }

    pub fn get_node_comments(&self, py: Python<'_>, node_id: NodeId) -> PyResult<Py<PySet>> {
        // Comments can originate in Rust (post-load callbacks such as the IOS-XR
        // comment fixup write straight into the arena), so seed the Python-visible
        // set from the node the first time it is materialized. Afterwards Python
        // owns it and `cisco_style_text` syncs any additions back.
        let seed: Vec<String> = {
            let tree = self.tree.read().unwrap();
            tree.arena
                .get(node_id)
                .map(|node| node.comments().iter().cloned().collect())
                .unwrap_or_default()
        };
        let mut data_map = self.node_data.write().unwrap();
        let entry = data_map.entry(node_id).or_default();
        if entry.comments.is_none() {
            entry.comments = Some(PySet::new(py, seed.iter())?.unbind());
        }
        Ok(entry
            .comments
            .as_ref()
            .expect("comments set was just initialized")
            .clone_ref(py))
    }

    pub fn get_node_instances(&self, py: Python<'_>, node_id: NodeId) -> Py<PyList> {
        let mut data_map = self.node_data.write().unwrap();
        let entry = data_map.entry(node_id).or_default();
        entry
            .instances
            .get_or_insert_with(|| PyList::empty(py).unbind())
            .clone_ref(py)
    }

    pub fn clear_node_cache(&self, node_id: NodeId) {
        let mut cache = self.intern_cache.write().unwrap();
        cache.remove(&node_id);
        let mut data = self.node_data.write().unwrap();
        data.remove(&node_id);
    }
}

/// Collects the `__name__` of every callback still on `rules.post_load_callbacks`.
///
/// Callbacks without a `__name__` (partials, lambdas, callable objects) are
/// necessarily Python-only, so they are skipped rather than treated as an
/// error.
fn callback_names(rules: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
    let mut names = Vec::new();
    for callback in rules.getattr("post_load_callbacks")?.try_iter()? {
        if let Ok(name) = callback?.getattr("__name__")?.extract::<String>() {
            names.push(name);
        }
    }
    Ok(names)
}
