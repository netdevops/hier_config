//! Shared tree state and handle interning cache.

use std::collections::HashMap;
use std::sync::{Arc, RwLock, RwLockReadGuard, RwLockWriteGuard};

use hier_config_core::{NodeId, Platform, Tree};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PySet, PyWeakrefMethods, PyWeakrefReference};

/// Lock poisoning is an error, not permission to continue with damaged state.
pub(crate) trait PyRwLockExt<T> {
    fn read_py(&self) -> PyResult<RwLockReadGuard<'_, T>>;
    fn write_py(&self) -> PyResult<RwLockWriteGuard<'_, T>>;
}

impl<T> PyRwLockExt<T> for RwLock<T> {
    fn read_py(&self) -> PyResult<RwLockReadGuard<'_, T>> {
        self.read().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("configuration lock is poisoned")
        })
    }

    fn write_py(&self) -> PyResult<RwLockWriteGuard<'_, T>> {
        self.write().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("configuration lock is poisoned")
        })
    }
}

pub(crate) fn ensure_live(tree: &Tree, node_id: NodeId) -> PyResult<()> {
    if tree.arena.contains(node_id) {
        Ok(())
    } else {
        Err(pyo3::exceptions::PyValueError::new_err(
            "configuration node has been deleted",
        ))
    }
}

/// Per-node Python-visible mutable state.
///
/// Every field is created on first access. Iterating a large configuration
/// materializes a handle per node but almost never touches these, so allocating
/// them eagerly would cost two Python objects per node for nothing.
///
/// Comments are deliberately absent: they live only in the Rust arena and are
/// exposed through the live [`crate::comments::PyNodeComments`] view, so there
/// is exactly one source of truth for them.
#[derive(Debug, Default)]
pub struct NodePyData {
    pub facts: Option<Py<PyDict>>,
    pub instances: Option<Py<PyList>>,
}

#[derive(Debug)]
pub struct SharedTree {
    pub tree: RwLock<Tree>,
    pub platform: Platform,
    pub node_data: RwLock<HashMap<NodeId, NodePyData>>,
    pub intern_cache: RwLock<HashMap<NodeId, Py<PyWeakrefReference>>>,
    /// Weak handle to the owning `HConfig`.
    ///
    /// A strong `Py<PyAny>` here would close a reference cycle through the Rust
    /// `Arc<SharedTree>`, which `CPython`'s cycle collector cannot see, so no
    /// configuration would ever be freed. The same weak-handle pattern as
    /// `intern_cache` keeps the handle cheap to re-materialize instead.
    pub root_handle: RwLock<Option<Py<PyWeakrefReference>>>,
    pub driver_obj: RwLock<Option<Py<PyAny>>>,
    /// The `driver.rules` object the Rust tree was last synchronized from.
    ///
    /// Holding the object (rather than its `id()`) makes the identity check
    /// sound: a freed object's address can be reused, a live reference cannot.
    pub synced_rules: RwLock<Option<Py<PyAny>>>,
}

