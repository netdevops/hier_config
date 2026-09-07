//! `PyHConfig` representing the root configuration tree in Python.

use std::collections::BTreeSet;
use std::sync::Arc;

use hier_config_core::models::{Dump, DumpLine};
use hier_config_core::{Platform, Tree};
use pyo3::IntoPyObjectExt;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PySet, PyString, PyTuple, PyType};

use crate::base::PyHConfigBase;
use crate::errors::to_py_err;
use crate::tree::SharedTree;

fn get_dump_field<'py>(
    item: &Bound<'py, PyAny>,
    n_dict: &Bound<'py, PyString>,
    key: &Bound<'py, PyString>,
) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(dict_obj) = item.getattr(n_dict)
        && let Ok(dict) = dict_obj.downcast::<PyDict>()
        && let Some(val) = dict.get_item(key)?
    {
        return Ok(val);
    }
    item.getattr(key)
}

fn extract_dump_strings(val: Bound<'_, PyAny>) -> PyResult<BTreeSet<String>> {
    let mut set = BTreeSet::new();
    if let Ok(fset) = val.downcast::<PyFrozenSet>() {
        for item in fset.iter() {
            set.insert(item.extract::<String>()?);
        }
    } else if let Ok(pyset) = val.downcast::<PySet>() {
        for item in pyset.iter() {
            set.insert(item.extract::<String>()?);
        }
    } else if !val.is_none() {
        for item in val.try_iter()? {
            set.insert(item?.extract::<String>()?);
        }
    }
    Ok(set)
}

fn parse_dump_line<'py>(
    item: &Bound<'py, PyAny>,
    n_dict: &Bound<'py, PyString>,
    k_depth: &Bound<'py, PyString>,
    k_text: &Bound<'py, PyString>,
    k_tags: &Bound<'py, PyString>,
    k_comments: &Bound<'py, PyString>,
    k_new_in_config: &Bound<'py, PyString>,
) -> PyResult<DumpLine> {
    let depth: usize = get_dump_field(item, n_dict, k_depth)?.extract()?;
    let text: String = get_dump_field(item, n_dict, k_text)?.extract()?;
    let tags = extract_dump_strings(get_dump_field(item, n_dict, k_tags)?)?;
    let comments = extract_dump_strings(get_dump_field(item, n_dict, k_comments)?)?;
    let new_in_config: bool = get_dump_field(item, n_dict, k_new_in_config)?.extract()?;
    Ok(DumpLine {
        depth,
        text,
        tags,
        comments,
        new_in_config,
    })
}

#[pyclass(extends = PyHConfigBase, subclass, module = "_hier_config_rust", name = "HConfig")]
#[derive(Debug)]
pub struct PyHConfig {
    pub driver_obj: PyObject,
}

impl PyHConfig {
    pub fn parse_platform(py: Python<'_>, driver: &PyObject) -> Platform {
        if let Ok(plat_val) = driver.getattr(py, "platform") {
            if let Ok(val) = plat_val.getattr(py, "value")
                && let Ok(s) = val.extract::<String>(py)
                && let Ok(p) = s.parse::<Platform>()
            {
                return p;
            }
            if let Ok(s) = plat_val.extract::<String>(py)
                && let Ok(p) = s.parse::<Platform>()
            {
                return p;
            }
        }
        if let Ok(cls) = driver.getattr(py, "__class__")
            && let Ok(name) = cls.getattr(py, "__name__")
            && let Ok(s) = name.extract::<String>(py)
        {
            match s.as_str() {
                "HConfigDriverAristaEOS" => return Platform::AristaEos,
                "HConfigDriverArubaAOSCX" => return Platform::ArubaAoscx,
                "HConfigDriverCiscoIOS" => return Platform::CiscoIos,
                "HConfigDriverCiscoNXOS" => return Platform::CiscoNxos,
                "HConfigDriverCiscoIOSXR" => return Platform::CiscoXr,
                "HConfigDriverFortinetFortiOS" => return Platform::FortinetFortios,
                "HConfigDriverHPComware5" => return Platform::HpComware5,
                "HConfigDriverHPProcurve" => return Platform::HpProcurve,
                "HConfigDriverHuaweiVrp" => return Platform::HuaweiVrp,
                "HConfigDriverJuniperJUNOS" => return Platform::JuniperJunos,
                "HConfigDriverNokiaSRL" => return Platform::NokiaSrl,
                "HConfigDriverVYOS" => return Platform::Vyos,
                _ => {}
            }
        }
        Platform::Generic
    }

    pub fn get_default_driver(py: Python<'_>, platform: Platform) -> PyResult<PyObject> {
        let constructors = py.import("hier_config.constructors")?;
        let plat_str = match platform {
            Platform::AristaEos => "ARISTA_EOS",
            Platform::ArubaAoscx => "ARUBA_AOSCX",
            Platform::CiscoIos => "CISCO_IOS",
            Platform::CiscoNxos => "CISCO_NXOS",
            Platform::CiscoXr => "CISCO_XR",
            Platform::FortinetFortios => "FORTINET_FORTIOS",
            Platform::Generic => "GENERIC",
            Platform::HpComware5 => "HP_COMWARE5",
            Platform::HpProcurve => "HP_PROCURVE",
            Platform::HuaweiVrp => "HUAWEI_VRP",
            Platform::JuniperJunos => "JUNIPER_JUNOS",
            Platform::NokiaSrl => "NOKIA_SRL",
            Platform::Vyos => "VYOS",
        };
        let models = py.import("hier_config.models")?;
        let platform_enum = models.getattr("Platform")?.getattr(plat_str)?;
        let driver = constructors
            .getattr("get_hconfig_driver")?
            .call1((platform_enum,))?;
        Ok(driver.into_any().unbind())
    }
}

