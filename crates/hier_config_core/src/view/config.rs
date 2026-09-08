//! The native whole-config view.
//!
//! [`ConfigView`] provides the behaviour of Python's `HConfigViewBase`, with
//! everything platform-specific delegated to a [`ConfigOps`] implementation.

use std::collections::BTreeSet;
use std::fmt;
use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::models::MatchRule;
use crate::platforms::functions::expand_range;
use crate::tree::Tree;
use crate::view::interface::{InterfaceOps, InterfaceView};
use crate::view::models::{StackMember, Vlan};

/// The command prefix introducing an interface block on most platforms.
pub const DEFAULT_INTERFACE_PREFIX: &str = "interface ";

/// The regular expression matching an explicit VLAN definition block.
pub const DEFAULT_VLAN_DEFINITION_PATTERN: &str = "^vlan [0-9,-]+$";

/// Platform-specific behaviour for a whole configuration.
pub trait ConfigOps: fmt::Debug + Send + Sync {
    /// The interface hooks used for every interface in this configuration.
    fn interface_ops(&self) -> &'static dyn InterfaceOps;

    /// The command prefix introducing an interface block.
    fn interface_prefix(&self) -> &'static str {
        DEFAULT_INTERFACE_PREFIX
    }

    /// The regular expression matching an explicit VLAN definition block.
    fn vlan_definition_pattern(&self) -> &'static str {
        DEFAULT_VLAN_DEFINITION_PATTERN
    }

    /// The child command prefix naming a VLAN inside its definition block.
    fn vlan_name_prefix(&self) -> &'static str {
        "name "
    }

    /// The configured hostname.
    fn hostname(&self, view: &ConfigView<'_>) -> Option<String> {
        view.child_word("hostname ", 1).map(str::to_owned)
    }

    /// The IPv4 default gateway.
    fn ipv4_default_gw(&self, view: &ConfigView<'_>) -> Option<Ipv4Addr> {
        let _ = view;
        None
    }

    /// The configured stack members.
    fn stack_members(&self, view: &ConfigView<'_>) -> Vec<StackMember> {
        let _ = view;
        Vec::new()
    }

    /// The nodes defining the device's interfaces.
    fn interfaces(&self, view: &ConfigView<'_>) -> Vec<NodeId> {
        view.tree()
            .get_children(view.root(), &MatchRule::startswith(self.interface_prefix()))
    }

    /// A view over each interface in the configuration.
    fn interface_views<'a>(&self, view: &ConfigView<'a>) -> Vec<InterfaceView<'a>> {
        view.default_interface_views()
    }

    /// Every distinct interface name mentioned in the configuration.
    fn interface_names_mentioned(&self, view: &ConfigView<'_>) -> BTreeSet<String> {
        view.default_interface_names_mentioned()
    }

    /// The configured VLANs.
    fn vlans(&self, view: &ConfigView<'_>) -> Vec<Vlan> {
        view.default_vlans(false)
    }
}

/// A structured view over a whole configuration tree.
#[derive(Clone, Copy)]
pub struct ConfigView<'a> {
    tree: &'a Tree,
    ops: &'static dyn ConfigOps,
}

impl fmt::Debug for ConfigView<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("ConfigView")
            .field("hostname", &self.hostname())
            .finish()
    }
}

impl<'a> ConfigView<'a> {
    /// Build a view over `tree`.
    #[must_use]
    pub const fn new(tree: &'a Tree, ops: &'static dyn ConfigOps) -> Self {
        Self { tree, ops }
    }

