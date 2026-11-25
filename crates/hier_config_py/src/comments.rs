//! A live, mutable set view over a node's comments.
//!
//! Comments used to exist twice: once in the Rust arena and once in a Python
//! `set` cached per node. The two drifted apart -- `discard()` never reached the
//! arena and `deep_copy()` never carried the Python copy -- so this view
//! replaces the shadow store outright. It owns no elements; every operation
//! reads or writes the arena, which makes the arena the single source of truth.
//!
//! The `comments` properties still advertise `set[str]`, which is the contract
//! callers code against, and this view implements that protocol. Its stub
//! surface is therefore modelled on typeshed's declaration of `set`: operands
//! are declared narrowly and returns concretely, and the `NotImplemented`
//! fallback that drives Python's reflected-operator dispatch stays a runtime
//! detail rather than widening a declared return type.

use std::collections::BTreeSet;
use std::sync::Arc;

use hier_config_core::NodeId;
use pyo3::basic::CompareOp;
use pyo3::exceptions::{PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyFrozenSet, PySet, PyTuple};

use crate::tree::{PyRwLockExt, SharedTree, ensure_live};

/// A mutable view over the comments attached to one configuration node.
#[pyo3_stub_gen::derive::gen_stub_pyclass]
#[pyclass(
    module = "hier_config._hier_config_rust",
    name = "NodeComments",
    frozen
)]
#[derive(Debug)]
pub struct PyNodeComments {
    pub(crate) tree: Arc<SharedTree>,
    pub(crate) node_id: NodeId,
}

impl PyNodeComments {
    /// Copies the node's comments out of the arena.
    pub(crate) fn snapshot(&self) -> PyResult<BTreeSet<String>> {
        let tree = self.tree.read_node(self.node_id)?;
        Ok(tree
            .arena
            .get(self.node_id)
            .map(|node| node.comments().clone())
            .unwrap_or_default())
    }

    /// Materializes the view as a plain `set` so Python's own set algebra
    /// supplies the operator semantics rather than a hand-written reimplementation.
    fn as_py_set<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PySet>> {
        PySet::new(py, self.snapshot()?.iter())
    }

    fn with_comments<R>(&self, f: impl FnOnce(&mut BTreeSet<String>) -> R) -> PyResult<R> {
        let mut tree = self.tree.write_node(self.node_id)?;
        let node = tree
            .arena
            .get_mut(self.node_id)
            .ok_or_else(|| PyValueError::new_err("configuration node has been deleted"))?;
        Ok(f(node.comments_mut()))
    }

    /// Replaces the node's comments wholesale.
    pub(crate) fn replace(
        tree: &Arc<SharedTree>,
        node_id: NodeId,
        items: BTreeSet<String>,
    ) -> PyResult<()> {
        let mut guard = tree.tree.write_py()?;
        ensure_live(&guard, node_id)?;
        if let Some(node) = guard.arena.get_mut(node_id) {
            *node.comments_mut() = items;
        }
        Ok(())
    }

    fn binary(&self, py: Python<'_>, other: &Bound<'_, PyAny>, op: &str) -> PyResult<Py<PyAny>> {
        let Ok(rhs) = coerce_operand(py, other) else {
            return Ok(py.NotImplemented());
        };
        Ok(self.as_py_set(py)?.call_method1(op, (rhs,))?.unbind())
    }

    /// Delegates one rich comparison to the materialized `set`.
    ///
    /// An operand that cannot be coerced yields `NotImplemented` so Python
    /// falls back to the reflected comparison, exactly as `set` does.
    fn compare(
        &self,
        py: Python<'_>,
        other: &Bound<'_, PyAny>,
        op: CompareOp,
    ) -> PyResult<Py<PyAny>> {
        let Ok(rhs) = coerce_operand(py, other) else {
            return Ok(py.NotImplemented());
        };
        self.as_py_set(py)?.rich_compare(rhs, op).map(Bound::unbind)
    }

    fn delegate(
        &self,
        py: Python<'_>,
        others: &Bound<'_, PyTuple>,
        name: &str,
    ) -> PyResult<Py<PyAny>> {
        Ok(self.as_py_set(py)?.call_method1(name, others)?.unbind())
    }
}

