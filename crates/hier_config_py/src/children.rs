//! `PyHConfigChildren` container mimicking Python's `HConfigChildren`.

use std::sync::Arc;

use hier_config_core::NodeId;
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::{PyIndexError, PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyList, PySlice};

use crate::base::PyHConfigBase;
use crate::child::PyHConfigChild;
use crate::tree::SharedTree;

#[pyclass(module = "_hier_config_rust", name = "HConfigChildren")]
#[derive(Debug)]
pub struct PyHConfigChildren {
    pub tree: Arc<SharedTree>,
    pub parent_id: NodeId,
}

#[pyclass(module = "_hier_config_rust", name = "HConfigChildrenIter")]
#[derive(Debug)]
pub struct PyHConfigChildrenIter {
    pub tree: Arc<SharedTree>,
    pub child_ids: Vec<NodeId>,
    pub index: usize,
}

#[pymethods]
impl PyHConfigChildrenIter {
    const fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<Option<PyObject>> {
        if slf.index < slf.child_ids.len() {
            let id = slf.child_ids[slf.index];
            slf.index += 1;
            let child = SharedTree::get_or_create_child(&slf.tree, py, id, None)?;
            Ok(Some(child.into_any()))
        } else {
            Ok(None)
        }
    }
}

#[pymethods]
impl PyHConfigChildren {
    fn __len__(&self) -> usize {
        let tree = self.tree.tree.read().unwrap();
        tree.arena
            .get(self.parent_id)
            .map_or(0, |n| n.children.len())
    }

    fn __contains__(&self, text: &str) -> bool {
        let tree = self.tree.tree.read().unwrap();
        tree.arena
            .get(self.parent_id)
            .is_some_and(|n| n.children.contains(text))
    }

    fn __getitem__(&self, py: Python<'_>, item: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let tree = self.tree.tree.read().unwrap();
        let Some(parent_node) = tree.arena.get(self.parent_id) else {
            if item.extract::<isize>().is_ok() || item.downcast::<PySlice>().is_ok() {
                return Err(PyIndexError::new_err("list index out of range"));
            }
            if let Ok(key) = item.extract::<String>() {
                return Err(PyKeyError::new_err(key));
            }
            return Err(PyTypeError::new_err(
                "indices must be integers, slices, or strings",
            ));
        };
        let children = &parent_node.children;

        if let Ok(idx) = item.extract::<isize>() {
            let len = isize::try_from(children.len())
                .map_err(|_| PyIndexError::new_err("list index out of range"))?;
            let actual_idx = if idx < 0 { idx + len } else { idx };
            let Ok(actual_idx) = usize::try_from(actual_idx) else {
                return Err(PyIndexError::new_err("list index out of range"));
            };
            let Some(child_id) = children.get_index(actual_idx) else {
                return Err(PyIndexError::new_err("list index out of range"));
            };
            let child = SharedTree::get_or_create_child(&self.tree, py, child_id, None)?;
            return Ok(child.into_any());
        }

        if let Ok(slice) = item.downcast::<PySlice>() {
            let indices = slice.indices(
                isize::try_from(children.len())
                    .map_err(|_| PyIndexError::new_err("list index out of range"))?,
            )?;
            let list = PyList::empty(py);
            let mut i = indices.start;
            let step = indices.step;
            let end = indices.stop;
            if step != 0 {
                while (step > 0 && i < end) || (step < 0 && i > end) {
                    let Ok(pos) = usize::try_from(i) else { break };
                    let Some(child_id) = children.get_index(pos) else {
                        break;
                    };
                    let child = SharedTree::get_or_create_child(&self.tree, py, child_id, None)?;
                    list.append(child)?;
                    i += step;
                }
            }
            return Ok(list.into_any().unbind());
        }

        if let Ok(key) = item.extract::<String>() {
            let Some(child_id) = children.get(&key) else {
                return Err(PyKeyError::new_err(key));
            };
            let child = SharedTree::get_or_create_child(&self.tree, py, child_id, None)?;
            return Ok(child.into_any());
        }

        Err(PyTypeError::new_err(
            "indices must be integers, slices, or strings",
        ))
    }

    fn __setitem__(&self, item: isize, value: &Bound<'_, PyAny>) -> PyResult<()> {
        let (new_child_id, other_tree) = if let Ok(c) = value.extract::<PyRef<'_, PyHConfigChild>>()
        {
            let base = c.as_ref();
            (base.node_id, Arc::clone(&base.tree))
        } else if let Ok(b) = value.extract::<PyRef<'_, PyHConfigBase>>() {
            (b.node_id, Arc::clone(&b.tree))
        } else {
            return Err(PyTypeError::new_err("value must be an HConfigChild"));
        };