    /// The tree this view reads from.
    #[must_use]
    pub const fn tree(&self) -> &'a Tree {
        self.tree
    }

    /// The root node of the tree.
    #[must_use]
    pub const fn root(&self) -> NodeId {
        self.tree.root
    }

    /// The platform hooks backing this view.
    #[must_use]
    pub fn ops(&self) -> &'static dyn ConfigOps {
        self.ops
    }

    /// The text of the first top-level child matching `rule`.
    #[must_use]
    pub fn child_text(&self, rule: &MatchRule) -> Option<&'a str> {
        let child = self.tree.get_child(self.tree.root, rule)?;
        self.tree.get(child).map(|node| node.text.as_ref())
    }

    /// The word at `index` of the first top-level child starting with `prefix`.
    #[must_use]
    pub fn child_word(&self, prefix: &str, index: usize) -> Option<&'a str> {
        self.child_text(&MatchRule::startswith(prefix))?
            .split_whitespace()
            .nth(index)
    }

    /// The text of every top-level child matching `rule`.
    #[must_use]
    pub fn children_text(&self, rule: &MatchRule) -> Vec<&'a str> {
        self.tree
            .get_children(self.tree.root, rule)
            .into_iter()
            .filter_map(|id| self.tree.get(id).map(|node| node.text.as_ref()))
            .collect()
    }

    // -- HConfigViewBase --------------------------------------------------

    /// The configured hostname.
    #[must_use]
    pub fn hostname(&self) -> Option<String> {
        self.ops.hostname(self)
    }

    /// The IPv4 default gateway.
    #[must_use]
    pub fn ipv4_default_gw(&self) -> Option<Ipv4Addr> {
        self.ops.ipv4_default_gw(self)
    }

    /// The nodes defining the device's interfaces.
    #[must_use]
    pub fn interfaces(&self) -> Vec<NodeId> {
        self.ops.interfaces(self)
    }

    /// A view over each interface in the configuration.
    #[must_use]
    pub fn interface_views(&self) -> Vec<InterfaceView<'a>> {
        self.ops.interface_views(self)
    }

    /// The base-class interface views: one per node returned by `interfaces`.
    #[must_use]
    pub fn default_interface_views(&self) -> Vec<InterfaceView<'a>> {
        let interface_ops = self.ops.interface_ops();
        self.interfaces()
            .into_iter()
            .map(|node| InterfaceView::new(self.tree, node, interface_ops))
            .collect()
    }

    /// The views representing bundle (LAG) interfaces.
    #[must_use]
    pub fn bundle_interface_views(&self) -> Vec<InterfaceView<'a>> {
        self.interface_views()
            .into_iter()
            .filter(InterfaceView::is_bundle)
            .collect()
    }

    /// Build a view for `node` using this configuration's interface hooks.
    #[must_use]
    pub fn interface_view_for(&self, node: NodeId) -> InterfaceView<'a> {
        InterfaceView::new(self.tree, node, self.ops.interface_ops())
    }

    /// The name of each interface, in configuration order.
    #[must_use]
    pub fn interface_names(&self) -> Vec<&'a str> {
        self.interface_views()
            .into_iter()
            .map(|view| view.name())
            .collect()
    }

    /// Every distinct interface name mentioned in the configuration.
    #[must_use]
    pub fn interface_names_mentioned(&self) -> BTreeSet<String> {
        self.ops.interface_names_mentioned(self)
    }

    /// The base-class set of interface names mentioned in the configuration.
    #[must_use]
    pub fn default_interface_names_mentioned(&self) -> BTreeSet<String> {
        self.interface_names()
            .into_iter()
            .map(str::to_owned)
            .collect()
    }

    /// The view for the interface with the given name, if present.
    #[must_use]
    pub fn interface_view_by_name(&self, name: &str) -> Option<InterfaceView<'a>> {
        self.interface_views()
            .into_iter()
            .find(|view| view.name() == name)
    }

    /// The SNMP location, or an empty string when unset.
    #[must_use]
    pub fn location(&self) -> String {
        self.child_text(&MatchRule::startswith("snmp-server location "))
            .map_or_else(String::new, |text| {
                text.splitn(3, char::is_whitespace)
                    .nth(2)
                    .unwrap_or("")
                    .replace('"', "")
            })
    }

    /// The distinct module numbers of physical interfaces, in order seen.
    #[must_use]
    pub fn module_numbers(&self) -> Vec<u32> {
        let mut seen = BTreeSet::new();
        let mut ordered = Vec::new();
        for view in self.interface_views() {
            if let Some(module) = view.module_number()
                && seen.insert(module)
            {
                ordered.push(module);
            }
        }
        ordered
    }

    /// The configured stack members.
    #[must_use]
    pub fn stack_members(&self) -> Vec<StackMember> {
        self.ops.stack_members(self)
    }

    /// The distinct VLAN IDs present in the configuration.
    #[must_use]
    pub fn vlan_ids(&self) -> BTreeSet<u32> {
        self.vlans().into_iter().map(|vlan| vlan.id).collect()
    }

    /// The configured VLANs.
    ///
    /// Explicitly defined VLAN blocks come first, followed by any remaining
    /// unnamed VLANs mentioned only on interfaces.
    #[must_use]
    pub fn vlans(&self) -> Vec<Vlan> {
        self.ops.vlans(self)
    }

    /// The base-class VLAN list.
    ///
    /// When `include_tagged` is set, VLANs that appear only as tagged members
    /// on an interface are reported too.
    #[must_use]
    pub fn default_vlans(&self, include_tagged: bool) -> Vec<Vlan> {
        let mut seen = BTreeSet::new();
        let mut vlans = Vec::new();

        let definitions = self
            .tree
            .get_children(
                self.tree.root,
                &MatchRule::re_search(self.ops.vlan_definition_pattern()),
            )
            .into_iter()
            .filter_map(|id| self.tree.get(id).map(|node| (id, node.text.as_ref())));

        for (id, text) in definitions {
            let name = self
                .tree
                .get_child(id, &MatchRule::startswith(self.ops.vlan_name_prefix()))
                .and_then(|child| self.tree.get(child))
                .and_then(|node| node.text.split_once(char::is_whitespace))
                .map(|(_, rest)| rest.replace('"', ""))
                .filter(|name| !name.is_empty());

            let Some(range) = text.split_whitespace().nth(1) else {
                continue;
            };
            let Ok(ids) = expand_range(range) else {
                continue;
            };
            for vlan_id in ids {
                seen.insert(vlan_id);
                vlans.push(Vlan {
                    id: vlan_id,
                    name: name.clone(),
                });
            }
        }

        for view in self.interface_views() {
            if include_tagged {
                for tagged in view.tagged_vlans() {
                    if seen.insert(tagged) {
                        vlans.push(Vlan {
                            id: tagged,
                            name: None,
                        });
                    }
                }
            }
            if let Some(native_vlan) = view.native_vlan()
                && seen.insert(native_vlan)
            {
                vlans.push(Vlan {
                    id: native_vlan,
                    name: None,
                });
            }
        }

        vlans
    }
}

