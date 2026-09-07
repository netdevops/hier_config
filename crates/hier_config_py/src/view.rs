//! Python bindings for native configuration views.

use std::net::Ipv4Addr;
use std::sync::Arc;

use hier_config_core::models::Platform;
use hier_config_core::view::models::{
    InterfaceDot1qMode, InterfaceDuplex, NACHostMode, StackMember, Vlan,
};
use hier_config_core::view::{HConfigView, InterfaceView};
use pyo3::exceptions::{PyNotImplementedError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyFrozenSet, PyList, PyTuple};

use crate::base::PyHConfigBase;
use crate::child::PyHConfigChild;
use crate::root::PyHConfig;
use crate::tree::SharedTree;

fn to_py_ip_interface(py: Python<'_>, addr: Ipv4Addr, prefix: u8) -> PyResult<PyObject> {
    let ipaddress = py.import("ipaddress")?;
    let ip_iface_cls = ipaddress.getattr("IPv4Interface")?;
    let ip_str = format!("{addr}/{prefix}");
    let obj = ip_iface_cls.call1((ip_str,))?;
    Ok(obj.unbind())
}

fn to_py_ip_address(py: Python<'_>, ip: Ipv4Addr) -> PyResult<PyObject> {
    let ipaddress = py.import("ipaddress")?;
    let ip_addr_cls = ipaddress.getattr("IPv4Address")?;
    let obj = ip_addr_cls.call1((ip.to_string(),))?;
    Ok(obj.unbind())
}

fn to_py_stack_member(py: Python<'_>, sm: &StackMember) -> PyResult<PyObject> {
    let models = py.import("hier_config.platforms.models")?;
    let cls = models.getattr("StackMember")?;
    let dict = pyo3::types::PyDict::new(py);
    dict.set_item("id", sm.id)?;
    dict.set_item("priority", sm.priority)?;
    dict.set_item("mac_address", sm.mac_address.as_deref())?;
    dict.set_item("model", &sm.model)?;
    let kwargs = Some(&dict);
    let obj = cls.call((), kwargs)?;
    Ok(obj.unbind())
}

fn to_py_vlan(py: Python<'_>, vlan: &Vlan) -> PyResult<PyObject> {
    let models = py.import("hier_config.platforms.models")?;
    let cls = models.getattr("Vlan")?;
    let dict = pyo3::types::PyDict::new(py);
    dict.set_item("id", vlan.id)?;
    dict.set_item("name", vlan.name.as_deref())?;
    let kwargs = Some(&dict);
    let obj = cls.call((), kwargs)?;
    Ok(obj.unbind())
}

fn to_py_dot1q_mode(py: Python<'_>, mode: InterfaceDot1qMode) -> PyResult<PyObject> {
    let models = py.import("hier_config.platforms.models")?;
    let cls = models.getattr("InterfaceDot1qMode")?;
    let attr_name = match mode {
        InterfaceDot1qMode::Access => "ACCESS",
        InterfaceDot1qMode::Tagged => "TAGGED",
        InterfaceDot1qMode::TaggedAll => "TAGGED_ALL",
    };
    let obj = cls.getattr(attr_name)?;
    Ok(obj.unbind())
}

fn to_py_duplex(py: Python<'_>, duplex: InterfaceDuplex) -> PyResult<PyObject> {
    let models = py.import("hier_config.platforms.models")?;
    let cls = models.getattr("InterfaceDuplex")?;
    let val_str = match duplex {
        InterfaceDuplex::Full => "full",
        InterfaceDuplex::Half => "half",
        InterfaceDuplex::Auto => "auto",
    };
    let obj = cls.call1((val_str,))?;
    Ok(obj.unbind())
}

fn to_py_nac_host_mode(py: Python<'_>, mode: NACHostMode) -> PyResult<PyObject> {
    let models = py.import("hier_config.platforms.models")?;
    let cls = models.getattr("NACHostMode")?;
    let val_str = match mode {
        NACHostMode::SingleHost => "single-host",
        NACHostMode::MultiAuth => "multi-auth",
        NACHostMode::MultiDomain => "multi-domain",
        NACHostMode::MultiHost => "multi-host",
    };
    let obj = cls.call1((val_str,))?;
    Ok(obj.unbind())
}