        let len = {
            let tree = self.tree.tree.read().unwrap();
            let parent_node = tree
                .arena
                .get(self.parent_id)
                .ok_or_else(|| PyIndexError::new_err("list index out of range"))?;
            isize::try_from(parent_node.children.len())
                .map_err(|_| PyIndexError::new_err("list index out of range"))?
        };

        let actual_idx = if item < 0 { item + len } else { item };
        if actual_idx >= len {
            return Err(PyIndexError::new_err("list index out of range"));
        }
        let Ok(actual_idx) = usize::try_from(actual_idx) else {
            return Err(PyIndexError::new_err("list index out of range"));
        };

        if Arc::ptr_eq(&self.tree, &other_tree) {
            let mut tree = self.tree.tree.write().unwrap();
            tree.set_child_at(self.parent_id, actual_idx, new_child_id)
                .map_err(crate::errors::to_py_err)?;
        } else {
            let mut my_tree = self.tree.tree.write().unwrap();
            let src_tree = other_tree.tree.read().unwrap();
            let copied_id = my_tree
                .add_deep_copy_of(self.parent_id, &src_tree, new_child_id, false)
                .map_err(crate::errors::to_py_err)?;
            my_tree
                .set_child_at(self.parent_id, actual_idx, copied_id)
                .map_err(crate::errors::to_py_err)?;
        }

