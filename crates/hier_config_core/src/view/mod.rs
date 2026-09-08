//! Native, structured views over a parsed configuration tree.
//!
//! This is the Rust equivalent of `hier_config/platforms/view_base.py` and the
//! per-platform `view.py` modules. It exists so that `hier_config_core` is
//! usable as a standalone Rust library, without a Python interpreter.
//!
//! Both implementations are held to the same behaviour by the shared corpus in
//! `testdata/views/`, which is executed from Rust and from Python.

pub mod config;
pub mod helpers;
pub mod interface;
pub mod models;
pub mod platforms;

pub use config::{ConfigOps, ConfigView};
pub use helpers::{
    dot1q_mode_from_vlans, interface_number, is_subinterface, module_number,
    module_number_from_number, parent_interface_name, parse_ipv4_interface,
    parse_ipv4_interface_str, port_number, port_number_from_number, subinterface_number,
};
pub use interface::{InterfaceOps, InterfaceView};
pub use models::{
    InterfaceDot1qMode, InterfaceDuplex, Ipv4Interface, NacHostMode, StackMember, Vlan,
};
pub use platforms::view_ops_for_platform;