impl SharedTree {
    pub(crate) fn read_node(&self, node_id: NodeId) -> PyResult<RwLockReadGuard<'_, Tree>> {
        let tree = self.tree.read_py()?;
        ensure_live(&tree, node_id)?;
        Ok(tree)
    }

    pub(crate) fn write_node(&self, node_id: NodeId) -> PyResult<RwLockWriteGuard<'_, Tree>> {
        let tree = self.tree.write_py()?;
        ensure_live(&tree, node_id)?;
        Ok(tree)
    }

    pub fn new(tree: Tree, platform: Platform) -> Self {
        Self {
            tree: RwLock::new(tree),
            platform,
            node_data: RwLock::new(HashMap::new()),
            intern_cache: RwLock::new(HashMap::new()),
            root_handle: RwLock::new(None),
            driver_obj: RwLock::new(None),
            synced_rules: RwLock::new(None),
        }
    }

    /// Resolves the weak root handle, or `None` when the `HConfig` is gone.
    ///
    /// `upgrade` is a C-level dereference; routing through Python's
    /// `weakref.ref.__call__` would cost a full interpreter call on a path that
    /// runs for every `parent`/`root` access.
    pub(crate) fn root_handle(&self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        let guard = self.root_handle.read_py()?;
        let Some(weak) = guard.as_ref() else {
            return Ok(None);
        };
        Ok(weak.bind(py).upgrade().map(Bound::unbind))
    }

    /// Records `obj` as the owning `HConfig` without keeping it alive.
    pub(crate) fn set_root_handle(&self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        let weak = PyWeakrefReference::new(obj)?;
        *self.root_handle.write_py()? = Some(weak.unbind());
        Ok(())
    }

    pub fn set_driver(&self, driver: Py<PyAny>) -> PyResult<()> {
        *self.driver_obj.write_py()? = Some(driver);
        Ok(())
    }

    /// Re-synchronizes the Rust rules only when the driver's `rules` object changed.
    ///
    /// [`Self::sync_rules`] serializes the whole rule set to JSON, which is far too
    /// expensive to repeat on every property read. Reassigning `driver.rules`
    /// (including `rules.model_copy(update=...)`) produces a new object, so an
    /// identity comparison catches every supported way of changing the rules while
    /// costing one `getattr` and one pointer compare on the common path.
    pub fn sync_rules_if_stale(&self, py: Python<'_>) -> PyResult<()> {
        let driver_opt = {
            let guard = self.driver_obj.read_py()?;
            guard.as_ref().map(|d| d.clone_ref(py))
        };
        let Some(driver) = driver_opt else {
            return Ok(());
        };
        let Ok(rules_obj) = driver.bind(py).getattr("rules") else {
            return Ok(());
        };
        {
            let guard = self.synced_rules.read_py()?;
            if let Some(previous) = guard.as_ref()
                && previous.bind(py).is(&rules_obj)
            {
                return Ok(());
            }
        }
        self.sync_rules(py)
    }

    pub fn sync_rules(&self, py: Python<'_>) -> PyResult<()> {
        let driver_opt = {
            let guard = self.driver_obj.read_py()?;
            guard.as_ref().map(|d| d.clone_ref(py))
        };
        let Some(driver) = driver_opt else {
            return Ok(());
        };
        let driver_bound = driver.bind(py);

        let rules_obj = driver_bound.getattr("rules")?;
        // A test double (`MagicMock(spec=HConfigDriverBase)`) satisfies every
        // `getattr` but returns mocks instead of a `str`/JSON document. That shape
        // is not a misconfigured driver, so fall back to the platform defaults and
        // skip the sync rather than failing construction. A real driver whose JSON
        // is malformed still raises below.
        let (Ok(np_str), Ok(dp_str)) = (
            driver_bound.getattr("negation_prefix")?.extract::<String>(),
            driver_bound
                .getattr("declaration_prefix")?
                .extract::<String>(),
        ) else {
            *self.synced_rules.write_py()? = Some(rules_obj.unbind());
            return Ok(());
        };
        let Some(driver_rules) = build_driver_rules(py, &rules_obj)? else {
            *self.synced_rules.write_py()? = Some(rules_obj.unbind());
            return Ok(());
        };
        {
            let mut tree = self.tree.write_py()?;
            tree.driver.negation_prefix = np_str;
            tree.driver.declaration_prefix = dp_str;
            tree.driver.rules = driver_rules;
        }
        *self.synced_rules.write_py()? = Some(rules_obj.unbind());
        Ok(())
    }

    /// Retrieves an existing cached `PyHConfigChild` handle or instantiates and caches a new one.
    pub fn get_or_create_child(
        self_arc: &Arc<Self>,
        py: Python<'_>,
        node_id: NodeId,
        parent_handle: Option<Py<PyAny>>,
    ) -> PyResult<Py<crate::child::PyHConfigChild>> {
        drop(self_arc.read_node(node_id)?);
        // 1. Check intern cache. `upgrade` is a C-level dereference; going through
        //    Python's `weakref.ref.__call__` here would cost a full interpreter
        //    call on a path that runs once per node per traversal.
        {
            let cache = self_arc.intern_cache.read_py()?;
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
            let mut cache = self_arc.intern_cache.write_py()?;
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
    ) -> PyResult<Vec<Py<PyAny>>> {
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
        drop(self_arc.read_node(node_id)?);
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

    pub fn get_node_facts(&self, py: Python<'_>, node_id: NodeId) -> PyResult<Py<PyDict>> {
        let _tree = self.read_node(node_id)?;
        let mut data_map = self.node_data.write_py()?;
        let entry = data_map.entry(node_id).or_default();
        Ok(entry
            .facts
            .get_or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py))
    }

    /// Returns a live, mutable view over the node's comments in the Rust arena.
    ///
    /// The view holds no copy of its own, so `add`/`discard` are immediately
    /// visible to `dump()`, `deep_copy()`, rendering and every other reader.
    pub fn node_comments(
        self_arc: &Arc<Self>,
        node_id: NodeId,
    ) -> PyResult<crate::comments::PyNodeComments> {
        drop(self_arc.read_node(node_id)?);
        Ok(crate::comments::PyNodeComments {
            tree: Arc::clone(self_arc),
            node_id,
        })
    }

    pub fn get_node_instances(&self, py: Python<'_>, node_id: NodeId) -> PyResult<Py<PyList>> {
        let _tree = self.read_node(node_id)?;
        let mut data_map = self.node_data.write_py()?;
        let entry = data_map.entry(node_id).or_default();
        Ok(entry
            .instances
            .get_or_insert_with(|| PyList::empty(py).unbind())
            .clone_ref(py))
    }

    pub fn clear_node_cache(&self, node_id: NodeId) -> PyResult<()> {
        let mut cache = self.intern_cache.write_py()?;
        cache.remove(&node_id);
        let mut data = self.node_data.write_py()?;
        data.remove(&node_id);
        Ok(())
    }
}

