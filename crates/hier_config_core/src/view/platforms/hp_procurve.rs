//! Native view hooks for HP `ProCurve` / Aruba `AOSS`.

use std::collections::BTreeSet;
use std::net::Ipv4Addr;

use crate::models::MatchRule;
use crate::platforms::hp_procurve::hp_procurve_expand_range;
use crate::regex_cache::regex;
use crate::view::config::{ConfigOps, ConfigView};
use crate::view::helpers::parse_ipv4_interface;
use crate::view::interface::{InterfaceOps, InterfaceView};
use crate::view::models::{InterfaceDuplex, Ipv4Interface, NacHostMode, StackMember, Vlan};

const BUNDLE_PREFIX: &str = "trk";

/// Derive the configured speeds from a `speed-duplex` value.
fn speed_from_speed_duplex(speed_duplex: &str) -> Option<Vec<u32>> {
    if speed_duplex.starts_with("10") {
        let first = speed_duplex.split('-').next()?;
        return Some(vec![first.parse().ok()?]);
    }
    if let Some(rest) = speed_duplex.strip_prefix("auto-") {
        return rest
            .split('-')
            .map(|part| part.parse().ok())
            .collect::<Option<Vec<u32>>>();
    }
    None
}

/// Derive the duplex setting from a `speed-duplex` value.
fn duplex_from_speed_duplex(speed_duplex: &str) -> Option<InterfaceDuplex> {
    if speed_duplex.starts_with("auto") {
        return InterfaceDuplex::from_config_word(speed_duplex.get(..4)?);
    }
    if speed_duplex.ends_with("half") || speed_duplex.ends_with("full") {
        return InterfaceDuplex::from_config_word(&speed_duplex[speed_duplex.len() - 4..]);
    }
    InterfaceDuplex::from_config_word(speed_duplex)
}

/// Interface hooks for HP `ProCurve` / Aruba `AOSS`.
#[derive(Debug, Clone, Copy)]
pub struct HpProcurveInterfaceOps;

impl HpProcurveInterfaceOps {
    /// The text of the sibling `speed-duplex` value, without its keyword.
    /// The full `speed-duplex ...` line.
    ///
    /// Python passes the whole child text -- not just the value word -- to its
    /// `_speed_from_speed_duplex` / `_duplex_from_speed_duplex` helpers. That is
    /// preserved faithfully here so the two implementations agree.
    fn speed_duplex<'a>(view: &InterfaceView<'a>) -> Option<&'a str> {
        view.child_text(&MatchRule::startswith("speed-duplex "))
    }
}