type DumpRow = (usize, Py<PyAny>, Py<PyAny>, Py<PyAny>, bool);

/// `object.__setattr__(obj, name, value)` without the Python-level call.
///
/// Pydantic's `BaseModel` overrides `__setattr__`, so populating an instance's
/// slots has to go through `object`'s implementation. Calling it as a bound
/// method allocates an argument tuple per assignment; `PyObject_GenericSetAttr`
/// *is* that implementation and takes its arguments directly.
///
/// # Safety
///
/// The three pointers come from live `Bound` handles, so they are valid and the
/// GIL is held for the duration of the call. A non-zero return means `CPython`
/// has
/// set the error indicator, which is converted back into a `PyErr`.
#[allow(unsafe_code)]
fn generic_setattr(
    obj: &Bound<'_, PyAny>,
    name: &Bound<'_, PyAny>,
    value: &Bound<'_, PyAny>,
) -> PyResult<()> {
    // SAFETY: The three pointers come from live `Bound` handles, so they are
    // valid and the GIL is held for the duration of the call. A non-zero return
    // means CPython has set the error indicator, which is converted back to PyErr.
    let rc =
        unsafe { pyo3::ffi::PyObject_GenericSetAttr(obj.as_ptr(), name.as_ptr(), value.as_ptr()) };
    if rc == 0 {
        Ok(())
    } else {
        Err(PyErr::fetch(obj.py()))
    }
}

/// Allocates an uninitialised instance of `ty`, equivalent to `object.__new__(ty)`.
///
/// `dump()` mints one model per configuration line, and routing each allocation
/// through the Python-level `object.__new__` costs a bound-method lookup, an
/// argument tuple, and a full call dispatch. `tp_new` is the implementation that
/// call ultimately reaches.
///
/// # Safety
///
/// `ty` comes from a live `Bound` handle and the GIL is held for the duration of
/// the call, so the pointer is valid. A null return means `CPython` has set the
/// error indicator, which is converted back into a `PyErr`.
#[allow(unsafe_code)]
fn generic_new<'py>(ty: &Bound<'py, PyType>) -> PyResult<Bound<'py, PyAny>> {
    let py = ty.py();
    // SAFETY: `ty` is a live type object and the GIL is held, so the pointer is
    // valid for the duration of the call. A null return means CPython has set the
    // error indicator, which is converted back into a `PyErr`.
    let obj = unsafe {
        pyo3::ffi::PyType_GenericNew(
            ty.as_ptr().cast(),
            std::ptr::null_mut(),
            std::ptr::null_mut(),
        )
    };
    // SAFETY: `PyType_GenericNew` returns a new strong reference on success and
    // null on failure; both cases are handled by `from_owned_ptr_or_err`.
    unsafe { Bound::from_owned_ptr_or_err(py, obj) }
}

pub(crate) fn create_py_hconfig(
    py: Python<'_>,
    tree: Tree,
    platform: Platform,
    driver_obj: PyObject,
) -> PyResult<Py<PyHConfig>> {
    let root_id = tree.root;
    let shared_tree = Arc::new(SharedTree::new(tree, platform));
    shared_tree.set_driver(driver_obj.clone_ref(py));
    shared_tree.sync_rules(py)?;
    let hconfig = Py::new(
        py,
        (
            PyHConfig { driver_obj },
            PyHConfigBase {
                tree: Arc::clone(&shared_tree),
                node_id: root_id,
            },
        ),
    )?;
    let mut handle = shared_tree.root_handle.write().unwrap();
    *handle = Some(hconfig.clone_ref(py).into_any());
    drop(handle);
    Ok(hconfig)
}

#[pymethods]
impl PyHConfig {
    #[new]
    #[pyo3(signature = (driver))]
    fn new(py: Python<'_>, driver: PyObject) -> PyResult<(Self, PyHConfigBase)> {
        let platform = Self::parse_platform(py, &driver);
        let tree = Tree::for_platform(platform);
        let root_id = tree.root;
        let shared_tree = Arc::new(SharedTree::new(tree, platform));
        shared_tree.set_driver(driver.clone_ref(py));
        shared_tree.sync_rules(py)?;

        Ok((
            Self { driver_obj: driver },
            PyHConfigBase {
                tree: shared_tree,
                node_id: root_id,
            },
        ))
    }

    #[pyo3(signature = (driver))]
    fn __init__(slf: &Bound<'_, Self>, driver: &Bound<'_, PyAny>) -> PyResult<()> {
        let _ = driver;
        let base_ref = slf.extract::<PyRef<'_, PyHConfigBase>>()?;
        *base_ref.tree.root_handle.write().unwrap() = Some(slf.clone().unbind().into_any());
        Ok(())
    }

    #[getter]
    pub fn driver(slf: PyRef<'_, Self>) -> PyObject {
        let py = slf.py();
        slf.driver_obj.clone_ref(py)
    }

    #[getter]
    pub fn root(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let tree = Arc::clone(&slf.as_ref().tree);
        {
            let handle = tree.root_handle.read().unwrap();
            if let Some(ref h) = *handle {
                return Ok(h.clone_ref(py));
            }
        }
        let obj = slf.into_py_any(py)?;
        let mut handle = tree.root_handle.write().unwrap();
        *handle = Some(obj.clone_ref(py));
        Ok(obj)
    }

    #[getter]
    pub fn parent(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        Self::root(slf)
    }

    #[getter]
    pub fn real_indent_level(_slf: PyRef<'_, Self>) -> i32 {
        -1
    }

    #[getter]
    pub fn is_leaf(_slf: PyRef<'_, Self>) -> bool {
        false
    }

    #[getter]
    pub fn is_branch(_slf: PyRef<'_, Self>) -> bool {
        true
    }

