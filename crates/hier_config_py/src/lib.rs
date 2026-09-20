//! `PyO3` bindings for `hier_config_core`.

// `#[pymethods]` receivers must be owned `PyRef<'_, Self>` values to access
// base class fields via `.as_ref()`, so clippy's `needless_pass_by_value` is unactionable.
#![allow(clippy::needless_pass_by_value)]

// Apart from the stub generator entry point, the extension's Rust modules remain
// crate-private. Keeping them private lets
// `unreachable_pub` police the internal surface and stops clippy from demanding
// public-API documentation for what are really implementation details.
pub(crate) mod base;
pub(crate) mod child;
pub(crate) mod children;
pub(crate) mod comments;
pub(crate) mod errors;
pub(crate) mod formats;
pub(crate) mod root;
pub(crate) mod tree;
pub(crate) mod view;
pub(crate) mod workflow;

use pyo3::prelude::*;

use base::PyHConfigBase;
use child::PyHConfigChild;
use children::{PyHConfigChildren, PyHConfigChildrenIter};
use errors::{DuplicateChildError, HierConfigError, InvalidConfigError};
use root::PyHConfig;

/// Gather the stub metadata registered alongside the native Python bindings.
///
/// # Errors
///
/// Returns an error if the binding metadata cannot be gathered.
pub fn stub_info() -> pyo3_stub_gen::Result<pyo3_stub_gen::StubInfo> {
    gather_stub_info(std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."))
}

fn gather_stub_info(
    project_root: std::path::PathBuf,
) -> pyo3_stub_gen::Result<pyo3_stub_gen::StubInfo> {
    // Keep the extension's short library name as the generator default.
    // All registrations explicitly name the canonical Python module, while
    // sibling Python modules need fully qualified imports to avoid collisions
    // between hier_config.models and hier_config.platforms.models.
    let mut info = pyo3_stub_gen::StubInfo::from_project_root(
        "_hier_config_rust".to_owned(),
        project_root,
        true,
        pyo3_stub_gen::StubGenConfig::default(),
    )?;
    // The generator's exception macro marks user-defined exception bases as
    // builtins. Resolve those bases against the classes in this same module.
    for module in info.modules.values_mut() {
        if module.name == "hier_config._hier_config_rust" {
            module.verbatim_all_entries.insert("__version__".to_owned());
        }
        let names: std::collections::BTreeSet<_> =
            module.class.values().map(|class| class.name).collect();
        for class in module.class.values_mut() {
            for base in &mut class.bases {
                if let Some(name) = base.name.strip_prefix("builtins.")
                    && names.contains(name)
                {
                    *base = pyo3_stub_gen::TypeInfo::unqualified(name);
                }
            }
        }
    }
    Ok(info)
}

pyo3_stub_gen::module_variable!("hier_config._hier_config_rust", "__version__", String);

// Parsing allocates a node (and a lookup key) per configuration line, so the
// allocator sits squarely on the hot path. The platform allocator — macOS's in
// particular — is markedly slower than mimalloc under that pattern. This only
// governs allocations made by this extension's Rust code; CPython keeps using
// its own allocators.
#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

/// Returns the canonical platform rules JSON for a given platform name or ID.
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[gen_stub(override_return_type(type_repr="str", imports=()))]
fn get_platform_rules_json(
    #[gen_stub(override_type(type_repr="str", imports=()))] platform_str: &str,
) -> PyResult<&'static str> {
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
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[gen_stub(override_return_type(type_repr="str", imports=()))]
fn driver_swap_negation(
    #[gen_stub(override_type(type_repr="str", imports=()))] platform_str: &str,
    #[gen_stub(override_type(type_repr="str", imports=()))] text: &str,
) -> PyResult<String> {
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
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[gen_stub(override_return_type(type_repr="str", imports=()))]
fn convert_to_set_commands(
    #[gen_stub(override_type(type_repr="str", imports=()))] config_raw: &str,
) -> String {
    hier_config_core::convert_to_set_commands(config_raw)
}

/// Applies platform-specific configuration preprocessor (e.g. converting to set commands for JunOS/VyOS/SRL).
#[pyo3_stub_gen::derive::gen_stub_pyfunction(module = "hier_config._hier_config_rust")]
#[pyfunction]
#[gen_stub(override_return_type(type_repr="str", imports=()))]
fn config_preprocessor(
    #[gen_stub(override_type(type_repr="str", imports=()))] platform_str: &str,
    #[gen_stub(override_type(type_repr="str", imports=()))] config_text: &str,
) -> PyResult<String> {
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
    m.add(
        "InvalidConfigError",
        m.py().get_type::<InvalidConfigError>(),
    )?;
    m.add_function(wrap_pyfunction!(get_platform_rules_json, m)?)?;
    m.add_function(wrap_pyfunction!(driver_swap_negation, m)?)?;
    m.add_function(wrap_pyfunction!(convert_to_set_commands, m)?)?;
    m.add_function(wrap_pyfunction!(config_preprocessor, m)?)?;
    m.add_function(wrap_pyfunction!(formats::formats_from_json, m)?)?;
    m.add_function(wrap_pyfunction!(formats::formats_to_json, m)?)?;
    m.add_function(wrap_pyfunction!(formats::formats_from_xml, m)?)?;
    m.add_function(wrap_pyfunction!(formats::formats_to_xml, m)?)?;
    m.add_function(wrap_pyfunction!(formats::formats_to_netconf_xml, m)?)?;
    m.add_function(wrap_pyfunction!(formats::formats_to_gnmi_json, m)?)?;
    m.add_class::<PyHConfigBase>()?;
    m.add_class::<PyHConfigChild>()?;
    m.add_class::<PyHConfig>()?;
    m.add_class::<PyHConfigChildren>()?;
    m.add_class::<PyHConfigChildrenIter>()?;
    m.add_class::<comments::PyNodeComments>()?;
    m.add_class::<workflow::PyWorkflowRemediation>()?;
    view::register(m)?;
    Ok(())
}

#[cfg(test)]
mod stub_tests {
    #[test]
    fn compiled_metadata_is_independent_of_source_files_and_git_history() {
        pyo3::Python::initialize();
        let directory = tempfile::tempdir_in(env!("CARGO_MANIFEST_DIR")).unwrap();
        assert_eq!(std::fs::read_dir(directory.path()).unwrap().count(), 0);

        let isolated = super::gather_stub_info(directory.path().to_owned()).unwrap();
        let current = super::stub_info().unwrap();
        let module = "hier_config._hier_config_rust";

        assert_eq!(
            isolated.modules[module].to_string(),
            current.modules[module].to_string()
        );
        assert_eq!(std::fs::read_dir(directory.path()).unwrap().count(), 0);
    }
}
