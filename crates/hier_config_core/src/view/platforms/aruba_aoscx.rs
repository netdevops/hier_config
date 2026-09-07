//! Native view hooks for Aruba AOS-CX.

use std::net::Ipv4Addr;

use crate::models::MatchRule;
use crate::platforms::functions::expand_range;
use crate::view::config::{ConfigOps, ConfigView};
use crate::view::helpers::parse_ipv4_interface_str;
use crate::view::interface::{InterfaceOps, InterfaceView};
use crate::view::models::{InterfaceDuplex, Ipv4Interface, NacHostMode, Vlan};

/// Expand a VLAN range spec, skipping a malformed one instead of failing.
///
/// The driver's post-load callbacks deliberately leave an unparseable spec
/// (e.g. `10-12-13`) collapsed, so the view tolerates the same input.
fn safe_expand_range(spec: &str) -> Vec<u32> {
    expand_range(spec).unwrap_or_default()
}

/// Interface hooks for Aruba AOS-CX.
#[derive(Debug, Clone, Copy)]
pub struct ArubaAoscxInterfaceOps;

impl InterfaceOps for ArubaAoscxInterfaceOps {
    fn bundle_prefix(&self) -> Option<&'static str> {
        Some("lag ")
    }

    fn bundle_membership_prefix(&self) -> Option<&'static str> {
        Some("lag ")
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

    fn name<'a>(&self, view: &InterfaceView<'a>) -> &'a str {
        view.text()
            .split_once(char::is_whitespace)
            .map_or("", |(_, rest)| rest.trim_start())
    }

    fn number<'a>(&self, view: &InterfaceView<'a>) -> &'a str {
        let name = view.name();
        let stripped = name.trim_start_matches(|c: char| c.is_ascii_alphabetic() || c == '-');
        stripped.strip_prefix(' ').unwrap_or(stripped)
    }

    fn parent_name(&self, view: &InterfaceView<'_>) -> Option<String> {
        if view.is_subinterface() {
            return view.name().split('.').next().map(str::to_owned);
        }
        if view.bundle_id().is_some() && !view.is_bundle() {
            return view.bundle_name();
        }
        None
    }

    fn enabled(&self, view: &InterfaceView<'_>) -> bool {
        // AOS-CX ports are admin-down by default and express the up state as
        // an explicit `no shutdown`, so absence of `shutdown` is not enough.
        view.has_child("no shutdown")
    }

    fn bundle_id(&self, view: &InterfaceView<'_>) -> Option<String> {
        if view.is_bundle() {
            // Names look like "lag 1" or "lag 1 multi-chassis"; the id is the
            // token after the "lag " prefix, not the last word.
            return view.name().split_whitespace().nth(1).map(str::to_owned);
        }
        view.default_bundle_id()
    }

    fn bundle_member_interfaces(&self, view: &InterfaceView<'_>) -> Vec<String> {
        if !view.is_bundle() {
            return Vec::new();
        }
        let Some(bundle_id) = view.bundle_id() else {
            return Vec::new();
        };
        let lag_text = format!("lag {bundle_id}");
        let lag_rule = MatchRule::equals(lag_text.as_str());
        view.sibling_views(&MatchRule::startswith("interface "))
            .into_iter()
            .filter(|sibling| sibling.child_text(&lag_rule).is_some())
            .filter_map(|sibling| {
                sibling
                    .text()
                    .split_once(char::is_whitespace)
                    .map(|(_, rest)| rest.trim_start().to_owned())
            })
            .collect()
    }

    fn ipv4_interfaces(&self, view: &InterfaceView<'_>) -> Vec<Ipv4Interface> {
        view.children_text(&MatchRule::startswith("ip address "))
            .into_iter()
            .filter_map(|text| {
                let address = text.split_whitespace().nth(2)?;
                if address == "dhcp" {
                    return None;
                }
                parse_ipv4_interface_str(address)
            })
            .collect()
    }

    fn has_nac(&self, view: &InterfaceView<'_>) -> bool {
        view.child_text(&MatchRule::startswith("aaa authentication port-access"))
            .is_some()
    }

    fn nac_control_direction_in(&self, _view: &InterfaceView<'_>) -> bool {
        false
    }

    fn nac_host_mode(&self, _view: &InterfaceView<'_>) -> Option<NacHostMode> {
        None
    }

    fn nac_mab_first(&self, _view: &InterfaceView<'_>) -> bool {
        false
    }

    fn duplex(&self, view: &InterfaceView<'_>) -> Option<InterfaceDuplex> {
        Some(
            view.child_word("duplex ", 1)
                .and_then(InterfaceDuplex::from_config_word)
                .unwrap_or(InterfaceDuplex::Auto),
        )
    }

    fn poe(&self, view: &InterfaceView<'_>) -> Option<bool> {
        Some(!view.has_child("no power-over-ethernet"))
    }

    fn speed(&self, view: &InterfaceView<'_>) -> Option<Vec<u32>> {
        let text = view.child_text(&MatchRule::startswith("speed "))?;
        if text == "speed auto" {
            return None;
        }
        Some(vec![text.split_whitespace().nth(1)?.parse().ok()?])
    }

    fn native_vlan(&self, view: &InterfaceView<'_>) -> Option<u32> {
        if view.is_loopback() || view.is_svi() {
            return None;
        }
        view.child_number("vlan trunk native ", 3)
            .or_else(|| view.child_number("vlan access ", 2))
    }

    fn tagged_all(&self, view: &InterfaceView<'_>) -> bool {
        view.has_child("vlan trunk allowed all")
    }

    fn tagged_vlans(&self, view: &InterfaceView<'_>) -> Vec<u32> {
        let mut vlans: Vec<u32> = view
            .children_text(&MatchRule::re_search(r"^vlan trunk allowed [0-9,-]+$"))
            .into_iter()
            .filter_map(|text| text.split_whitespace().nth(3))
            .flat_map(safe_expand_range)
            .collect();
        vlans.sort_unstable();
        vlans.dedup();
        vlans
    }

    fn vrf(&self, view: &InterfaceView<'_>) -> String {
        view.child_word("vrf attach ", 2)
            .unwrap_or_default()
            .to_owned()
    }
}

/// The shared interface hooks for Aruba AOS-CX.
pub static INTERFACE_OPS: ArubaAoscxInterfaceOps = ArubaAoscxInterfaceOps;

/// Whole-config hooks for Aruba AOS-CX.
#[derive(Debug, Clone, Copy)]
pub struct ArubaAoscxConfigOps;

impl ConfigOps for ArubaAoscxConfigOps {
    fn interface_ops(&self) -> &'static dyn InterfaceOps {
        &INTERFACE_OPS
    }

    fn hostname(&self, view: &ConfigView<'_>) -> Option<String> {
        Some(view.child_word("hostname ", 1)?.to_lowercase())
    }

    fn ipv4_default_gw(&self, view: &ConfigView<'_>) -> Option<Ipv4Addr> {
        view.child_word("ip route 0.0.0.0/0 ", 3)?.parse().ok()
    }

    /// Determine the configured VLANs.
    ///
    /// Uses tolerant range expansion and also yields unnamed VLANs that only
    /// appear as tagged members on interfaces.
    fn vlans(&self, view: &ConfigView<'_>) -> Vec<Vlan> {
        view.default_vlans(true)
    }
}

/// The shared whole-config hooks for Aruba AOS-CX.
pub static CONFIG_OPS: ArubaAoscxConfigOps = ArubaAoscxConfigOps;