    pub fn instantiate_child(slf: PyRef<'_, Self>, text: &str) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        let child_id = {
            let mut tree = base.tree.tree.write().unwrap();
            tree.create_child_unattached(base.node_id, text)
        };
        let child = SharedTree::get_or_create_child(&base.tree, py, child_id, None)?;
        Ok(child.into_any())
    }

    pub fn merge(slf: PyRef<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let py = slf.py();
        let slf_obj = slf.into_py_any(py)?;
        let slf_bound = slf_obj.bind(py);

        let merge_single = |other_obj: &Bound<'_, PyAny>| -> PyResult<()> {
            let children = other_obj.getattr("children")?;
            for child in children.try_iter()? {
                let child_item = child?;
                let kwargs = PyDict::new(py);
                kwargs.set_item("merged", true)?;
                slf_bound.call_method("add_deep_copy_of", (child_item,), Some(&kwargs))?;
            }
            Ok(())
        };

        if other.extract::<PyRef<'_, Self>>().is_ok() {
            merge_single(other)?;
        } else {
            for item in other.try_iter()? {
                let conf = item?;
                merge_single(&conf)?;
            }
        }
        Ok(slf_obj)
    }

    /// Parses a raw configuration string entirely in Rust.
    ///
    /// Runs `full_text_sub`, the platform preprocessor, the line-by-line parse and
    /// sectional-exit removal in a single FFI call with the GIL released, allocating
    /// no Python objects. When `run_post_load` is true the natively-implemented
    /// post-load callbacks for the platform are applied as well; callers pass false
    /// when a custom driver supplies its own Python callbacks.
    #[pyo3(signature = (config_raw, run_post_load = true))]
    pub fn _load_native(
        slf: PyRef<'_, Self>,
        config_raw: &str,
        run_post_load: bool,
    ) -> PyResult<()> {
        let py = slf.py();
        let base: &PyHConfigBase = slf.as_ref();
        let shared = Arc::clone(&base.tree);
        // Copy the text out of Python memory so the GIL can be released for the parse.
        let owned = config_raw.to_owned();

        let result = py.allow_threads(move || {
            let mut tree = shared.tree.write().unwrap();
            hier_config_core::parser::parse_into_tree(&mut tree, &owned)?;
            hier_config_core::post_load::delete_sectional_exit_recursive(&mut tree);
            if run_post_load {
                hier_config_core::post_load::run_post_load_callbacks(&mut tree);
            }
            Ok::<(), hier_config_core::TreeError>(())
        });

        result.map_err(to_py_err)
    }

    /// Parses pre-formatted `lines` into this tree inside a single FFI call.
    ///
    /// Mirrors [`Self::_load_native`] but applies only `per_line_sub` rules, matching
    /// the semantics of `get_hconfig_fast_load`.
    ///
    /// `lines` may be a single `str` — which is split on line boundaries in Rust,
    /// avoiding any per-line marshalling — or any iterable of `str`.
    ///
    /// # Errors
    ///
    /// Returns an error if `lines` is not a `str` or an iterable of `str`, or if a
    /// line cannot be inserted into the tree.
    pub fn _load_fast_native(
        slf: PyRef<'_, Self>,
        lines: &Bound<'_, PyAny>,
        run_post_load: bool,
    ) -> PyResult<()> {
        let py = slf.py();
        let base: &PyHConfigBase = slf.as_ref();
        let shared = Arc::clone(&base.tree);

        // The parse runs without the GIL, so the text has to be copied out of Python
        // memory first.
        let (buf, spans) = if let Ok(text) = lines.downcast::<PyString>() {
            // A single string only needs one copy; splitting happens Rust-side.
            (text.to_str()?.to_owned(), None)
        } else {
            // For a sequence, pack every line into one contiguous buffer plus offsets
            // rather than a Vec<String>: a large config is tens of thousands of lines,
            // and one allocation beats one per line. Offsets rather than a joined
            // string keep lines that themselves contain a newline intact.
            let mut buf = String::new();
            let mut spans: Vec<(usize, usize)> = Vec::new();
            let mut push = |line: &Bound<'_, PyAny>| -> PyResult<()> {
                let start = buf.len();
                buf.push_str(line.downcast::<PyString>()?.to_str()?);
                spans.push((start, buf.len()));
                Ok(())
            };
            // A list or tuple is by far the common case and can be walked by index,
            // which skips constructing a Python iterator and calling `__next__` once
            // per line.
            if let Ok(list) = lines.downcast::<PyList>() {
                for line in list {
                    push(&line)?;
                }
            } else if let Ok(tuple) = lines.downcast::<PyTuple>() {
                for line in tuple {
                    push(&line)?;
                }
            } else {
                for line in lines.try_iter()? {
                    push(&line?)?;
                }
            }
            (buf, Some(spans))
        };

        let result = py.allow_threads(move || {
            let borrowed: Vec<&str> = match &spans {
                Some(spans) => spans.iter().map(|&(s, e)| &buf[s..e]).collect(),
                None => buf.lines().collect(),
            };
            let mut tree = shared.tree.write().unwrap();
            hier_config_core::parser::load_fast(&mut tree, &borrowed, run_post_load)
        });

        result.map_err(to_py_err)
    }

    /// Reads and parses an on-disk config file into this tree inside a single FFI call.
    ///
    /// Reads the file directly via `std::fs::read_to_string` with the GIL released,
    /// avoiding intermediate Python `str` allocations.
    #[pyo3(signature = (path, run_post_load = true))]
    pub fn _load_file_native(
        slf: PyRef<'_, Self>,
        path: &str,
        run_post_load: bool,
    ) -> PyResult<()> {
        let py = slf.py();
        let base: &PyHConfigBase = slf.as_ref();
        let shared = Arc::clone(&base.tree);
        let path_buf = std::path::PathBuf::from(path);

        py.allow_threads(move || {
            let content = std::fs::read_to_string(&path_buf)?;
            let mut tree = shared.tree.write().unwrap();
            hier_config_core::parser::parse_into_tree(&mut tree, &content).map_err(to_py_err)?;
            hier_config_core::post_load::delete_sectional_exit_recursive(&mut tree);
            if run_post_load {
                hier_config_core::post_load::run_post_load_callbacks(&mut tree);
            }
            Ok::<(), PyErr>(())
        })
    }

    /// Reconstructs the tree structure from a [`Dump`] model inside a single FFI call.
    ///
    /// Unpacks line attributes and delegates tree reconstruction to native Rust in O(N)
    /// without per-node Python FFI round-trips.
    #[pyo3(signature = (dump))]
    pub fn _load_from_dump_native(slf: PyRef<'_, Self>, dump: &Bound<'_, PyAny>) -> PyResult<()> {
        let py = slf.py();
        let base: &PyHConfigBase = slf.as_ref();
        let shared = Arc::clone(&base.tree);

        let lines_attr = if let Ok(lines) = dump.getattr("lines") {
            lines
        } else {
            dump.clone()
        };

        let n_dict = PyString::intern(py, "__dict__");
        let k_depth = PyString::intern(py, "depth");
        let k_text = PyString::intern(py, "text");
        let k_tags = PyString::intern(py, "tags");
        let k_comments = PyString::intern(py, "comments");
        let k_new_in_config = PyString::intern(py, "new_in_config");

        let mut dump_lines = Vec::new();
        if let Ok(tuple) = lines_attr.downcast::<PyTuple>() {
            dump_lines.reserve(tuple.len());
            for item in tuple.iter() {
                dump_lines.push(parse_dump_line(
                    &item,
                    &n_dict,
                    &k_depth,
                    &k_text,
                    &k_tags,
                    &k_comments,
                    &k_new_in_config,
                )?);
            }
        } else if let Ok(list) = lines_attr.downcast::<PyList>() {
            dump_lines.reserve(list.len());
            for item in list.iter() {
                dump_lines.push(parse_dump_line(
                    &item,
                    &n_dict,
                    &k_depth,
                    &k_text,
                    &k_tags,
                    &k_comments,
                    &k_new_in_config,
                )?);
            }
        } else {
            for item in lines_attr.try_iter()? {
                dump_lines.push(parse_dump_line(
                    &item?,
                    &n_dict,
                    &k_depth,
                    &k_text,
                    &k_tags,
                    &k_comments,
                    &k_new_in_config,
                )?);
            }
        }

        py.allow_threads(move || {
            let mut tree = shared.tree.write().unwrap();
            tree.load_from_dump(&Dump { lines: dump_lines })
        })
        .map_err(to_py_err)
    }

    pub fn add_children_deep(slf: PyRef<'_, Self>, lines: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let py = slf.py();
        let mut current: PyObject = slf.into_py_any(py)?;
        let mut count = 0;
        for line in lines.try_iter()? {
            let text: String = line?.extract()?;
            let base: PyRef<'_, PyHConfigBase> = current.extract(py)?;
            current = base.add_child(py, &text, true, true)?;
            count += 1;
        }
        if count == 0 {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "base was an HConfig object",
            ));
        }
        Ok(current)
    }

    pub fn add_ancestor_copy_of(
        slf: PyRef<'_, Self>,
        parent_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let py = slf.py();
        let parent_child = parent_to_add.extract::<PyRef<'_, crate::child::PyHConfigChild>>()?;
        let parent_base = parent_child.as_ref();
        let lineage = parent_base.lineage(py)?;
        let mut current: PyObject = slf.into_py_any(py)?;
        for ancestor in lineage {
            let base: PyRef<'_, PyHConfigBase> = current.extract(py)?;
            current = base.add_shallow_copy_of(py, ancestor.bind(py), false)?;
        }
        Ok(current)
    }

    pub fn difference(slf: PyRef<'_, Self>, target: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        let target_hconfig = target.extract::<PyRef<'_, Self>>()?;
        let target_base = target_hconfig.as_ref();

        let my_tree = base.tree.tree.read().unwrap();
        let other_tree = target_base.tree.tree.read().unwrap();
        let delta_tree =
            hier_config_core::remediation::difference(&my_tree, &other_tree).map_err(to_py_err)?;
        drop(my_tree);
        drop(other_tree);

        let hconfig = create_py_hconfig(
            py,
            delta_tree,
            base.tree.platform,
            slf.driver_obj.clone_ref(py),
        )?;
        Ok(hconfig.into_any())
    }

    /// v4 name for `config_to_get_to()`.
    #[pyo3(signature = (target, delta = None))]
    pub fn remediation(
        slf: PyRef<'_, Self>,
        target: &Bound<'_, PyAny>,
        delta: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyObject> {
        Self::config_to_get_to(slf, target, delta)
    }

    #[pyo3(signature = (target, delta = None))]
    pub fn config_to_get_to(
        slf: PyRef<'_, Self>,
        target: &Bound<'_, PyAny>,
        delta: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        base.tree.sync_rules(py)?;
        let target_hconfig = target.extract::<PyRef<'_, Self>>()?;
        let target_base = target_hconfig.as_ref();
        target_base.tree.sync_rules(py)?;

        if let Some(d) = delta {
            let delta_hconfig = d.extract::<PyRef<'_, Self>>()?;
            let delta_base = delta_hconfig.as_ref();
            delta_base.tree.sync_rules(py)?;
            let mut delta_tree = delta_base.tree.tree.write().unwrap();

            // When a source aliases the delta tree, read-locking the same `RwLock` on
            // this thread while the write lock is held would deadlock. In that case
            // clone the source from the write guard we already hold; otherwise read-lock.
            let delta_is_base = Arc::ptr_eq(&delta_base.tree, &base.tree);
            let delta_is_target = Arc::ptr_eq(&delta_base.tree, &target_base.tree);
            let my_clone: Option<Tree> = delta_is_base.then(|| delta_tree.clone());
            let target_clone: Option<Tree> = delta_is_target.then(|| delta_tree.clone());
            let my_guard = (!delta_is_base).then(|| base.tree.tree.read().unwrap());
            let target_guard = (!delta_is_target).then(|| target_base.tree.tree.read().unwrap());
            let my_tree: &Tree = my_clone
                .as_ref()
                .unwrap_or_else(|| my_guard.as_deref().unwrap());
            let other_tree: &Tree = target_clone
                .as_ref()
                .unwrap_or_else(|| target_guard.as_deref().unwrap());

            hier_config_core::remediation::config_to_get_to_into(
                my_tree,
                other_tree,
                &mut delta_tree,
            )
            .map_err(to_py_err)?;
            Ok(d.clone().unbind())
        } else {
            let my_tree = base.tree.tree.read().unwrap();
            let other_tree = target_base.tree.tree.read().unwrap();
            let delta_tree = hier_config_core::remediation::config_to_get_to(&my_tree, &other_tree)
                .map_err(to_py_err)?;
            drop(my_tree);
            drop(other_tree);

            let hconfig = create_py_hconfig(
                py,
                delta_tree,
                base.tree.platform,
                slf.driver_obj.clone_ref(py),
            )?;
            Ok(hconfig.into_any())
        }
    }

    #[pyo3(signature = (config, *, prune_empty_branches = false))]
    pub fn future(
        slf: PyRef<'_, Self>,
        config: &Bound<'_, PyAny>,
        prune_empty_branches: bool,
    ) -> PyResult<PyObject> {
        let (future_config, _) = Self::future_with_report(slf, config, prune_empty_branches)?;
        Ok(future_config)
    }

    /// Like `future()`, but also reports how the change's negations resolved.
    ///
    /// Returns `(future_config, FutureReport)`. The report's nodes belong to
    /// the returned tree, so callers can walk their surrounding context.
    #[pyo3(signature = (config, *, prune_empty_branches = false))]
    pub fn future_with_report(
        slf: PyRef<'_, Self>,
        config: &Bound<'_, PyAny>,
        prune_empty_branches: bool,
    ) -> PyResult<(PyObject, PyObject)> {
        let py = slf.py();
        let base = slf.as_ref();
        base.tree.sync_rules(py)?;
        let config_hconfig = config.extract::<PyRef<'_, Self>>()?;
        let config_base = config_hconfig.as_ref();
        config_base.tree.sync_rules(py)?;

        let my_tree = base.tree.tree.read().unwrap();
        let cfg_tree = config_base.tree.tree.read().unwrap();
        let (fut_tree, report) = hier_config_core::remediation::future_with_report(
            &my_tree,
            &cfg_tree,
            prune_empty_branches,
        )
        .map_err(to_py_err)?;
        drop(my_tree);
        drop(cfg_tree);

        let fut_root = fut_tree.root;
        let shared_tree = Arc::new(SharedTree::new(fut_tree, base.tree.platform));
        shared_tree.set_driver(slf.driver_obj.clone_ref(py));
        shared_tree.sync_rules(py)?;
        let hconfig = Py::new(
            py,
            (
                Self {
                    driver_obj: slf.driver_obj.clone_ref(py),
                },
                PyHConfigBase {
                    tree: Arc::clone(&shared_tree),
                    node_id: fut_root,
                },
            ),
        )?;
        let mut handle = shared_tree.root_handle.write().unwrap();
        *handle = Some(hconfig.clone_ref(py).into_any());
        drop(handle);

        let wrap = |ids: &[hier_config_core::NodeId]| -> PyResult<Vec<PyObject>> {
            ids.iter()
                .map(|&id| {
                    SharedTree::get_or_create_child(&shared_tree, py, id, None).map(Py::into_any)
                })
                .collect()
        };
        let unresolved = wrap(&report.unresolved_negations)?;
        let replacements = wrap(&report.idempotency_replacements)?;
        let py_report = py
            .import("hier_config.tree_algorithms")?
            .getattr("FutureReport")?
            .call1((
                PyTuple::new(py, unresolved)?,
                PyTuple::new(py, replacements)?,
            ))?;

        Ok((hconfig.into_any(), py_report.unbind()))
    }

    pub fn deep_copy(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        let cloned_tree = {
            let tree = base.tree.tree.read().unwrap();
            tree.clone()
        };
        let cloned_root = cloned_tree.root;
        let shared_tree = Arc::new(SharedTree::new(cloned_tree, base.tree.platform));
        shared_tree.set_driver(slf.driver_obj.clone_ref(py));
        shared_tree.sync_rules(py)?;
        let hconfig = Py::new(
            py,
            (
                Self {
                    driver_obj: slf.driver_obj.clone_ref(py),
                },
                PyHConfigBase {
                    tree: Arc::clone(&shared_tree),
                    node_id: cloned_root,
                },
            ),
        )?;
        let mut handle = shared_tree.root_handle.write().unwrap();
        *handle = Some(hconfig.clone_ref(py).into_any());
        drop(handle);
        Ok(hconfig.into_any())
    }

    pub fn with_tags(slf: PyRef<'_, Self>, tags: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let py = slf.py();
        let frozenset_fn = py.import("builtins")?.getattr("frozenset")?;
        let tags_set = frozenset_fn.call1((tags,))?;

        let driver = slf.driver_obj.clone_ref(py);
        let platform = Self::parse_platform(py, &driver);
        let tree = Tree::for_platform(platform);
        let root_id = tree.root;
        let shared_tree = Arc::new(SharedTree::new(tree, platform));
        shared_tree.set_driver(driver.clone_ref(py));
        shared_tree.sync_rules(py)?;

        let new_conf = Py::new(
            py,
            (
                Self { driver_obj: driver },
                PyHConfigBase {
                    tree: Arc::clone(&shared_tree),
                    node_id: root_id,
                },
            ),
        )?;
        let mut handle = shared_tree.root_handle.write().unwrap();
        *handle = Some(new_conf.clone_ref(py).into_any());
        drop(handle);

        let slf_base = slf.as_ref();
        slf_base.with_tags_internal(py, &tags_set, new_conf.bind(py).as_any())?;
        Ok(new_conf.into_any())
    }

    pub fn _is_object_referenced(
        slf: PyRef<'_, Self>,
        name: &str,
        reference_locations: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let py = slf.py();
        let re_mod = py.import("re")?;
        let re_escape = re_mod.getattr("escape")?;
        let re_search = re_mod.getattr("search")?;

        let escaped_name = re_escape.call1((name,))?;
        let slf_obj = slf.into_py_any(py)?;
        let slf_bound = slf_obj.bind(py);

        for ref_loc in reference_locations.try_iter()? {
            let ref_loc = ref_loc?;
            let ref_re_template: String = ref_loc.getattr("reference_re")?.extract()?;
            let pattern = ref_re_template.replace("{name}", &escaped_name.extract::<String>()?);
            let match_rules = ref_loc.getattr("match_rules")?;
            let sections = slf_bound.call_method("get_children_deep", (match_rules,), None)?;
            for section in sections.try_iter()? {
                let section = section?;
                let all_children = section.call_method0("all_children")?;
                for d in all_children.try_iter()? {
                    let d = d?;
                    let text = d.getattr("text")?;
                    let m = re_search.call1((&pattern, text))?;
                    if !m.is_none() {
                        return Ok(true);
                    }
                }
            }
        }
        Ok(false)
    }

    pub fn unused_objects(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let re_mod = py.import("re")?;
        let re_search = re_mod.getattr("search")?;

        let driver = slf.driver_obj.bind(py);
        let rules = driver.getattr("rules")?;
        let unused_rules = rules.getattr("unused_objects")?;

        let slf_obj = slf.into_py_any(py)?;
        let slf_bound = slf_obj.bind(py);

        let mut unused_list = Vec::new();
        let mut seen_names = std::collections::HashSet::new();

        for rule in unused_rules.try_iter()? {
            let rule = rule?;
            let match_rules = rule.getattr("match_rules")?;
            let name_re = rule.getattr("name_re")?;
            let reference_locations = rule.getattr("reference_locations")?;

            let definitions = slf_bound.call_method("get_children_deep", (match_rules,), None)?;
            for def_child in definitions.try_iter()? {
                let def_child = def_child?;
                let text = def_child.getattr("text")?;
                let m = re_search.call1((&name_re, text))?;
                if m.is_none() {
                    continue;
                }
                let name: String = m.call_method1("group", ("name",))?.extract()?;
                if seen_names.contains(&name) {
                    continue;
                }
                seen_names.insert(name.clone());

                let is_referenced: bool = slf_bound
                    .call_method1("_is_object_referenced", (name, &reference_locations))?
                    .extract()?;
                if !is_referenced {
                    unused_list.push(def_child.unbind());
                }
            }
        }

        crate::base::items_sequence(py, unused_list)
    }

    pub fn set_order_weight(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        let base = slf.as_ref();
        {
            let mut tree = base.tree.tree.write().unwrap();
            tree.set_order_weight();
        }
        slf
    }

    #[pyo3(signature = (*, sectional_exiting = false))]
    pub fn dump_simple(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        sectional_exiting: bool,
    ) -> PyResult<Py<PyTuple>> {
        let base = slf.as_ref();
        base.dump_simple(py, sectional_exiting)
    }

    /// Create an `HConfig` from raw configuration text (or a Path to it).
    #[classmethod]
    #[pyo3(signature = (platform_or_driver, config_text = None))]
    pub fn from_text(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        platform_or_driver: PyObject,
        config_text: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let text = match config_text {
            Some(obj) => obj,
            None => "".into_pyobject(py)?.into_any().unbind(),
        };
        py.import("hier_config.constructors")?
            .getattr("hconfig_from_text")?
            .call1((platform_or_driver, text))
            .map(Bound::unbind)
    }

    /// Create an `HConfig` from pre-split configuration lines (fast load).
    #[classmethod]
    pub fn from_lines(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        platform_or_driver: PyObject,
        lines: PyObject,
    ) -> PyResult<PyObject> {
        py.import("hier_config.constructors")?
            .getattr("hconfig_from_lines")?
            .call1((platform_or_driver, lines))
            .map(Bound::unbind)
    }

    /// Reconstruct an `HConfig` from a serialized `Dump`.
    #[classmethod]
    pub fn from_dump(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        platform_or_driver: PyObject,
        dump: PyObject,
    ) -> PyResult<PyObject> {
        py.import("hier_config.constructors")?
            .getattr("hconfig_from_dump")?
            .call1((platform_or_driver, dump))
            .map(Bound::unbind)
    }

    /// Create an `HConfig` from a JSON object or JSON text.
    #[classmethod]
    #[pyo3(signature = (platform_or_driver, data, *, list_keys = None))]
    pub fn from_json(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        platform_or_driver: PyObject,
        data: PyObject,
        list_keys: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let kwargs = PyDict::new(py);
        kwargs.set_item("list_keys", list_keys)?;
        py.import("hier_config.formats")?
            .getattr("hconfig_from_json")?
            .call((platform_or_driver, data), Some(&kwargs))
            .map(Bound::unbind)
    }

    /// Create an `HConfig` from an XML document.
    #[classmethod]
    #[pyo3(signature = (platform_or_driver, source, *, list_keys = None))]
    pub fn from_xml(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        platform_or_driver: PyObject,
        source: PyObject,
        list_keys: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let kwargs = PyDict::new(py);
        kwargs.set_item("list_keys", list_keys)?;
        py.import("hier_config.formats")?
            .getattr("hconfig_from_xml")?
            .call((platform_or_driver, source), Some(&kwargs))
            .map(Bound::unbind)
    }

    /// Render a tree built by `from_json` back to JSON text.
    #[pyo3(signature = (*, indent = Some(2)))]
    pub fn to_json(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        indent: Option<u32>,
    ) -> PyResult<PyObject> {
        let kwargs = PyDict::new(py);
        kwargs.set_item("indent", indent)?;
        py.import("hier_config.formats")?
            .getattr("hconfig_to_json")?
            .call((slf.into_pyobject(py)?,), Some(&kwargs))
            .map(Bound::unbind)
    }

    /// Render a tree built by `from_xml` back to XML text.
    pub fn to_xml(slf: PyRef<'_, Self>, py: Python<'_>) -> PyResult<PyObject> {
        py.import("hier_config.formats")?
            .getattr("hconfig_to_xml")?
            .call1((slf.into_pyobject(py)?,))
            .map(Bound::unbind)
    }

    /// v4 name for `dump_simple()`.
    #[pyo3(signature = (*, sectional_exiting = false))]
    pub fn to_lines(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        sectional_exiting: bool,
    ) -> PyResult<Py<PyTuple>> {
        let base = slf.as_ref();
        base.dump_simple(py, sectional_exiting)
    }

    pub fn dump(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let base = slf.as_ref();
        let models_mod = py.import("hier_config.models")?;
        let dump_line_cls = models_mod.getattr("DumpLine")?;
        let dump_cls = models_mod.getattr("Dump")?;

        // Read node state straight out of the arena. Going through per-node
        // `HConfigChild` handles would allocate one Python object per line and
        // then pay five attribute round-trips on each of them.
        let ordered: Vec<DumpRow> = {
            let tree = base.tree.tree.read().unwrap();
            let node_data = base.tree.node_data.read().unwrap();
            // Every node under the root becomes one row, so the arena's own length is
            // an upper bound on the row count. Calling `all_children` purely to size
            // this would walk the whole tree an extra time and allocate a `Vec` to
            // throw away.
            let mut rows = Vec::with_capacity(tree.arena.len());
            // Tags and comments are empty on the overwhelming majority of lines.
            // Frozensets are immutable, so one shared instance can back every such
            // line instead of allocating two throwaway objects per line.
            let empty_set: Py<PyAny> = PyFrozenSet::empty(py)?.into_any().unbind();
            for node_id in tree.all_children_sorted(base.node_id) {
                let node = &tree.arena[node_id];
                let tags = if node.tags().is_empty() {
                    empty_set.clone_ref(py)
                } else {
                    PyFrozenSet::new(py, node.tags().iter())?
                        .into_any()
                        .unbind()
                };

                // Comments live in two places: the Rust node and, once Python has
                // mutated them, the per-node Python set. Union both.
                let py_comments = node_data.get(&node_id).and_then(|d| d.comments.as_ref());
                let comments = match py_comments {
                    Some(py_comments) => {
                        let merged = PySet::new(py, node.comments().iter())?;
                        for item in py_comments.bind(py).iter() {
                            merged.add(item)?;
                        }
                        PyFrozenSet::new(py, merged.iter())?.into_any().unbind()
                    }
                    None if node.comments().is_empty() => empty_set.clone_ref(py),
                    None => PyFrozenSet::new(py, node.comments().iter())?
                        .into_any()
                        .unbind(),
                };

                rows.push((
                    tree.depth(node_id),
                    PyString::new(py, &node.text).into_any().unbind(),
                    tags,
                    comments,
                    node.new_in_config,
                ));
            }
            rows
        };

        // Populate each model's slots directly rather than calling `DumpLine(...)`
        // or `model_construct`. Both re-derive per-field metadata on every call and
        // dominate the runtime at tens of thousands of lines; every value here is
        // already the correct type because it came from the tree's own typed state.
        let builtins = py.import("builtins")?;
        let object_new = builtins.getattr("object")?.getattr("__new__")?;
        let line_fields_set = PyFrozenSet::new(
            py,
            ["depth", "text", "tags", "comments", "new_in_config"].iter(),
        )?;
        let none = py.None().into_bound(py);

        // Hoist everything that is identical on every line: the attribute names,
        // the single-element argument tuple handed to `object.__new__`, and the
        // interned field-name keys used to build each instance's `__dict__`.
        let n_dict = PyString::intern(py, "__dict__").into_any();
        let n_fields_set = PyString::intern(py, "__pydantic_fields_set__").into_any();
        let n_extra = PyString::intern(py, "__pydantic_extra__").into_any();
        let n_private = PyString::intern(py, "__pydantic_private__").into_any();
        let k_depth = PyString::intern(py, "depth");
        let k_text = PyString::intern(py, "text");
        let k_tags = PyString::intern(py, "tags");
        let k_comments = PyString::intern(py, "comments");
        let k_new_in_config = PyString::intern(py, "new_in_config");
        let py_false = false.into_pyobject(py)?.to_owned().into_any();
        let py_true = true.into_pyobject(py)?.to_owned().into_any();

        // Copying a template dict that already holds all five keys keeps every
        // instance's `__dict__` on the "replace an existing key" path, which skips
        // the insert and table-resize work an empty dict pays on each line.
        let template = PyDict::new(py);
        template.set_item(&k_depth, 0usize)?;
        template.set_item(&k_text, "")?;
        template.set_item(&k_tags, &none)?;
        template.set_item(&k_comments, &none)?;
        template.set_item(&k_new_in_config, &py_false)?;

        let line_type = dump_line_cls.downcast::<PyType>()?;
        let mut lines = Vec::with_capacity(ordered.len());
        for (depth, text, tags, comments, new_in_config) in ordered {
            let fields = template.copy()?;
            fields.set_item(&k_depth, depth)?;
            fields.set_item(&k_text, text)?;
            fields.set_item(&k_tags, tags)?;
            fields.set_item(&k_comments, comments)?;
            fields.set_item(
                &k_new_in_config,
                if new_in_config { &py_true } else { &py_false },
            )?;

            let line = generic_new(line_type)?;
            generic_setattr(&line, &n_dict, fields.as_any())?;
            generic_setattr(&line, &n_fields_set, line_fields_set.as_any())?;
            generic_setattr(&line, &n_extra, &none)?;
            generic_setattr(&line, &n_private, &none)?;
            lines.push(line);
        }

        let dump_fields = PyDict::new(py);
        dump_fields.set_item("lines", PyTuple::new(py, lines)?)?;
        let dump_obj = object_new.call1((&dump_cls,))?;
        generic_setattr(&dump_obj, &n_dict, dump_fields.as_any())?;
        generic_setattr(
            &dump_obj,
            &n_fields_set,
            PyFrozenSet::new(py, ["lines"].iter())?.as_any(),
        )?;
        generic_setattr(&dump_obj, &n_extra, &none)?;
        generic_setattr(&dump_obj, &n_private, &none)?;
        Ok(dump_obj.unbind())
    }

    pub fn __deepcopy__(slf: PyRef<'_, Self>, _memo: &Bound<'_, PyAny>) -> PyResult<Py<Self>> {
        let py = slf.py();
        let base = slf.as_ref();
        let cloned_tree = {
            let tree = base.tree.tree.read().unwrap();
            tree.clone()
        };
        let root_id = cloned_tree.root;
        let platform = base.tree.platform;
        let new_shared_tree = Arc::new(SharedTree::new(cloned_tree, platform));

        {
            let data = base.tree.node_data.read().unwrap();
            let mut new_data = new_shared_tree.node_data.write().unwrap();
            let copy_mod = py.import("copy")?;
            let deepcopy_fn = copy_mod.getattr("deepcopy")?;
            for (&nid, nd) in data.iter() {
                let mut copied = crate::tree::NodePyData::default();
                if let Some(facts) = &nd.facts {
                    copied.facts = Some(deepcopy_fn.call1((facts,))?.extract()?);
                }
                if let Some(comments) = &nd.comments {
                    copied.comments = Some(deepcopy_fn.call1((comments,))?.extract()?);
                }
                if let Some(instances) = &nd.instances {
                    copied.instances = Some(deepcopy_fn.call1((instances,))?.extract()?);
                }
                new_data.insert(nid, copied);
            }
        }

        let new_driver = slf.driver_obj.clone_ref(py);
        let new_conf = Py::new(
            py,
            (
                Self {
                    driver_obj: new_driver,
                },
                PyHConfigBase {
                    tree: Arc::clone(&new_shared_tree),
                    node_id: root_id,
                },
            ),
        )?;
        let mut handle = new_shared_tree.root_handle.write().unwrap();
        *handle = Some(new_conf.clone_ref(py).into_any());
        drop(handle);
        Ok(new_conf)
    }

    pub fn __reduce__(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let constructors = py.import("hier_config.constructors")?;
        let func = constructors.getattr("get_hconfig_from_dump")?;
        let driver = slf.driver_obj.clone_ref(py);
        let dump = Self::dump(slf)?;
        let args = PyTuple::new(py, vec![driver, dump])?;
        Ok(
            PyTuple::new(py, vec![func.into_any().unbind(), args.into_any().unbind()])?
                .into_any()
                .unbind(),
        )
    }

    fn __repr__(slf: PyRef<'_, Self>) -> PyResult<String> {
        let py = slf.py();
        let driver_cls = slf.driver_obj.getattr(py, "__class__")?;
        let driver_name: String = driver_cls.getattr(py, "__name__")?.extract(py)?;
        let py_lines = slf.as_ref().dump_simple(py, false)?;
        Ok(format!(
            "HConfig(driver={}, lines={})",
            driver_name,
            py_lines.bind(py).repr()?
        ))
    }

    fn __str__(slf: PyRef<'_, Self>) -> String {
        // Mirrors the reference implementation, which joins ``str(child)`` over
        // the *direct* children only. Each child already renders its own
        // subtree, so walking every descendant here would emit nested lines
        // twice. ``lines`` skips the root's own text and exit, making it
        // exactly equivalent.
        slf.as_ref().lines(true).join("\n")
    }

    fn __eq__(slf: PyRef<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let py = slf.py();
        if let Ok(other_hconfig) = other.extract::<PyRef<'_, Self>>() {
            let base = slf.as_ref();
            let other_base = other_hconfig.as_ref();
            let my_children = base.get_children_object(py)?;
            let other_children = other_base.get_children_object(py)?;
            let res = my_children.bind(py).eq(other_children.bind(py))?;
            return res.into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    fn __ne__(slf: PyRef<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let py = slf.py();
        if let Ok(other_hconfig) = other.extract::<PyRef<'_, Self>>() {
            let base = slf.as_ref();
            let other_base = other_hconfig.as_ref();
            let my_children = base.get_children_object(py)?;
            let other_children = other_base.get_children_object(py)?;
            let res = my_children.bind(py).ne(other_children.bind(py))?;
            return res.into_py_any(py);
        }
        Ok(py.NotImplemented())
    }

    fn __hash__(slf: PyRef<'_, Self>) -> PyResult<isize> {
        let py = slf.py();
        let base = slf.as_ref();
        let children = base.get_children_object(py)?;
        let h = children.bind(py).hash()?;
        Ok(h)
    }
}