#[cfg(test)]
mod tests {
    use super::{ConfigOps, ConfigView};
    use crate::models::Platform;
    use crate::tree::Tree;
    use crate::view::interface::InterfaceOps;
    use crate::view::models::InterfaceDot1qMode;

    /// Hooks that override nothing, so every default trait body is exercised
    /// with each optional capability switched off.
    #[derive(Debug, Clone, Copy)]
    struct BareInterfaceOps;

    impl InterfaceOps for BareInterfaceOps {}

    static BARE_INTERFACE_OPS: BareInterfaceOps = BareInterfaceOps;

    #[derive(Debug, Clone, Copy)]
    struct BareConfigOps;

    impl ConfigOps for BareConfigOps {
        fn interface_ops(&self) -> &'static dyn InterfaceOps {
            &BARE_INTERFACE_OPS
        }
    }

    static BARE_CONFIG_OPS: BareConfigOps = BareConfigOps;

    /// Hooks that opt into the optional capabilities but still override no
    /// behavior, so the Cisco-style default derivations are exercised.
    #[derive(Debug, Clone, Copy)]
    struct CapableInterfaceOps;

    impl InterfaceOps for CapableInterfaceOps {
        fn bundle_prefix(&self) -> Option<&'static str> {
            Some("Port-channel")
        }

        fn bundle_membership_prefix(&self) -> Option<&'static str> {
            Some("channel-group ")
        }

        fn supports_vlan(&self) -> bool {
            true
        }

        fn supports_physical(&self) -> bool {
            true
        }
    }

    static CAPABLE_INTERFACE_OPS: CapableInterfaceOps = CapableInterfaceOps;

    #[derive(Debug, Clone, Copy)]
    struct CapableConfigOps;

    impl ConfigOps for CapableConfigOps {
        fn interface_ops(&self) -> &'static dyn InterfaceOps {
            &CAPABLE_INTERFACE_OPS
        }
    }

    static CAPABLE_CONFIG_OPS: CapableConfigOps = CapableConfigOps;

    const CONFIG: &str = "\
hostname Example-Switch
snmp-server location \"Rack 1, DC-A\"
vlan 10
  name USERS
