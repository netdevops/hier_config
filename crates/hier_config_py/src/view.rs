//! `PyO3` bindings for the structured views in `hier_config_core`.
//!
//! These wrap `hier_config_core::view` so `hier_config.platforms.view_base` is
//! a thin Python facade over one implementation. Before this existed the view
//! logic was written twice -- once in Rust and once in Python -- and kept in
//! step by a generated corpus. There is now a single source of truth.
//!
//! Both view classes hold a shared handle to the tree and rebuild the borrowed
//! `hier_config_core` view for the duration of each attribute read, because the
//! native views borrow the tree and cannot outlive a lock guard.

// The native views borrow the tree, so `with_view` hands the callback a
// `&ConfigView<'_>` built over a lock guard. Passing a bare method item there
// fails to infer the higher-ranked lifetime ("implementation of `FnOnce` is not
// general enough"), so every call site must spell out a closure even where
// clippy would prefer the method itself.
#![allow(clippy::redundant_closure_for_method_calls)]

use std::sync::Arc;

use hier_config_core::view::{
    ConfigOps, ConfigView, InterfaceDot1qMode, InterfaceDuplex, InterfaceOps, InterfaceView,
    Ipv4Interface, NacHostMode, StackMember, Vlan, view_ops_for_platform,
};
use hier_config_core::{NodeId, Platform};
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::GILOnceCell;
use pyo3::types::{PyFrozenSet, PyTuple, PyType};

use crate::root::PyHConfig;
use crate::tree::SharedTree;

/// Caches a class object looked up once from a Python module.
struct CachedType {
    module: &'static str,
    name: &'static str,
    cell: GILOnceCell<Py<PyType>>,
}

impl CachedType {
    /// Declare a lazily-imported class.
    const fn new(module: &'static str, name: &'static str) -> Self {
        Self {
            module,
            name,
            cell: GILOnceCell::new(),
        }
    }

    /// Import the class, caching it after the first successful lookup.
    fn get<'py>(&self, py: Python<'py>) -> PyResult<&Bound<'py, PyType>> {
        let cached = self.cell.get_or_try_init(py, || {
            py.import(self.module)?
                .getattr(self.name)?
                .downcast_into::<PyType>()
                .map(Bound::unbind)
                .map_err(PyErr::from)
        })?;
        Ok(cached.bind(py))
    }
}

/// `ipaddress.IPv4Address`, used for the default-gateway property.
static IPV4_ADDRESS: CachedType = CachedType::new("ipaddress", "IPv4Address");
/// `ipaddress.IPv4Interface`, used for every addressed-interface property.
static IPV4_INTERFACE: CachedType = CachedType::new("ipaddress", "IPv4Interface");
/// `hier_config.platforms.models.InterfaceDot1qMode`.
static DOT1Q_MODE: CachedType =
    CachedType::new("hier_config.platforms.models", "InterfaceDot1qMode");
/// `hier_config.platforms.models.InterfaceDuplex`.
static DUPLEX: CachedType = CachedType::new("hier_config.platforms.models", "InterfaceDuplex");
/// `hier_config.platforms.models.NACHostMode`.
static NAC_HOST_MODE: CachedType = CachedType::new("hier_config.platforms.models", "NACHostMode");
/// `hier_config.platforms.models.StackMember`.
static STACK_MEMBER: CachedType = CachedType::new("hier_config.platforms.models", "StackMember");
/// `hier_config.platforms.models.Vlan`.
static VLAN: CachedType = CachedType::new("hier_config.platforms.models", "Vlan");

/// Build `ipaddress.IPv4Interface("addr/len")`.
fn to_py_ipv4_interface(py: Python<'_>, value: Ipv4Interface) -> PyResult<PyObject> {
    let text = format!("{}/{}", value.address, value.prefix_len);
    IPV4_INTERFACE.get(py)?.call1((text,))?.into_py_any(py)
}