impl InterfaceOps for HpProcurveInterfaceOps {
    fn bundle_prefix(&self) -> Option<&'static str> {
        Some(BUNDLE_PREFIX)
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
        let text = view.text();
        if text.starts_with("interface ") {
            return text.split_whitespace().nth(1).unwrap_or("");
        }
        text
    }

    fn description(&self, view: &InterfaceView<'_>) -> String {
        view.child_text(&MatchRule::startswith("name "))
            .and_then(|text| text.split_once(char::is_whitespace))
            .map_or_else(String::new, |(_, rest)| rest.replace('"', ""))
    }

    fn enabled(&self, view: &InterfaceView<'_>) -> bool {
        !view.has_child("disable")
    }

    fn bundle_id(&self, view: &InterfaceView<'_>) -> Option<String> {
        let bundle_name = view.bundle_name()?;
        Some(
            bundle_name
                .to_lowercase()
                .trim_start_matches(BUNDLE_PREFIX)
                .to_owned(),
        )
    }

    fn bundle_name(&self, view: &InterfaceView<'_>) -> Option<String> {
        let name = view.name();
        for text in view.siblings_text(&MatchRule::startswith("trunk ")) {
            let mut words = text.split_whitespace().skip(1);
            let interface_range = words.next()?;
            let Ok(interfaces) = hp_procurve_expand_range(interface_range) else {
                continue;
            };
            if interfaces.iter().any(|interface| interface == name) {
                // Capitalizing is consistent with `1/A1` interface naming and
                // with references under `vlan 10/n  tagged Trk1`.
                let bundle = words.next()?;
                let mut chars = bundle.chars();
                let first = chars.next()?;
                let mut capitalized: String = first.to_uppercase().collect();
                capitalized.push_str(&chars.as_str().to_lowercase());
                return Some(capitalized);
            }
        }
        None
    }

    fn bundle_member_interfaces(&self, view: &InterfaceView<'_>) -> Vec<String> {
        let pattern = format!(r"^trunk .* {} (trunk|lacp)$", view.name().to_lowercase());
        let Some(text) = view.sibling_text(&MatchRule::re_search(pattern.as_str())) else {
            return Vec::new();
        };
        text.split_whitespace()
            .nth(1)
            .and_then(|range| hp_procurve_expand_range(range).ok())
            .unwrap_or_default()
    }

    fn ipv4_interfaces(&self, view: &InterfaceView<'_>) -> Vec<Ipv4Interface> {
        view.children_text(&MatchRule::startswith("ip address "))
            .into_iter()
            .filter_map(|text| {
                let words: Vec<&str> = text.split_whitespace().skip(2).take(2).collect();
                parse_ipv4_interface(&words)
            })
            .collect()
    }

    fn has_nac(&self, view: &InterfaceView<'_>) -> bool {
        let name = view.name();
        view.has_sibling(&format!("aaa port-access authenticator {name}"))
            || view.has_sibling(&format!("aaa port-access mac-based {name}"))
    }

    fn nac_control_direction_in(&self, view: &InterfaceView<'_>) -> bool {
        let name = view.name();
        view.has_sibling(&format!("aaa port-access {name} controlled-direction in"))
    }

    fn nac_host_mode(&self, _view: &InterfaceView<'_>) -> Option<NacHostMode> {
        // ProCurve does not support host mode.
        None
    }

    fn nac_mab_first(&self, view: &InterfaceView<'_>) -> bool {
        let name = view.name();
        view.has_sibling(&format!(
            "aaa port-access {name} auth-order mac-based authenticator"
        ))
    }

    fn nac_max_dot1x_clients(&self, view: &InterfaceView<'_>) -> Option<u32> {
        let name = view.name();
        let prefix = format!("aaa port-access authenticator {name} client-limit ");
        Some(
            view.sibling_text(&MatchRule::startswith(prefix.as_str()))
                .and_then(|text| text.split_whitespace().nth(5))
                .and_then(|word| word.parse().ok())
                .unwrap_or(1),
        )
    }

    fn nac_max_mab_clients(&self, view: &InterfaceView<'_>) -> Option<u32> {
        let name = view.name();
        let prefix = format!("aaa port-access mac-based {name} addr-limit ");
        Some(
            view.sibling_text(&MatchRule::startswith(prefix.as_str()))
                .and_then(|text| text.split_whitespace().nth(5))
                .and_then(|word| word.parse().ok())
                .unwrap_or(1),
        )
    }

    fn duplex(&self, view: &InterfaceView<'_>) -> Option<InterfaceDuplex> {
        Self::speed_duplex(view).map_or(Some(InterfaceDuplex::Auto), duplex_from_speed_duplex)
    }

    fn poe(&self, view: &InterfaceView<'_>) -> Option<bool> {
        Some(!view.has_child("no power-over-ethernet"))
    }

    fn speed(&self, view: &InterfaceView<'_>) -> Option<Vec<u32>> {
        speed_from_speed_duplex(Self::speed_duplex(view)?)
    }

    fn native_vlan(&self, view: &InterfaceView<'_>) -> Option<u32> {
        view.child_number("untagged vlan ", 2)
    }

    fn tagged_all(&self, _view: &InterfaceView<'_>) -> bool {
        false
    }

    fn tagged_vlans(&self, view: &InterfaceView<'_>) -> Vec<u32> {
        view.children_text(&MatchRule::startswith("tagged vlan "))
            .into_iter()
            .filter_map(|text| text.split_whitespace().nth(2)?.parse().ok())
            .collect()
    }

    fn vrf(&self, _view: &InterfaceView<'_>) -> String {
        String::new()
    }
}

