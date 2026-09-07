//! View implementation for HP `ProCurve`.

use std::collections::BTreeSet;
use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::tree::Tree;
use crate::view::helpers::{
    child_startswith, default_module_number, default_parent_name, has_child_in, parent_id,
    parse_ipv4_interface, word_as_u32,
};
use crate::view::interface::InterfaceView;
use crate::view::models::{InterfaceDot1qMode, InterfaceDuplex, NACHostMode, StackMember, Vlan};

/// Tree view logic for HP `ProCurve`.
#[derive(Debug)]
pub struct HConfigViewHpProcurve<'a> {
    pub tree: &'a Tree,
}

impl<'a> HConfigViewHpProcurve<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree) -> Self {
        Self { tree }
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn dot1q_mode_from_vlans(
        &self,
        _untagged_vlan: Option<u32>,
        _tagged_vlans: &[u32],
        _tagged_all: bool,
    ) -> Result<Option<InterfaceDot1qMode>, &'static str> {
        Err("not implemented")
    }

    #[must_use]
    pub fn hostname(&self) -> Option<String> {
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("hostname ")
                && let Some(host) = text.split_whitespace().nth(1)
            {
                let cleaned = host.trim_matches('"').to_ascii_lowercase();
                return Some(cleaned);
            }
        }
        None
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn interface_names_mentioned(
        &self,
        interface_names: &[String],
    ) -> Result<BTreeSet<String>, &'static str> {
        let mut interfaces: BTreeSet<String> = interface_names.iter().cloned().collect();
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            let text_without_negation = if let Some(stripped) = text.strip_prefix("no ") {
                stripped
            } else {
                text.as_ref()
            };
            if text_without_negation.starts_with("aaa port-access ") {
                let words: Vec<&str> = text_without_negation.split_whitespace().collect();
                if words.len() >= 4 {
                    let found = if words[2] == "authenticator" || words[2] == "mac-based" {
                        words[3]
                    } else {
                        words[2]
                    };
                    if found.chars().all(|c| c.is_ascii_digit() || c == '/') {
                        interfaces.insert(found.to_string());
                    }
                }
            }
        }
        Ok(interfaces)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn ipv4_default_gw(&self) -> Result<Option<Ipv4Addr>, &'static str> {
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("ip default-gateway ")
                && let Some(gw_str) = text.split_whitespace().nth(2)
                && let Ok(gw) = gw_str.parse::<Ipv4Addr>()
            {
                return Ok(Some(gw));
            }
        }
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn location(&self) -> Result<String, &'static str> {
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("snmp-server location ") {
                let loc = text.splitn(3, ' ').nth(2).unwrap_or("").replace('"', "");
                return Ok(loc);
            }
        }
        Ok(String::new())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn stack_members(&self) -> Result<Vec<StackMember>, &'static str> {
        let mut members = Vec::new();
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            if self.tree.arena[cid].text.as_ref() == "stacking" {
                for &mid in self.tree.arena[cid].children.as_slice() {
                    let text = &self.tree.arena[mid].text;
                    if text.starts_with("member") {
                        let words: Vec<&str> = text.split_whitespace().collect();
                        if words.len() >= 6
                            && words[2] == "type"
                            && let Ok(member_id) = words[1].parse::<u32>()
                        {
                            members.push(StackMember {
                                id: member_id,
                                priority: 256 - member_id,
                                mac_address: Some(words[5].to_string()),
                                model: words[3].replace('"', ""),
                            });
                        }
                    }
                }
            }
        }
        Ok(members)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn vlans(&self, interface_views: &[InterfaceView<'a>]) -> Result<Vec<Vlan>, &'static str> {
        let mut yielded_vlans = BTreeSet::new();
        let mut vlans = Vec::new();
        let vlan_re = crate::regex_cache::regex(r"^vlan [0-9,-]+$").ok_or("regex error")?;

        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if vlan_re.is_match(text) {
                let mut vlan_name = None;
                for &nid in self.tree.arena[cid].children.as_slice() {
                    let ntext = &self.tree.arena[nid].text;
                    if ntext.starts_with("name ") {
                        let name = ntext.split_once(' ').map_or("", |x| x.1).replace('"', "");
                        vlan_name = Some(name);
                        break;
                    }
                }
                if let Some(range_str) = text.split_whitespace().nth(1)
                    && let Ok(vids) = crate::platforms::functions::expand_range(range_str)
                {
                    for vid in vids {
                        yielded_vlans.insert(vid);
                        vlans.push(Vlan {
                            id: vid,
                            name: vlan_name.clone(),
                        });
                    }
                }
            }
        }

        for iv in interface_views {
            if let Ok(tagged) = iv.tagged_vlans() {
                for v in tagged {
                    if yielded_vlans.insert(v) {
                        vlans.push(Vlan { id: v, name: None });
                    }
                }
            }
            if let Ok(Some(native_vlan)) = iv.native_vlan()
                && yielded_vlans.insert(native_vlan)
            {
                vlans.push(Vlan {
                    id: native_vlan,
                    name: None,
                });
            }
        }

        Ok(vlans)
    }
}

