//! Full tree configuration view querying network device configuration trees.

use std::collections::BTreeSet;
use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::models::Platform;
use crate::platforms;
use crate::tree::Tree;
use crate::view::interface::InterfaceView;
use crate::view::models::{InterfaceDot1qMode, StackMember, Vlan};

/// High-level view querying a parsed configuration tree for device-level properties.
#[derive(Debug)]
pub struct HConfigView<'a> {
    pub tree: &'a Tree,
    pub platform: Platform,
}

impl<'a> HConfigView<'a> {
    #[must_use]
    pub const fn new(tree: &'a Tree, platform: Platform) -> Self {
        Self { tree, platform }
    }

    /// Derives 802.1Q mode from VLAN specification.
    ///
    /// # Errors
    /// Returns Err if not implemented for the platform.
    pub const fn dot1q_mode_from_vlans(
        &self,
        untagged_vlan: Option<u32>,
        tagged_vlans: &[u32],
        tagged_all: bool,
    ) -> Result<Option<InterfaceDot1qMode>, &'static str> {
        match self.platform {
            Platform::AristaEos => {
                platforms::arista_eos::view::HConfigViewAristaEos::new(self.tree)
                    .dot1q_mode_from_vlans(untagged_vlan, tagged_vlans, tagged_all)
            }
            Platform::ArubaAoscx => {
                platforms::aruba_aoscx::view::HConfigViewArubaAoscx::new(self.tree)
                    .dot1q_mode_from_vlans(untagged_vlan, tagged_vlans, tagged_all)
            }
            Platform::CiscoIos => platforms::cisco_ios::view::HConfigViewCiscoIos::new(self.tree)
                .dot1q_mode_from_vlans(untagged_vlan, tagged_vlans, tagged_all),
            Platform::CiscoNxos => {
                platforms::cisco_nxos::view::HConfigViewCiscoNxos::new(self.tree)
                    .dot1q_mode_from_vlans(untagged_vlan, tagged_vlans, tagged_all)
            }
            Platform::CiscoXr => platforms::cisco_xr::view::HConfigViewCiscoXr::new(self.tree)
                .dot1q_mode_from_vlans(untagged_vlan, tagged_vlans, tagged_all),
            Platform::HpProcurve => {
                platforms::hp_procurve::view::HConfigViewHpProcurve::new(self.tree)
                    .dot1q_mode_from_vlans(untagged_vlan, tagged_vlans, tagged_all)
            }
            _ => platforms::generic::view::HConfigViewGeneric::new(self.tree)
                .dot1q_mode_from_vlans(untagged_vlan, tagged_vlans, tagged_all),
        }
    }

    /// Device hostname in lowercase.
    #[must_use]
    pub fn hostname(&self) -> Option<String> {
        match self.platform {
            Platform::AristaEos => {
                platforms::arista_eos::view::HConfigViewAristaEos::new(self.tree).hostname()
            }
            Platform::ArubaAoscx => {
                platforms::aruba_aoscx::view::HConfigViewArubaAoscx::new(self.tree).hostname()
            }
            Platform::CiscoIos => {
                platforms::cisco_ios::view::HConfigViewCiscoIos::new(self.tree).hostname()
            }
            Platform::CiscoNxos => {
                platforms::cisco_nxos::view::HConfigViewCiscoNxos::new(self.tree).hostname()
            }
            Platform::CiscoXr => {
                platforms::cisco_xr::view::HConfigViewCiscoXr::new(self.tree).hostname()
            }
            Platform::HpProcurve => {
                platforms::hp_procurve::view::HConfigViewHpProcurve::new(self.tree).hostname()
            }
            _ => platforms::generic::view::HConfigViewGeneric::new(self.tree).hostname(),
        }
    }

    /// Set of interface `NodeIds` in the tree.
    #[must_use]
    pub fn interface_node_ids(&self) -> Vec<NodeId> {
        let mut ids = Vec::new();
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("interface ") {
                ids.push(cid);
            }
        }
        ids
    }

    /// Returns interface views for all interfaces.
    #[must_use]
    pub fn interface_views(&self) -> Vec<InterfaceView<'a>> {
        let mut views = Vec::new();
        for &cid in self.tree.arena[self.tree.root].children.as_slice() {
            let text = &self.tree.arena[cid].text;
            if text.starts_with("interface ") {
                views.push(InterfaceView::new(self.tree, cid, self.platform));
            }
        }
        if self.platform == Platform::HpProcurve {
            for &cid in self.tree.arena[self.tree.root].children.as_slice() {
                let text = &self.tree.arena[cid].text;
                if text.starts_with("vlan ") {
                    let has_ip = self.tree.arena[cid]
                        .children
                        .as_slice()
                        .iter()
                        .any(|&sid| self.tree.arena[sid].text.starts_with("ip address "));
                    if has_ip {
                        views.push(InterfaceView::new(self.tree, cid, self.platform));
                    }
                }
            }
        }
        views
    }

    /// Lookup interface view by name.
    #[must_use]
    pub fn interface_view_by_name(&self, name: &str) -> Option<InterfaceView<'a>> {
        self.interface_views()
            .into_iter()
            .find(|iv| iv.name().as_deref() == Ok(name))
    }

    /// All interface names in the config.
    #[must_use]
    pub fn interfaces_names(&self) -> Vec<String> {
        self.interface_views()
            .into_iter()
            .filter_map(|iv| iv.name().ok())
            .collect()
    }

    /// Bundle interface views.
    #[must_use]
    pub fn bundle_interface_views(&self) -> Vec<InterfaceView<'a>> {
        self.interface_views()
            .into_iter()
            .filter(|iv| iv.is_bundle().unwrap_or(false))
            .collect()
    }

    /// Module numbers used by interfaces in this configuration.
    #[must_use]
    pub fn module_numbers(&self) -> Vec<u32> {
        let mut seen = BTreeSet::new();
        let mut result = Vec::new();
        for iv in self.interface_views() {
            if let Ok(Some(mod_num)) = iv.module_number()
                && seen.insert(mod_num)
            {
                result.push(mod_num);
            }
        }
        result
    }

    /// Interface names mentioned throughout configuration.
    ///
    /// # Errors
    /// Returns Err if not implemented.
    pub fn interface_names_mentioned(&self) -> Result<BTreeSet<String>, &'static str> {
        let names = self.interfaces_names();
        match self.platform {
            Platform::AristaEos => {
                platforms::arista_eos::view::HConfigViewAristaEos::new(self.tree)
                    .interface_names_mentioned(&names)
            }
            Platform::ArubaAoscx => {
                platforms::aruba_aoscx::view::HConfigViewArubaAoscx::new(self.tree)
                    .interface_names_mentioned(&names)
            }
            Platform::CiscoIos => platforms::cisco_ios::view::HConfigViewCiscoIos::new(self.tree)
                .interface_names_mentioned(&names),
            Platform::CiscoNxos => {
                platforms::cisco_nxos::view::HConfigViewCiscoNxos::new(self.tree)
                    .interface_names_mentioned(&names)
            }
            Platform::CiscoXr => platforms::cisco_xr::view::HConfigViewCiscoXr::new(self.tree)
                .interface_names_mentioned(&names),
            Platform::HpProcurve => {
                platforms::hp_procurve::view::HConfigViewHpProcurve::new(self.tree)
                    .interface_names_mentioned(&names)
            }
            _ => platforms::generic::view::HConfigViewGeneric::new(self.tree)
                .interface_names_mentioned(&names),
        }
    }

    /// Default IPv4 gateway.
    ///
    /// # Errors
    /// Returns Err if not implemented.
    pub fn ipv4_default_gw(&self) -> Result<Option<Ipv4Addr>, &'static str> {
        match self.platform {
            Platform::AristaEos => {
                platforms::arista_eos::view::HConfigViewAristaEos::new(self.tree).ipv4_default_gw()
            }
            Platform::ArubaAoscx => {
                platforms::aruba_aoscx::view::HConfigViewArubaAoscx::new(self.tree)
                    .ipv4_default_gw()
            }
            Platform::CiscoIos => {
                platforms::cisco_ios::view::HConfigViewCiscoIos::new(self.tree).ipv4_default_gw()
            }
            Platform::CiscoNxos => {
                platforms::cisco_nxos::view::HConfigViewCiscoNxos::new(self.tree).ipv4_default_gw()
            }
            Platform::CiscoXr => {
                platforms::cisco_xr::view::HConfigViewCiscoXr::new(self.tree).ipv4_default_gw()
            }
            Platform::HpProcurve => {
                platforms::hp_procurve::view::HConfigViewHpProcurve::new(self.tree)
                    .ipv4_default_gw()
            }
            _ => platforms::generic::view::HConfigViewGeneric::new(self.tree).ipv4_default_gw(),
        }
    }

    /// SNMP server location.
    ///
    /// # Errors
    /// Returns Err if not implemented.
    pub fn location(&self) -> Result<String, &'static str> {
        match self.platform {
            Platform::AristaEos => {
                platforms::arista_eos::view::HConfigViewAristaEos::new(self.tree).location()
            }
            Platform::ArubaAoscx => {
                platforms::aruba_aoscx::view::HConfigViewArubaAoscx::new(self.tree).location()
            }
            Platform::CiscoIos => {
                platforms::cisco_ios::view::HConfigViewCiscoIos::new(self.tree).location()
            }
            Platform::CiscoNxos => {
                platforms::cisco_nxos::view::HConfigViewCiscoNxos::new(self.tree).location()
            }
            Platform::CiscoXr => {
                platforms::cisco_xr::view::HConfigViewCiscoXr::new(self.tree).location()
            }
            Platform::HpProcurve => {
                platforms::hp_procurve::view::HConfigViewHpProcurve::new(self.tree).location()
            }
            _ => platforms::generic::view::HConfigViewGeneric::new(self.tree).location(),
        }
    }

    /// Stack members configured on the device.
    ///
    /// # Errors
    /// Returns Err if not implemented.
    pub fn stack_members(&self) -> Result<Vec<StackMember>, &'static str> {
        match self.platform {
            Platform::AristaEos => {
                platforms::arista_eos::view::HConfigViewAristaEos::new(self.tree).stack_members()
            }
            Platform::ArubaAoscx => {
                platforms::aruba_aoscx::view::HConfigViewArubaAoscx::new(self.tree).stack_members()
            }
            Platform::CiscoIos => {
                platforms::cisco_ios::view::HConfigViewCiscoIos::new(self.tree).stack_members()
            }
            Platform::CiscoNxos => {
                platforms::cisco_nxos::view::HConfigViewCiscoNxos::new(self.tree).stack_members()
            }
            Platform::CiscoXr => {
                platforms::cisco_xr::view::HConfigViewCiscoXr::new(self.tree).stack_members()
            }
            Platform::HpProcurve => {
                platforms::hp_procurve::view::HConfigViewHpProcurve::new(self.tree).stack_members()
            }
            _ => platforms::generic::view::HConfigViewGeneric::new(self.tree).stack_members(),
        }
    }

    /// VLANs configured in the tree.
    ///
    /// # Errors
    /// Returns Err if not implemented.
    /// Determines the configured VLAN IDs.
    ///
    /// # Errors
    /// Returns `Err` if the platform does not implement VLAN parsing.
    pub fn vlan_ids(&self) -> Result<Vec<u32>, &'static str> {
        Ok(self.vlans()?.into_iter().map(|vlan| vlan.id).collect())
    }

    /// # Errors
    /// Returns `Err` if the underlying property is not implemented for this platform.
    pub fn vlans(&self) -> Result<Vec<Vlan>, &'static str> {
        let interface_views = self.interface_views();
        match self.platform {
            Platform::AristaEos => {
                platforms::arista_eos::view::HConfigViewAristaEos::new(self.tree)
                    .vlans(&interface_views)
            }
            Platform::ArubaAoscx => {
                platforms::aruba_aoscx::view::HConfigViewArubaAoscx::new(self.tree)
                    .vlans(&interface_views)
            }
            Platform::CiscoIos => platforms::cisco_ios::view::HConfigViewCiscoIos::new(self.tree)
                .vlans(&interface_views),
            Platform::CiscoNxos => {
                platforms::cisco_nxos::view::HConfigViewCiscoNxos::new(self.tree)
                    .vlans(&interface_views)
            }
            Platform::CiscoXr => platforms::cisco_xr::view::HConfigViewCiscoXr::new(self.tree)
                .vlans(&interface_views),
            Platform::HpProcurve => {
                platforms::hp_procurve::view::HConfigViewHpProcurve::new(self.tree)
                    .vlans(&interface_views)
            }
            _ => {
                platforms::generic::view::HConfigViewGeneric::new(self.tree).vlans(&interface_views)
            }
        }
    }
}