/// Build `hier_config.platforms.models.Vlan(id=…, name=…)`.
fn to_py_vlan(py: Python<'_>, value: &Vlan) -> PyResult<PyObject> {
    let kwargs = pyo3::types::PyDict::new(py);
    kwargs.set_item("id", value.id)?;
    kwargs.set_item("name", value.name.clone())?;
    VLAN.get(py)?.call((), Some(&kwargs))?.into_py_any(py)
}

/// Build `hier_config.platforms.models.StackMember(...)`.
fn to_py_stack_member(py: Python<'_>, value: &StackMember) -> PyResult<PyObject> {
    let kwargs = pyo3::types::PyDict::new(py);
    kwargs.set_item("id", value.id)?;
    kwargs.set_item("priority", value.priority)?;
    kwargs.set_item("mac_address", value.mac_address.clone())?;
    kwargs.set_item("model", value.model.clone())?;
    STACK_MEMBER
        .get(py)?
        .call((), Some(&kwargs))?
        .into_py_any(py)
}

/// Look an enum member up by name, e.g. `InterfaceDuplex["FULL"]`.
fn enum_member(py: Python<'_>, cached: &CachedType, name: &str) -> PyResult<PyObject> {
    cached.get(py)?.get_item(name)?.into_py_any(py)
}

/// Map the native dot1q mode onto its Python enum member.
fn to_py_dot1q_mode(py: Python<'_>, mode: InterfaceDot1qMode) -> PyResult<PyObject> {
    let name = match mode {
        InterfaceDot1qMode::Access => "ACCESS",
        InterfaceDot1qMode::Tagged => "TAGGED",
        InterfaceDot1qMode::TaggedAll => "TAGGED_ALL",
    };
    enum_member(py, &DOT1Q_MODE, name)
}

/// Map the native duplex setting onto its Python enum member.
fn to_py_duplex(py: Python<'_>, duplex: InterfaceDuplex) -> PyResult<PyObject> {
    let name = match duplex {
        InterfaceDuplex::Auto => "AUTO",
        InterfaceDuplex::Full => "FULL",
        InterfaceDuplex::Half => "HALF",
    };
    enum_member(py, &DUPLEX, name)
}

/// Map the native NAC host mode onto its Python enum member.
fn to_py_nac_host_mode(py: Python<'_>, mode: NacHostMode) -> PyResult<PyObject> {
    let name = match mode {
        NacHostMode::SingleHost => "SINGLE_HOST",
        NacHostMode::MultiDomain => "MULTI_DOMAIN",
        NacHostMode::MultiAuth => "MULTI_AUTH",
        NacHostMode::MultiHost => "MULTI_HOST",
    };
    enum_member(py, &NAC_HOST_MODE, name)
}

/// Resolve the platform hooks for `platform`, or raise for a view-less platform.
static PLATFORM: CachedType = CachedType::new("hier_config.models", "Platform");

/// The `hier_config.models.Platform` member name for a native platform.
const fn platform_name(platform: Platform) -> &'static str {
    match platform {
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
    }
}

/// Convert a native platform into its `hier_config.models.Platform` member.
fn to_py_platform(py: Python<'_>, platform: Platform) -> PyResult<PyObject> {
    Ok(PLATFORM.get(py)?.getattr(platform_name(platform))?.unbind())
}

fn ops_for(platform: Platform) -> PyResult<&'static dyn ConfigOps> {
    view_ops_for_platform(platform).ok_or_else(|| {
        PyValueError::new_err(format!(
            "No view is defined for platform: {}",
            platform.as_str()
        ))
    })
}

/// Read the platform recorded on an `HConfig`'s driver.
fn platform_of(config: &Bound<'_, PyHConfig>) -> PyResult<Platform> {
    let borrowed = config.try_borrow()?;
    let shared = &borrowed.as_super().tree;
    let tree = shared
        .tree
        .read()
        .map_err(|_| PyRuntimeError::new_err("config lock was poisoned"))?;
    Ok(tree.driver.platform)
}

