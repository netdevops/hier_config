//! View implementation for Cisco IOS / IOS-XE.

use std::collections::BTreeSet;
use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::tree::Tree;
use crate::view::helpers::{
    child_startswith, default_module_number, default_parent_name, has_child_equals, has_child_in,
    is_loopback, is_subinterface, is_svi, parse_ipv4_interface, word_as_u32,
};
use crate::view::interface::InterfaceView;
use crate::view::models::{InterfaceDot1qMode, InterfaceDuplex, NACHostMode, StackMember, Vlan};

/// Tree view logic for Cisco IOS.
#[derive(Debug)]
pub struct HConfigViewCiscoIos<'a> {
    pub tree: &'a Tree,
}

impl<'a> HConfigViewCiscoIos<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree) -> Self {
        Self { tree }
    }

    /// Derives 802.1Q mode from VLAN specification (unimplemented on Cisco IOS tree view).
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Cisco IOS.
    pub const fn dot1q_mode_from_vlans(
        &self,
        _untagged_vlan: Option<u32>,
        _tagged_vlans: &[u32],
        _tagged_all: bool,
    ) -> Result<Option<InterfaceDot1qMode>, &'static str> {
        Err("not implemented")
    }

    /// Device hostname in lowercase.
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

    /// Interface names mentioned throughout configuration.
    ///
    /// # Errors
    /// Returns Err if not implemented.
    pub fn interface_names_mentioned(
        &self,
        interface_names: &[String],
    ) -> Result<BTreeSet<String>, &'static str> {
        let set: BTreeSet<String> = interface_names.iter().cloned().collect();
        Ok(set)
    }

    /// Default IPv4 gateway.
    ///
    /// # Errors
    /// Returns Err if not implemented.
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

    /// SNMP server location.
    ///
    /// # Errors
    /// Returns Err if not implemented.
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

    /// Stack members configured on the device.
    ///
    /// # Errors
    /// Returns Err if not implemented.
    pub fn stack_members(&self) -> Result<Vec<StackMember>, &'static str> {
        let switch_re =
            crate::regex_cache::regex(r"^switch .* provision .*").ok_or("regex error")?;
        let mut members = Vec::new();
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if switch_re.is_match(text) {
                let words: Vec<&str> = text.split_whitespace().collect();
                if words.len() >= 4
                    && let Ok(member_id) = words[1].parse::<u32>()
                {
                    members.push(StackMember {
                        id: member_id,
                        priority: 256 - member_id,
                        mac_address: None,
                        model: words[3].to_string(),
                    });
                }
            }
        }
        Ok(members)
    }

    /// VLANs configured in the tree.
    ///
    /// # Errors
    /// Returns Err if not implemented.
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

/// Interface view logic for Cisco IOS.
#[derive(Debug)]
pub struct ConfigViewInterfaceCiscoIos<'a> {
    pub tree: &'a Tree,
    pub node_id: NodeId,
}

impl<'a> ConfigViewInterfaceCiscoIos<'a> {
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
        Ok("Port-channel")
    }

    #[must_use]
    pub fn name(&self) -> String {
        let text = self.text();
        text.split_whitespace().nth(1).unwrap_or(text).to_string()
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
        let name = self.name();
        let prefix = self.bundle_prefix()?;
        Ok(name.starts_with(prefix))
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn bundle_id(&self) -> Result<Option<String>, &'static str> {
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if text.starts_with("channel-group")
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
        Err("not implemented".to_string())
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
        let is_shutdown = self.tree.arena[self.node_id]
            .children
            .as_slice()
            .iter()
            .any(|&cid| self.tree.arena[cid].text.as_ref() == "shutdown");
        Ok(!is_shutdown)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn has_nac(&self) -> Result<bool, &'static str> {
        Ok(has_child_in(
            self.tree,
            self.node_id,
            &["authentication port-control auto", "mab"],
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
        Ok(has_child_equals(
            self.tree,
            self.node_id,
            "authentication control-direction in",
        ))
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn nac_host_mode(&self) -> Result<Option<NACHostMode>, String> {
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("authentication host-mode ") {
                let mode_str = text.split_whitespace().nth(2).unwrap_or("");
                match mode_str {
                    "multi-auth" => return Ok(Some(NACHostMode::MultiAuth)),
                    "multi-domain" => return Ok(Some(NACHostMode::MultiDomain)),
                    "multi-host" => return Ok(Some(NACHostMode::MultiHost)),
                    "single-host" => return Ok(Some(NACHostMode::SingleHost)),
                    other => return Err(format!("Unhandled NAC host mode: {other}")),
                }
            }
        }
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn nac_mab_first(&self) -> Result<bool, &'static str> {
        Ok(has_child_equals(
            self.tree,
            self.node_id,
            "authentication order mab dot1x",
        ))
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
        let name = self.name();

        // It's configured as a sub-interface.
        if is_subinterface(&name)
            && let Some(vlan) = child_startswith(self.tree, self.node_id, "encapsulation dot1Q ")
        {
            return Ok(word_as_u32(vlan, 2));
        }

        // It's not a switchport.
        if has_child_equals(self.tree, self.node_id, "no switchport")
            || child_startswith(self.tree, self.node_id, "ip address ").is_some()
            || is_loopback(&name)
            || is_svi(&name)
        {
            return Ok(None);
        }

        // It's configured as a trunk.
        if has_child_equals(self.tree, self.node_id, "switchport mode trunk") {
            return Ok(
                child_startswith(self.tree, self.node_id, "switchport trunk native vlan ")
                    .and_then(|vlan| word_as_u32(vlan, 4)),
            );
        }

        // It's either dynamic or configured as an access port.
        if let Some(vlan) = child_startswith(self.tree, self.node_id, "switchport access vlan ") {
            return Ok(word_as_u32(vlan, 3));
        }

        // Default VLAN.
        Ok(Some(1))
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
            .any(|&cid| self.tree.arena[cid].text.as_ref() == "power inline never");
        Ok(!has)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn speed(&self) -> Result<Option<Vec<u32>>, &'static str> {
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("speed ") {
                if &**text == "speed auto" || &**text == "auto" {
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
        let is_trunk = self.tree.arena[self.node_id]
            .children
            .as_slice()
            .iter()
            .any(|&cid| self.tree.arena[cid].text.as_ref() == "switchport mode trunk");
        let tagged_vlans = self.tagged_vlans().unwrap_or_default();
        Ok(is_trunk && tagged_vlans.is_empty())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn tagged_vlans(&self) -> Result<Vec<u32>, &'static str> {
        let vlan_re = crate::regex_cache::regex(r"^switchport trunk allowed vlan [0-9,-]+$")
            .ok_or("regex error")?;
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if vlan_re.is_match(text) {
                let words: Vec<&str> = text.split_whitespace().collect();
                if words.len() >= 5
                    && let Ok(vlans) = crate::platforms::functions::expand_range(words[4])
                {
                    return Ok(vlans);
                }
            }
        }
        Ok(Vec::new())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn vrf(&self) -> Result<String, &'static str> {
        for &cid in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("ip vrf forwarding ")
                && let Some(v) = text.split_whitespace().nth(3)
            {
                return Ok(v.to_string());
            }
        }
        Ok(String::new())
    }
}