/// Extracts `str` elements from any iterable, rejecting non-string members the
/// way `set[str]` semantics require.
pub(crate) fn extract_str_iter(value: &Bound<'_, PyAny>) -> PyResult<BTreeSet<String>> {
    let mut out = BTreeSet::new();
    for item in value.try_iter()? {
        out.insert(item?.extract::<String>()?);
    }
    Ok(out)
}

/// Converts another operand into something `set` operators accept.
///
/// A second view has to be materialized first; anything that is not already
/// set-like is rejected so the operator can return `NotImplemented`.
fn coerce_operand<'py>(py: Python<'py>, other: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(view) = other.cast::<PyNodeComments>() {
        return Ok(view.get().as_py_set(py)?.into_any());
    }
    if other.is_instance_of::<PySet>() || other.is_instance_of::<PyFrozenSet>() {
        return Ok(other.clone());
    }
    Err(PyTypeError::new_err("unsupported operand"))
}

#[pyo3_stub_gen::derive::gen_stub_pymethods]
#[pymethods]
impl PyNodeComments {
    fn __len__(&self) -> PyResult<usize> {
        Ok(self.snapshot()?.len())
    }

    fn __contains__(
        &self,
        #[gen_stub(override_type(type_repr = "builtins.object", imports = ("builtins")))]
        item: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        // `x in comments` answers False for a non-str, matching `set`.
        let Ok(text) = item.extract::<String>() else {
            return Ok(false);
        };
        Ok(self.snapshot()?.contains(&text))
    }

