//! View implementation for Arista EOS.

use std::collections::BTreeSet;
use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::tree::Tree;
use crate::view::interface::InterfaceView;
use crate::view::models::{InterfaceDot1qMode, StackMember, Vlan};

/// Tree view logic for Arista EOS.
#[derive(Debug)]
pub struct HConfigViewAristaEos<'a> {
    pub tree: &'a Tree,
}

impl<'a> HConfigViewAristaEos<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree) -> Self {
        Self { tree }
    }

    /// Derives 802.1Q mode from VLAN specification (unimplemented on Arista EOS).
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
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

    /// Interface names mentioned throughout configuration (unimplemented on Arista EOS).
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn interface_names_mentioned(
        &self,
        _interface_names: &[String],
    ) -> Result<BTreeSet<String>, &'static str> {
        Err("not implemented")
    }

    /// Default IPv4 gateway (unimplemented on Arista EOS).
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn ipv4_default_gw(&self) -> Result<Option<Ipv4Addr>, &'static str> {
        Err("not implemented")
    }

    /// SNMP server location (unimplemented on Arista EOS).
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn location(&self) -> Result<String, &'static str> {
        Err("not implemented")
    }

    /// Stack members configured on the device (unimplemented on Arista EOS).
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn stack_members(&self) -> Result<Vec<StackMember>, &'static str> {
        Err("not implemented")
    }

    /// VLANs configured in the tree (unimplemented on Arista EOS).
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn vlans(
        &self,
        _interface_views: &[InterfaceView<'_>],
    ) -> Result<Vec<Vlan>, &'static str> {
        Err("not implemented")
    }
}

/// Interface view logic for Arista EOS.
#[derive(Debug)]
pub struct ConfigViewInterfaceAristaEos<'a> {
    pub tree: &'a Tree,
    pub node_id: NodeId,
}

impl<'a> ConfigViewInterfaceAristaEos<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree, node_id: NodeId) -> Self {
        Self { tree, node_id }
    }

    /// Returns the raw node text.
    #[must_use]
    pub fn text(&self) -> &str {
        &self.tree.arena[self.node_id].text
    }

    /// Determines the bundle prefix for the platform.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn bundle_prefix(&self) -> Result<&'static str, &'static str> {
        Err("not implemented")
    }

    /// Determines the name of the interface.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn name(&self) -> Result<String, &'static str> {
        Err("not implemented")
    }

    /// Removes letters from the interface name.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn number(&self) -> Result<String, &'static str> {
        Err("not implemented")
    }

    /// Returns whether the interface is a bundle.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn is_bundle(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// Returns the bundle ID.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn bundle_id(&self) -> Result<Option<String>, &'static str> {
        Err("not implemented")
    }

    /// Returns the bundle name.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn bundle_name(&self) -> Result<Option<String>, &'static str> {
        Err("not implemented")
    }

    /// Returns the bundle member interfaces.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub fn bundle_member_interfaces(&self) -> Result<Vec<String>, String> {
        Err("not implemented".to_string())
    }

    /// Determines the description of the interface.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn description(&self) -> Result<String, &'static str> {
        Err("not implemented")
    }

    /// Determines the configured Duplex of the interface.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn duplex(&self) -> Result<crate::view::models::InterfaceDuplex, &'static str> {
        Err("not implemented")
    }

    /// Determines if the interface is enabled.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn enabled(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// Determines if the interface has NAC configured.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn has_nac(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// IPv4 interfaces configured on this interface.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn ipv4_interfaces(&self) -> Result<Vec<(Ipv4Addr, u8)>, &'static str> {
        Err("not implemented")
    }

    /// Module number.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn module_number(&self) -> Result<Option<u32>, &'static str> {
        Err("not implemented")
    }

    /// NAC control direction in.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn nac_control_direction_in(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// NAC host mode.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub fn nac_host_mode(&self) -> Result<Option<crate::view::models::NACHostMode>, String> {
        Err("not implemented".to_string())
    }

    /// NAC MAB first.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn nac_mab_first(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// NAC max dot1x clients.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn nac_max_dot1x_clients(&self) -> Result<u32, &'static str> {
        Err("not implemented")
    }

    /// NAC max MAB clients.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn nac_max_mab_clients(&self) -> Result<u32, &'static str> {
        Err("not implemented")
    }

    /// Native VLAN.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn native_vlan(&self) -> Result<Option<u32>, &'static str> {
        Err("not implemented")
    }

    /// Parent interface name.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn parent_name(
        &self,
        _is_subinterface: bool,
    ) -> Result<Option<String>, &'static str> {
        Err("not implemented")
    }

    /// Power over Ethernet enabled.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn poe(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// Interface speeds in Mbps.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn speed(&self) -> Result<Option<Vec<u32>>, &'static str> {
        Err("not implemented")
    }

    /// Tagged all VLANs.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn tagged_all(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// Tagged VLANs.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn tagged_vlans(&self) -> Result<Vec<u32>, &'static str> {
        Err("not implemented")
    }

    /// VRF.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn vrf(&self) -> Result<String, &'static str> {
        Err("not implemented")
    }

    /// Returns whether the interface is a loopback.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn is_loopback(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }

    /// Returns whether the interface is an SVI.
    ///
    /// # Errors
    /// Returns Err because this is not implemented for Arista EOS.
    pub const fn is_svi(&self) -> Result<bool, &'static str> {
        Err("not implemented")
    }
}