/// A structured, read-only view over a whole configuration.
///
/// Instances are constructed with an `HConfig`, exactly as the previous
/// pure-Python `HConfigViewBase` subclasses were, so `driver.view_class`
/// keeps working for custom drivers.
#[pyclass(
    name = "HConfigView",
    module = "hier_config.platforms.view_base",
    subclass
)]
pub(crate) struct PyHConfigView {
    tree: Arc<SharedTree>,
    ops: &'static dyn ConfigOps,
    platform: Platform,
    config: PyObject,
}

impl std::fmt::Debug for PyHConfigView {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("PyHConfigView")
            .finish_non_exhaustive()
    }
}

impl PyHConfigView {
    /// Run `action` against a native view built over the locked tree.
    fn with_view<T>(&self, action: impl FnOnce(&ConfigView<'_>) -> T) -> PyResult<T> {
        let tree = self
            .tree
            .tree
            .read()
            .map_err(|_| PyRuntimeError::new_err("config lock was poisoned"))?;
        let view = ConfigView::new(&tree, self.ops);
        Ok(action(&view))
    }

    /// Build the interface views, mapping each onto its Python wrapper.
    fn interface_view_objects(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let nodes = self.with_view(|view| {
            view.interface_views()
                .iter()
                .map(InterfaceView::node)
                .collect::<Vec<_>>()
        })?;
        self.wrap_interfaces(py, &nodes)
    }

    /// Wrap already-resolved interface nodes as Python view objects.
    fn wrap_interfaces(&self, py: Python<'_>, nodes: &[NodeId]) -> PyResult<Vec<PyObject>> {
        let interface_ops = self.ops.interface_ops();
        nodes
            .iter()
            .map(|node| {
                Py::new(
                    py,
                    PyConfigViewInterface {
                        tree: Arc::clone(&self.tree),
                        node: *node,
                        ops: interface_ops,
                        platform: self.platform,
                    },
                )
                .and_then(|view| view.into_py_any(py))
            })
            .collect()
    }
}

#[pymethods]
impl PyHConfigView {
    /// Build a view over `config`.
    #[new]
    fn new(config: &Bound<'_, PyHConfig>) -> PyResult<Self> {
        let platform = platform_of(config)?;
        let borrowed = config.try_borrow()?;
        Ok(Self {
            tree: Arc::clone(&borrowed.as_super().tree),
            ops: ops_for(platform)?,
            platform,
            config: config.clone().unbind().into_any(),
        })
    }

    /// The `HConfig` this view reads from.
    #[getter]
    fn config(&self, py: Python<'_>) -> PyObject {
        self.config.clone_ref(py)
    }

    /// The platform this view interprets the config as.
    #[getter]
    fn platform(&self, py: Python<'_>) -> PyResult<PyObject> {
        to_py_platform(py, self.platform)
    }

    /// The configured hostname, if the platform records one.
    #[getter]
    fn hostname(&self) -> PyResult<Option<String>> {
        self.with_view(|view| view.hostname())
    }

    /// The IPv4 default gateway, if one is configured.
    #[getter]
    fn ipv4_default_gw(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let Some(address) = self.with_view(|view| view.ipv4_default_gw())? else {
            return Ok(None);
        };
        Ok(Some(
            IPV4_ADDRESS
                .get(py)?
                .call1((address.to_string(),))?
                .into_py_any(py)?,
        ))
    }

    /// A view for every interface in the configuration.
    #[getter]
    fn interface_views(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        self.interface_view_objects(py)
    }

    /// A view for every interface that is a link bundle.
    #[getter]
    fn bundle_interface_views(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let nodes = self.with_view(|view| {
            view.bundle_interface_views()
                .iter()
                .map(InterfaceView::node)
                .collect::<Vec<_>>()
        })?;
        self.wrap_interfaces(py, &nodes)
    }

    /// The `HConfigChild` holding each interface's config block.
    #[getter]
    fn interfaces(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let nodes = self.with_view(|view| view.interfaces())?;
        let children = SharedTree::get_or_create_children_batch(&self.tree, py, &nodes)?;
        children
            .into_iter()
            .map(|child| child.into_py_any(py))
            .collect()
    }