    #[gen_stub(override_return_type(type_repr = "collections.abc.Iterator[builtins.str]", imports = ("collections.abc", "builtins")))]
    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.as_py_set(py)?.try_iter()?.into_any().unbind())
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        if self.snapshot()?.is_empty() {
            return Ok("set()".to_owned());
        }
        self.as_py_set(py)?.repr()?.extract()
    }

    #[gen_stub(override_return_type(type_repr = "builtins.bool", imports = ("builtins")))]
    fn __eq__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "builtins.object", imports = ("builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.compare(py, other, CompareOp::Eq)
    }

    #[gen_stub(override_return_type(type_repr = "builtins.bool", imports = ("builtins")))]
    fn __ne__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "builtins.object", imports = ("builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.compare(py, other, CompareOp::Ne)
    }

    #[gen_stub(override_return_type(type_repr = "builtins.bool", imports = ("builtins")))]
    fn __lt__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.compare(py, other, CompareOp::Lt)
    }

    #[gen_stub(override_return_type(type_repr = "builtins.bool", imports = ("builtins")))]
    fn __le__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.compare(py, other, CompareOp::Le)
    }

    #[gen_stub(override_return_type(type_repr = "builtins.bool", imports = ("builtins")))]
    fn __gt__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.compare(py, other, CompareOp::Gt)
    }

    #[gen_stub(override_return_type(type_repr = "builtins.bool", imports = ("builtins")))]
    fn __ge__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.compare(py, other, CompareOp::Ge)
    }

    /// Add an element to the node's comments.
    fn add(&self, item: &str) -> PyResult<()> {
        self.with_comments(|c| {
            c.insert(item.to_owned());
        })
    }

    /// Remove an element if present.
    fn discard(
        &self,
        #[gen_stub(override_type(type_repr = "builtins.object", imports = ("builtins")))]
        item: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let Ok(text) = item.extract::<String>() else {
            return Ok(());
        };
        self.with_comments(|c| {
            c.remove(&text);
        })
    }

    /// Remove an element, raising `KeyError` when it is absent.
    fn remove(
        &self,
        #[gen_stub(override_type(type_repr = "builtins.object", imports = ("builtins")))]
        item: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let removed = match item.extract::<String>() {
            Ok(text) => self.with_comments(|c| c.remove(&text))?,
            Err(_) => false,
        };
        if removed {
            Ok(())
        } else {
            Err(PyKeyError::new_err(item.clone().unbind()))
        }
    }

    /// Remove every comment from the node.
    fn clear(&self) -> PyResult<()> {
        self.with_comments(BTreeSet::clear)
    }

    /// Remove and return an arbitrary comment.
    fn pop(&self) -> PyResult<String> {
        self.with_comments(BTreeSet::pop_first)?
            .ok_or_else(|| PyKeyError::new_err("pop from an empty set"))
    }

    /// Add every element of each iterable in `others`.
    #[pyo3(signature = (*others))]
    fn update(
        &self,
        #[gen_stub(override_type(type_repr = "collections.abc.Iterable[builtins.str]", imports = ("collections.abc", "builtins")))]
        others: &Bound<'_, PyTuple>,
    ) -> PyResult<()> {
        let mut incoming = BTreeSet::new();
        for other in others.iter() {
            incoming.extend(extract_str_iter(&other)?);
        }
        self.with_comments(|c| c.extend(incoming))
    }

    /// Return a plain `set` copy of the node's comments.
    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn copy(&self, py: Python<'_>) -> PyResult<Py<PySet>> {
        Ok(self.as_py_set(py)?.unbind())
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn __or__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.str]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.binary(py, other, "__or__")
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn __ror__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.str]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.binary(py, other, "__or__")
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn __and__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.binary(py, other, "__and__")
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn __rand__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.binary(py, other, "__and__")
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn __sub__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.str]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.binary(py, other, "__sub__")
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn __rsub__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.str]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        let Ok(rhs) = coerce_operand(py, other) else {
            return Ok(py.NotImplemented());
        };
        Ok(rhs
            .call_method1("__sub__", (self.as_py_set(py)?,))?
            .unbind())
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn __xor__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.str]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.binary(py, other, "__xor__")
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn __rxor__(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.str]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        self.binary(py, other, "__xor__")
    }

    #[gen_stub(override_return_type(type_repr = "typing_extensions.Self", imports = ("typing_extensions")))]
    fn __ior__(
        &self,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.str]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let incoming = extract_str_iter(other)?;
        self.with_comments(|c| c.extend(incoming))?;
        Ok(())
    }

    #[gen_stub(override_return_type(type_repr = "typing_extensions.Self", imports = ("typing_extensions")))]
    fn __isub__(
        &self,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let incoming = extract_str_iter(other)?;
        self.with_comments(|c| c.retain(|item| !incoming.contains(item)))?;
        Ok(())
    }

    #[gen_stub(override_return_type(type_repr = "typing_extensions.Self", imports = ("typing_extensions")))]
    fn __iand__(
        &self,
        #[gen_stub(override_type(type_repr = "collections.abc.Set[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let incoming = extract_str_iter(other)?;
        self.with_comments(|c| c.retain(|item| incoming.contains(item)))?;
        Ok(())
    }

    #[pyo3(signature = (*others))]
    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn union(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Iterable[builtins.str]", imports = ("collections.abc", "builtins")))]
        others: &Bound<'_, PyTuple>,
    ) -> PyResult<Py<PyAny>> {
        self.delegate(py, others, "union")
    }

    #[pyo3(signature = (*others))]
    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn intersection(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Iterable[builtins.object]", imports = ("collections.abc", "builtins")))]
        others: &Bound<'_, PyTuple>,
    ) -> PyResult<Py<PyAny>> {
        self.delegate(py, others, "intersection")
    }

    #[pyo3(signature = (*others))]
    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn difference(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Iterable[builtins.object]", imports = ("collections.abc", "builtins")))]
        others: &Bound<'_, PyTuple>,
    ) -> PyResult<Py<PyAny>> {
        self.delegate(py, others, "difference")
    }

    #[gen_stub(override_return_type(type_repr = "builtins.set[builtins.str]", imports = ("builtins")))]
    fn symmetric_difference(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Iterable[builtins.str]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        Ok(self
            .as_py_set(py)?
            .call_method1("symmetric_difference", (other,))?
            .unbind())
    }

    fn issubset(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Iterable[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        self.as_py_set(py)?
            .call_method1("issubset", (other,))?
            .extract()
    }

    fn issuperset(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Iterable[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        self.as_py_set(py)?
            .call_method1("issuperset", (other,))?
            .extract()
    }

    fn isdisjoint(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr = "collections.abc.Iterable[builtins.object]", imports = ("collections.abc", "builtins")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        self.as_py_set(py)?
            .call_method1("isdisjoint", (other,))?
            .extract()
    }
}