vlan 20
interface Port-channel1
  switchport mode trunk
interface Ethernet1/1
  description uplink
  channel-group 1 mode active
  switchport mode trunk
  switchport trunk allowed vlan 10,20
interface Ethernet2/1
  switchport access vlan 10
interface Ethernet2/2
  shutdown
  switchport mode trunk
interface Ethernet3/1
  no switchport
  ip address 192.0.2.1 255.255.255.0
interface Ethernet3/1.100
  encapsulation dot1Q 100
interface Loopback0
  ip address 10.0.0.1/32
interface Vlan10
  ip address 198.51.100.1/24
";

    fn tree() -> Tree {
        Tree::from_str(Platform::Generic, CONFIG).expect("config parses")
    }

    #[test]
    fn reads_top_level_attributes() {
        let tree = tree();
        let view = ConfigView::new(&tree, &BARE_CONFIG_OPS);
        assert_eq!(view.hostname().as_deref(), Some("Example-Switch"));
        assert_eq!(view.location(), "Rack 1, DC-A");
        assert_eq!(view.ipv4_default_gw(), None);
        assert!(view.stack_members().is_empty());
    }

    #[test]
    fn discovers_every_interface_block() {
        let tree = tree();
        let view = ConfigView::new(&tree, &BARE_CONFIG_OPS);
        assert_eq!(
            view.interface_names(),
            vec![
                "Port-channel1",
                "Ethernet1/1",
                "Ethernet2/1",
                "Ethernet2/2",
                "Ethernet3/1",
                "Ethernet3/1.100",
                "Loopback0",
                "Vlan10",
            ]
        );
        assert_eq!(view.interface_views().len(), 8);
        assert!(view.interface_view_by_name("Ethernet2/1").is_some());
        assert!(view.interface_view_by_name("Ethernet9/9").is_none());
    }

    #[test]
    fn collects_vlans_from_definition_blocks() {
        let tree = tree();
        let view = ConfigView::new(&tree, &BARE_CONFIG_OPS);
        let vlans = view.vlans();
        assert_eq!(vlans.len(), 2);
        assert_eq!(vlans[0].id, 10);
        assert_eq!(vlans[0].name.as_deref(), Some("USERS"));
        assert_eq!(vlans[1].id, 20);
        assert_eq!(vlans[1].name, None);
        assert_eq!(
            view.vlan_ids().into_iter().collect::<Vec<_>>(),
            vec![10, 20]
        );
    }

    #[test]
    fn classifies_interfaces_by_name() {
        let tree = tree();
        let view = ConfigView::new(&tree, &CAPABLE_CONFIG_OPS);

        let bundle = view
            .interface_view_by_name("Port-channel1")
            .expect("Port-channel1");
        assert!(bundle.is_bundle());
        assert_eq!(bundle.number(), "1");

        let member = view
            .interface_view_by_name("Ethernet1/1")
            .expect("Ethernet1/1");
        assert!(!member.is_bundle());
        assert_eq!(member.bundle_id().as_deref(), Some("1"));
        assert_eq!(member.bundle_name().as_deref(), Some("Port-channel1"));
        assert_eq!(member.module_number(), Some(1));
        assert_eq!(member.port_number(), Some(1));

        let sub = view
            .interface_view_by_name("Ethernet3/1.100")
            .expect("subinterface");
        assert!(sub.is_subinterface());
        assert_eq!(sub.parent_name().as_deref(), Some("Ethernet3/1"));
        assert_eq!(sub.subinterface_number(), Some(100));

        let loopback = view.interface_view_by_name("Loopback0").expect("Loopback0");
        assert!(loopback.is_loopback());
        assert!(!loopback.is_svi());

        let svi = view.interface_view_by_name("Vlan10").expect("Vlan10");
        assert!(svi.is_svi());
        assert!(!svi.is_loopback());
    }

    #[test]
    fn derives_vlan_membership_when_supported() {
        let tree = tree();
        let view = ConfigView::new(&tree, &CAPABLE_CONFIG_OPS);

        let trunk = view
            .interface_view_by_name("Ethernet1/1")
            .expect("Ethernet1/1");
        assert_eq!(trunk.tagged_vlans(), vec![10, 20]);
        assert!(!trunk.tagged_all());
        assert_eq!(trunk.dot1q_mode(), Some(InterfaceDot1qMode::Tagged));

        let access = view
            .interface_view_by_name("Ethernet2/1")
            .expect("Ethernet2/1");
        assert_eq!(access.native_vlan(), Some(10));
        assert_eq!(access.dot1q_mode(), Some(InterfaceDot1qMode::Access));

        let trunk_all = view
            .interface_view_by_name("Ethernet2/2")
            .expect("Ethernet2/2");
        assert!(trunk_all.tagged_all());
        assert_eq!(trunk_all.dot1q_mode(), Some(InterfaceDot1qMode::TaggedAll));

        let routed = view
            .interface_view_by_name("Ethernet3/1")
            .expect("Ethernet3/1");
        assert_eq!(routed.native_vlan(), None);
        assert_eq!(routed.dot1q_mode(), None);
    }

    #[test]
    fn vlan_membership_is_gated_off_when_unsupported() {
        let tree = tree();
        let view = ConfigView::new(&tree, &BARE_CONFIG_OPS);
        let trunk = view
            .interface_view_by_name("Ethernet1/1")
            .expect("Ethernet1/1");
        assert!(trunk.tagged_vlans().is_empty());
        assert!(!trunk.tagged_all());
        assert_eq!(trunk.native_vlan(), None);
        assert_eq!(trunk.dot1q_mode(), None);
    }

    #[test]
    fn vlans_can_include_interface_tagged_vlans() {
        let tree = tree();
        let view = ConfigView::new(&tree, &CAPABLE_CONFIG_OPS);
        let ids: Vec<u32> = view
            .default_vlans(true)
            .into_iter()
            .map(|vlan| vlan.id)
            .collect();
        // VLAN 1 comes from the base native-VLAN default on the access-less
        // trunk ports, matching the Python derivation.
        assert_eq!(ids, vec![10, 20, 1]);
    }

    #[test]
    fn reads_descriptions_addresses_and_admin_state() {
        let tree = tree();
        let view = ConfigView::new(&tree, &CAPABLE_CONFIG_OPS);

        let described = view
            .interface_view_by_name("Ethernet1/1")
            .expect("Ethernet1/1");
        assert_eq!(described.description(), "uplink");
        assert!(described.enabled());
        assert!(described.ipv4_interfaces().is_empty());

        let shut = view
            .interface_view_by_name("Ethernet2/2")
            .expect("Ethernet2/2");
        assert!(!shut.enabled());
        assert_eq!(shut.description(), "");

        // `ipv4_interfaces` is abstract in Python and defaults to empty in
        // Rust: reading addresses is always a platform responsibility.
        let routed = view
            .interface_view_by_name("Ethernet3/1")
            .expect("Ethernet3/1");
        assert!(routed.ipv4_interfaces().is_empty());
        assert_eq!(routed.vrf(), "");
    }

    #[test]
    fn module_numbers_follow_physical_support() {
        let tree = tree();

        let bare = ConfigView::new(&tree, &BARE_CONFIG_OPS);
        assert!(bare.module_numbers().is_empty());
        assert!(!BARE_INTERFACE_OPS.supports_physical());
        assert!(!BARE_INTERFACE_OPS.supports_nac());
        assert!(!BARE_INTERFACE_OPS.supports_vlan());

        let capable = ConfigView::new(&tree, &CAPABLE_CONFIG_OPS);
        assert_eq!(capable.module_numbers(), vec![1, 2, 3]);
    }
}