    /// The name of every configured interface.
    #[getter]
    fn interfaces_names(&self) -> PyResult<Vec<String>> {
        self.with_view(|view| {
            view.interface_names()
                .into_iter()
                .map(ToOwned::to_owned)
                .collect()
        })
    }

    /// Every interface name mentioned anywhere in the configuration.
    #[getter]
    fn interface_names_mentioned<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyFrozenSet>> {
        let names = self.with_view(|view| view.interface_names_mentioned())?;
        PyFrozenSet::new(py, names.iter())
    }

    /// The SNMP location string, or an empty string when unset.
    #[getter]
    fn location(&self) -> PyResult<String> {
        self.with_view(|view| view.location())
    }

    /// Every hardware module number referenced by an interface.
    #[getter]
    fn module_numbers(&self) -> PyResult<Vec<u32>> {
        self.with_view(|view| view.module_numbers())
    }

    /// The members of a switch stack, if the platform reports one.
    #[getter]
    fn stack_members(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let members = self.with_view(|view| view.stack_members())?;
        members
            .iter()
            .map(|member| to_py_stack_member(py, member))
            .collect()
    }

    /// Every VLAN ID defined in the configuration.
    #[getter]
    fn vlan_ids<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyFrozenSet>> {
        let ids = self.with_view(|view| view.vlan_ids())?;
        PyFrozenSet::new(py, ids.iter())
    }

    /// Every VLAN defined in the configuration.
    #[getter]
    fn vlans(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let vlans = self.with_view(|view| view.vlans())?;
        vlans.iter().map(|vlan| to_py_vlan(py, vlan)).collect()
    }

    /// The view for `name`, or `None` when no such interface exists.
    fn interface_view_by_name(&self, py: Python<'_>, name: &str) -> PyResult<Option<PyObject>> {
        let node =
            self.with_view(|view| view.interface_view_by_name(name).map(|iface| iface.node()))?;
        let Some(node) = node else { return Ok(None) };
        Ok(self.wrap_interfaces(py, &[node])?.into_iter().next())
    }

    /// Classify a switchport from its native and tagged VLANs.
    #[staticmethod]
    #[pyo3(signature = (untagged_vlan=None, tagged_vlans=None, *, tagged_all=false))]
    fn dot1q_mode_from_vlans(
        py: Python<'_>,
        untagged_vlan: Option<u32>,
        tagged_vlans: Option<Vec<u32>>,
        tagged_all: bool,
    ) -> PyResult<Option<PyObject>> {
        let tagged_vlans = tagged_vlans.unwrap_or_default();
        let mode =
            hier_config_core::view::dot1q_mode_from_vlans(untagged_vlan, &tagged_vlans, tagged_all);
        mode.map(|mode| to_py_dot1q_mode(py, mode)).transpose()
    }

    /// Describe the view for debugging.
    fn __repr__(&self) -> PyResult<String> {
        let hostname = self.hostname()?;
        Ok(format!("HConfigView(hostname={hostname:?})"))
    }
}

/// A structured, read-only view over a single interface.
#[pyclass(
    name = "ConfigViewInterface",
    module = "hier_config.platforms.view_base",
    subclass
)]
pub(crate) struct PyConfigViewInterface {
    tree: Arc<SharedTree>,
    node: NodeId,
    ops: &'static dyn InterfaceOps,
    platform: Platform,
}

impl std::fmt::Debug for PyConfigViewInterface {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("PyConfigViewInterface")
            .field("node", &self.node)
            .finish_non_exhaustive()
    }
}

impl PyConfigViewInterface {
    /// Run `action` against a native view built over the locked tree.
    fn with_view<T>(&self, action: impl FnOnce(&InterfaceView<'_>) -> T) -> PyResult<T> {
        let tree = self
            .tree
            .tree
            .read()
            .map_err(|_| PyRuntimeError::new_err("config lock was poisoned"))?;
        let view = InterfaceView::new(&tree, self.node, self.ops);
        Ok(action(&view))
    }
}

#[pymethods]
impl PyConfigViewInterface {
    /// The `HConfigChild` holding this interface's config block.
    #[getter]
    fn config(&self, py: Python<'_>) -> PyResult<PyObject> {
        let child = SharedTree::get_or_create_child(&self.tree, py, self.node, None)?;
        child.into_py_any(py)
    }