/// Native interface view exposed to Python.
#[pyclass(module = "_hier_config_rust", name = "NativeConfigViewInterface")]
#[derive(Debug)]
pub struct PyNativeConfigViewInterface {
    pub tree: Arc<SharedTree>,
    pub node_id: hier_config_core::NodeId,
    pub platform: Platform,
    pub config_child: PyObject,
}

#[pymethods]
impl PyNativeConfigViewInterface {
    #[getter]
    pub fn config(&self, py: Python<'_>) -> PyObject {
        self.config_child.clone_ref(py)
    }

    #[getter]
    pub fn bundle_id(&self) -> PyResult<Option<String>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.bundle_id()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn bundle_member_interfaces(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        match view.bundle_member_interfaces() {
            Ok(members) => {
                let py_list = PyList::new(py, members)?;
                Ok(py_list.into_any().unbind())
            }
            Err(e) => {
                if e.starts_with("Interface is a bundle but bundle config was not found") {
                    Err(PyTypeError::new_err(e))
                } else if e.starts_with("The bundle config line couldn't be found") {
                    Err(PyValueError::new_err(e))
                } else {
                    Err(PyNotImplementedError::new_err(e))
                }
            }
        }
    }

    #[getter]
    pub fn bundle_name(&self) -> PyResult<Option<String>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.bundle_name()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn description(&self) -> PyResult<String> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.description()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn dot1q_mode(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        match view.dot1q_mode() {
            Some(mode) => Ok(Some(to_py_dot1q_mode(py, mode)?)),
            None => Ok(None),
        }
    }

