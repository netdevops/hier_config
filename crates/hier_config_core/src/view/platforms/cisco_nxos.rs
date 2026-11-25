//! Native view hooks for Cisco NX-OS.

use std::net::Ipv4Addr;

use crate::models::MatchRule;
use crate::view::config::{ConfigOps, ConfigView};
use crate::view::helpers::parse_ipv4_interface;
use crate::view::interface::{InterfaceOps, InterfaceView};
use crate::view::models::Ipv4Interface;

/// Interface hooks for Cisco NX-OS.
#[derive(Debug, Clone, Copy)]
pub struct CiscoNxosInterfaceOps;

impl InterfaceOps for CiscoNxosInterfaceOps {
    fn bundle_prefix(&self) -> Option<&'static str> {
        Some("port-channel")
    }

    fn bundle_membership_prefix(&self) -> Option<&'static str> {
        Some("channel-group ")
    }

    fn supports_vlan(&self) -> bool {
        true
    }

    fn ipv4_interfaces(&self, view: &InterfaceView<'_>) -> Vec<Ipv4Interface> {
        view.children_text(&MatchRule::startswith("ip address "))
            .into_iter()
            .filter_map(|text| {
                let words: Vec<&str> = text.split_whitespace().skip(2).collect();
                parse_ipv4_interface(&words)
            })
            .collect()
    }

    fn vrf(&self, view: &InterfaceView<'_>) -> String {
        view.child_word("vrf member ", 2)
            .unwrap_or_default()
            .to_owned()
    }
}

/// The shared interface hooks for Cisco NX-OS.
pub static INTERFACE_OPS: CiscoNxosInterfaceOps = CiscoNxosInterfaceOps;

/// Whole-config hooks for Cisco NX-OS.
#[derive(Debug, Clone, Copy)]
pub struct CiscoNxosConfigOps;

impl ConfigOps for CiscoNxosConfigOps {
    fn interface_ops(&self) -> &'static dyn InterfaceOps {
        &INTERFACE_OPS
    }

    fn hostname(&self, view: &ConfigView<'_>) -> Option<String> {
        Some(view.child_word("hostname ", 1)?.to_lowercase())
    }

    fn ipv4_default_gw(&self, view: &ConfigView<'_>) -> Option<Ipv4Addr> {
        view.child_word("ip route 0.0.0.0/0 ", 3)?.parse().ok()
    }
}

/// The shared whole-config hooks for Cisco NX-OS.
pub static CONFIG_OPS: CiscoNxosConfigOps = CiscoNxosConfigOps;
