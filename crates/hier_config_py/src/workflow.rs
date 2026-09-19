//! `PyO3` bindings for high-performance configuration remediation workflow.

use std::collections::BTreeSet;
use std::sync::{Arc, OnceLock};

use hier_config_core::models::{Platform, TagRule};
use hier_config_core::tree::Tree;
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple, PyType};

use crate::base::{PyHConfigBase, extract_strings, parse_match_rules_seq};
use crate::errors::to_py_err;
use crate::root::{PyHConfig, create_py_hconfig};
use crate::tree::PyRwLockExt;

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
    Err(PyTypeError::new_err(
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

/// Validates the `plugins` argument and materialises it as a tuple.
fn collect_plugins(py: Python<'_>, plugins: Option<&Bound<'_, PyAny>>) -> PyResult<Py<PyTuple>> {
    let Some(obj) = plugins.filter(|obj| !obj.is_none()) else {
        return Ok(PyTuple::empty(py).unbind());
    };
    let iter = obj.try_iter().map_err(|_| {
        PyTypeError::new_err(format!(
            "plugins must be an iterable of callables, got {}",
            obj.get_type()
                .name()
                .map_or_else(|_| "<unknown>".to_string(), |name| name.to_string())
        ))
    })?;
    let mut collected = Vec::new();
    for item in iter {
        let item = item?;
        if !item.is_callable() {
            return Err(PyTypeError::new_err(
                "plugins must be an iterable of callables",
            ));
        }
        collected.push(item);
    }
    Ok(PyTuple::new(py, collected)?.unbind())
}

/// Native implementation of remediation and rollback workflow.
/// Manages configuration workflows for a network device by comparing
/// running and generated configurations and creating remediations to align
/// the device with the intended configuration state.
///
/// Attributes:
///     `running_config` (HConfig): The current configuration of the network device.
///     `generated_config` (HConfig): The target configuration for the network device.
///
/// Raises:
///     `ValueError`: If `running_config` and `generated_config` have different drivers.
///
/// Example:
///     Initialize `WorkflowRemediation` with the running and generated configurations
///     and generate remediation and rollback configurations.
///
/// ```python
/// from hier_config import WorkflowRemediation, get_hconfig
/// from hier_config.models import Platform
///
/// # Create running and generated configurations as HConfig objects
/// running_config = get_hconfig(Platform.CISCO_IOS, "running_config_text")
/// generated_config = get_hconfig(Platform.CISCO_IOS, "generated_config_text")
///
/// # Initialize WorkflowRemediation with running and generated configurations
/// workflow = WorkflowRemediation(running_config, generated_config)
///
/// # Generate the remediation configuration to apply the target configuration to the device
/// remediation_config = workflow.remediation_config
/// print("Remediation configuration:")
/// for line in remediation_config.all_children_sorted():
///     print(line.cisco_style_text())
///
/// # Generate the rollback configuration to revert back to the running configuration
/// rollback_config = workflow.rollback_config
/// print("Rollback configuration:")
/// for line in rollback_config.all_children_sorted():
///     print(line.cisco_style_text())
/// ```
#[pyo3_stub_gen::derive::gen_stub_pyclass]
#[pyclass(
    subclass,
    module = "hier_config._hier_config_rust",
    name = "WorkflowRemediation"
)]
#[derive(Debug)]
#[allow(clippy::struct_field_names)]
pub struct PyWorkflowRemediation {
    pub(crate) running_config: Py<PyHConfig>,
    pub(crate) generated_config: Py<PyHConfig>,
    pub(crate) plugins: Py<PyTuple>,
    pub(crate) remediation_config: OnceLock<Py<PyHConfig>>,
    pub(crate) rollback_config: OnceLock<Py<PyHConfig>>,
}

