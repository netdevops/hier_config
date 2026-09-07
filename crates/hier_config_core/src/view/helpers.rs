//! Small shared helpers used by the per-platform configuration views.
//!
//! These mirror the `HConfigChild` accessors the original Python views relied
//! on (`config.children`, `config.get_child(...)`, `config.get_children(...)`)
//! so each platform view can be ported faithfully without duplicating arena
//! traversal logic.

use std::net::Ipv4Addr;

use crate::arena::NodeId;
use crate::tree::Tree;

/// Texts of the direct children of `node_id`.
pub fn child_texts(tree: &Tree, node_id: NodeId) -> impl Iterator<Item = &str> {
    tree.arena[node_id]
        .children
        .as_slice()
        .iter()
        .map(|&cid| tree.arena[cid].text.as_ref())
}

/// True when a direct child's text equals `text`.
pub fn has_child_equals(tree: &Tree, node_id: NodeId, text: &str) -> bool {
    child_texts(tree, node_id).any(|t| t == text)
}

/// True when any of `texts` matches a direct child's text.
pub fn has_child_in(tree: &Tree, node_id: NodeId, texts: &[&str]) -> bool {
    child_texts(tree, node_id).any(|t| texts.contains(&t))
}

/// First direct child whose text starts with `prefix`.
pub fn child_startswith<'a>(tree: &'a Tree, node_id: NodeId, prefix: &str) -> Option<&'a str> {
    child_texts(tree, node_id).find(|t| t.starts_with(prefix))
}

/// All direct children whose text starts with `prefix`.
pub fn children_startswith<'a>(
    tree: &'a Tree,
    node_id: NodeId,
    prefix: &'a str,
) -> impl Iterator<Item = &'a str> {
    child_texts(tree, node_id).filter(move |t| t.starts_with(prefix))
}

/// The parent node of `node_id`, defaulting to the root when absent.
#[must_use]
pub fn parent_id(tree: &Tree, node_id: NodeId) -> NodeId {
    tree.arena[node_id].parent.unwrap_or(tree.root)
}

/// Word at `index` of `text`, parsed as a `u32`.
#[must_use]
pub fn word_as_u32(text: &str, index: usize) -> Option<u32> {
    text.split_whitespace().nth(index)?.parse::<u32>().ok()
}

/// Word at `index` of `text`.
#[must_use]
pub fn word(text: &str, index: usize) -> Option<&str> {
    text.split_whitespace().nth(index)
}

/// `parent_name` semantics shared by every platform except Aruba AOS-CX.
#[must_use]
pub fn default_parent_name(name: &str, is_subinterface: bool) -> Option<String> {
    if is_subinterface {
        return Some(name.split('.').next().unwrap_or(name).to_string());
    }
    None
}

/// `module_number` semantics shared by every implementing platform: the first
/// slash-delimited component of the interface number, when one exists.
#[must_use]
pub fn default_module_number(number: &str) -> Option<u32> {
    let (head, _) = number.split_once('/')?;
    head.parse::<u32>().ok()
}

/// Name-derived `is_subinterface`, identical on every platform.
#[must_use]
pub fn is_subinterface(name: &str) -> bool {
    name.contains('.')
}

/// Name-derived `is_loopback`, identical on every platform.
#[must_use]
pub fn is_loopback(name: &str) -> bool {
    name.to_lowercase().starts_with("loopback")
}

/// Name-derived `is_svi`, identical on every platform.
#[must_use]
pub fn is_svi(name: &str) -> bool {
    name.to_lowercase().starts_with("vlan")
}

/// Parse an IPv4 address spec written either as `A.B.C.D/len` or as the
/// `A.B.C.D` / `M.M.M.M` (address, netmask) word pair used by NX-OS style
/// `ip address` lines.
///
/// Returns `None` when the address is unparseable or the netmask is not a
/// contiguous run of leading ones.
#[must_use]
pub fn parse_ipv4_interface(spec: &str, netmask: Option<&str>) -> Option<(Ipv4Addr, u8)> {
    if let Some((ip_str, prefix_str)) = spec.split_once('/') {
        let ip = ip_str.parse::<Ipv4Addr>().ok()?;
        let prefix = prefix_str.parse::<u8>().ok()?;
        return (prefix <= 32).then_some((ip, prefix));
    }
    let ip = spec.parse::<Ipv4Addr>().ok()?;
    let mask = netmask?.parse::<Ipv4Addr>().ok()?;
    let bits = u32::from(mask);
    let prefix = bits.leading_ones();
    // Reject discontiguous masks such as 255.0.255.0.
    (bits.count_ones() == prefix).then(|| (ip, u8::try_from(prefix).unwrap_or(32)))
}