        Ok(())
    }

    #[pyo3(signature = (key, default = None))]
    pub fn get(&self, py: Python<'_>, key: &str, default: Option<PyObject>) -> PyResult<PyObject> {
        let tree = self.tree.tree.read().unwrap();
        if let Some(parent_node) = tree.arena.get(self.parent_id)
            && let Some(child_id) = parent_node.children.get(key)
        {
            let child = SharedTree::get_or_create_child(&self.tree, py, child_id, None)?;
            return Ok(child.into_any());
        }
        Ok(default.unwrap_or_else(|| py.None()))
    }

    pub fn index(&self, child: &Bound<'_, PyAny>) -> PyResult<usize> {
        let child_node_id = if let Ok(c) = child.extract::<PyRef<'_, PyHConfigChild>>() {
            c.as_ref().node_id
        } else if let Ok(b) = child.extract::<PyRef<'_, PyHConfigBase>>() {
            b.node_id
        } else {
            return Err(PyValueError::new_err("item not found in children"));
        };
        let tree = self.tree.tree.read().unwrap();
        let Some(parent_node) = tree.arena.get(self.parent_id) else {
            return Err(PyValueError::new_err("item not found in children"));
        };
        parent_node
            .children
            .index_of(child_node_id)
            .ok_or_else(|| PyValueError::new_err("item not found in children"))
    }

    pub fn append(&self, py: Python<'_>, child: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let (child_node_id, other_tree) =
            if let Ok(c) = child.extract::<PyRef<'_, PyHConfigChild>>() {
                let base = c.as_ref();
                (base.node_id, Arc::clone(&base.tree))
            } else if let Ok(b) = child.extract::<PyRef<'_, PyHConfigBase>>() {
                (b.node_id, Arc::clone(&b.tree))
            } else {
                return Err(PyTypeError::new_err("child must be an HConfigChild"));
            };

        let new_child_id = if Arc::ptr_eq(&self.tree, &other_tree) {
            let mut tree = self.tree.tree.write().unwrap();
            tree.move_child(child_node_id, self.parent_id)
                .map_err(crate::errors::to_py_err)?;
            child_node_id
        } else {
            let mut my_tree = self.tree.tree.write().unwrap();
            let src_tree = other_tree.tree.read().unwrap();
            my_tree
                .add_deep_copy_of(self.parent_id, &src_tree, child_node_id, false)
                .map_err(crate::errors::to_py_err)?
        };

        let res = SharedTree::get_or_create_child(&self.tree, py, new_child_id, None)?;
        Ok(res.into_any())
    }

    pub fn clear(&self) {
        let to_remove: Vec<NodeId> = {
            let tree = self.tree.tree.read().unwrap();
            tree.arena
                .get(self.parent_id)
                .map_or_else(Vec::new, |n| n.children.iter().collect())
        };
        {
            let mut tree = self.tree.tree.write().unwrap();
            for id in &to_remove {
                tree.delete_child(*id);
            }
        }
        for id in to_remove {
            self.tree.clear_node_cache(id);
        }
    }

    pub fn delete(&self, child_or_text: &Bound<'_, PyAny>) -> PyResult<()> {
        if let Ok(text) = child_or_text.extract::<String>() {
            let child_id = {
                let tree = self.tree.tree.read().unwrap();
                tree.arena
                    .get(self.parent_id)
                    .and_then(|n| n.children.get(&text))
            };
            if let Some(id) = child_id {
                let mut tree = self.tree.tree.write().unwrap();
                tree.delete_child(id);
                self.tree.clear_node_cache(id);
            }
        } else if let Ok(child_base) = child_or_text.extract::<PyRef<'_, PyHConfigChild>>() {
            let child_node_id = child_base.as_ref().node_id;
            let is_child = {
                let tree = self.tree.tree.read().unwrap();
                tree.arena
                    .get(self.parent_id)
                    .is_some_and(|n| n.children.index_of(child_node_id).is_some())
            };
            if is_child {
                let mut tree = self.tree.tree.write().unwrap();
                tree.delete_child(child_node_id);
                self.tree.clear_node_cache(child_node_id);
            }
        } else if let Ok(child_base) = child_or_text.extract::<PyRef<'_, PyHConfigBase>>() {
            let child_node_id = child_base.node_id;
            let is_child = {
                let tree = self.tree.tree.read().unwrap();
                tree.arena
                    .get(self.parent_id)
                    .is_some_and(|n| n.children.index_of(child_node_id).is_some())
            };
            if is_child {
                let mut tree = self.tree.tree.write().unwrap();
                tree.delete_child(child_node_id);
                self.tree.clear_node_cache(child_node_id);
            }
        } else {
            return Err(PyTypeError::new_err(
                "delete argument must be HConfigChild or str",
            ));
        }
        Ok(())
    }

    pub fn extend(&self, py: Python<'_>, children: &Bound<'_, PyAny>) -> PyResult<()> {
        for child in children.try_iter()? {
            self.append(py, &child?)?;
        }
        Ok(())
    }

    pub fn rebuild_mapping(&self) {
        let mut tree = self.tree.tree.write().unwrap();
        tree.rebuild_children_mapping(self.parent_id);
    }

    fn __iter__(&self) -> PyHConfigChildrenIter {
        let tree = self.tree.tree.read().unwrap();
        let child_ids = tree
            .arena
            .get(self.parent_id)
            .map_or_else(Vec::new, |n| n.children.as_slice().to_vec());
        PyHConfigChildrenIter {
            tree: Arc::clone(&self.tree),
            child_ids,
            index: 0,
        }
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        if let Ok(other_children) = other.extract::<PyRef<'_, Self>>() {
            let my_tree = self.tree.tree.read().unwrap();
            let other_tree = other_children.tree.tree.read().unwrap();
            let my_items = my_tree
                .arena
                .get(self.parent_id)
                .map_or(&[][..], |n| n.children.as_slice());
            let other_items = other_tree
                .arena
                .get(other_children.parent_id)
                .map_or(&[][..], |n| n.children.as_slice());
            if my_items.len() != other_items.len() {
                return false.into_py_any(py);
            }
            if my_items.is_empty() {
                return true.into_py_any(py);
            }
            for (&a, &b) in my_items.iter().zip(other_items.iter()) {
                let text_a = my_tree.arena.get(a).map(|n| &n.text);
                let text_b = other_tree.arena.get(b).map(|n| &n.text);
                if text_a != text_b {
                    return false.into_py_any(py);
                }
            }
            return true.into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    fn __ne__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        if let Ok(_other_children) = other.extract::<PyRef<'_, Self>>() {
            let eq_obj = self.__eq__(py, other)?;
            let eq: bool = eq_obj.extract(py)?;
            return (!eq).into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    fn __hash__(&self) -> isize {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        let tree = self.tree.tree.read().unwrap();
        if let Some(parent_node) = tree.arena.get(self.parent_id) {
            for &c in parent_node.children.as_slice() {
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
        isize::from_ne_bytes(isize_bytes)
    }

    fn __repr__(&self) -> String {
        let tree = self.tree.tree.read().unwrap();
        let len = tree
            .arena
            .get(self.parent_id)
            .map_or(0, |n| n.children.len());
        format!("<HConfigChildren len={len}>")
    }
}