/// Interface view logic for HP `ProCurve`.
#[derive(Debug)]
pub struct ConfigViewInterfaceHpProcurve<'a> {
    pub tree: &'a Tree,
    pub node_id: NodeId,
}

impl<'a> ConfigViewInterfaceHpProcurve<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree, node_id: NodeId) -> Self {
        Self { tree, node_id }
    }

    #[must_use]
    pub fn text(&self) -> &str {
        &self.tree.arena[self.node_id].text
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn bundle_prefix(&self) -> Result<&'static str, &'static str> {
        Ok("trk")
    }

    #[must_use]
    pub fn name(&self) -> String {
        let text = self.text();
        if text.starts_with("interface ") {
            text.split_whitespace().nth(1).unwrap_or(text).to_string()
        } else {
            text.to_string()
        }
    }

    #[must_use]
    pub fn number(&self) -> String {
        let name = self.name();
        name.trim_start_matches(|c: char| c.is_ascii_alphabetic() || c == '-')
            .to_string()
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn is_bundle(&self) -> Result<bool, &'static str> {
        let prefix = self.bundle_prefix()?;
        Ok(self
            .name()
            .to_ascii_lowercase()
            .starts_with(&prefix.to_ascii_lowercase()))
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn bundle_id(&self) -> Result<Option<String>, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn bundle_name(&self) -> Result<Option<String>, &'static str> {
        let Some(parent_id) = self.tree.arena[self.node_id].parent else {
            return Ok(None);
        };
        let name = self.name();
        for &sibling_id in self.tree.arena[parent_id].children.as_slice() {
            let text = &self.tree.arena[sibling_id].text;
            if text.starts_with("trunk ") {
                let words: Vec<&str> = text.split_whitespace().collect();
                if words.len() >= 3
                    && let Ok(interfaces) =
                        crate::platforms::hp_procurve::hp_procurve_expand_range(words[1])
                    && interfaces.contains(&name)
                {
                    let mut chars = words[2].chars();
                    let cap = match chars.next() {
                        None => String::new(),
                        Some(f) => {
                            let mut cap: String = f.to_uppercase().collect();
                            cap.push_str(&chars.as_str().to_lowercase());
                            cap
                        }
                    };
                    return Ok(Some(cap));
                }
            }
        }
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn bundle_member_interfaces(&self) -> Result<Vec<String>, String> {
        let parent_id = self.tree.arena[self.node_id]
            .parent
            .ok_or_else(|| "Parent not found".to_string())?;
        let name = self.name().to_ascii_lowercase();
        let is_bundle = self.is_bundle().unwrap_or(false);

        // Find matching trunk command
        let mut found_trunk_line: Option<String> = None;
        for &sibling_id in self.tree.arena[parent_id].children.as_slice() {
            let text = &self.tree.arena[sibling_id].text;
            if text.starts_with("trunk ") {
                let words: Vec<&str> = text.split_whitespace().collect();
                if words.len() >= 4 {
                    let trunk_type = words[words.len() - 1].to_ascii_lowercase();
                    let trunk_tag = words[2].to_ascii_lowercase();
                    if trunk_tag == name && (trunk_type == "trunk" || trunk_type == "lacp") {
                        found_trunk_line = Some(words[1].to_string());
                        break;
                    }
                }
            }
        }

        if is_bundle && found_trunk_line.is_none() {
            return Err(format!(
                "Interface is a bundle but bundle config was not found: {}",
                self.name()
            ));
        }
        let range_spec = found_trunk_line
            .ok_or_else(|| format!("The bundle config line couldn't be found: {}", self.name()))?;

        crate::platforms::hp_procurve::hp_procurve_expand_range(&range_spec)
            .map_err(ToString::to_string)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn description(&self) -> Result<String, &'static str> {
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if text.starts_with("name ") {
                let desc = text.split_once(' ').map_or("", |x| x.1).replace('"', "");
                return Ok(desc);
            }
        }
        Ok(String::new())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn duplex(&self) -> Result<InterfaceDuplex, &'static str> {
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if text.starts_with("speed-duplex ") {
                let val = text.strip_prefix("speed-duplex ").unwrap_or(text);
                if val.starts_with("auto") {
                    return Ok(InterfaceDuplex::Auto);
                }
                if val.ends_with("half") {
                    return Ok(InterfaceDuplex::Half);
                }
                if val.ends_with("full") {
                    return Ok(InterfaceDuplex::Full);
                }
                match val {
                    "auto" => return Ok(InterfaceDuplex::Auto),
                    "full" => return Ok(InterfaceDuplex::Full),
                    "half" => return Ok(InterfaceDuplex::Half),
                    _ => {}
                }
            }
        }
        Ok(InterfaceDuplex::Auto)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn enabled(&self) -> Result<bool, &'static str> {
        let is_disabled = self.tree.arena[self.node_id]
            .children
            .as_slice()
            .iter()
            .any(|&cid| self.tree.arena[cid].text.as_ref() == "disable");
        Ok(!is_disabled)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn has_nac(&self) -> Result<bool, &'static str> {
        let name = self.name();
        let authenticator = format!("aaa port-access authenticator {name}");
        let mac_based = format!("aaa port-access mac-based {name}");
        Ok(has_child_in(
            self.tree,
            parent_id(self.tree, self.node_id),
            &[authenticator.as_str(), mac_based.as_str()],
        ))
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn ipv4_interfaces(&self) -> Result<Vec<(Ipv4Addr, u8)>, &'static str> {
        let mut ifaces = Vec::new();
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if let Some(rest) = text.strip_prefix("ip address ") {
                let words: Vec<&str> = rest.split_whitespace().collect();
                if let Some(first) = words.first()
                    && let Some(parsed) = parse_ipv4_interface(first, words.get(1).copied())
                {
                    ifaces.push(parsed);
                }
            }
        }
        Ok(ifaces)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn module_number(&self) -> Result<Option<u32>, &'static str> {
        Ok(default_module_number(&self.number()))
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn nac_control_direction_in(&self) -> Result<bool, &'static str> {
        let expected = format!("aaa port-access {} controlled-direction in", self.name());
        Ok(has_child_in(
            self.tree,
            parent_id(self.tree, self.node_id),
            &[expected.as_str()],
        ))
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn nac_host_mode(&self) -> Result<Option<NACHostMode>, String> {
        // hp_procurve does not support host mode.
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn nac_mab_first(&self) -> Result<bool, &'static str> {
        let expected = format!(
            "aaa port-access {} auth-order mac-based authenticator",
            self.name()
        );
        Ok(has_child_in(
            self.tree,
            parent_id(self.tree, self.node_id),
            &[expected.as_str()],
        ))
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn nac_max_dot1x_clients(&self) -> Result<u32, &'static str> {
        let prefix = format!(
            "aaa port-access authenticator {} client-limit ",
            self.name()
        );
        Ok(
            child_startswith(self.tree, parent_id(self.tree, self.node_id), &prefix)
                .and_then(|text| word_as_u32(text, 5))
                .unwrap_or(1),
        )
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn nac_max_mab_clients(&self) -> Result<u32, &'static str> {
        let prefix = format!("aaa port-access mac-based {} addr-limit ", self.name());
        Ok(
            child_startswith(self.tree, parent_id(self.tree, self.node_id), &prefix)
                .and_then(|text| word_as_u32(text, 5))
                .unwrap_or(1),
        )
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn native_vlan(&self) -> Result<Option<u32>, &'static str> {
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("untagged vlan ")
                && let Some(vlan) = text
                    .split_whitespace()
                    .nth(2)
                    .and_then(|s| s.parse::<u32>().ok())
            {
                return Ok(Some(vlan));
            }
        }
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn parent_name(&self, is_subinterface: bool) -> Result<Option<String>, &'static str> {
        Ok(default_parent_name(&self.name(), is_subinterface))
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn poe(&self) -> Result<bool, &'static str> {
        let has = self.tree.arena[self.node_id]
            .children
            .as_slice()
            .iter()
            .any(|&cid| self.tree.arena[cid].text.as_ref() == "no power-over-ethernet");
        Ok(!has)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn speed(&self) -> Result<Option<Vec<u32>>, &'static str> {
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("speed-duplex ") {
                let sd = text.strip_prefix("speed-duplex ").unwrap_or(text);
                if sd.starts_with("10") {
                    if let Some(spd) = sd.split('-').next().and_then(|s| s.parse::<u32>().ok()) {
                        return Ok(Some(vec![spd]));
                    }
                } else if let Some(stripped) = sd.strip_prefix("auto-") {
                    let mut speeds = Vec::new();
                    for s in stripped.split('-') {
                        if let Ok(spd) = s.parse::<u32>() {
                            speeds.push(spd);
                        }
                    }
                    if !speeds.is_empty() {
                        return Ok(Some(speeds));
                    }
                }
            }
        }
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn tagged_all(&self) -> Result<bool, &'static str> {
        Ok(false)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn tagged_vlans(&self) -> Result<Vec<u32>, &'static str> {
        let mut vlans = Vec::new();
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("tagged vlan ")
                && let Some(v) = text
                    .split_whitespace()
                    .nth(2)
                    .and_then(|s| s.parse::<u32>().ok())
            {
                vlans.push(v);
            }
        }
        Ok(vlans)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn vrf(&self) -> Result<String, &'static str> {
        Ok(String::new())
    }
}
