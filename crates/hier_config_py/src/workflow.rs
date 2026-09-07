//! `PyO3` bindings for high-performance configuration remediation workflow.

use std::collections::BTreeSet;
use std::sync::Arc;

use hier_config_core::models::{Platform, TagRule};
use hier_config_core::tree::Tree;
use pyo3::prelude::*;
use pyo3::types::{PyTuple, PyType};

use crate::base::{PyHConfigBase, extract_strings, parse_match_rules_seq};
use crate::errors::to_py_err;
use crate::root::{PyHConfig, create_py_hconfig};

pub(crate) fn parse_tag_rules_seq(
    py: Python<'_>,
    rules: &Bound<'_, PyAny>,
) -> PyResult<Vec<TagRule>> {
    let mut list = Vec::new();
    for item in rules.try_iter()? {
        let rule = item?;
        let match_rules_obj = rule.getattr("match_rules")?;
        let match_rules = parse_match_rules_seq(py, &match_rules_obj)?;
        let apply_tags_obj = rule.getattr("apply_tags")?;
        let mut apply_tags = BTreeSet::new();
        for tag in apply_tags_obj.try_iter()? {
            apply_tags.insert(tag?.extract::<String>()?);
        }
        list.push(TagRule {
            match_rules,
            apply_tags,
        });
    }
    Ok(list)
}

fn parse_tags_arg(val: Option<&Bound<'_, PyAny>>) -> PyResult<Vec<String>> {
    let Some(v) = val else {
        return Ok(Vec::new());
    };
    if v.is_none() {
        return Ok(Vec::new());
    }
    extract_strings(v)
}

fn parse_platform_arg(platform_val: &Bound<'_, PyAny>) -> PyResult<Platform> {
    if let Ok(val) = platform_val.getattr("value")
        && let Ok(s) = val.extract::<String>()
    {
        return s.parse::<Platform>().map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("unknown platform '{s}': {e}"))
        });
    }
    if let Ok(s) = platform_val.extract::<String>() {
        return s.parse::<Platform>().map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("unknown platform '{s}': {e}"))
        });
    }
    Err(pyo3::exceptions::PyTypeError::new_err(
        "expected Platform enum or str for platform",
    ))
}

/// Builds a Python `IncompatibleDriverError`, which is defined in
/// `hier_config.exceptions` rather than the extension module.
fn incompatible_driver_error(py: Python<'_>, message: &str) -> PyErr {
    let exc = py
        .import("hier_config.exceptions")
        .and_then(|m| m.getattr("IncompatibleDriverError"));
    match exc {
        Ok(cls) => PyErr::from_value(
            cls.call1((message,))
                .unwrap_or_else(|e| e.value(py).clone().into_any()),
        ),
        Err(err) => err,
    }
}

/// Native implementation of remediation and rollback workflow.
#[pyclass(subclass, module = "_hier_config_rust", name = "WorkflowRemediation")]
#[derive(Debug)]
#[allow(clippy::struct_field_names)]
pub struct PyWorkflowRemediation {
    pub(crate) running_config: Py<PyHConfig>,
    pub(crate) generated_config: Py<PyHConfig>,
    pub(crate) plugins: Py<PyTuple>,
    pub(crate) remediation_config: Option<Py<PyHConfig>>,
    pub(crate) rollback_config: Option<Py<PyHConfig>>,
}

#[pymethods]
impl PyWorkflowRemediation {
    #[new]
    #[pyo3(signature = (running_config, generated_config, plugins = None))]
    fn new(
        py: Python<'_>,
        running_config: &Bound<'_, PyAny>,
        generated_config: &Bound<'_, PyAny>,
        plugins: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let running: Py<PyHConfig> = running_config.extract()?;
        let generated: Py<PyHConfig> = generated_config.extract()?;

        let r_driver = running_config.getattr("driver")?;
        let g_driver = generated_config.getattr("driver")?;
        let r_class = r_driver.get_type();
        let g_class = g_driver.get_type();
        if !r_class.is(&g_class) {
            return Err(incompatible_driver_error(
                py,
                "The running and generated configs must use the same driver.",
            ));
        }

        let plugins = match plugins {
            Some(obj) => {
                let mut collected = Vec::new();
                for item in obj.try_iter()? {
                    collected.push(item?);
                }
                PyTuple::new(py, collected)?.unbind()
            }
            None => PyTuple::empty(py).unbind(),
        };

        Ok(Self {
            running_config: running,
            generated_config: generated,
            plugins,
            remediation_config: None,
            rollback_config: None,
        })
    }

