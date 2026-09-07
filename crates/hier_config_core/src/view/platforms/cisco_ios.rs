//! Native view hooks for Cisco IOS / IOS-XE.

use std::net::Ipv4Addr;

use crate::models::MatchRule;
use crate::view::config::{ConfigOps, ConfigView};
use crate::view::helpers::parse_ipv4_interface;
use crate::view::interface::{InterfaceOps, InterfaceView};
use crate::view::models::{InterfaceDuplex, Ipv4Interface, NacHostMode, StackMember};

/// Interface hooks for Cisco IOS / IOS-XE.
#[derive(Debug, Clone, Copy)]
pub struct CiscoIosInterfaceOps;

impl InterfaceOps for CiscoIosInterfaceOps {
    fn bundle_prefix(&self) -> Option<&'static str> {
        Some("Port-channel")
    }

    fn bundle_membership_prefix(&self) -> Option<&'static str> {
        Some("channel-group ")
    }

    fn encapsulation_prefix(&self) -> &'static str {
        "encapsulation dot1Q "
    }

    fn supports_vlan(&self) -> bool {
        true
    }

    fn supports_physical(&self) -> bool {
        true
    }

    fn supports_nac(&self) -> bool {
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
        view.child_word("ip vrf forwarding ", 3)
            .unwrap_or_default()
            .to_owned()
    }

    fn has_nac(&self, view: &InterfaceView<'_>) -> bool {
        view.has_child("authentication port-control auto") || view.has_child("mab")
    }

    fn nac_control_direction_in(&self, view: &InterfaceView<'_>) -> bool {
        view.has_child("authentication control-direction in")
    }

    fn nac_host_mode(&self, view: &InterfaceView<'_>) -> Option<NacHostMode> {
        NacHostMode::from_config_word(view.child_word("authentication host-mode ", 2)?)
    }

    fn nac_mab_first(&self, view: &InterfaceView<'_>) -> bool {
        view.has_child("authentication order mab dot1x")
    }

    fn duplex(&self, view: &InterfaceView<'_>) -> Option<InterfaceDuplex> {
        Some(
            view.child_word("duplex ", 1)
                .and_then(InterfaceDuplex::from_config_word)
                .unwrap_or(InterfaceDuplex::Auto),
        )
    }

    fn poe(&self, view: &InterfaceView<'_>) -> Option<bool> {
        Some(!view.has_child("power inline never"))
    }

    fn speed(&self, view: &InterfaceView<'_>) -> Option<Vec<u32>> {
        Some(vec![view.child_number("speed ", 1)?])
    }
}

/// The shared interface hooks for Cisco IOS.
pub static INTERFACE_OPS: CiscoIosInterfaceOps = CiscoIosInterfaceOps;

/// Whole-config hooks for Cisco IOS / IOS-XE.
#[derive(Debug, Clone, Copy)]
pub struct CiscoIosConfigOps;

impl ConfigOps for CiscoIosConfigOps {
    fn interface_ops(&self) -> &'static dyn InterfaceOps {
        &INTERFACE_OPS
    }

    fn hostname(&self, view: &ConfigView<'_>) -> Option<String> {
        Some(view.child_word("hostname ", 1)?.to_lowercase())
    }

    fn ipv4_default_gw(&self, view: &ConfigView<'_>) -> Option<Ipv4Addr> {
        view.child_word("ip default-gateway ", 2)?.parse().ok()
    }

    fn stack_members(&self, view: &ConfigView<'_>) -> Vec<StackMember> {
        view.children_text(&MatchRule::re_search("^switch .* provision .*"))
            .into_iter()
            .filter_map(|text| {
                let words: Vec<&str> = text.split_whitespace().collect();
                let id: u32 = words.get(1)?.parse().ok()?;
                Some(StackMember {
                    id,
                    priority: 256 - id,
                    mac_address: None,
                    model: (*words.get(3)?).to_owned(),
                })
            })
            .collect()
    }
}

/// The shared whole-config hooks for Cisco IOS.
pub static CONFIG_OPS: CiscoIosConfigOps = CiscoIosConfigOps;
