//! Native view hooks for Cisco IOS XR.

use std::net::Ipv4Addr;

use crate::models::MatchRule;
use crate::view::config::{ConfigOps, ConfigView};
use crate::view::helpers::parse_ipv4_interface;
use crate::view::interface::{InterfaceOps, InterfaceView};
use crate::view::models::Ipv4Interface;

/// Interface hooks for Cisco IOS XR.
///
/// IOS XR has no switchports, so the VLAN view only reports sub-interface
/// dot1q encapsulations.
#[derive(Debug, Clone, Copy)]
pub struct CiscoXrInterfaceOps;

impl InterfaceOps for CiscoXrInterfaceOps {
    fn bundle_prefix(&self) -> Option<&'static str> {
        Some("Bundle-Ether")
    }

    fn bundle_membership_prefix(&self) -> Option<&'static str> {
        Some("bundle id ")
    }

    fn supports_vlan(&self) -> bool {
        true
    }

    fn ipv4_interfaces(&self, view: &InterfaceView<'_>) -> Vec<Ipv4Interface> {
        view.children_text(&MatchRule::startswith("ipv4 address "))
            .into_iter()
            .filter_map(|text| {
                let words: Vec<&str> = text.split_whitespace().skip(2).collect();
                parse_ipv4_interface(&words)
            })
            .collect()
    }

    fn native_vlan(&self, view: &InterfaceView<'_>) -> Option<u32> {
        if !view.is_subinterface() {
            return None;
        }
        view.child_number("encapsulation dot1q ", 2)
    }

    fn vrf(&self, view: &InterfaceView<'_>) -> String {
        view.child_word("vrf ", 1).unwrap_or_default().to_owned()
    }
}

/// The shared interface hooks for Cisco IOS XR.
pub static INTERFACE_OPS: CiscoXrInterfaceOps = CiscoXrInterfaceOps;

/// Whole-config hooks for Cisco IOS XR.
#[derive(Debug, Clone, Copy)]
pub struct CiscoXrConfigOps;

impl ConfigOps for CiscoXrConfigOps {
    fn interface_ops(&self) -> &'static dyn InterfaceOps {
        &INTERFACE_OPS
    }

    fn hostname(&self, view: &ConfigView<'_>) -> Option<String> {
        Some(view.child_word("hostname ", 1)?.to_lowercase())
    }

    fn ipv4_default_gw(&self, view: &ConfigView<'_>) -> Option<Ipv4Addr> {
        let tree = view.tree();
        let router_static = tree.get_child(tree.root, &MatchRule::equals("router static"))?;
        let address_family = tree.get_child(
            router_static,
            &MatchRule::equals("address-family ipv4 unicast"),
        )?;
        let route = tree.get_child(address_family, &MatchRule::startswith("0.0.0.0/0 "))?;
        tree.get(route)?
            .text
            .split_whitespace()
            .nth(1)?
            .parse()
            .ok()
    }
}

/// The shared whole-config hooks for Cisco IOS XR.
pub static CONFIG_OPS: CiscoXrConfigOps = CiscoXrConfigOps;
