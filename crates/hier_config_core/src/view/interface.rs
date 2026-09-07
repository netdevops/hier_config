//! The native interface view.
//!
//! [`InterfaceView`] provides the behaviour of Python's
//! `ConfigViewInterfaceBase` plus its four mixins. Everything platform-specific
//! is delegated to an [`InterfaceOps`] implementation.
//!
//! Every method of [`InterfaceOps`] has a default body, so a platform
//! implements only what its Python sibling overrides. Nothing is left
//! unimplemented: unsupported capabilities answer `None` or an empty
//! collection, exactly as an absent Python mixin does.

use std::fmt;

use crate::arena::NodeId;
use crate::models::MatchRule;
use crate::platforms::functions::expand_range;
use crate::tree::Tree;
use crate::view::helpers;
use crate::view::models::{InterfaceDot1qMode, InterfaceDuplex, Ipv4Interface, NacHostMode};

/// The default subinterface dot1q encapsulation command prefix.
pub const DEFAULT_ENCAPSULATION_PREFIX: &str = "encapsulation dot1q ";

/// Platform-specific behaviour for a single interface.
///
/// Implementations are zero-sized marker types held as `&'static dyn`, so a
/// view is cheap to construct and free of allocation.
pub trait InterfaceOps: fmt::Debug + Send + Sync {
    /// The platform's bundle interface name prefix, e.g. `Port-Channel`.
    ///
    /// `None` means the platform has no bundle concept, which is equivalent to
    /// a Python view that does not mix in `InterfaceBundleViewMixin`.
    fn bundle_prefix(&self) -> Option<&'static str> {
        None
    }

    /// The child command prefix assigning an interface to a bundle.
    fn bundle_membership_prefix(&self) -> Option<&'static str> {
        None
    }

    /// The subinterface dot1q encapsulation command prefix.
    fn encapsulation_prefix(&self) -> &'static str {
        DEFAULT_ENCAPSULATION_PREFIX
    }

    /// Whether the platform models 802.1Q VLAN membership on interfaces.
    fn supports_vlan(&self) -> bool {
        false
    }

    /// Whether the platform models physical interface attributes.
    /// Whether the platform's view exposes NAC (802.1X) properties.
    fn supports_nac(&self) -> bool {
        false
    }

    fn supports_physical(&self) -> bool {
        false
    }

    /// The configured IPv4 interface addresses.
    /// The interface name, e.g. `GigabitEthernet1/0/1`.
    fn name<'a>(&self, view: &InterfaceView<'a>) -> &'a str {
        view.default_name()
    }

    /// The interface name with the leading letters stripped.
    fn number<'a>(&self, view: &InterfaceView<'a>) -> &'a str {
        view.default_number()
    }

    /// The parent interface name, when this interface has one.
    fn parent_name(&self, view: &InterfaceView<'_>) -> Option<String> {
        view.default_parent_name()
    }

    /// The interface description, or an empty string when unset.
    fn description(&self, view: &InterfaceView<'_>) -> String {
        view.default_description()
    }

    /// Whether the interface is administratively enabled.
    fn enabled(&self, view: &InterfaceView<'_>) -> bool {
        view.default_enabled()
    }

    /// The bundle ID this interface is a member of.
    fn bundle_id(&self, view: &InterfaceView<'_>) -> Option<String> {
        view.default_bundle_id()
    }

    /// The bundle interface name this interface is a member of.
    fn bundle_name(&self, view: &InterfaceView<'_>) -> Option<String> {
        view.default_bundle_name()
    }

    /// The names of the interfaces that are members of this bundle.
    fn bundle_member_interfaces(&self, view: &InterfaceView<'_>) -> Vec<String> {
        view.default_bundle_member_interfaces()
    }

    fn ipv4_interfaces(&self, view: &InterfaceView<'_>) -> Vec<Ipv4Interface> {
        let _ = view;
        Vec::new()
    }

    /// The VRF the interface belongs to; empty when it is in the global table.
    fn vrf(&self, view: &InterfaceView<'_>) -> String {
        let _ = view;
        String::new()
    }

    /// Whether NAC (802.1X/MAB) is enabled on the interface.
    fn has_nac(&self, view: &InterfaceView<'_>) -> bool {
        let _ = view;
        false
    }

    /// Whether NAC control direction `in` is configured.
    fn nac_control_direction_in(&self, view: &InterfaceView<'_>) -> bool {
        let _ = view;
        false
    }

    /// The configured NAC host mode.
    fn nac_host_mode(&self, view: &InterfaceView<'_>) -> Option<NacHostMode> {
        let _ = view;
        None
    }

    /// Whether MAB is attempted before 802.1X.
    fn nac_mab_first(&self, view: &InterfaceView<'_>) -> bool {
        let _ = view;
        false
    }

    /// The maximum number of dot1x clients, where the platform reports one.
    fn nac_max_dot1x_clients(&self, view: &InterfaceView<'_>) -> Option<u32> {
        let _ = view;
        None
    }

    /// The maximum number of MAB clients, where the platform reports one.
    fn nac_max_mab_clients(&self, view: &InterfaceView<'_>) -> Option<u32> {
        let _ = view;
        None
    }

    /// The configured duplex setting.
    fn duplex(&self, view: &InterfaceView<'_>) -> Option<InterfaceDuplex> {
        let _ = view;
        None
    }

    /// Whether Power over Ethernet is enabled.
    fn poe(&self, view: &InterfaceView<'_>) -> Option<bool> {
        let _ = view;
        None
    }

    /// The configured speeds in Mbps.
    fn speed(&self, view: &InterfaceView<'_>) -> Option<Vec<u32>> {
        let _ = view;
        None
    }

    /// The native (untagged) VLAN.
    ///
    /// Override only when the platform's syntax differs from the Cisco-style
    /// default implemented by [`InterfaceView::default_native_vlan`].
    fn native_vlan(&self, view: &InterfaceView<'_>) -> Option<u32> {
        view.default_native_vlan()
    }

    /// The tagged VLANs.
    fn tagged_vlans(&self, view: &InterfaceView<'_>) -> Vec<u32> {
        view.default_tagged_vlans()
    }

    /// Whether every VLAN is tagged on the interface.
    fn tagged_all(&self, view: &InterfaceView<'_>) -> bool {
        view.default_tagged_all()
    }
}