    /// The interface description, or an empty string when unset.
    #[getter]
    fn description(&self) -> PyResult<String> {
        self.with_view(|view| view.description())
    }

    /// Whether the interface is administratively enabled.
    #[getter]
    fn enabled(&self) -> PyResult<bool> {
        self.with_view(|view| view.enabled())
    }

    /// The first configured IPv4 interface address, if any.
    #[getter]
    fn ipv4_interface(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let value = self.with_view(|view| view.ipv4_interface())?;
        value
            .map(|value| to_py_ipv4_interface(py, value))
            .transpose()
    }

    /// Every configured IPv4 interface address.
    #[getter]
    fn ipv4_interfaces(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let values = self.with_view(|view| view.ipv4_interfaces())?;
        values
            .into_iter()
            .map(|value| to_py_ipv4_interface(py, value))
            .collect()
    }

    /// Whether this is a loopback interface.
    #[getter]
    fn is_loopback(&self) -> PyResult<bool> {
        self.with_view(|view| view.is_loopback())
    }

    /// Whether this is a subinterface of another interface.
    #[getter]
    fn is_subinterface(&self) -> PyResult<bool> {
        self.with_view(|view| view.is_subinterface())
    }

    /// Whether this is a switched virtual interface.
    #[getter]
    fn is_svi(&self) -> PyResult<bool> {
        self.with_view(|view| view.is_svi())
    }

    /// The interface name, e.g. `GigabitEthernet1/0/1`.
    #[getter]
    fn name(&self) -> PyResult<String> {
        self.with_view(|view| view.name().to_owned())
    }

    /// The numeric portion of the interface name.
    #[getter]
    fn number(&self) -> PyResult<String> {
        self.with_view(|view| view.number().to_owned())
    }

    /// The parent interface's name when this is a subinterface.
    #[getter]
    fn parent_name(&self) -> PyResult<Option<String>> {
        self.with_view(|view| view.parent_name())
    }

    /// The port portion of the interface number.
    #[getter]
    fn port_number(&self) -> PyResult<Option<u32>> {
        self.with_view(|view| view.port_number())
    }

    /// The subinterface portion of the interface number.
    #[getter]
    fn subinterface_number(&self) -> PyResult<Option<u32>> {
        self.with_view(|view| view.subinterface_number())
    }

    /// The VRF this interface belongs to, or an empty string.
    #[getter]
    fn vrf(&self) -> PyResult<String> {
        self.with_view(|view| view.vrf())
    }

    /// The bundle this interface is a member of, if any.
    #[getter]
    fn bundle_id(&self) -> PyResult<Option<String>> {
        self.with_view(|view| view.bundle_id())
    }

    /// The name of the bundle this interface is a member of, if any.
    #[getter]
    fn bundle_name(&self) -> PyResult<Option<String>> {
        self.with_view(|view| view.bundle_name())
    }

    /// Whether this interface is itself a bundle.
    #[getter]
    fn is_bundle(&self) -> PyResult<bool> {
        self.with_view(|view| view.is_bundle())
    }

    /// The names of the interfaces bundled into this one.
    #[getter]
    fn bundle_member_interfaces(&self) -> PyResult<Vec<String>> {
        self.with_view(|view| view.bundle_member_interfaces())
    }

    /// The 802.1Q mode of this switchport, if it is one.
    #[getter]
    fn dot1q_mode(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let mode = self.with_view(|view| view.dot1q_mode())?;
        mode.map(|mode| to_py_dot1q_mode(py, mode)).transpose()
    }

    /// The untagged VLAN of this switchport, if it has one.
    #[getter]
    fn native_vlan(&self) -> PyResult<Option<u32>> {
        self.with_view(|view| view.native_vlan())
    }

