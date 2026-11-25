//! `PyO3` bindings for the structured-format mapping in `hier_config_core`.
//!
//! These wrap `hier_config_core::formats` so `hier_config.formats` is a thin
//! Python facade. Keeping the mapping in Rust means a pure-Rust consumer gets
//! the same JSON/XML/NETCONF/gNMI rendering the Python package does.

use hier_config_core::formats::{self, FormatError, GnmiRemediation};
use hier_config_core::{Driver, Platform, Tree};
use pyo3::IntoPyObjectExt;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde_json::{Map, Value};

use crate::errors::format_err;
use crate::root::{PyHConfig, create_py_hconfig};

/// Borrows the whole tree behind an `HConfig` so a format renderer can read it.
fn with_tree<T>(config: &Bound<'_, PyHConfig>, action: impl FnOnce(&Tree) -> T) -> PyResult<T> {
    let base = config.cast::<PyHConfig>()?.try_borrow()?;
    let shared = &base.as_super().tree;
    let tree = shared
        .tree
        .read()
        .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("config lock was poisoned"))?;
    Ok(action(&tree))
}

/// Resolves the `list_keys` keyword, which is `None` or a tuple of names.
fn keys_arg(list_keys: Option<Vec<String>>) -> Option<Vec<String>> {
    list_keys.filter(|keys| !keys.is_empty())
}

/// Publishes a freshly built tree as an `HConfig` owned by `driver_obj`.
fn publish(
    py: Python<'_>,
    tree: Result<Tree, FormatError>,
    platform: Platform,
    driver_obj: Py<PyAny>,
) -> PyResult<Py<PyHConfig>> {
    let tree = tree.map_err(|error| format_err(&error))?;
    create_py_hconfig(py, tree, platform, driver_obj)
}

/// Converts a `serde_json` value into the equivalent Python object.
fn to_py_value(py: Python<'_>, value: &Value) -> PyResult<Py<PyAny>> {
    match value {
        Value::Null => Ok(py.None()),
        Value::Bool(flag) => flag.into_py_any(py),
        Value::Number(number) => {
            if let Some(int) = number.as_i64() {
                int.into_py_any(py)
            } else if let Some(unsigned) = number.as_u64() {
                unsigned.into_py_any(py)
            } else {
                number.as_f64().unwrap_or(f64::NAN).into_py_any(py)
            }
        }
        Value::String(text) => text.into_py_any(py),
        Value::Array(items) => {
            let list = PyList::empty(py);
            for item in items {
                list.append(to_py_value(py, item)?)?;
            }
            list.into_py_any(py)
        }
        Value::Object(members) => to_py_object(py, members)?.into_py_any(py),
    }
}

/// Converts a `serde_json` object into a Python dict, preserving member order.
fn to_py_object<'py>(
    py: Python<'py>,
    members: &Map<String, Value>,
) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    for (key, member) in members {
        dict.set_item(key, to_py_value(py, member)?)?;
    }
    Ok(dict)
}

/// Renders a gNMI result as the `GnmiRemediation` dict Python callers expect.
fn gnmi_to_py(py: Python<'_>, result: &GnmiRemediation) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    dict.set_item("update", to_py_object(py, &result.update)?)?;
    dict.set_item("delete", PyList::new(py, &result.delete)?)?;
    dict.into_py_any(py)
}

/// Builds an `HConfig` from JSON text.
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[pyo3(signature = (driver_obj, data, list_keys = None))]
#[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
pub(crate) fn formats_from_json(
    py: Python<'_>,
    #[gen_stub(override_type(type_repr="object", imports=()))] driver_obj: Py<PyAny>,
    #[gen_stub(override_type(type_repr="str", imports=()))] data: &str,
    #[gen_stub(override_type(type_repr="list[str] | None", imports=()))] list_keys: Option<
        Vec<String>,
    >,
) -> PyResult<Py<PyHConfig>> {
    let platform = PyHConfig::parse_platform(py, &driver_obj)?;
    let keys = keys_arg(list_keys);
    let tree = formats::from_json(Driver::for_platform(platform), data, keys.as_deref());
    publish(py, tree, platform, driver_obj)
}