    #[pyo3(signature = (running_config, generated_config, plugins = None))]
    #[allow(
        clippy::missing_const_for_fn,
        clippy::unnecessary_wraps,
        clippy::needless_pass_by_value
    )]
    fn __init__(
        slf: &Bound<'_, Self>,
        running_config: &Bound<'_, PyAny>,
        generated_config: &Bound<'_, PyAny>,
        plugins: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let _ = (slf, running_config, generated_config, plugins);
        Ok(())
    }

    #[getter]
    pub fn plugins(&self, py: Python<'_>) -> Py<PyTuple> {
        self.plugins.clone_ref(py)
    }

    /// Creates a workflow by parsing running and generated configuration strings
    /// using the default driver for `platform` in Rust with the GIL released.
    #[classmethod]
    #[pyo3(signature = (platform, running_text, generated_text))]
    fn from_strings(
        cls: &Bound<'_, PyType>,
        platform: &Bound<'_, PyAny>,
        running_text: &str,
        generated_text: &str,
    ) -> PyResult<PyObject> {
        let py = cls.py();
        let plat = parse_platform_arg(platform)?;
        let driver_obj = PyHConfig::get_default_driver(py, plat)?;

        let running_owned = running_text.to_owned();
        let generated_owned = generated_text.to_owned();

        let (running_tree, generated_tree) = py
            .allow_threads(move || {
                let r = Tree::from_str(plat, &running_owned)?;
                let g = Tree::from_str(plat, &generated_owned)?;
                Ok::<(Tree, Tree), hier_config_core::tree::TreeError>((r, g))
            })
            .map_err(to_py_err)?;

        let running_hconfig = create_py_hconfig(py, running_tree, plat, driver_obj.clone_ref(py))?;
        let generated_hconfig = create_py_hconfig(py, generated_tree, plat, driver_obj)?;

        let inst = cls.call1((running_hconfig, generated_hconfig))?;
        Ok(inst.into_any().unbind())
    }

    /// Renders the remediation as a NETCONF edit-config payload.
    ///
    /// Requires running and generated configs built by `HConfig.from_xml()`.
    #[pyo3(signature = (*, list_keys = None))]
    fn remediation_netconf_xml(
        &mut self,
        py: Python<'_>,
        list_keys: Option<Vec<String>>,
    ) -> PyResult<String> {
        let remediation = self.remediation_config(py)?;
        crate::formats::formats_to_netconf_xml(
            remediation.bind(py),
            Some(self.running_config.bind(py)),
            list_keys,
        )
    }

    /// Renders the remediation as a gNMI-SetRequest-style dict.
    ///
    /// Requires running and generated configs built by `HConfig.from_json()`.
    #[pyo3(signature = (*, list_keys = None))]
    fn remediation_json(
        &mut self,
        py: Python<'_>,
        list_keys: Option<Vec<String>>,
    ) -> PyResult<PyObject> {
        let remediation = self.remediation_config(py)?;
        crate::formats::formats_to_gnmi_json(
            py,
            remediation.bind(py),
            Some(self.running_config.bind(py)),
            list_keys,
        )
    }

    #[getter]
    pub fn running_config(&self, py: Python<'_>) -> Py<PyHConfig> {
        self.running_config.clone_ref(py)
    }

    #[getter]
    pub fn generated_config(&self, py: Python<'_>) -> Py<PyHConfig> {
        self.generated_config.clone_ref(py)
    }

    #[getter]
    pub fn remediation_config(&mut self, py: Python<'_>) -> PyResult<Py<PyHConfig>> {
        if let Some(ref rem) = self.remediation_config {
            return Ok(rem.clone_ref(py));
        }

        let running_bound = self.running_config.bind(py);
        let generated_bound = self.generated_config.bind(py);
        let running_base = running_bound.extract::<PyRef<'_, PyHConfigBase>>()?;
        let generated_base = generated_bound.extract::<PyRef<'_, PyHConfigBase>>()?;

        running_base.tree.sync_rules(py)?;
        generated_base.tree.sync_rules(py)?;

        let platform = running_base.tree.platform;
        let running_tree = Arc::clone(&running_base.tree);
        let generated_tree = Arc::clone(&generated_base.tree);

        let delta_tree = py
            .allow_threads(move || {
                let r_tree = running_tree.tree.read().unwrap();
                let g_tree = generated_tree.tree.read().unwrap();
                let mut rem = hier_config_core::remediation::config_to_get_to(&r_tree, &g_tree)?;
                rem.set_order_weight();
                Ok::<Tree, hier_config_core::tree::TreeError>(rem)
            })
            .map_err(to_py_err)?;

        let driver_obj = running_bound.getattr("driver")?.unbind();
        let hconfig = create_py_hconfig(py, delta_tree, platform, driver_obj)?;

        // Driver-level transforms (#180), then user plugins (#181).
        let bound = hconfig.bind(py);
        let callbacks = bound
            .getattr("driver")?
            .getattr("rules")?
            .getattr("remediation_transform_callbacks")?;
        for callback in callbacks.try_iter()? {
            callback?.call1((bound,))?;
        }
        for plugin in self.plugins.bind(py).iter() {
            plugin.call1((bound,))?;
        }

        self.remediation_config = Some(hconfig.clone_ref(py));
        Ok(hconfig)
    }

    #[getter]
    pub fn rollback_config(&mut self, py: Python<'_>) -> PyResult<Py<PyHConfig>> {
        if let Some(ref roll) = self.rollback_config {
            return Ok(roll.clone_ref(py));
        }

        let running_bound = self.running_config.bind(py);
        let generated_bound = self.generated_config.bind(py);
        let running_base = running_bound.extract::<PyRef<'_, PyHConfigBase>>()?;
        let generated_base = generated_bound.extract::<PyRef<'_, PyHConfigBase>>()?;

        running_base.tree.sync_rules(py)?;
        generated_base.tree.sync_rules(py)?;

        let platform = running_base.tree.platform;
        let running_tree = Arc::clone(&running_base.tree);
        let generated_tree = Arc::clone(&generated_base.tree);

        let delta_tree = py
            .allow_threads(move || {
                let r_tree = running_tree.tree.read().unwrap();
                let g_tree = generated_tree.tree.read().unwrap();
                let mut roll = hier_config_core::remediation::config_to_get_to(&g_tree, &r_tree)?;
                roll.set_order_weight();
                Ok::<Tree, hier_config_core::tree::TreeError>(roll)
            })
            .map_err(to_py_err)?;

        let driver_obj = running_bound.getattr("driver")?.unbind();
        let hconfig = create_py_hconfig(py, delta_tree, platform, driver_obj)?;
        self.rollback_config = Some(hconfig.clone_ref(py));
        Ok(hconfig)
    }

    pub fn apply_remediation_tag_rules(
        &mut self,
        py: Python<'_>,
        tag_rules: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let parsed_rules = parse_tag_rules_seq(py, tag_rules)?;
        let rem_hconfig = self.remediation_config(py)?;
        let rem_bound = rem_hconfig.bind(py);
        let rem_base = rem_bound.extract::<PyRef<'_, PyHConfigBase>>()?;
        let rem_tree = Arc::clone(&rem_base.tree);
        py.allow_threads(move || {
            let mut tree = rem_tree.tree.write().unwrap();
            tree.apply_tag_rules(&parsed_rules);
        });
        Ok(())
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    pub fn remediation_text(
        &mut self,
        py: Python<'_>,
        include_tags: Option<&Bound<'_, PyAny>>,
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<String> {
        let inc = parse_tags_arg(include_tags)?;
        let exc = parse_tags_arg(exclude_tags)?;
        let rem_hconfig = self.remediation_config(py)?;
        let rem_bound = rem_hconfig.bind(py);
        let rem_base = rem_bound.extract::<PyRef<'_, PyHConfigBase>>()?;
        let rem_tree = Arc::clone(&rem_base.tree);
        let text = py.allow_threads(move || {
            let tree = rem_tree.tree.read().unwrap();
            let inc_refs: Vec<&str> = inc.iter().map(String::as_str).collect();
            let exc_refs: Vec<&str> = exc.iter().map(String::as_str).collect();
            tree.rendered_text_by_tags(&inc_refs, &exc_refs)
        });
        Ok(text)
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    pub fn remediation_config_filtered_text(
        &mut self,
        py: Python<'_>,
        include_tags: Option<&Bound<'_, PyAny>>,
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<String> {
        self.remediation_text(py, include_tags, exclude_tags)
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    pub fn rollback_text(
        &mut self,
        py: Python<'_>,
        include_tags: Option<&Bound<'_, PyAny>>,
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<String> {
        let inc = parse_tags_arg(include_tags)?;
        let exc = parse_tags_arg(exclude_tags)?;
        let roll_hconfig = self.rollback_config(py)?;
        let roll_bound = roll_hconfig.bind(py);
        let roll_base = roll_bound.extract::<PyRef<'_, PyHConfigBase>>()?;
        let roll_tree = Arc::clone(&roll_base.tree);
        let text = py.allow_threads(move || {
            let tree = roll_tree.tree.read().unwrap();
            let inc_refs: Vec<&str> = inc.iter().map(String::as_str).collect();
            let exc_refs: Vec<&str> = exc.iter().map(String::as_str).collect();
            tree.rendered_text_by_tags(&inc_refs, &exc_refs)
        });
        Ok(text)
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    pub fn rollback_config_filtered_text(
        &mut self,
        py: Python<'_>,
        include_tags: Option<&Bound<'_, PyAny>>,
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<String> {
        self.rollback_text(py, include_tags, exclude_tags)
    }
}
