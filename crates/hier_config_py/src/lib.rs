//! `PyO3` bindings for `hier_config_core`.

// `#[pymethods]` receivers must be owned `PyRef<'_, Self>` values to access
// base class fields via `.as_ref()`, so clippy's `needless_pass_by_value` is unactionable.
#![allow(clippy::needless_pass_by_value)]

// This crate is the `_hier_config_rust` extension module and nothing consumes it
// as a Rust library, so every module is crate-private. Keeping them private lets
// `unreachable_pub` police the internal surface and stops clippy from demanding
// public-API documentation for what are really implementation details.
pub(crate) mod base;
pub(crate) mod child;
pub(crate) mod children;
pub(crate) mod errors;
pub(crate) mod root;
pub(crate) mod tree;
pub(crate) mod view;
pub(crate) mod workflow;

use pyo3::prelude::*;

use base::PyHConfigBase;
use child::PyHConfigChild;
use children::{PyHConfigChildren, PyHConfigChildrenIter};
use errors::{DuplicateChildError, HierConfigError};
use root::PyHConfig;

// Parsing allocates a node (and a lookup key) per configuration line, so the
// allocator sits squarely on the hot path. The platform allocator — macOS's in
// particular — is markedly slower than mimalloc under that pattern. This only
// governs allocations made by this extension's Rust code; CPython keeps using
// its own allocators.
#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

/// Returns the canonical platform rules JSON for a given platform name or ID.
#[pyfunction]
fn get_platform_rules_json(platform_str: &str) -> PyResult<&'static str> {
    let platform = platform_str
        .parse::<hier_config_core::Platform>()
        .map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "unknown platform '{platform_str}': {e}"
            ))
        })?;
    Ok(hier_config_core::Driver::rules_json_for_platform(platform))
}

/// Swaps the negation prefix of a command string for a platform according to its driver syntax rules.
#[pyfunction]
fn driver_swap_negation(platform_str: &str, text: &str) -> PyResult<String> {
    let platform = platform_str
        .parse::<hier_config_core::Platform>()
        .map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "unknown platform '{platform_str}': {e}"
            ))
        })?;
    let driver = hier_config_core::Driver::cached_for_platform(platform);
    driver
        .try_swap_negation(text)
        .map_err(pyo3::exceptions::PyValueError::new_err)
}

/// Converts a hierarchical configuration into flat set commands.
#[pyfunction]
fn convert_to_set_commands(config_raw: &str) -> String {
    hier_config_core::convert_to_set_commands(config_raw)
}

/// Applies platform-specific configuration preprocessor (e.g. converting to set commands for JunOS/VyOS/SRL).
#[pyfunction]
fn config_preprocessor(platform_str: &str, config_text: &str) -> PyResult<String> {
    let platform = platform_str
        .parse::<hier_config_core::Platform>()
        .map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "unknown platform '{platform_str}': {e}"
            ))
        })?;
    Ok(hier_config_core::config_preprocessor(platform, config_text).into_owned())
}

/// Python module definition for `_hier_config_rust`.
#[pymodule]
fn _hier_config_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add(
        "DuplicateChildError",
        m.py().get_type::<DuplicateChildError>(),
    )?;
    m.add("HierConfigError", m.py().get_type::<HierConfigError>())?;
    m.add_function(wrap_pyfunction!(get_platform_rules_json, m)?)?;
    m.add_function(wrap_pyfunction!(driver_swap_negation, m)?)?;
    m.add_function(wrap_pyfunction!(convert_to_set_commands, m)?)?;
    m.add_function(wrap_pyfunction!(config_preprocessor, m)?)?;
    m.add_class::<PyHConfigBase>()?;
    m.add_class::<PyHConfigChild>()?;
    m.add_class::<PyHConfig>()?;
    m.add_class::<PyHConfigChildren>()?;
    m.add_class::<PyHConfigChildrenIter>()?;
    m.add_class::<view::PyNativeConfigViewInterface>()?;
    m.add_class::<view::PyNativeHConfigView>()?;
    m.add_class::<workflow::PyWorkflowRemediation>()?;
    Ok(())
}
