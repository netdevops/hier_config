//! View implementation for Cisco IOS XR.

use std::collections::BTreeSet;
use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::tree::Tree;
use crate::view::helpers::{default_module_number, default_parent_name, parse_ipv4_interface};
use crate::view::interface::InterfaceView;
use crate::view::models::{InterfaceDot1qMode, InterfaceDuplex, NACHostMode, StackMember, Vlan};

/// Tree view logic for Cisco IOS XR.
#[derive(Debug)]
pub struct HConfigViewCiscoXr<'a> {
    pub tree: &'a Tree,
}

impl<'a> HConfigViewCiscoXr<'a> {
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
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn interface_names_mentioned(
        &self,
        _interface_names: &[String],
    ) -> Result<BTreeSet<String>, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn ipv4_default_gw(&self) -> Result<Option<Ipv4Addr>, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn location(&self) -> Result<String, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn stack_members(&self) -> Result<Vec<StackMember>, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn vlans(
        &self,
        _interface_views: &[InterfaceView<'_>],
    ) -> Result<Vec<Vlan>, &'static str> {
        Err("not implemented")
    }
}

/// Interface view logic for Cisco IOS XR.
#[derive(Debug)]
pub struct ConfigViewInterfaceCiscoXr<'a> {
    pub tree: &'a Tree,
    pub node_id: NodeId,
}

impl<'a> ConfigViewInterfaceCiscoXr<'a> {
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
        Ok("Bundle-Ether")
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
        Ok(name
            .to_ascii_lowercase()
            .starts_with(&prefix.to_ascii_lowercase()))
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn bundle_id(&self) -> Result<Option<String>, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn bundle_name(&self) -> Result<Option<String>, &'static str> {
        Err("not implemented")
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
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn duplex(&self) -> Result<InterfaceDuplex, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn enabled(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn has_nac(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn ipv4_interfaces(&self) -> Result<Vec<(Ipv4Addr, u8)>, &'static str> {
        let mut ifaces = Vec::new();
        for &child_id in self.tree.arena[self.node_id].children.as_slice() {
            let text = &self.tree.arena[child_id].text;
            if let Some(rest) = text.strip_prefix("ipv4 address ") {
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
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn nac_control_direction_in(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn nac_host_mode(&self) -> Result<Option<NACHostMode>, String> {
        Err("not implemented".to_string())
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn nac_mab_first(&self) -> Result<bool, &'static str> {
        Err("not implemented")
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
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn native_vlan(&self) -> Result<Option<u32>, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn parent_name(&self, is_subinterface: bool) -> Result<Option<String>, &'static str> {
        Ok(default_parent_name(&self.name(), is_subinterface))
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn poe(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn speed(&self) -> Result<Option<Vec<u32>>, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn tagged_all(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn tagged_vlans(&self) -> Result<Vec<u32>, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn vrf(&self) -> Result<String, &'static str> {
        Err("not implemented")
    }
}
