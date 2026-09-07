//! View implementation for Aruba AOS-CX.

use std::collections::BTreeSet;
use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::tree::Tree;
use crate::view::interface::InterfaceView;
use crate::view::models::{InterfaceDot1qMode, InterfaceDuplex, NACHostMode, StackMember, Vlan};

/// Tree view logic for Aruba AOS-CX.
#[derive(Debug)]
pub struct HConfigViewArubaAoscx<'a> {
    pub tree: &'a Tree,
}

impl<'a> HConfigViewArubaAoscx<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree) -> Self {
        Self { tree }
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn dot1q_mode_from_vlans(
        &self,
        untagged_vlan: Option<u32>,
        tagged_vlans: &[u32],
        tagged_all: bool,
    ) -> Result<Option<InterfaceDot1qMode>, &'static str> {
        if tagged_all {
            return Ok(Some(InterfaceDot1qMode::TaggedAll));
        }
        if !tagged_vlans.is_empty() {
            return Ok(Some(InterfaceDot1qMode::Tagged));
        }
        if untagged_vlan.is_some() {
            return Ok(Some(InterfaceDot1qMode::Access));
        }
        Ok(None)
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
        let set: BTreeSet<String> = interface_names.iter().cloned().collect();
        Ok(set)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn ipv4_default_gw(&self) -> Result<Option<Ipv4Addr>, &'static str> {
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("ip route 0.0.0.0/0 ")
                && let Some(gw_str) = text.split_whitespace().nth(3)
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
    pub const fn stack_members(&self) -> Result<Vec<StackMember>, &'static str> {
        Ok(Vec::new())
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

/// Interface view logic for Aruba AOS-CX.
#[derive(Debug)]
pub struct ConfigViewInterfaceArubaAoscx<'a> {
    pub tree: &'a Tree,
    pub node_id: NodeId,
}