#[pyo3_stub_gen::derive::gen_stub_pymethods]
#[pymethods]
impl PyWorkflowRemediation {
    // `#[classmethod]` is what makes PyO3 hand the actual subtype to `__new__`
    // (see `FnType::FnNewClass`). It must precede `#[new]` so the stub
    // generator still records this as the `__new__` constructor.
    #[classmethod]
    #[new]
    #[gen_stub(override_return_type(type_repr="typing_extensions.Self", imports=("typing_extensions")))]
    #[pyo3(signature = (running_config, generated_config, plugins = None, *args, **kwargs))]
    fn new(
        cls: &Bound<'_, PyType>,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] running_config: &Bound<
            '_,
            PyAny,
        >,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] generated_config: &Bound<
            '_,
            PyAny,
        >,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[collections.abc.Callable[[HConfig], None]] | None", imports=("collections.abc")))]
        plugins: Option<&Bound<'_, PyAny>>,
        // Subclasses are free to declare extra `__init__` parameters; the native
        // `__new__` runs first, so it has to tolerate them.
        #[gen_stub(override_type(type_repr="builtins.object", imports=("builtins")))] args: &Bound<
            '_,
            PyTuple,
        >,
        #[gen_stub(override_type(type_repr="builtins.object", imports=("builtins")))]
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        let _ = (args, kwargs);
        let py = cls.py();
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

        // The base class keeps the `plugins` contract strict. A proper subclass
        // may repurpose the third positional parameter for its own `__init__`
        // signature (PyO3 forwards the full original argument tuple to
        // `__new__`), so an unusable value there is ignored the same way the
        // trailing `*args` are, rather than raising.
        let plugins = match collect_plugins(py, plugins) {
            Ok(plugins) => plugins,
            Err(err) => {
                if cls.is(PyType::new::<Self>(py)) {
                    return Err(err);
                }
                PyTuple::empty(py).unbind()
            }
        };