/// Renders an `HConfig` built by `formats_from_json` back to JSON text.
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
// PyO3 renders non-literal defaults such as `Some(2)` as `Ellipsis` in
// `__text_signature__`; spell the default out so runtime and stub agree.
#[pyo3(signature = (config, indent = Some(2)), text_signature = "(config, indent=2)")]
#[gen_stub(override_return_type(type_repr="str", imports=()))]
pub(crate) fn formats_to_json(
    #[gen_stub(override_type(type_repr="HConfig", imports=()))] config: &Bound<'_, PyHConfig>,
    indent: Option<usize>,
) -> PyResult<String> {
    with_tree(config, |tree| formats::to_json(tree, indent))
}

/// Builds an `HConfig` from an XML document.
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[pyo3(signature = (driver_obj, source, list_keys = None))]
#[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
pub(crate) fn formats_from_xml(
    py: Python<'_>,
    #[gen_stub(override_type(type_repr="object", imports=()))] driver_obj: Py<PyAny>,
    #[gen_stub(override_type(type_repr="str", imports=()))] source: &str,
    #[gen_stub(override_type(type_repr="list[str] | None", imports=()))] list_keys: Option<
        Vec<String>,
    >,
) -> PyResult<Py<PyHConfig>> {
    let platform = PyHConfig::parse_platform(py, &driver_obj)?;
    let keys = keys_arg(list_keys);
    let tree = formats::from_xml(Driver::for_platform(platform), source, keys.as_deref());
    publish(py, tree, platform, driver_obj)
}

/// Renders an `HConfig` built by `formats_from_xml` back to XML text.
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[gen_stub(override_return_type(type_repr="str", imports=()))]
pub(crate) fn formats_to_xml(
    #[gen_stub(override_type(type_repr="HConfig", imports=()))] config: &Bound<'_, PyHConfig>,
) -> PyResult<String> {
    with_tree(config, formats::to_xml)?.map_err(|error| format_err(&error))
}

/// Renders a remediation as a NETCONF `edit-config` payload.
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[pyo3(signature = (remediation, running = None, list_keys = None))]
#[gen_stub(override_return_type(type_repr="str", imports=()))]
pub(crate) fn formats_to_netconf_xml(
    #[gen_stub(override_type(type_repr="HConfig", imports=()))] remediation: &Bound<'_, PyHConfig>,
    #[gen_stub(override_type(type_repr="HConfig | None", imports=()))] running: Option<
        &Bound<'_, PyHConfig>,
    >,
    #[gen_stub(override_type(type_repr="list[str] | None", imports=()))] list_keys: Option<
        Vec<String>,
    >,
) -> PyResult<String> {
    let keys = keys_arg(list_keys);
    let render = |running_tree: Option<&Tree>| -> PyResult<String> {
        with_tree(remediation, |tree| {
            formats::to_netconf_xml(tree, running_tree, keys.as_deref())
        })?
        .map_err(|error| format_err(&error))
    };
    match running {
        Some(running) => with_tree(running, |running_tree| render(Some(running_tree)))?,
        None => render(None),
    }
}

/// Renders a remediation as a gNMI-`SetRequest`-style dict.
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[pyo3(signature = (remediation, running = None, list_keys = None))]
#[gen_stub(override_return_type(type_repr="hier_config.formats.GnmiRemediation", imports=("hier_config.formats")))]
pub(crate) fn formats_to_gnmi_json(
    py: Python<'_>,
    #[gen_stub(override_type(type_repr="HConfig", imports=()))] remediation: &Bound<'_, PyHConfig>,
    #[gen_stub(override_type(type_repr="HConfig | None", imports=()))] running: Option<
        &Bound<'_, PyHConfig>,
    >,
    #[gen_stub(override_type(type_repr="list[str] | None", imports=()))] list_keys: Option<
        Vec<String>,
    >,
) -> PyResult<Py<PyAny>> {
    let keys = keys_arg(list_keys);
    let render = |running_tree: Option<&Tree>| -> PyResult<GnmiRemediation> {
        with_tree(remediation, |tree| {
            formats::to_gnmi_json(tree, running_tree, keys.as_deref())
        })?
        .map_err(|error| format_err(&error))
    };
    let result = match running {
        Some(running) => with_tree(running, |running_tree| render(Some(running_tree)))?,
        None => render(None),
    }?;
    gnmi_to_py(py, &result)
}