/// Deserializes a Python `HConfigDriverRules` into the core rule set.
///
/// Returns `Ok(None)` when `model_dump_json` does not yield a JSON string, which
/// is the `MagicMock` shape rather than a misconfigured driver; a real driver
/// whose JSON is malformed still raises.
fn build_driver_rules(
    py: Python<'_>,
    rules_obj: &Bound<'_, PyAny>,
) -> PyResult<Option<hier_config_core::DriverRules>> {
    let kwargs = PyDict::new(py);
    let exclude_set = PySet::new(
        py,
        ["post_load_callbacks", "remediation_transform_callbacks"],
    )?;
    kwargs.set_item("exclude", exclude_set)?;
    let Ok(json_str) = rules_obj
        .getattr("model_dump_json")?
        .call((), Some(&kwargs))?
        .extract::<String>()
    else {
        return Ok(None);
    };
    let mut driver_rules = serde_json::from_str::<hier_config_core::DriverRules>(&json_str)
        .map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "failed to sync driver rules from Python driver: {e}"
            ))
        })?;
    driver_rules
        .validate_regexes()
        .map_err(pyo3::exceptions::PyValueError::new_err)?;
    // `post_load_callbacks` is excluded from the JSON above because it holds
    // Python callables, so carry the surviving names across separately: the
    // core skips any callback the caller removed on the Python side (#286).
    driver_rules.enabled_post_load = Some(callback_names(rules_obj)?);
    Ok(Some(driver_rules))
}

/// Collects the `__name__` of every callback still on `rules.post_load_callbacks`.
///
/// Callbacks without a `__name__` (partials, lambdas, callable objects) are
/// necessarily Python-only, so they are skipped rather than treated as an
/// error.
fn callback_names(rules: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
    let mut names = Vec::new();
    for callback in rules.getattr("post_load_callbacks")?.try_iter()? {
        if let Ok(name) = callback?
            .getattr("__name__")
            .and_then(|n| n.extract::<String>())
        {
            names.push(name);
        }
    }
    Ok(names)
}

#[cfg(test)]
mod tests {
    use super::SharedTree;
    use hier_config_core::tree::Tree;
    use hier_config_core::{Driver, Platform};
    use pyo3::ffi::c_str;
    use pyo3::prelude::*;

    fn shared_tree() -> SharedTree {
        let platform = Platform::Generic;
        SharedTree::new(Tree::new(Driver::for_platform(platform)), platform)
    }

    /// A weakref-able stand-in for the owning `HConfig`.
    fn owner(py: Python<'_>) -> PyResult<Bound<'_, PyAny>> {
        py.eval(c_str!("type('Owner', (object,), {})()"), None, None)
    }

    #[test]
    fn root_handle_is_none_before_it_is_set() {
        Python::initialize();
        Python::attach(|py| {
            assert!(shared_tree().root_handle(py).unwrap().is_none());
        });
    }

    #[test]
    fn root_handle_resolves_while_the_owner_is_alive() {
        Python::initialize();
        Python::attach(|py| {
            let tree = shared_tree();
            let owner = owner(py).unwrap();
            tree.set_root_handle(&owner).unwrap();

            let resolved = tree.root_handle(py).unwrap().expect("owner is still alive");

            assert!(resolved.bind(py).is(&owner));
        });
    }

    /// The whole point of the weak handle: the tree must not keep the config
    /// alive, and reading the handle afterwards must report absence rather
    /// than panic or resurrect a dangling pointer.
    #[test]
    fn root_handle_is_none_once_the_owner_is_dropped() {
        Python::initialize();
        Python::attach(|py| {
            let tree = shared_tree();
            let owner = owner(py).unwrap();
            tree.set_root_handle(&owner).unwrap();
            drop(owner);

            assert!(tree.root_handle(py).unwrap().is_none());
        });
    }
}