impl<'a> ConfigViewInterfaceArubaAoscx<'a> {
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
        Ok("lag ")
    }

    #[must_use]
    pub fn name(&self) -> String {
        let text = self.text();
        let parts: Vec<&str> = text.splitn(2, ' ').collect();
        if parts.len() == 2 {
            parts[1].to_string()
        } else {
            text.to_string()
        }
    }

    #[must_use]
    pub fn number(&self) -> String {
        let name = self.name();
        let trimmed = name.trim_start_matches(|c: char| c.is_ascii_alphabetic() || c == '-');
        trimmed.trim_start_matches(' ').to_string()
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
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn bundle_id(&self) -> Result<Option<String>, &'static str> {
        if self.is_bundle().unwrap_or(false) {
            let name = self.name();
            return Ok(name.split_whitespace().nth(1).map(ToString::to_string));
        }
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if text.starts_with("lag ")
                && let Some(id_part) = text.split_whitespace().nth(1)
            {
                return Ok(Some(id_part.to_string()));
            }
        }
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn bundle_name(&self) -> Result<Option<String>, &'static str> {
        let bid = self.bundle_id()?;
        let prefix = self.bundle_prefix()?;
        Ok(bid.map(|id| format!("{prefix}{id}")))
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn bundle_member_interfaces(&self) -> Result<Vec<String>, String> {
        if !self.is_bundle().unwrap_or(false) {
            return Ok(Vec::new());
        }
        let Ok(Some(bid)) = self.bundle_id() else {
            return Ok(Vec::new());
        };
        let lag_text = format!("lag {bid}");
        let mut members = Vec::new();
        for &child_id in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if text.starts_with("interface ") {
                let has_lag = self.tree.arena[child_id]
                    .children
                    .as_slice()
                    .iter()
                    .any(|&sid| self.tree.arena[sid].text.as_ref() == lag_text);
                if has_lag && let Some(iface_name) = text.split_once(' ').map(|x| x.1) {
                    members.push(iface_name.to_string());
                }
            }
        }
        Ok(members)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn description(&self) -> Result<String, &'static str> {
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if text.starts_with("description ") {
                let desc = text.split_once(' ').map_or("", |x| x.1);
                return Ok(desc.to_string());
            }
        }
        Ok(String::new())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn duplex(&self) -> Result<InterfaceDuplex, &'static str> {
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if text.starts_with("duplex ")
                && let Some(mode) = text.split_whitespace().nth(1)
            {
                match mode {
                    "full" => return Ok(InterfaceDuplex::Full),
                    "half" => return Ok(InterfaceDuplex::Half),
                    "auto" => return Ok(InterfaceDuplex::Auto),
                    _ => {}
                }
            }
        }
        Ok(InterfaceDuplex::Auto)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn enabled(&self) -> Result<bool, &'static str> {
        let has_no_shutdown = self.tree.arena[self.node_id]
            .children
            .as_slice()
            .iter()
            .any(|&cid| self.tree.arena[cid].text.as_ref() == "no shutdown");
        Ok(has_no_shutdown)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn has_nac(&self) -> Result<bool, &'static str> {
        let has = self.tree.arena[self.node_id]
            .children
            .as_slice()
            .iter()
            .any(|&cid| {
                let t = &self.tree.arena[cid].text;
                t.starts_with("aaa authentication port-access ")
            });
        Ok(has)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn ipv4_interfaces(&self) -> Result<Vec<(Ipv4Addr, u8)>, &'static str> {
        let mut ifaces = Vec::new();
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if text.starts_with("ip address ")
                && let Some(spec) = text.split_whitespace().nth(2)
                && let Some((ip_str, prefix_str)) = spec.split_once('/')
                && let (Ok(ip), Ok(prefix)) = (ip_str.parse::<Ipv4Addr>(), prefix_str.parse::<u8>())
            {
                ifaces.push((ip, prefix));
            }
        }
        Ok(ifaces)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn module_number(&self) -> Result<Option<u32>, &'static str> {
        let name = self.name();
        let parts: Vec<&str> = name.split('/').collect();
        if parts.len() == 3 {
            return Ok(parts[1].parse::<u32>().ok());
        }
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn nac_control_direction_in(&self) -> Result<bool, &'static str> {
        Ok(false)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn nac_host_mode(&self) -> Result<Option<NACHostMode>, String> {
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn nac_mab_first(&self) -> Result<bool, &'static str> {
        Ok(false)
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn nac_max_dot1x_clients(&self) -> Result<u32, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn nac_max_mab_clients(&self) -> Result<u32, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn native_vlan(&self) -> Result<Option<u32>, &'static str> {
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("vlan trunk native ")
                && let Some(vlan) = text
                    .split_whitespace()
                    .nth(3)
                    .and_then(|s| s.parse::<u32>().ok())
            {
                return Ok(Some(vlan));
            }
            if text.starts_with("vlan access ")
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
        if is_subinterface {
            let name = self.name();
            let parent = name.split('.').next().unwrap_or(&name);
            return Ok(Some(parent.to_string()));
        }
        if let Ok(Some(bname)) = self.bundle_name()
            && !self.is_bundle().unwrap_or(false)
        {
            return Ok(Some(bname));
        }
        Ok(None)
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
            if text.starts_with("speed ") {
                if &**text == "speed auto" {
                    return Ok(None);
                }
                if let Some(spd) = text
                    .split_whitespace()
                    .nth(1)
                    .and_then(|s| s.parse::<u32>().ok())
                {
                    return Ok(Some(vec![spd]));
                }
            }
        }
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn tagged_all(&self) -> Result<bool, &'static str> {
        let has = self.tree.arena[self.node_id]
            .children
            .as_slice()
            .iter()
            .any(|&cid| self.tree.arena[cid].text.as_ref() == "vlan trunk allowed all");
        Ok(has)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn tagged_vlans(&self) -> Result<Vec<u32>, &'static str> {
        let vlan_re =
            crate::regex_cache::regex(r"^vlan trunk allowed [0-9,-]+$").ok_or("regex error")?;
        let mut all_vlans = BTreeSet::new();
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if vlan_re.is_match(text) {
                let words: Vec<&str> = text.split_whitespace().collect();
                if words.len() >= 4
                    && let Ok(vlans) = crate::platforms::functions::expand_range(words[3])
                {
                    all_vlans.extend(vlans);
                }
            }
        }
        Ok(all_vlans.into_iter().collect())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn vrf(&self) -> Result<String, &'static str> {
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("vrf attach ")
                && let Some(v) = text.split_whitespace().nth(2)
            {
                return Ok(v.to_string());
            }
        }
        Ok(String::new())
    }
}
