//! Generic / fallback view implementation.

use std::collections::BTreeSet;
use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::tree::Tree;
use crate::view::interface::InterfaceView;
use crate::view::models::{InterfaceDot1qMode, InterfaceDuplex, NACHostMode, StackMember, Vlan};

/// Generic tree view logic.
#[derive(Debug)]
pub struct HConfigViewGeneric<'a> {
    pub tree: &'a Tree,
}

impl<'a> HConfigViewGeneric<'a> {
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
    pub const fn hostname(&self) -> Option<String> {
        None
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn interface_names_mentioned(
        &self,
        interface_names: &[String],
    ) -> Result<BTreeSet<String>, &'static str> {
        Ok(interface_names.iter().cloned().collect())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn ipv4_default_gw(&self) -> Result<Option<Ipv4Addr>, &'static str> {
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn location(&self) -> Result<String, &'static str> {
        Ok(String::new())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn stack_members(&self) -> Result<Vec<StackMember>, &'static str> {
        Ok(Vec::new())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn vlans(
        &self,
        _interface_views: &[InterfaceView<'a>],
    ) -> Result<Vec<Vlan>, &'static str> {
        Ok(Vec::new())
    }
}

/// Generic interface view logic.
#[derive(Debug)]
pub struct ConfigViewInterfaceGeneric<'a> {
    pub tree: &'a Tree,
    pub node_id: NodeId,
}

impl<'a> ConfigViewInterfaceGeneric<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree, node_id: NodeId) -> Self {
        Self { tree, node_id }
    }

    #[must_use]
    pub fn text(&self) -> &str {
        &self.tree.arena[self.node_id].text
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn bundle_prefix(&self) -> Result<&'static str, &'static str> {
        Err("not implemented")
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
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn is_bundle(&self) -> Result<bool, &'static str> {
        Err("not implemented")
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
    pub const fn description(&self) -> Result<String, &'static str> {
        Ok(String::new())
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn duplex(&self) -> Result<InterfaceDuplex, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn enabled(&self) -> Result<bool, &'static str> {
        Ok(true)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn has_nac(&self) -> Result<bool, &'static str> {
        Ok(false)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn ipv4_interfaces(&self) -> Result<Vec<(Ipv4Addr, u8)>, &'static str> {
        Ok(Vec::new())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn module_number(&self) -> Result<Option<u32>, &'static str> {
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn nac_control_direction_in(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn nac_host_mode(&self) -> Result<Option<NACHostMode>, String> {
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` because this property is not implemented for this platform.
    pub const fn nac_mab_first(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn nac_max_dot1x_clients(&self) -> Result<u32, &'static str> {
        Ok(0)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn nac_max_mab_clients(&self) -> Result<u32, &'static str> {
        Ok(0)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn native_vlan(&self) -> Result<Option<u32>, &'static str> {
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
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn poe(&self) -> Result<bool, &'static str> {
        Ok(false)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn speed(&self) -> Result<Option<Vec<u32>>, &'static str> {
        Ok(None)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn tagged_all(&self) -> Result<bool, &'static str> {
        Ok(false)
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn tagged_vlans(&self) -> Result<Vec<u32>, &'static str> {
        Ok(Vec::new())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub const fn vrf(&self) -> Result<String, &'static str> {
        Ok(String::new())
    }
}