    #[getter]
    pub fn duplex(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        match view.duplex() {
            Ok(dup) => to_py_duplex(py, dup),
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn enabled(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.enabled()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn has_nac(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.has_nac()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn ipv4_interface(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        match view.ipv4_interfaces() {
            Ok(ifaces) => {
                if let Some(&(addr, prefix)) = ifaces.first() {
                    Ok(Some(to_py_ip_interface(py, addr, prefix)?))
                } else {
                    Ok(None)
                }
            }
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn ipv4_interfaces(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        match view.ipv4_interfaces() {
            Ok(ifaces) => {
                let mut py_items = Vec::new();
                for (addr, prefix) in ifaces {
                    py_items.push(to_py_ip_interface(py, addr, prefix)?);
                }
                let py_list = PyList::new(py, py_items)?;
                Ok(py_list.into_any().unbind())
            }
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn is_bundle(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.is_bundle()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn is_loopback(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.is_loopback()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn is_subinterface(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.is_subinterface()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn is_svi(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.is_svi()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn module_number(&self) -> PyResult<Option<u32>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.module_number()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn nac_control_direction_in(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.nac_control_direction_in()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn nac_host_mode(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        match view.nac_host_mode() {
            Ok(Some(mode)) => Ok(Some(to_py_nac_host_mode(py, mode)?)),
            Ok(None) => Ok(None),
            Err(e) => {
                if e.starts_with("Unhandled NAC host mode:") {
                    Err(PyValueError::new_err(e))
                } else {
                    Err(PyNotImplementedError::new_err(e))
                }
            }
        }
    }

    #[getter]
    pub fn nac_mab_first(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.nac_mab_first()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn nac_max_dot1x_clients(&self) -> PyResult<u32> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.nac_max_dot1x_clients()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn nac_max_mab_clients(&self) -> PyResult<u32> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.nac_max_mab_clients()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn name(&self) -> PyResult<String> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.name()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn native_vlan(&self) -> PyResult<Option<u32>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.native_vlan()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn number(&self) -> PyResult<String> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.number()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn parent_name(&self) -> PyResult<Option<String>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.parent_name()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn poe(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.poe()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn port_number(&self) -> PyResult<u32> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.port_number()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn speed(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        match view.speed() {
            Ok(Some(speeds)) => {
                let py_tuple = PyTuple::new(py, speeds)?;
                Ok(Some(py_tuple.into_any().unbind()))
            }
            Ok(None) => Ok(None),
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn subinterface_number(&self) -> PyResult<Option<u32>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.subinterface_number()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn tagged_all(&self) -> PyResult<bool> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.tagged_all()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn tagged_vlans(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        match view.tagged_vlans() {
            Ok(vlans) => {
                let py_tuple = PyTuple::new(py, vlans)?;
                Ok(py_tuple.into_any().unbind())
            }
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn vrf(&self) -> PyResult<String> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = InterfaceView::new(&tree_guard, self.node_id, self.platform);
        view.vrf()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }
}

/// Native configuration view exposed to Python.
#[pyclass(module = "_hier_config_rust", name = "NativeHConfigView")]
#[derive(Debug)]
pub struct PyNativeHConfigView {
    pub tree: Arc<SharedTree>,
    pub platform: Platform,
    pub config_root: PyObject,
}

#[pymethods]
impl PyNativeHConfigView {
    #[new]
    pub fn new(py: Python<'_>, config: &Bound<'_, PyAny>) -> PyResult<Self> {
        let base = config.downcast::<PyHConfigBase>()?;
        let shared_tree = Arc::clone(&base.borrow().tree);

        let platform = if let Ok(root) = config.extract::<PyRef<'_, PyHConfig>>() {
            PyHConfig::parse_platform(py, &root.driver_obj)
        } else {
            Platform::Generic
        };

        Ok(Self {
            tree: shared_tree,
            platform,
            config_root: config.clone().unbind(),
        })
    }

    #[getter]
    pub fn config(&self, py: Python<'_>) -> PyObject {
        self.config_root.clone_ref(py)
    }

    #[pyo3(signature = (untagged_vlan=None, tagged_vlans=None, tagged_all=false))]
    pub fn dot1q_mode_from_vlans(
        &self,
        py: Python<'_>,
        untagged_vlan: Option<u32>,
        tagged_vlans: Option<Vec<u32>>,
        tagged_all: bool,
    ) -> PyResult<Option<PyObject>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        let tagged = tagged_vlans.unwrap_or_default();
        match view.dot1q_mode_from_vlans(untagged_vlan, &tagged, tagged_all) {
            Ok(Some(mode)) => Ok(Some(to_py_dot1q_mode(py, mode)?)),
            Ok(None) => Ok(None),
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn hostname(&self) -> Option<String> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        view.hostname()
    }

    #[getter]
    pub fn location(&self) -> PyResult<String> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        view.location()
            .map_err(|e| PyNotImplementedError::new_err(e.to_string()))
    }

    #[getter]
    pub fn ipv4_default_gw(&self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        match view.ipv4_default_gw() {
            Ok(Some(gw)) => Ok(Some(to_py_ip_address(py, gw)?)),
            Ok(None) => Ok(None),
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn interfaces(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        let ids = view.interface_node_ids();
        drop(tree_guard);

        let mut py_items = Vec::new();
        for nid in ids {
            let child = Py::new(
                py,
                (
                    PyHConfigChild {
                        parent_handle: Some(self.config_root.clone_ref(py)),
                    },
                    PyHConfigBase {
                        tree: Arc::clone(&self.tree),
                        node_id: nid,
                    },
                ),
            )?;
            py_items.push(child.into_any());
        }
        let py_list = PyList::new(py, py_items)?;
        Ok(py_list.into_any().unbind())
    }

    #[getter]
    pub fn interface_views(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        let views = view.interface_views();
        let node_ids: Vec<hier_config_core::NodeId> = views.iter().map(|iv| iv.node_id).collect();
        drop(tree_guard);

        let mut py_items = Vec::new();
        for nid in node_ids {
            let child = SharedTree::get_or_create_child(
                &self.tree,
                py,
                nid,
                Some(self.config_root.clone_ref(py)),
            )?;
            let child_obj = child.into_any();
            let native_iv = PyNativeConfigViewInterface {
                tree: Arc::clone(&self.tree),
                node_id: nid,
                platform: self.platform,
                config_child: child_obj,
            };
            let py_native_iv = Py::new(py, native_iv)?;
            py_items.push(py_native_iv.into_any());
        }
        let py_list = PyList::new(py, py_items)?;
        Ok(py_list.into_any().unbind())
    }

    pub fn interface_view_by_name(&self, py: Python<'_>, name: &str) -> PyResult<Option<PyObject>> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        let opt_iv = view.interface_view_by_name(name);
        let opt_node_id = opt_iv.map(|iv| iv.node_id);
        drop(tree_guard);

        match opt_node_id {
            Some(nid) => {
                let child = SharedTree::get_or_create_child(
                    &self.tree,
                    py,
                    nid,
                    Some(self.config_root.clone_ref(py)),
                )?;
                let child_obj = child.into_any();
                let native_iv = PyNativeConfigViewInterface {
                    tree: Arc::clone(&self.tree),
                    node_id: nid,
                    platform: self.platform,
                    config_child: child_obj,
                };
                let py_native_iv = Py::new(py, native_iv)?;
                Ok(Some(py_native_iv.into_any()))
            }
            None => Ok(None),
        }
    }

    #[getter]
    pub fn interfaces_names(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        let names = view.interfaces_names();
        let py_list = PyList::new(py, names)?;
        Ok(py_list.into_any().unbind())
    }

    #[getter]
    pub fn bundle_interface_views(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        let views = view.bundle_interface_views();
        let node_ids: Vec<hier_config_core::NodeId> = views.iter().map(|iv| iv.node_id).collect();
        drop(tree_guard);

        let mut py_items = Vec::new();
        for nid in node_ids {
            let child = SharedTree::get_or_create_child(
                &self.tree,
                py,
                nid,
                Some(self.config_root.clone_ref(py)),
            )?;
            let child_obj = child.into_any();
            let native_iv = PyNativeConfigViewInterface {
                tree: Arc::clone(&self.tree),
                node_id: nid,
                platform: self.platform,
                config_child: child_obj,
            };
            let py_native_iv = Py::new(py, native_iv)?;
            py_items.push(py_native_iv.into_any());
        }
        let py_list = PyList::new(py, py_items)?;
        Ok(py_list.into_any().unbind())
    }

    #[getter]
    pub fn module_numbers(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        let mods = view.module_numbers();
        let py_list = PyList::new(py, mods)?;
        Ok(py_list.into_any().unbind())
    }

    #[getter]
    pub fn interface_names_mentioned(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        match view.interface_names_mentioned() {
            Ok(names) => {
                let py_frozenset = PyFrozenSet::new(py, names)?;
                Ok(py_frozenset.into_any().unbind())
            }
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn stack_members(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        match view.stack_members() {
            Ok(members) => {
                let mut py_items = Vec::new();
                for sm in members {
                    py_items.push(to_py_stack_member(py, &sm)?);
                }
                let py_list = PyList::new(py, py_items)?;
                Ok(py_list.into_any().unbind())
            }
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn vlans(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        match view.vlans() {
            Ok(vlans) => {
                let mut py_items = Vec::new();
                for vlan in vlans {
                    py_items.push(to_py_vlan(py, &vlan)?);
                }
                let py_list = PyList::new(py, py_items)?;
                Ok(py_list.into_any().unbind())
            }
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }

    #[getter]
    pub fn vlan_ids(&self, py: Python<'_>) -> PyResult<PyObject> {
        let tree_guard = self.tree.tree.read().unwrap();
        let view = HConfigView::new(&tree_guard, self.platform);
        match view.vlan_ids() {
            Ok(ids) => {
                let py_frozenset = PyFrozenSet::new(py, ids)?;
                Ok(py_frozenset.into_any().unbind())
            }
            Err(e) => Err(PyNotImplementedError::new_err(e.to_string())),
        }
    }
}
