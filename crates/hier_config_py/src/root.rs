//! `PyHConfig` representing the root configuration tree in Python.

use std::collections::BTreeSet;
use std::sync::Arc;

use hier_config_core::models::{Dump, DumpLine};
use hier_config_core::{Platform, Tree};
use pyo3::IntoPyObjectExt;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PySet, PyString, PyTuple, PyType};
use pyo3::{PyTraverseError, PyVisit};

use crate::base::PyHConfigBase;
use crate::errors::to_py_err;
use crate::tree::{NodePyData, PyRwLockExt, SharedTree};

fn get_dump_field<'py>(
    item: &Bound<'py, PyAny>,
    n_dict: &Bound<'py, PyString>,
    key: &Bound<'py, PyString>,
) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(dict_obj) = item.getattr(n_dict)
        && let Ok(dict) = dict_obj.cast::<PyDict>()
        && let Some(val) = dict.get_item(key)?
    {
        return Ok(val);
    }
    item.getattr(key)
}

fn extract_dump_strings(val: Bound<'_, PyAny>) -> PyResult<BTreeSet<String>> {
    let mut set = BTreeSet::new();
    if let Ok(fset) = val.cast::<PyFrozenSet>() {
        for item in fset.iter() {
            set.insert(item.extract::<String>()?);
        }
    } else if let Ok(pyset) = val.cast::<PySet>() {
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

/// A class for representing and comparing Cisco like configurations in a
/// hierarchical tree data structure.
#[pyo3_stub_gen::derive::gen_stub_pyclass]
#[pyclass(extends = PyHConfigBase, subclass, module = "hier_config._hier_config_rust", name = "HConfig")]
#[derive(Debug)]
pub struct PyHConfig {
    pub driver_obj: Py<PyAny>,
}

impl PyHConfig {
    pub fn parse_platform(py: Python<'_>, driver: &Py<PyAny>) -> PyResult<Platform> {
        let selector = driver.getattr(py, "platform")?;
        if selector.is_none(py) {
            return Ok(Platform::Generic);
        }
        // Platform is a str enum, so both enum members and explicit string
        // selectors follow the same parsing path. A non-string selector is
        // rejected rather than coerced: `test_review_handles.py` pins that bad
        // platform metadata must not silently fall back to Generic. Drivers
        // that carry no platform (including test doubles) must say so with
        // `platform = None`, which is handled above.
        let Ok(value) = selector.extract::<String>(py) else {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "driver.platform must be a string or None, got {}",
                selector.bind(py).get_type().name()?
            )));
        };
        value.parse::<Platform>().map_err(|_| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "unsupported driver.platform: {value:?}"
            ))
        })
    }

    pub fn get_default_driver(py: Python<'_>, platform: Platform) -> PyResult<Py<PyAny>> {
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
/// method allocates an argument tuple per assignment; `Py<PyAny>_GenericSetAttr`
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
    driver_obj: Py<PyAny>,
) -> PyResult<Py<PyHConfig>> {
    let root_id = tree.root;
    let shared_tree = Arc::new(SharedTree::new(tree, platform));
    shared_tree.set_driver(driver_obj.clone_ref(py))?;
    // A test double (`MagicMock(spec=HConfigDriverBase)`) exposes only the
    // attributes declared on the class, so `driver.rules` may be missing
    // entirely. The stale check tolerates that and leaves the platform
    // defaults in place instead of failing construction.
    shared_tree.sync_rules_if_stale(py)?;
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
    shared_tree.set_root_handle(hconfig.bind(py).as_any())?;
    Ok(hconfig)
}