/// The shared interface hooks for HP `ProCurve`.
pub static INTERFACE_OPS: HpProcurveInterfaceOps = HpProcurveInterfaceOps;

/// Whole-config hooks for HP `ProCurve` / Aruba `AOSS`.
#[derive(Debug, Clone, Copy)]
pub struct HpProcurveConfigOps;

impl ConfigOps for HpProcurveConfigOps {
    fn interface_ops(&self) -> &'static dyn InterfaceOps {
        &INTERFACE_OPS
    }

    fn hostname(&self, view: &ConfigView<'_>) -> Option<String> {
        Some(
            view.child_word("hostname ", 1)?
                .to_lowercase()
                .replace('"', ""),
        )
    }

    fn ipv4_default_gw(&self, view: &ConfigView<'_>) -> Option<Ipv4Addr> {
        view.child_word("ip default-gateway ", 2)?.parse().ok()
    }

    /// Interface views, including VLAN blocks that carry an IPv4 address.
    fn interface_views<'a>(&self, view: &ConfigView<'a>) -> Vec<InterfaceView<'a>> {
        let mut views = view.default_interface_views();
        let tree = view.tree();
        let address_rule = MatchRule::startswith("ip address ");
        for vlan in tree.get_children(tree.root, &MatchRule::startswith("vlan ")) {
            if tree.get_child(vlan, &address_rule).is_some() {
                views.push(view.interface_view_for(vlan));
            }
        }
        views
    }

    fn interface_names_mentioned(&self, view: &ConfigView<'_>) -> BTreeSet<String> {
        let mut interfaces: BTreeSet<String> = view
            .interface_views()
            .into_iter()
            .map(|interface| interface.name().to_owned())
            .collect();

        let Some(port_pattern) = regex(r"^(\d+|\d+/\d+)$") else {
            return interfaces;
        };
        let driver = &view.tree().driver;
        for text in view.children_text(&MatchRule::startswith("")) {
            let text = driver.text_without_negation(text);
            if !text.starts_with("aaa port-access ") {
                continue;
            }
            let words: Vec<&str> = text.split_whitespace().collect();
            let Some(&keyword) = words.get(2) else {
                continue;
            };
            let found = if keyword == "authenticator" || keyword == "mac-based" {
                words.get(3)
            } else {
                Some(&keyword)
            };
            if let Some(&found) = found
                && port_pattern.is_match(found)
            {
                interfaces.insert(found.to_owned());
            }
        }
        interfaces
    }

    fn stack_members(&self, view: &ConfigView<'_>) -> Vec<StackMember> {
        let tree = view.tree();
        let Some(stacking) = tree.get_child(tree.root, &MatchRule::equals("stacking")) else {
            return Vec::new();
        };
        tree.get_children(stacking, &MatchRule::startswith("member"))
            .into_iter()
            .filter_map(|member| {
                let node = tree.get(member)?;
                let words: Vec<&str> = node.text.split_whitespace().collect();
                if words.get(2) != Some(&"type") {
                    return None;
                }
                let id: u32 = words.get(1)?.parse().ok()?;
                Some(StackMember {
                    id,
                    priority: 256 - id,
                    mac_address: Some((*words.get(5)?).to_owned()),
                    model: words.get(3)?.replace('"', ""),
                })
            })
            .collect()
    }

    /// The configured VLANs, including those only mentioned on interfaces.
    fn vlans(&self, view: &ConfigView<'_>) -> Vec<Vlan> {
        view.default_vlans(true)
    }
}

/// The shared whole-config hooks for HP `ProCurve`.
pub static CONFIG_OPS: HpProcurveConfigOps = HpProcurveConfigOps;
