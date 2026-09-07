//! Dispatch interface view logic to the platform-specific view modules.
//!
//! Each platform owns its parsing logic under
//! `crates/hier_config_core/src/platforms/<platform>/view.rs`, alongside that
//! platform's `mod.rs` and `rules.json`. This module is a thin dispatcher that
//! selects the right platform implementation at runtime.

use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::models::Platform;
use crate::platforms;
use crate::tree::Tree;
use crate::view::models::{InterfaceDot1qMode, InterfaceDuplex, NACHostMode};

/// Computes dot1q mode based on VLAN configuration rules.
#[must_use]
pub const fn derive_dot1q_mode(
    tagged_all: bool,
    has_tagged_vlans: bool,
    native_vlan: Option<u32>,
    is_svi: bool,
) -> Option<InterfaceDot1qMode> {
    if tagged_all {
        return Some(InterfaceDot1qMode::TaggedAll);
    }
    if has_tagged_vlans {
        return Some(InterfaceDot1qMode::Tagged);
    }
    if native_vlan.is_some() && !is_svi {
        return Some(InterfaceDot1qMode::Access);
    }
    None
}

/// Calls `$method` on the platform-specific interface view for `$self`'s platform.
macro_rules! dispatch {
    ($self:ident, $method:ident $(, $arg:expr)*) => {
        match $self.platform {
            Platform::AristaEos => platforms::arista_eos::view::ConfigViewInterfaceAristaEos::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::ArubaAoscx => platforms::aruba_aoscx::view::ConfigViewInterfaceArubaAoscx::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::CiscoIos => platforms::cisco_ios::view::ConfigViewInterfaceCiscoIos::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::CiscoNxos => platforms::cisco_nxos::view::ConfigViewInterfaceCiscoNxos::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::CiscoXr => platforms::cisco_xr::view::ConfigViewInterfaceCiscoXr::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::HpProcurve => platforms::hp_procurve::view::ConfigViewInterfaceHpProcurve::new($self.tree, $self.node_id).$method($($arg),*),
            _ => platforms::generic::view::ConfigViewInterfaceGeneric::new($self.tree, $self.node_id).$method($($arg),*),
        }
    };
}

/// Calls `$method` on the platform view for every platform except Arista EOS.
macro_rules! dispatch_non_arista {
    ($self:ident, $method:ident $(, $arg:expr)*) => {
        match $self.platform {
            Platform::ArubaAoscx => platforms::aruba_aoscx::view::ConfigViewInterfaceArubaAoscx::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::CiscoIos => platforms::cisco_ios::view::ConfigViewInterfaceCiscoIos::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::CiscoNxos => platforms::cisco_nxos::view::ConfigViewInterfaceCiscoNxos::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::CiscoXr => platforms::cisco_xr::view::ConfigViewInterfaceCiscoXr::new($self.tree, $self.node_id).$method($($arg),*),
            Platform::HpProcurve => platforms::hp_procurve::view::ConfigViewInterfaceHpProcurve::new($self.tree, $self.node_id).$method($($arg),*),
            _ => platforms::generic::view::ConfigViewInterfaceGeneric::new($self.tree, $self.node_id).$method($($arg),*),
        }
    };
}

/// Interface view querying properties of an interface node within a [`Tree`].
#[derive(Debug)]
pub struct InterfaceView<'a> {
    pub tree: &'a Tree,
    pub node_id: NodeId,
    pub platform: Platform,
}