#[pyo3_stub_gen::derive::gen_stub_pymethods]
#[pymethods]
impl PyHConfig {
    #[new]
    #[gen_stub(override_return_type(type_repr="typing_extensions.Self", imports=("typing_extensions")))]
    #[pyo3(signature = (driver, *args, **kwargs))]
    fn new(
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="hier_config.platforms.driver_base.HConfigDriverBase", imports=("hier_config.platforms.driver_base")))]
        driver: Py<PyAny>,
        // A subclass may declare its own `__init__(self, driver, label)`. The
        // native `__new__` runs first and with the same arguments, so a rigid
        // signature would reject the subclass outright. Extra arguments belong
        // to the subclass and are ignored here.
        #[gen_stub(override_type(type_repr="builtins.object", imports=("builtins")))] args: &Bound<
            '_,
            PyTuple,
        >,
        #[gen_stub(override_type(type_repr="builtins.object", imports=("builtins")))]
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<(Self, PyHConfigBase)> {
        let _ = (args, kwargs);
        let platform = Self::parse_platform(py, &driver)?;
        let tree = Tree::for_platform(platform);
        let root_id = tree.root;
        let shared_tree = Arc::new(SharedTree::new(tree, platform));
        shared_tree.set_driver(driver.clone_ref(py))?;
        // See `create_py_hconfig`: a driver without a `rules` attribute keeps
        // the platform defaults rather than aborting construction.
        shared_tree.sync_rules_if_stale(py)?;

        Ok((
            Self { driver_obj: driver },
            PyHConfigBase {
                tree: shared_tree,
                node_id: root_id,
            },
        ))
    }

    #[pyo3(signature = (driver, *args, **kwargs))]
    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    fn __init__(
        slf: &Bound<'_, Self>,
        #[gen_stub(override_type(type_repr="hier_config.platforms.driver_base.HConfigDriverBase", imports=("hier_config.platforms.driver_base")))]
        driver: &Bound<'_, PyAny>,
        #[gen_stub(override_type(type_repr="builtins.object", imports=("builtins")))] args: &Bound<
            '_,
            PyTuple,
        >,
        #[gen_stub(override_type(type_repr="builtins.object", imports=("builtins")))]
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let _ = (driver, args, kwargs);
        let base_ref = slf.extract::<PyRef<'_, PyHConfigBase>>()?;
        base_ref.tree.set_root_handle(slf.as_any())?;
        Ok(())
    }

    /// Lets `CPython`'s cycle collector see the Python objects this config owns.
    ///
    /// The tree itself is reachable only through a Rust `Arc`, which the
    /// collector cannot traverse, so anything Python-owned that could close a
    /// cycle has to be reported here.
    #[gen_stub(skip)]
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.driver_obj)
    }

    /// Breaks any cycle the collector found.
    ///
    /// The driver is the only strong Python reference held; the tree's own
    /// handles are weak, so dropping this one is enough.
    #[gen_stub(skip)]
    fn __clear__(&mut self) {
        Python::attach(|py| {
            self.driver_obj = py.None();
        });
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="hier_config.platforms.driver_base.HConfigDriverBase", imports=("hier_config.platforms.driver_base")))]
    pub fn driver(slf: PyRef<'_, Self>) -> Py<PyAny> {
        let py = slf.py();
        slf.driver_obj.clone_ref(py)
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    /// The `HConfig` object at the base of the tree.
    pub fn root(slf: PyRef<'_, Self>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let tree = Arc::clone(&slf.as_ref().tree);
        if let Some(handle) = tree.root_handle(py)? {
            return Ok(handle);
        }
        // The recorded handle is weak, so it is gone whenever no caller holds
        // the config. `slf` is that config, so re-record it rather than failing.
        let obj = slf.into_py_any(py)?;
        tree.set_root_handle(obj.bind(py))?;
        Ok(obj)
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn parent(slf: PyRef<'_, Self>) -> PyResult<Py<PyAny>> {
        Self::root(slf)
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="int", imports=()))]
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

    #[gen_stub(override_return_type(type_repr="HConfigChild", imports=()))]
    pub fn instantiate_child(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="str", imports=()))] text: &str,
    ) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let base = slf.as_ref();
        let child_id = {
            let mut tree = base.write_tree()?;
            tree.create_child_unattached(base.node_id, text)
        };
        let child = SharedTree::get_or_create_child(&base.tree, py, child_id, None)?;
        Ok(child.into_any())
    }

    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    /// Merges other `HConfig` objects into this one.
    pub fn merge(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="HConfig | collections.abc.Iterable[HConfig]", imports=("collections.abc")))]
        other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
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
        } else if let Ok(iter) = other.try_iter() {
            for item in iter {
                merge_single(&item?)?;
            }
        } else {
            merge_single(other)?;
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
    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn _load_native(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="str", imports=()))] config_raw: &str,
        #[gen_stub(override_type(type_repr="bool", imports=()))] run_post_load: bool,
    ) -> PyResult<()> {
        let py = slf.py();
        let base: &PyHConfigBase = slf.as_ref();
        let shared = Arc::clone(&base.tree);
        // Copy the text out of Python memory so the GIL can be released for the parse.
        let owned = config_raw.to_owned();

        py.detach(move || {
            let mut tree = shared.tree.write_py()?;
            hier_config_core::parser::parse_into_tree(&mut tree, &owned).map_err(to_py_err)?;
            hier_config_core::post_load::delete_sectional_exit_recursive(&mut tree);
            if run_post_load {
                hier_config_core::post_load::run_post_load_callbacks(&mut tree);
            }
            Ok::<(), PyErr>(())
        })
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
    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn _load_fast_native(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="str | collections.abc.Iterable[str]", imports=("collections.abc")))]
        lines: &Bound<'_, PyAny>,
        #[gen_stub(override_type(type_repr="bool", imports=()))] run_post_load: bool,
    ) -> PyResult<()> {
        let py = slf.py();
        let base: &PyHConfigBase = slf.as_ref();
        let shared = Arc::clone(&base.tree);

        // The parse runs without the GIL, so the text has to be copied out of Python
        // memory first.
        let (buf, spans) = if let Ok(text) = lines.cast::<PyString>() {
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
                buf.push_str(line.cast::<PyString>()?.to_str()?);
                spans.push((start, buf.len()));
                Ok(())
            };
            // A list or tuple is by far the common case and can be walked by index,
            // which skips constructing a Python iterator and calling `__next__` once
            // per line.
            if let Ok(list) = lines.cast::<PyList>() {
                for line in list {
                    push(&line)?;
                }
            } else if let Ok(tuple) = lines.cast::<PyTuple>() {
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

        py.detach(move || {
            let borrowed: Vec<&str> = match &spans {
                Some(spans) => spans.iter().map(|&(s, e)| &buf[s..e]).collect(),
                None => buf.lines().collect(),
            };
            let mut tree = shared.tree.write_py()?;
            hier_config_core::parser::load_fast(&mut tree, &borrowed, run_post_load)
                .map_err(to_py_err)
        })
    }

    /// Reads and parses an on-disk config file into this tree inside a single FFI call.
    ///
    /// Reads the file directly via `std::fs::read_to_string` with the GIL released,
    /// avoiding intermediate Python `str` allocations.
    #[pyo3(signature = (path, run_post_load = true))]
    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn _load_file_native(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="str", imports=()))] path: &str,
        #[gen_stub(override_type(type_repr="bool", imports=()))] run_post_load: bool,
    ) -> PyResult<()> {
        let py = slf.py();
        let base: &PyHConfigBase = slf.as_ref();
        let shared = Arc::clone(&base.tree);
        let path_buf = std::path::PathBuf::from(path);

        py.detach(move || {
            let content = std::fs::read_to_string(&path_buf)?;
            let mut tree = shared.tree.write_py()?;
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
    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    pub fn _load_from_dump_native(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[hier_config.models.DumpLine]", imports=("collections.abc", "hier_config.models")))]
        dump: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
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
        if let Ok(tuple) = lines_attr.cast::<PyTuple>() {
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
        } else if let Ok(list) = lines_attr.cast::<PyList>() {
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

        py.detach(move || {
            let mut tree = shared.tree.write_py()?;
            tree.load_from_dump(&Dump { lines: dump_lines })
                .map_err(to_py_err)
        })
    }

    #[gen_stub(override_return_type(type_repr="HConfigChild", imports=()))]
    /// Add child instances of `HConfigChild` deeply.
    pub fn add_children_deep(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str]", imports=("collections.abc")))]
        lines: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let mut current: Py<PyAny> = slf.into_py_any(py)?;
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

    #[gen_stub(override_return_type(type_repr="HConfig | HConfigChild", imports=()))]
    /// Add a copy of the ancestry of `parent_to_add` to self
    /// and return the deepest child which is equivalent to `parent_to_add`.
    pub fn add_ancestor_copy_of(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="HConfigChild", imports=()))] parent_to_add: &Bound<
            '_,
            PyAny,
        >,
    ) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let parent_child = parent_to_add.extract::<PyRef<'_, crate::child::PyHConfigChild>>()?;
        let parent_base = parent_child.as_ref();
        let base = slf.as_ref();

        let new_node_id = if Arc::ptr_eq(&base.tree, &parent_base.tree) {
            let mut my_tree = base.write_tree()?;
            crate::tree::ensure_live(&my_tree, parent_base.node_id)?;
            my_tree
                .add_ancestor_copy_within(base.node_id, parent_base.node_id)
                .map_err(to_py_err)?
        } else {
            let mut my_tree = base.write_tree()?;
            let src_tree = parent_base.read_tree()?;
            my_tree
                .add_ancestor_copy_of(base.node_id, &src_tree, parent_base.node_id)
                .map_err(to_py_err)?
        };

        let child = SharedTree::get_or_create_child(&base.tree, py, new_node_id, None)?;
        Ok(child.into_any())
    }

    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    /// Creates a new `HConfig` object with the config from self that is not in target.
    pub fn difference(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] target: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let base = slf.as_ref();
        let target_hconfig = target.extract::<PyRef<'_, Self>>()?;
        let target_base = target_hconfig.as_ref();

        let my_tree = base.read_tree()?;
        let other_tree = target_base.read_tree()?;
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
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn remediation(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] target: &Bound<'_, PyAny>,
        #[gen_stub(override_type(type_repr="HConfig | None", imports=()))] delta: Option<
            &Bound<'_, PyAny>,
        >,
    ) -> PyResult<Py<PyAny>> {
        Self::config_to_get_to(slf, target, delta)
    }

    #[pyo3(signature = (target, delta = None))]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    /// Figures out what commands need to be executed to transition from self to target.
    /// self is the source data structure(i.e. the `running_config`),
    /// target is the destination(i.e. `generated_config`).
    pub fn config_to_get_to(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] target: &Bound<'_, PyAny>,
        #[gen_stub(override_type(type_repr="HConfig | None", imports=()))] delta: Option<
            &Bound<'_, PyAny>,
        >,
    ) -> PyResult<Py<PyAny>> {
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
            let mut delta_tree = delta_base.write_tree()?;

            // When a source aliases the delta tree, read-locking the same `RwLock` on
            // this thread while the write lock is held would deadlock. In that case
            // clone the source from the write guard we already hold; otherwise read-lock.
            let delta_is_base = Arc::ptr_eq(&delta_base.tree, &base.tree);
            let delta_is_target = Arc::ptr_eq(&delta_base.tree, &target_base.tree);
            let my_clone: Option<Tree> = delta_is_base.then(|| delta_tree.clone());
            let target_clone: Option<Tree> = delta_is_target.then(|| delta_tree.clone());
            let my_guard = (!delta_is_base).then(|| base.read_tree()).transpose()?;
            let target_guard = (!delta_is_target)
                .then(|| target_base.read_tree())
                .transpose()?;
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
            let my_tree = base.read_tree()?;
            let other_tree = target_base.read_tree()?;
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
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    /// EXPERIMENTAL - predict the future config after config is applied to self.
    ///
    /// The quality of this method's output will in part depend on how well
    /// the OS options are tuned. Ensuring that idempotency rules are accurate is
    /// especially important.
    ///
    /// With `prune_empty_branches`, sections that the change emptied out are
    /// removed, matching devices that prune empty stanzas on commit; sections
    /// that were already empty are kept.
    pub fn future(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] config: &Bound<'_, PyAny>,
        #[gen_stub(override_type(type_repr="bool", imports=()))] prune_empty_branches: bool,
    ) -> PyResult<Py<PyAny>> {
        let (future_config, _) = Self::future_with_report(slf, config, prune_empty_branches)?;
        Ok(future_config)
    }

    /// Like `future()`, but also reports how the change's negations resolved.
    ///
    /// Returns `(future_config, FutureReport)`. The report's nodes belong to
    /// the returned tree, so callers can walk their surrounding context.
    #[pyo3(signature = (config, *, prune_empty_branches = false))]
    #[gen_stub(override_return_type(type_repr="tuple[HConfig, hier_config.tree_algorithms.FutureReport]", imports=("hier_config.tree_algorithms")))]
    pub fn future_with_report(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] config: &Bound<'_, PyAny>,
        #[gen_stub(override_type(type_repr="bool", imports=()))] prune_empty_branches: bool,
    ) -> PyResult<(Py<PyAny>, Py<PyAny>)> {
        let py = slf.py();
        let base = slf.as_ref();
        base.tree.sync_rules(py)?;
        let config_hconfig = config.extract::<PyRef<'_, Self>>()?;
        let config_base = config_hconfig.as_ref();
        config_base.tree.sync_rules(py)?;

        let my_tree = base.read_tree()?;
        let cfg_tree = config_base.read_tree()?;
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
        shared_tree.set_driver(slf.driver_obj.clone_ref(py))?;
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
        shared_tree.set_root_handle(hconfig.bind(py).as_any())?;

        let wrap = |ids: &[hier_config_core::NodeId]| -> PyResult<Vec<Py<PyAny>>> {
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

    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    /// Return a copy of this object.
    pub fn deep_copy(slf: PyRef<'_, Self>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let base = slf.as_ref();
        let cloned_tree = {
            let tree = base.read_tree()?;
            tree.clone()
        };
        let cloned_root = cloned_tree.root;
        let shared_tree = Arc::new(SharedTree::new(cloned_tree, base.tree.platform));
        shared_tree.set_driver(slf.driver_obj.clone_ref(py))?;
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
        shared_tree.set_root_handle(hconfig.bind(py).as_any())?;
        Ok(hconfig.into_any())
    }

    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    /// Returns a new instance recursively containing children that only have a subset of tags.
    pub fn with_tags(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str]", imports=("collections.abc")))]
        tags: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let mut tag_set = BTreeSet::new();
        for t in tags.try_iter()? {
            tag_set.insert(t?.extract::<String>()?);
        }

        let driver = slf.driver_obj.clone_ref(py);
        let platform = Self::parse_platform(py, &driver)?;

        let slf_base = slf.as_ref();
        let new_tree = {
            let tree = slf_base.read_tree()?;
            tree.with_tags(&tag_set).map_err(to_py_err)?
        };

        let new_conf = create_py_hconfig(py, new_tree, platform, driver)?;
        Ok(new_conf.into_any())
    }

    pub fn _is_object_referenced(
        slf: PyRef<'_, Self>,
        name: &str,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[hier_config.models.ReferenceLocation]", imports=("collections.abc", "hier_config.models")))]
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

    #[gen_stub(override_return_type(type_repr="collections.abc.Sequence[HConfigChild]", imports=("collections.abc")))]
    /// Yield top-level children that are defined objects with no references.
    ///
    /// Uses ``self.driver.rules.unused_objects`` to identify object definitions,
    /// extract their names, and search for references across the config tree.
    /// Objects with zero references are yielded.
    pub fn unused_objects(slf: PyRef<'_, Self>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let base = slf.as_ref();
        base.tree.sync_rules(py)?;
        let unused_ids = {
            let tree = base.read_tree()?;
            tree.try_unused_objects().map_err(to_py_err)?
        };
        let items = SharedTree::get_or_create_children_batch(&base.tree, py, &unused_ids)?;
        crate::base::items_sequence(py, items)
    }

    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    /// Sets self.order integer on all children.
    pub fn set_order_weight(slf: PyRef<'_, Self>) -> PyResult<PyRef<'_, Self>> {
        let base = slf.as_ref();
        // Ordering rules may have been reassigned since the parse; honor them.
        base.tree.sync_rules_if_stale(slf.py())?;
        {
            let mut tree = base.write_tree()?;
            tree.set_order_weight();
        }
        Ok(slf)
    }

    #[pyo3(signature = (*, sectional_exiting = false))]
    #[gen_stub(override_return_type(type_repr="tuple[str, ...]", imports=()))]
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
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn from_text(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="hier_config.models.Platform | str | hier_config.platforms.driver_base.HConfigDriverBase", imports=("hier_config.models", "hier_config.platforms.driver_base")))]
        platform_or_driver: Py<PyAny>,
        #[gen_stub(override_type(type_repr="str | os.PathLike[str] | None", imports=("os")))]
        config_text: Option<Py<PyAny>>,
    ) -> PyResult<Py<PyAny>> {
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
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn from_lines(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="hier_config.models.Platform | str | hier_config.platforms.driver_base.HConfigDriverBase", imports=("hier_config.models", "hier_config.platforms.driver_base")))]
        platform_or_driver: Py<PyAny>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str]", imports=("collections.abc")))]
        lines: Py<PyAny>,
    ) -> PyResult<Py<PyAny>> {
        py.import("hier_config.constructors")?
            .getattr("hconfig_from_lines")?
            .call1((platform_or_driver, lines))
            .map(Bound::unbind)
    }

    /// Reconstruct an `HConfig` from a serialized `Dump`.
    #[classmethod]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn from_dump(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="hier_config.models.Platform | str | hier_config.platforms.driver_base.HConfigDriverBase", imports=("hier_config.models", "hier_config.platforms.driver_base")))]
        platform_or_driver: Py<PyAny>,
        #[gen_stub(override_type(type_repr="hier_config.models.Dump", imports=("hier_config.models")))]
        dump: Py<PyAny>,
    ) -> PyResult<Py<PyAny>> {
        py.import("hier_config.constructors")?
            .getattr("hconfig_from_dump")?
            .call1((platform_or_driver, dump))
            .map(Bound::unbind)
    }

    /// Create an `HConfig` from a JSON object or JSON text.
    #[classmethod]
    #[pyo3(signature = (platform_or_driver, data, *, list_keys = None))]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn from_json(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="hier_config.models.Platform | str | hier_config.platforms.driver_base.HConfigDriverBase", imports=("hier_config.models", "hier_config.platforms.driver_base")))]
        platform_or_driver: Py<PyAny>,
        #[gen_stub(override_type(type_repr="str | dict[str, hier_config._typing.ValueT]", imports=("hier_config._typing")))]
        data: Py<PyAny>,
        #[gen_stub(override_type(type_repr="tuple[str, ...] | None", imports=()))]
        list_keys: Option<Py<PyAny>>,
    ) -> PyResult<Py<PyAny>> {
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
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn from_xml(
        _cls: &Bound<'_, PyType>,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="hier_config.models.Platform | str | hier_config.platforms.driver_base.HConfigDriverBase", imports=("hier_config.models", "hier_config.platforms.driver_base")))]
        platform_or_driver: Py<PyAny>,
        #[gen_stub(override_type(type_repr="str", imports=()))] source: Py<PyAny>,
        #[gen_stub(override_type(type_repr="tuple[str, ...] | None", imports=()))]
        list_keys: Option<Py<PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        let kwargs = PyDict::new(py);
        kwargs.set_item("list_keys", list_keys)?;
        py.import("hier_config.formats")?
            .getattr("hconfig_from_xml")?
            .call((platform_or_driver, source), Some(&kwargs))
            .map(Bound::unbind)
    }

    /// Render a tree built by `from_json` back to JSON text.
    // PyO3 renders non-literal defaults such as `Some(2)` as `Ellipsis` in
    // `__text_signature__`; spell the default out so runtime and stub agree.
    #[pyo3(signature = (*, indent = Some(2)), text_signature = "($self, *, indent=2)")]
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    pub fn to_json(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        indent: Option<u32>,
    ) -> PyResult<Py<PyAny>> {
        let kwargs = PyDict::new(py);
        kwargs.set_item("indent", indent)?;
        py.import("hier_config.formats")?
            .getattr("hconfig_to_json")?
            .call((slf.into_pyobject(py)?,), Some(&kwargs))
            .map(Bound::unbind)
    }

    /// Render a tree built by `from_xml` back to XML text.
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    pub fn to_xml(slf: PyRef<'_, Self>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        py.import("hier_config.formats")?
            .getattr("hconfig_to_xml")?
            .call1((slf.into_pyobject(py)?,))
            .map(Bound::unbind)
    }

    /// v4 name for `dump_simple()`.
    #[pyo3(signature = (*, sectional_exiting = false))]
    #[gen_stub(override_return_type(type_repr="tuple[str, ...]", imports=()))]
    pub fn to_lines(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        sectional_exiting: bool,
    ) -> PyResult<Py<PyTuple>> {
        let base = slf.as_ref();
        base.dump_simple(py, sectional_exiting)
    }

    #[gen_stub(override_return_type(type_repr="hier_config.models.Dump", imports=("hier_config.models")))]
    /// Dump loaded `HConfig` data.
    pub fn dump(slf: PyRef<'_, Self>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let base = slf.as_ref();
        let models_mod = py.import("hier_config.models")?;
        let dump_line_cls = models_mod.getattr("DumpLine")?;
        let dump_cls = models_mod.getattr("Dump")?;

        // Read node state straight out of the arena. Going through per-node
        // `HConfigChild` handles would allocate one Python object per line and
        // then pay five attribute round-trips on each of them.
        let ordered: Vec<DumpRow> = {
            let tree = base.read_tree()?;
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
                // v3 dumped the recursive union of a node's own tags with its
                // descendants', which is what `Tree::tags` computes.
                let node_tags = tree.tags(node_id);
                let tags = if node_tags.is_empty() {
                    empty_set.clone_ref(py)
                } else {
                    PyFrozenSet::new(py, node_tags.iter())?.into_any().unbind()
                };

                let comments = if node.comments().is_empty() {
                    empty_set.clone_ref(py)
                } else {
                    PyFrozenSet::new(py, node.comments().iter())?
                        .into_any()
                        .unbind()
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
        let line_field_names = ["depth", "text", "tags", "comments", "new_in_config"];
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

        let line_type = dump_line_cls.cast::<PyType>()?;
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
            // pydantic's `model_copy(update=...)` calls `.update()` on this, so it
            // has to be a fresh mutable set rather than a shared frozenset.
            generic_setattr(
                &line,
                &n_fields_set,
                PySet::new(py, line_field_names.iter())?.as_any(),
            )?;
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
            PySet::new(py, ["lines"].iter())?.as_any(),
        )?;
        generic_setattr(&dump_obj, &n_extra, &none)?;
        generic_setattr(&dump_obj, &n_private, &none)?;
        Ok(dump_obj.unbind())
    }

    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn __deepcopy__(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="dict[int, object]", imports=()))] memo: &Bound<
            '_,
            PyDict,
        >,
    ) -> PyResult<Py<Self>> {
        let py = slf.py();
        let base = slf.as_ref();
        let cloned_tree = {
            let tree = base.read_tree()?;
            tree.clone()
        };
        let root_id = cloned_tree.root;
        let platform = base.tree.platform;
        let new_shared_tree = Arc::new(SharedTree::new(cloned_tree, platform));

        // Clone Python references under the lock, never execute Python copy hooks
        // there: a fact's __deepcopy__ may access the original configuration.
        let snapshot: Vec<_> = {
            let data = base.tree.node_data.read_py()?;
            data.iter()
                .map(|(&nid, nd)| {
                    (
                        nid,
                        NodePyData {
                            facts: nd.facts.as_ref().map(|v| v.clone_ref(py)),
                            instances: nd.instances.as_ref().map(|v| v.clone_ref(py)),
                        },
                    )
                })
                .collect()
        };
        let new_driver = slf.driver_obj.clone_ref(py);
        new_shared_tree.set_driver(new_driver.clone_ref(py))?;
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
        new_shared_tree.set_root_handle(new_conf.bind(py).as_any())?;
        // Register the shell before traversing facts so back-references resolve to
        // this object, and carry the caller's memo through every recursive copy.
        memo.set_item(slf.as_ptr() as usize, new_conf.bind(py))?;
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        for (nid, nd) in snapshot {
            let mut copied = NodePyData::default();
            if let Some(facts) = nd.facts {
                copied.facts = Some(deepcopy.call1((facts, memo))?.extract()?);
            }
            if let Some(instances) = nd.instances {
                copied.instances = Some(deepcopy.call1((instances, memo))?.extract()?);
            }
            new_shared_tree.node_data.write_py()?.insert(nid, copied);
        }
        Ok(new_conf)
    }

    #[gen_stub(override_return_type(type_repr="tuple[collections.abc.Callable[..., HConfig], tuple[hier_config.platforms.driver_base.HConfigDriverBase, hier_config.models.Dump, list[tuple[int, object, object, int]]]]", imports=("collections.abc", "hier_config.platforms.driver_base", "hier_config.models")))]
    pub fn __reduce__(slf: PyRef<'_, Self>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let driver = slf.driver_obj.clone_ref(py);
        let base = slf.as_ref();

        // `Dump` carries only depth/text/tags/comments/new_in_config, so anything
        // else that lives on a node has to travel alongside it. Rows are keyed by
        // position in `all_children_sorted`, which is exactly the order the dump
        // lines are written in and the order the rebuild walks them back.
        let extras = PyList::empty(py);
        {
            let node_data = base.tree.node_data.read_py()?;
            let tree = base.read_tree()?;
            for (index, node_id) in tree
                .all_children_sorted(base.node_id)
                .into_iter()
                .enumerate()
            {
                let order_weight = tree.arena.get(node_id).map_or(0, |n| n.order_weight);
                let data = node_data.get(&node_id);
                let facts = data.and_then(|d| d.facts.as_ref());
                let instances = data.and_then(|d| d.instances.as_ref());
                if order_weight == 0 && facts.is_none() && instances.is_none() {
                    continue;
                }
                extras.append((
                    index,
                    facts.map_or_else(|| py.None(), |f| f.clone_ref(py).into_any()),
                    instances.map_or_else(|| py.None(), |i| i.clone_ref(py).into_any()),
                    order_weight,
                ))?;
            }
        }

        let dump = Self::dump(slf)?;
        let cls = py.get_type::<Self>();
        let func = cls.getattr("_rebuild")?;
        let args = PyTuple::new(py, vec![driver, dump, extras.into_any().unbind()])?;
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

    fn __str__(slf: PyRef<'_, Self>) -> PyResult<String> {
        // Mirrors the reference implementation, which joins ``str(child)`` over
        // the *direct* children only. Each child already renders its own
        // subtree, so walking every descendant here would emit nested lines
        // twice. ``lines`` skips the root's own text and exit, making it
        // exactly equivalent.
        Ok(slf.as_ref().lines(slf.py(), true)?.join("\n"))
    }

    #[gen_stub(override_return_type(type_repr="bool", imports=()))]
    /// Return self==value.
    fn __eq__(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="object", imports=()))] other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
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

    #[gen_stub(override_return_type(type_repr="bool", imports=()))]
    fn __ne__(
        slf: PyRef<'_, Self>,
        #[gen_stub(override_type(type_repr="object", imports=()))] other: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
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

    #[gen_stub(override_return_type(type_repr="int", imports=()))]
    /// Return hash(self).
    fn __hash__(slf: PyRef<'_, Self>) -> PyResult<isize> {
        let py = slf.py();
        let base = slf.as_ref();
        let children = base.get_children_object(py)?;
        let h = children.bind(py).hash()?;
        Ok(h)
    }

    #[gen_stub(skip)]
    /// Rebuilds a pickled configuration: the dump restores the tree, then the
    /// extras restore the per-node state a `Dump` cannot carry.
    #[staticmethod]
    fn _rebuild(
        py: Python<'_>,
        driver: Py<PyAny>,
        dump: Py<PyAny>,
        extras: &Bound<'_, PyList>,
    ) -> PyResult<Py<Self>> {
        let constructors = py.import("hier_config.constructors")?;
        let config: Py<Self> = constructors
            .getattr("hconfig_from_dump")?
            .call1((driver, dump))?
            .extract()?;

        if extras.is_empty() {
            return Ok(config);
        }

        let bound = config.bind(py);
        let borrowed = bound.borrow();
        let base = borrowed.as_ref();
        let by_index: Vec<_> = {
            let tree = base.read_tree()?;
            tree.all_children_sorted(base.node_id)
        };

        for row in extras.iter() {
            let (index, facts, instances, order_weight): (usize, Py<PyAny>, Py<PyAny>, i32) =
                row.extract()?;
            let Some(&node_id) = by_index.get(index) else {
                continue;
            };
            if order_weight != 0 {
                let mut tree = base.tree.write_node(node_id)?;
                if let Some(node) = tree.arena.get_mut(node_id) {
                    node.order_weight = order_weight;
                }
            }
            if facts.is_none(py) && instances.is_none(py) {
                continue;
            }
            let mut data = base.tree.node_data.write_py()?;
            let entry = data.entry(node_id).or_default();
            if !facts.is_none(py) {
                entry.facts = Some(facts.extract(py)?);
            }
            if !instances.is_none(py) {
                entry.instances = Some(instances.extract(py)?);
            }
        }
        drop(borrowed);
        Ok(config)
    }
}