    /// Whether every VLAN is tagged on this switchport.
    #[getter]
    fn tagged_all(&self) -> PyResult<bool> {
        self.with_view(|view| view.tagged_all())
    }

    /// The VLANs tagged on this switchport.
    #[getter]
    fn tagged_vlans<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        let vlans = self.with_view(|view| view.tagged_vlans())?;
        PyTuple::new(py, vlans)
    }

    /// Whether network access control is configured on this interface.
    #[getter]
    fn has_nac(&self) -> PyResult<bool> {
        self.with_view(|view| view.has_nac())
    }

    /// Whether NAC control is applied to inbound traffic only.
    #[getter]
    fn nac_control_direction_in(&self) -> PyResult<bool> {
        self.with_view(|view| view.nac_control_direction_in())
    }

    /// The configured NAC host mode, if any.
    #[getter]
    fn nac_host_mode(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let mode = self.with_view(|view| view.nac_host_mode())?;
        mode.map(|mode| to_py_nac_host_mode(py, mode)).transpose()
    }

    /// Whether MAC authentication bypass is attempted before 802.1X.
    #[getter]
    fn nac_mab_first(&self) -> PyResult<bool> {
        self.with_view(|view| view.nac_mab_first())
    }

    /// The maximum number of 802.1X clients, when the platform reports one.
    #[getter]
    fn nac_max_dot1x_clients(&self) -> PyResult<Option<u32>> {
        self.with_view(|view| view.nac_max_dot1x_clients())
    }

    /// The maximum number of MAB clients, when the platform reports one.
    #[getter]
    fn nac_max_mab_clients(&self) -> PyResult<Option<u32>> {
        self.with_view(|view| view.nac_max_mab_clients())
    }

    /// Whether this interface is backed by physical hardware.
    #[getter]
    fn is_physical(&self) -> PyResult<bool> {
        self.with_view(|view| view.is_physical())
    }

    /// The configured duplex setting, if any.
    #[getter]
    fn duplex(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let duplex = self.with_view(|view| view.duplex())?;
        duplex.map(|duplex| to_py_duplex(py, duplex)).transpose()
    }

    /// The hardware module this interface belongs to, if any.
    #[getter]
    fn module_number(&self) -> PyResult<Option<u32>> {
        self.with_view(|view| view.module_number())
    }

    /// Whether power over Ethernet is enabled, when the platform reports it.
    #[getter]
    fn poe(&self) -> PyResult<Option<bool>> {
        self.with_view(|view| view.poe())
    }

    /// The configured speeds, if any are pinned.
    #[getter]
    fn speed<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyTuple>>> {
        let Some(speeds) = self.with_view(|view| view.speed())? else {
            return Ok(None);
        };
        PyTuple::new(py, speeds).map(Some)
    }

    /// The platform this interface view interprets the config as.
    #[getter]
    fn platform(&self, py: Python<'_>) -> PyResult<PyObject> {
        to_py_platform(py, self.platform)
    }

    /// The optional capabilities this platform's interface view supports.
    ///
    /// Mirrors the mixins the pure-Python views used to inherit, so
    /// `isinstance(view, InterfaceVlanViewMixin)` still answers correctly.
    #[getter]
    fn capabilities<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyFrozenSet>> {
        let names = self.with_view(|view| {
            let ops = view.ops();
            let mut names = Vec::with_capacity(4);
            if ops.bundle_prefix().is_some() {
                names.push("bundle");
            }
            if ops.supports_vlan() {
                names.push("vlan");
            }
            if ops.supports_nac() {
                names.push("nac");
            }
            if ops.supports_physical() {
                names.push("physical");
            }
            names
        })?;
        PyFrozenSet::new(py, names.iter())
    }

    /// Describe the view for debugging.
    fn __repr__(&self) -> PyResult<String> {
        let name = self.name()?;
        Ok(format!("ConfigViewInterface(name={name:?})"))
    }
}

/// Register the view classes on the extension module.
pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyHConfigView>()?;
    module.add_class::<PyConfigViewInterface>()?;
    Ok(())
}