impl<'a> InterfaceView<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree, node_id: NodeId, platform: Platform) -> Self {
        Self {
            tree,
            node_id,
            platform,
        }
    }

    /// Returns the raw node text.
    #[must_use]
    pub fn text(&self) -> &str {
        &self.tree.arena[self.node_id].text
    }

    /// Determines the bundle prefix for the platform.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement bundles.
    pub const fn bundle_prefix(&self) -> Result<&'static str, &'static str> {
        dispatch!(self, bundle_prefix)
    }

    /// Determines the name of the interface.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement interface names.
    pub fn name(&self) -> Result<String, &'static str> {
        match self.platform {
            Platform::AristaEos => platforms::arista_eos::view::ConfigViewInterfaceAristaEos::new(
                self.tree,
                self.node_id,
            )
            .name(),
            _ => Ok(dispatch_non_arista!(self, name)),
        }
    }

    /// Removes letters from the interface name, leaving numbers and symbols.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement interface numbers.
    pub fn number(&self) -> Result<String, &'static str> {
        match self.platform {
            Platform::AristaEos => platforms::arista_eos::view::ConfigViewInterfaceAristaEos::new(
                self.tree,
                self.node_id,
            )
            .number(),
            _ => Ok(dispatch_non_arista!(self, number)),
        }
    }

    /// Determines whether the interface is a subinterface.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement interface names.
    pub fn is_subinterface(&self) -> Result<bool, &'static str> {
        Ok(self.name()?.contains('.'))
    }

    /// Determines whether the interface is a loopback.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement interface names.
    pub fn is_loopback(&self) -> Result<bool, &'static str> {
        Ok(self.name()?.to_ascii_lowercase().starts_with("loopback"))
    }

    /// Determines whether the interface is a switched virtual interface.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement interface names.
    pub fn is_svi(&self) -> Result<bool, &'static str> {
        Ok(self.name()?.to_ascii_lowercase().starts_with("vlan"))
    }

    /// Returns whether the interface is a bundle.
    ///
    /// # Errors
    /// Returns `Err` if bundle operations are not implemented for the platform.
    pub fn is_bundle(&self) -> Result<bool, &'static str> {
        dispatch!(self, is_bundle)
    }

    /// Returns the bundle ID.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn bundle_id(&self) -> Result<Option<String>, &'static str> {
        dispatch!(self, bundle_id)
    }

    /// Returns the bundle name.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn bundle_name(&self) -> Result<Option<String>, &'static str> {
        dispatch!(self, bundle_name)
    }

    /// Returns the bundle member interfaces.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn bundle_member_interfaces(&self) -> Result<Vec<String>, String> {
        dispatch!(self, bundle_member_interfaces)
    }

    /// Determines the description of the interface.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn description(&self) -> Result<String, &'static str> {
        dispatch!(self, description)
    }

    /// Determines the configured duplex of the interface.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn duplex(&self) -> Result<InterfaceDuplex, &'static str> {
        dispatch!(self, duplex)
    }

    /// Determines if the interface is enabled.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn enabled(&self) -> Result<bool, &'static str> {
        dispatch!(self, enabled)
    }

    /// Determines if the interface has NAC configured.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn has_nac(&self) -> Result<bool, &'static str> {
        dispatch!(self, has_nac)
    }

    /// Returns configured IPv4 interfaces as `(address, prefix_len)`.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn ipv4_interfaces(&self) -> Result<Vec<(Ipv4Addr, u8)>, &'static str> {
        dispatch!(self, ipv4_interfaces)
    }

    /// Determines the module number of the interface.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn module_number(&self) -> Result<Option<u32>, &'static str> {
        dispatch!(self, module_number)
    }

    /// Determines if NAC control direction in is configured.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn nac_control_direction_in(&self) -> Result<bool, &'static str> {
        dispatch!(self, nac_control_direction_in)
    }

    /// Determines the NAC host mode.
    ///
    /// # Errors
    /// Returns `Err` if not implemented, or on an unhandled host mode.
    pub fn nac_host_mode(&self) -> Result<Option<NACHostMode>, String> {
        dispatch!(self, nac_host_mode)
    }

    /// Determines if NAC is configured for MAB first.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn nac_mab_first(&self) -> Result<bool, &'static str> {
        dispatch!(self, nac_mab_first)
    }

    /// Determines the max dot1x clients.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn nac_max_dot1x_clients(&self) -> Result<u32, &'static str> {
        dispatch!(self, nac_max_dot1x_clients)
    }

    /// Determines the max MAB clients.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn nac_max_mab_clients(&self) -> Result<u32, &'static str> {
        dispatch!(self, nac_max_mab_clients)
    }

    /// Determines the native VLAN.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn native_vlan(&self) -> Result<Option<u32>, &'static str> {
        dispatch!(self, native_vlan)
    }

    /// Determines the parent interface name.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn parent_name(&self) -> Result<Option<String>, &'static str> {
        let is_sub = self.is_subinterface()?;
        dispatch!(self, parent_name, is_sub)
    }

    /// Determines if Power over Ethernet is enabled.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn poe(&self) -> Result<bool, &'static str> {
        dispatch!(self, poe)
    }

    /// Determines the interface port number.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement interface names.
    pub fn port_number(&self) -> Result<u32, &'static str> {
        let name = self.name()?;
        let last_part = name.split('/').next_back().unwrap_or(&name);
        let port_part = last_part.split('.').next().unwrap_or(last_part);
        Ok(port_part.parse::<u32>().unwrap_or(0))
    }

    /// Determines the statically allowed interface speeds, in Mbps.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn speed(&self) -> Result<Option<Vec<u32>>, &'static str> {
        dispatch!(self, speed)
    }

    /// Determines the sub-interface number.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement interface names.
    pub fn subinterface_number(&self) -> Result<Option<u32>, &'static str> {
        if self.is_subinterface()? {
            let name = self.name()?;
            Ok(name.split('.').next_back().and_then(|s| s.parse().ok()))
        } else {
            Ok(None)
        }
    }

    /// Determines if all VLANs are tagged.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn tagged_all(&self) -> Result<bool, &'static str> {
        dispatch!(self, tagged_all)
    }

    /// Determines the tagged VLANs.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn tagged_vlans(&self) -> Result<Vec<u32>, &'static str> {
        dispatch!(self, tagged_vlans)
    }

    /// Determines the VRF the interface belongs to.
    ///
    /// # Errors
    /// Returns `Err` if not implemented for the platform.
    pub fn vrf(&self) -> Result<String, &'static str> {
        dispatch!(self, vrf)
    }

    /// Derives the 802.1Q mode of the interface.
    #[must_use]
    pub fn dot1q_mode(&self) -> Option<InterfaceDot1qMode> {
        let tagged_all = self.tagged_all().unwrap_or(false);
        let tagged_vlans = self.tagged_vlans().unwrap_or_default();
        let native_vlan = self.native_vlan().unwrap_or(None);
        let is_svi = self.is_svi().unwrap_or(false);
        derive_dot1q_mode(tagged_all, !tagged_vlans.is_empty(), native_vlan, is_svi)
    }
}