/// A structured view over a single interface in a configuration tree.
#[derive(Clone, Copy)]
pub struct InterfaceView<'a> {
    tree: &'a Tree,
    node: NodeId,
    ops: &'static dyn InterfaceOps,
}

impl fmt::Debug for InterfaceView<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("InterfaceView")
            .field("name", &self.name())
            .finish()
    }
}

impl<'a> InterfaceView<'a> {
    /// Build a view over the interface rooted at `node`.
    #[must_use]
    pub const fn new(tree: &'a Tree, node: NodeId, ops: &'static dyn InterfaceOps) -> Self {
        Self { tree, node, ops }
    }

    /// The tree this view reads from.
    #[must_use]
    pub const fn tree(&self) -> &'a Tree {
        self.tree
    }

    /// The node holding the `interface ...` command.
    #[must_use]
    pub const fn node(&self) -> NodeId {
        self.node
    }

    /// The platform hooks backing this view.
    #[must_use]
    pub fn ops(&self) -> &'static dyn InterfaceOps {
        self.ops
    }

    /// The text of this interface's own config line.
    #[must_use]
    pub fn text(&self) -> &'a str {
        self.tree.get(self.node).map_or("", |node| &node.text)
    }

    /// The text of the first child matching `rule`, if any.
    #[must_use]
    pub fn child_text(&self, rule: &MatchRule) -> Option<&'a str> {
        let child = self.tree.get_child(self.node, rule)?;
        self.tree.get(child).map(|node| node.text.as_ref())
    }

    /// The text of every child matching `rule`.
    #[must_use]
    pub fn children_text(&self, rule: &MatchRule) -> Vec<&'a str> {
        self.tree
            .get_children(self.node, rule)
            .into_iter()
            .filter_map(|id| self.tree.get(id).map(|node| node.text.as_ref()))
            .collect()
    }

    /// Whether a child exactly matching `text` is present.
    #[must_use]
    pub fn has_child(&self, text: &str) -> bool {
        self.child_text(&MatchRule::equals(text)).is_some()
    }

    /// The word at `index` of the first child starting with `prefix`.
    #[must_use]
    pub fn child_word(&self, prefix: &str, index: usize) -> Option<&'a str> {
        self.child_text(&MatchRule::startswith(prefix))?
            .split_whitespace()
            .nth(index)
    }

    /// The word at `index` of the first child starting with `prefix`, as a number.
    #[must_use]
    pub fn child_number(&self, prefix: &str, index: usize) -> Option<u32> {
        self.child_word(prefix, index)?.parse().ok()
    }

    /// The parent node of this interface, normally the configuration root.
    #[must_use]
    pub fn parent(&self) -> Option<NodeId> {
        self.tree.get(self.node).and_then(|node| node.parent)
    }

    /// The text of the first sibling matching `rule`.
    #[must_use]
    pub fn sibling_text(&self, rule: &MatchRule) -> Option<&'a str> {
        let parent = self.parent()?;
        let sibling = self.tree.get_child(parent, rule)?;
        self.tree.get(sibling).map(|node| node.text.as_ref())
    }

    /// The text of every sibling matching `rule`.
    #[must_use]
    pub fn siblings_text(&self, rule: &MatchRule) -> Vec<&'a str> {
        let Some(parent) = self.parent() else {
            return Vec::new();
        };
        self.tree
            .get_children(parent, rule)
            .into_iter()
            .filter_map(|id| self.tree.get(id).map(|node| node.text.as_ref()))
            .collect()
    }

    /// A view over every sibling matching `rule`.
    #[must_use]
    pub fn sibling_views(&self, rule: &MatchRule) -> Vec<Self> {
        let Some(parent) = self.parent() else {
            return Vec::new();
        };
        self.tree
            .get_children(parent, rule)
            .into_iter()
            .map(|id| Self::new(self.tree, id, self.ops))
            .collect()
    }

    /// Whether a sibling with exactly `text` exists.
    #[must_use]
    pub fn has_sibling(&self, text: &str) -> bool {
        self.sibling_text(&MatchRule::equals(text)).is_some()
    }

    // -- ConfigViewInterfaceBase ------------------------------------------

    /// The interface description, or an empty string when unset.
    #[must_use]
    pub fn description(&self) -> String {
        self.ops.description(self)
    }

    /// The base-class interface description.
    #[must_use]
    pub fn default_description(&self) -> String {
        self.child_text(&MatchRule::startswith("description "))
            .and_then(|text| text.split_once(char::is_whitespace))
            .map_or_else(String::new, |(_, rest)| rest.to_owned())
    }

    /// Whether the interface is administratively enabled.
    #[must_use]
    pub fn enabled(&self) -> bool {
        self.ops.enabled(self)
    }

    /// The base-class administrative state.
    #[must_use]
    pub fn default_enabled(&self) -> bool {
        !self.has_child("shutdown")
    }

    /// The first configured IPv4 address, if any.
    #[must_use]
    pub fn ipv4_interface(&self) -> Option<Ipv4Interface> {
        self.ipv4_interfaces().into_iter().next()
    }

    /// Every configured IPv4 address.
    #[must_use]
    pub fn ipv4_interfaces(&self) -> Vec<Ipv4Interface> {
        self.ops.ipv4_interfaces(self)
    }

    /// Whether the interface is a loopback.
    #[must_use]
    pub fn is_loopback(&self) -> bool {
        self.name().to_lowercase().starts_with("loopback")
    }

    /// Whether the interface is a subinterface.
    #[must_use]
    pub fn is_subinterface(&self) -> bool {
        helpers::is_subinterface(self.name())
    }

    /// Whether the interface is a switched virtual interface.
    #[must_use]
    pub fn is_svi(&self) -> bool {
        self.name().to_lowercase().starts_with("vlan")
    }

    /// The interface name, e.g. `GigabitEthernet1/0/1`.
    #[must_use]
    pub fn name(&self) -> &'a str {
        self.ops.name(self)
    }

    /// The base-class interface name.
    #[must_use]
    pub fn default_name(&self) -> &'a str {
        self.text().split_whitespace().nth(1).unwrap_or("")
    }

    /// The interface name with the leading letters stripped.
    #[must_use]
    pub fn number(&self) -> &'a str {
        self.ops.number(self)
    }

    /// The base-class interface number.
    #[must_use]
    pub fn default_number(&self) -> &'a str {
        helpers::interface_number(self.name())
    }

    /// The parent interface name, when this is a subinterface.
    #[must_use]
    pub fn parent_name(&self) -> Option<String> {
        self.ops.parent_name(self)
    }

    /// The base-class parent interface name.
    #[must_use]
    pub fn default_parent_name(&self) -> Option<String> {
        helpers::parent_interface_name(self.name()).map(str::to_owned)
    }

    /// The interface's port number.
    #[must_use]
    pub fn port_number(&self) -> Option<u32> {
        helpers::port_number_from_number(self.number())
    }

    /// The subinterface number, when this is a subinterface.
    #[must_use]
    pub fn subinterface_number(&self) -> Option<u32> {
        helpers::subinterface_number(self.name())
    }

    /// The VRF the interface belongs to.
    #[must_use]
    pub fn vrf(&self) -> String {
        self.ops.vrf(self)
    }

    // -- InterfaceBundleViewMixin -----------------------------------------

    /// The bundle ID this interface is a member of.
    #[must_use]
    pub fn bundle_id(&self) -> Option<String> {
        self.ops.bundle_id(self)
    }

    /// The base-class bundle ID.
    #[must_use]
    pub fn default_bundle_id(&self) -> Option<String> {
        let prefix = self.ops.bundle_membership_prefix()?;
        self.child_word(prefix, prefix.split_whitespace().count())
            .map(str::to_owned)
    }

    /// The bundle interface name this interface is a member of.
    #[must_use]
    pub fn bundle_name(&self) -> Option<String> {
        self.ops.bundle_name(self)
    }

    /// The base-class bundle interface name.
    #[must_use]
    pub fn default_bundle_name(&self) -> Option<String> {
        let prefix = self.ops.bundle_prefix()?;
        let id = self.bundle_id()?;
        Some(format!("{prefix}{id}"))
    }

    /// Whether this interface is itself a bundle.
    #[must_use]
    pub fn is_bundle(&self) -> bool {
        self.ops.bundle_prefix().is_some_and(|prefix| {
            self.name()
                .to_lowercase()
                .starts_with(&prefix.to_lowercase())
        })
    }

    /// The names of the interfaces that are members of this bundle.
    #[must_use]
    pub fn bundle_member_interfaces(&self) -> Vec<String> {
        self.ops.bundle_member_interfaces(self)
    }

    /// The base-class bundle member interface names.
    #[must_use]
    pub fn default_bundle_member_interfaces(&self) -> Vec<String> {
        let Some(prefix) = self.ops.bundle_membership_prefix() else {
            return Vec::new();
        };
        if !self.is_bundle() {
            return Vec::new();
        }
        let id_index = prefix.split_whitespace().count();
        let number = self.number();
        let Some(parent) = self.tree.get(self.node).and_then(|node| node.parent) else {
            return Vec::new();
        };

        let membership_rule = MatchRule::startswith(prefix);
        self.tree
            .get_children(parent, &MatchRule::startswith("interface "))
            .into_iter()
            .filter_map(|candidate| {
                let member = Self::new(self.tree, candidate, self.ops);
                let matches = member
                    .child_text(&membership_rule)
                    .and_then(|text| text.split_whitespace().nth(id_index))
                    .is_some_and(|id| id == number);
                matches.then(|| member.name().to_owned())
            })
            .collect()
    }

    // -- InterfaceVlanViewMixin -------------------------------------------

    /// The derived 802.1Q mode.
    #[must_use]
    pub fn dot1q_mode(&self) -> Option<InterfaceDot1qMode> {
        if !self.ops.supports_vlan() {
            return None;
        }
        if self.tagged_all() {
            return Some(InterfaceDot1qMode::TaggedAll);
        }
        if !self.tagged_vlans().is_empty() {
            return Some(InterfaceDot1qMode::Tagged);
        }
        if self.native_vlan().is_some() && !self.is_svi() {
            return Some(InterfaceDot1qMode::Access);
        }
        None
    }

    /// The native (untagged) VLAN.
    #[must_use]
    pub fn native_vlan(&self) -> Option<u32> {
        if self.ops.supports_vlan() {
            self.ops.native_vlan(self)
        } else {
            None
        }
    }

    /// The tagged VLANs.
    #[must_use]
    pub fn tagged_vlans(&self) -> Vec<u32> {
        if self.ops.supports_vlan() {
            self.ops.tagged_vlans(self)
        } else {
            Vec::new()
        }
    }

    /// Whether every VLAN is tagged.
    #[must_use]
    pub fn tagged_all(&self) -> bool {
        self.ops.supports_vlan() && self.ops.tagged_all(self)
    }

    /// The Cisco-style native VLAN derivation shared by most platforms.
    #[must_use]
    pub fn default_native_vlan(&self) -> Option<u32> {
        let encapsulation = self.ops.encapsulation_prefix();
        if self.is_subinterface()
            && let Some(vlan) =
                self.child_number(encapsulation, encapsulation.split_whitespace().count())
        {
            return Some(vlan);
        }

        // Not a switchport.
        if self.has_child("no switchport")
            || self
                .child_text(&MatchRule::startswith("ip address "))
                .is_some()
            || self.is_loopback()
            || self.is_svi()
        {
            return None;
        }

        // Configured as a trunk.
        if self.has_child("switchport mode trunk") {
            return self.child_number("switchport trunk native vlan ", 4);
        }

        // Either dynamic or configured as an access port.
        self.child_number("switchport access vlan ", 3)
            .or(Some(DEFAULT_VLAN_ID))
    }

    /// The Cisco-style tagged VLAN derivation shared by most platforms.
    #[must_use]
    pub fn default_tagged_vlans(&self) -> Vec<u32> {
        self.child_text(&MatchRule::re_search(
            "^switchport trunk allowed vlan [0-9,-]+$",
        ))
        .and_then(|text| text.split_whitespace().nth(4))
        .and_then(|range| expand_range(range).ok())
        .unwrap_or_default()
    }

    /// The Cisco-style `tagged_all` derivation shared by most platforms.
    #[must_use]
    pub fn default_tagged_all(&self) -> bool {
        self.has_child("switchport mode trunk") && self.default_tagged_vlans().is_empty()
    }

    // -- InterfaceNACViewMixin --------------------------------------------

    /// Whether NAC is enabled on the interface.
    #[must_use]
    pub fn has_nac(&self) -> bool {
        self.ops.has_nac(self)
    }

    /// Whether NAC control direction `in` is configured.
    #[must_use]
    pub fn nac_control_direction_in(&self) -> bool {
        self.ops.nac_control_direction_in(self)
    }

    /// The configured NAC host mode.
    #[must_use]
    pub fn nac_host_mode(&self) -> Option<NacHostMode> {
        self.ops.nac_host_mode(self)
    }

    /// Whether MAB is attempted before 802.1X.
    #[must_use]
    pub fn nac_mab_first(&self) -> bool {
        self.ops.nac_mab_first(self)
    }

    /// The maximum number of dot1x clients.
    #[must_use]
    pub fn nac_max_dot1x_clients(&self) -> Option<u32> {
        self.ops.nac_max_dot1x_clients(self)
    }

    /// The maximum number of MAB clients.
    #[must_use]
    pub fn nac_max_mab_clients(&self) -> Option<u32> {
        self.ops.nac_max_mab_clients(self)
    }

    // -- InterfacePhysicalViewMixin ---------------------------------------

    /// Whether the platform models physical attributes for this interface.
    #[must_use]
    pub fn is_physical(&self) -> bool {
        self.ops.supports_physical()
    }

    /// The configured duplex setting.
    #[must_use]
    pub fn duplex(&self) -> Option<InterfaceDuplex> {
        self.ops.duplex(self)
    }

    /// The module number of the interface.
    #[must_use]
    pub fn module_number(&self) -> Option<u32> {
        if !self.ops.supports_physical() {
            return None;
        }
        helpers::module_number_from_number(self.number())
    }

    /// Whether Power over Ethernet is enabled.
    #[must_use]
    pub fn poe(&self) -> Option<bool> {
        self.ops.poe(self)
    }

    /// The configured speeds in Mbps.
    #[must_use]
    pub fn speed(&self) -> Option<Vec<u32>> {
        self.ops.speed(self)
    }
}

/// The VLAN an untagged access port falls back to when nothing is configured.
pub const DEFAULT_VLAN_ID: u32 = 1;
