//! Native view hooks for Arista EOS.

use std::net::Ipv4Addr;

use crate::models::MatchRule;
use crate::view::config::{ConfigOps, ConfigView};
use crate::view::helpers::parse_ipv4_interface;
use crate::view::interface::{InterfaceOps, InterfaceView};
use crate::view::models::Ipv4Interface;

/// Interface hooks for Arista EOS.
#[derive(Debug, Clone, Copy)]
pub struct AristaEosInterfaceOps;

impl InterfaceOps for AristaEosInterfaceOps {
    fn bundle_prefix(&self) -> Option<&'static str> {
        Some("Port-Channel")
    }

    fn bundle_membership_prefix(&self) -> Option<&'static str> {
        Some("channel-group ")
    }

    fn encapsulation_prefix(&self) -> &'static str {
        "encapsulation dot1q vlan "
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
        let Some(text) = view.child_text(&MatchRule::startswith("vrf ")) else {
            return String::new();
        };
        let words: Vec<&str> = text.split_whitespace().collect();
        let index = if words.get(1) == Some(&"forwarding") {
            2
        } else {
            1
        };
        words.get(index).copied().unwrap_or_default().to_owned()
    }
}

/// The shared interface hooks for Arista EOS.
pub static INTERFACE_OPS: AristaEosInterfaceOps = AristaEosInterfaceOps;

/// Whole-config hooks for Arista EOS.
#[derive(Debug, Clone, Copy)]
pub struct AristaEosConfigOps;

impl ConfigOps for AristaEosConfigOps {
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

/// The shared whole-config hooks for Arista EOS.
pub static CONFIG_OPS: AristaEosConfigOps = AristaEosConfigOps;