        Ok(Self {
            running_config: running,
            generated_config: generated,
            plugins,
            remediation_config: OnceLock::new(),
            rollback_config: OnceLock::new(),
        })
    }

    #[pyo3(signature = (running_config, generated_config, plugins = None, *args, **kwargs))]
    #[allow(
        clippy::missing_const_for_fn,
        clippy::unnecessary_wraps,
        clippy::needless_pass_by_value
    )]
    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    fn __init__(
        slf: &Bound<'_, Self>,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] running_config: &Bound<
            '_,
            PyAny,
        >,
        #[gen_stub(override_type(type_repr="HConfig", imports=()))] generated_config: &Bound<
            '_,
            PyAny,
        >,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[collections.abc.Callable[[HConfig], None]] | None", imports=("collections.abc")))]
        plugins: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="builtins.object", imports=("builtins")))] args: &Bound<
            '_,
            PyTuple,
        >,
        #[gen_stub(override_type(type_repr="builtins.object", imports=("builtins")))]
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let _ = (slf, running_config, generated_config, plugins, args, kwargs);
        Ok(())
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="tuple[collections.abc.Callable[[HConfig], None], ...]", imports=("collections.abc")))]
    /// The remediation plugins applied to every generated remediation.
    pub fn plugins(&self, py: Python<'_>) -> Py<PyTuple> {
        self.plugins.clone_ref(py)
    }

    /// Creates a workflow by parsing running and generated configuration strings
    /// using the default driver for `platform` in Rust with the GIL released.
    #[classmethod]
    #[pyo3(signature = (platform, running_text, generated_text))]
    #[gen_stub(override_return_type(type_repr="WorkflowRemediation", imports=()))]
    fn from_strings(
        cls: &Bound<'_, PyType>,
        #[gen_stub(override_type(type_repr="hier_config.models.Platform | str", imports=("hier_config.models")))]
        platform: &Bound<'_, PyAny>,
        #[gen_stub(override_type(type_repr="str", imports=()))] running_text: &str,
        #[gen_stub(override_type(type_repr="str", imports=()))] generated_text: &str,
    ) -> PyResult<Py<PyAny>> {
        let py = cls.py();
        let plat = parse_platform_arg(platform)?;
        let driver_obj = PyHConfig::get_default_driver(py, plat)?;

        let running_owned = running_text.to_owned();
        let generated_owned = generated_text.to_owned();

        let (running_tree, generated_tree) = py
            .detach(move || {
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
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    fn remediation_netconf_xml(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="tuple[str, ...] | None", imports=()))]
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
    #[gen_stub(override_return_type(type_repr="hier_config.formats.GnmiRemediation", imports=("hier_config.formats")))]
    fn remediation_json(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="tuple[str, ...] | None", imports=()))]
        list_keys: Option<Vec<String>>,
    ) -> PyResult<Py<PyAny>> {
        let remediation = self.remediation_config(py)?;
        crate::formats::formats_to_gnmi_json(
            py,
            remediation.bind(py),
            Some(self.running_config.bind(py)),
            list_keys,
        )
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn running_config(&self, py: Python<'_>) -> Py<PyHConfig> {
        self.running_config.clone_ref(py)
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn generated_config(&self, py: Python<'_>) -> Py<PyHConfig> {
        self.generated_config.clone_ref(py)
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn remediation_config(&self, py: Python<'_>) -> PyResult<Py<PyHConfig>> {
        if let Some(rem) = self.remediation_config.get() {
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

        let delta_tree = py.detach(move || {
            let r_tree = running_tree.tree.read_py()?;
            let g_tree = generated_tree.tree.read_py()?;
            let mut rem = hier_config_core::remediation::config_to_get_to(&r_tree, &g_tree)
                .map_err(to_py_err)?;
            rem.set_order_weight();
            Ok::<Tree, PyErr>(rem)
        })?;

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

        let _ = self.remediation_config.set(hconfig.clone_ref(py));
        Ok(self.remediation_config.get().unwrap().clone_ref(py))
    }

    #[getter]
    #[gen_stub(override_return_type(type_repr="HConfig", imports=()))]
    pub fn rollback_config(&self, py: Python<'_>) -> PyResult<Py<PyHConfig>> {
        if let Some(roll) = self.rollback_config.get() {
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

        let delta_tree = py.detach(move || {
            let r_tree = running_tree.tree.read_py()?;
            let g_tree = generated_tree.tree.read_py()?;
            let mut roll = hier_config_core::remediation::config_to_get_to(&g_tree, &r_tree)
                .map_err(to_py_err)?;
            roll.set_order_weight();
            Ok::<Tree, PyErr>(roll)
        })?;

        let driver_obj = running_bound.getattr("driver")?.unbind();
        let hconfig = create_py_hconfig(py, delta_tree, platform, driver_obj)?;
        let _ = self.rollback_config.set(hconfig.clone_ref(py));
        Ok(self.rollback_config.get().unwrap().clone_ref(py))
    }

    #[gen_stub(override_return_type(type_repr="None", imports=()))]
    /// Applies tag rules to selectively label parts of the remediation configuration.
    ///
    /// Args:
    ///     tag_rules: A set of tag rules specifying sections to tag.
    ///
    /// Notes:
    ///     This method is useful for managing configuration changes by marking specific
    ///     parts of the config for conditional remediation.
    #[expect(
        clippy::doc_markdown,
        reason = "Python Args entries require unquoted parameter names for mkdocstrings."
    )]
    pub fn apply_remediation_tag_rules(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="tuple[hier_config.models.TagRule, ...]", imports=("hier_config.models")))]
        tag_rules: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let parsed_rules = parse_tag_rules_seq(py, tag_rules)?;
        let rem_hconfig = self.remediation_config(py)?;
        let rem_bound = rem_hconfig.bind(py);
        let rem_base = rem_bound.extract::<PyRef<'_, PyHConfigBase>>()?;
        let rem_tree = Arc::clone(&rem_base.tree);
        py.detach(move || {
            let mut tree = rem_tree.tree.write_py()?;
            tree.apply_tag_rules(&parsed_rules);
            Ok(())
        })
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    /// Remediation configuration as text, filtered by included and excluded tags.
    pub fn remediation_text(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        include_tags: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<String> {
        let inc = parse_tags_arg(include_tags)?;
        let exc = parse_tags_arg(exclude_tags)?;
        let rem_hconfig = self.remediation_config(py)?;
        let rem_bound = rem_hconfig.bind(py);
        let rem_base = rem_bound.extract::<PyRef<'_, PyHConfigBase>>()?;
        let rem_tree = Arc::clone(&rem_base.tree);
        let text = py.detach(move || {
            let tree = rem_tree.tree.read_py()?;
            let inc_refs: Vec<&str> = inc.iter().map(String::as_str).collect();
            let exc_refs: Vec<&str> = exc.iter().map(String::as_str).collect();
            Ok::<String, PyErr>(tree.rendered_text_by_tags(&inc_refs, &exc_refs))
        })?;
        Ok(text)
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    /// Returns the remediation configuration as text, filtered by included and excluded tags.
    ///
    /// Args:
    ///     include_tags: Tags to include in the output.
    ///     exclude_tags: Tags to exclude from the output.
    ///
    /// Returns:
    ///     str: The filtered remediation configuration in a text format.
    ///
    /// Notes:
    ///     - If no tags are provided, the complete sorted remediation configuration is returned.
    ///     - Sorting respects configuration hierarchy and specified tags.
    #[expect(
        clippy::doc_markdown,
        reason = "Python Args entries require unquoted parameter names for mkdocstrings."
    )]
    pub fn remediation_config_filtered_text(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        include_tags: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<String> {
        self.remediation_text(py, include_tags, exclude_tags)
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    /// Rollback configuration as text, filtered by included and excluded tags.
    pub fn rollback_text(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        include_tags: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<String> {
        let inc = parse_tags_arg(include_tags)?;
        let exc = parse_tags_arg(exclude_tags)?;
        let roll_hconfig = self.rollback_config(py)?;
        let roll_bound = roll_hconfig.bind(py);
        let roll_base = roll_bound.extract::<PyRef<'_, PyHConfigBase>>()?;
        let roll_tree = Arc::clone(&roll_base.tree);
        let text = py.detach(move || {
            let tree = roll_tree.tree.read_py()?;
            let inc_refs: Vec<&str> = inc.iter().map(String::as_str).collect();
            let exc_refs: Vec<&str> = exc.iter().map(String::as_str).collect();
            Ok::<String, PyErr>(tree.rendered_text_by_tags(&inc_refs, &exc_refs))
        })?;
        Ok(text)
    }

    #[pyo3(signature = (include_tags = None, exclude_tags = None))]
    #[gen_stub(override_return_type(type_repr="str", imports=()))]
    /// Rollback configuration as text, filtered by included and excluded tags.
    pub fn rollback_config_filtered_text(
        &self,
        py: Python<'_>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        include_tags: Option<&Bound<'_, PyAny>>,
        #[gen_stub(override_type(type_repr="collections.abc.Iterable[str] | None", imports=("collections.abc")))]
        exclude_tags: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<String> {
        self.rollback_text(py, include_tags, exclude_tags)
    }

    #[gen_stub(skip)]
    /// Pickles the workflow through its own constructor arguments, so the two
    /// configurations keep the pickling behaviour they define themselves.
    fn __reduce__(slf: &Bound<'_, Self>) -> PyResult<Py<PyAny>> {
        let py = slf.py();
        let borrowed = slf.borrow();
        let args = PyTuple::new(
            py,
            vec![
                borrowed.running_config.clone_ref(py).into_any(),
                borrowed.generated_config.clone_ref(py).into_any(),
                borrowed.plugins.clone_ref(py).into_any(),
            ],
        )?;
        drop(borrowed);
        let cls = slf.get_type();
        Ok(
            PyTuple::new(py, vec![cls.into_any().unbind(), args.into_any().unbind()])?
                .into_any()
                .unbind(),
        )
    }
}
