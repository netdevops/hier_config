//! NETCONF `<edit-config>` payloads rendered from a remediation tree.

use super::json::split_text;
use super::xml::{Element, indent, render, single_root, xml_text};
use super::{FormatError, NETCONF_BASE_NS, resolve_list_keys};
use crate::arena::NodeId;
use crate::tree::Tree;
use std::sync::Arc;

/// Renders a remediation between [`from_xml`](super::from_xml) trees as NETCONF XML.
///
/// Negated nodes become elements carrying `nc:operation="delete"`; everything
/// else relies on the NETCONF default merge operation. When `running` is
/// given, deletions of keyed list entries are expressed by their key leaf
/// (found via `list_keys`); without it they fall back to value-bearing leaves.
///
/// # Errors
///
/// Returns [`FormatError`] unless the remediation has exactly one root node,
/// or if a negated node is an XML attribute, which NETCONF cannot express.
pub fn to_netconf_xml(
    remediation: &Tree,
    running: Option<&Tree>,
    list_keys: Option<&[String]>,
) -> Result<String, FormatError> {
    let root_node = single_root(remediation)?;
    let keys = resolve_list_keys(list_keys);
    let running_root = running.and_then(|tree| {
        tree.get_child_by_text(tree.root, &remediation.arena[root_node].text)
            .map(|id| (tree, id))
    });
    let mut element = netconf_element(
        remediation,
        root_node,
        &remediation.driver.negation_prefix,
        running_root,
        &keys,
    )?;
    element.set("xmlns:nc", NETCONF_BASE_NS);
    indent(&mut element);
    Ok(render(&element))
}

type RunningRef<'a> = Option<(&'a Tree, NodeId)>;

fn netconf_element(
    tree: &Tree,
    node_id: NodeId,
    negation_prefix: &str,
    running: RunningRef<'_>,
    list_keys: &[String],
) -> Result<Element, FormatError> {
    let text = Arc::clone(&tree.arena[node_id].text);
    if let Some(positive) = text.strip_prefix(negation_prefix) {
        return delete_element(positive, running, list_keys);
    }
    let (tag, payload) = split_text(&text);
    let mut element = Element::new(tag);
    if tree.arena[node_id].children.is_empty() {
        element.text = payload.map(xml_text);
        return Ok(element);
    }
    for child_id in tree.arena[node_id].children.iter() {
        let child_text = Arc::clone(&tree.arena[child_id].text);
        let childless = tree.arena[child_id].children.is_empty();
        if childless && let Some(name) = child_text.strip_prefix('@') {
            let (name, raw) = name.split_once(' ').unwrap_or((name, ""));
            element.set(name, xml_text(raw));
        } else if childless && let Some(raw) = child_text.strip_prefix("#text ") {
            element.text = Some(xml_text(raw));
        } else {
            // A negated child is looked up in the running parent by
            // `delete_element`, so it receives the parent context.
            let child_running = if child_text.starts_with(negation_prefix) {
                running
            } else {
                running.and_then(|(running_tree, running_id)| {
                    running_tree
                        .get_child_by_text(running_id, &child_text)
                        .map(|id| (running_tree, id))
                })
            };
            element.children.push(netconf_element(
                tree,
                child_id,
                negation_prefix,
                child_running,
                list_keys,
            )?);
        }
    }
    Ok(element)
}

fn delete_element(
    positive_text: &str,
    running_parent: RunningRef<'_>,
    list_keys: &[String],
) -> Result<Element, FormatError> {
    let (tag, payload) = split_text(positive_text);
    if tag.starts_with('@') {
        return Err(FormatError::Invalid(format!(
            "Attribute changes cannot be expressed as NETCONF operations: \
'{positive_text}'"
        )));
    }
    let mut element = Element::new(tag);
    element.set("nc:operation", "delete");
    let Some(raw_value) = payload else {
        return Ok(element);
    };
    // A keyed list entry (a branch in the running config) deletes by key leaf.
    if let Some(key) = running_entry_key(running_parent, positive_text, raw_value, list_keys) {
        let mut identity = Element::new(key);
        identity.text = Some(xml_text(raw_value));
        element.children.push(identity);
        return Ok(element);
    }
    element.text = Some(xml_text(raw_value));
    Ok(element)
}

/// Finds the key leaf identifying `positive_text` as a keyed list entry.
pub(crate) fn running_entry_key(
    running_parent: RunningRef<'_>,
    positive_text: &str,
    raw_value: &str,
    list_keys: &[String],
) -> Option<String> {
    let (tree, parent_id) = running_parent?;
    let entry_id = tree.get_child_by_text(parent_id, positive_text)?;
    if tree.arena[entry_id].children.is_empty() {
        return None;
    }
    matching_list_key(tree, entry_id, raw_value, list_keys)
}

/// Finds which list key holds `raw_value` inside `entry_id`.
pub(crate) fn matching_list_key(
    tree: &Tree,
    entry_id: NodeId,
    raw_value: &str,
    list_keys: &[String],
) -> Option<String> {
    list_keys
        .iter()
        .find(|key| {
            tree.get_child_by_text(entry_id, &format!("{key} {raw_value}"))
                .is_some()
        })
        .cloned()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::driver::Driver;
    use crate::formats::from_xml;
    use crate::models::Platform;

    fn trees(running: &str, intended: &str) -> (Tree, Tree) {
        let driver = || Driver::for_platform(Platform::CiscoIos);
        (
            from_xml(driver(), running, None).expect("valid XML"),
            from_xml(driver(), intended, None).expect("valid XML"),
        )
    }

    fn remediate(running: &str, intended: &str) -> (Tree, Tree) {
        let (running_tree, intended_tree) = trees(running, intended);
        let remediation = running_tree.config_to_get_to(&intended_tree).expect("diff");
        (running_tree, remediation)
    }

    #[test]
    fn merges_render_without_an_operation_attribute() {
        let (running, remediation) = remediate(
            "<c><hostname>r1</hostname></c>",
            "<c><hostname>r2</hostname></c>",
        );
        let rendered = to_netconf_xml(&remediation, Some(&running), None).expect("render");
        assert!(rendered.contains("<hostname>r2</hostname>"), "{rendered}");
        assert!(rendered.contains(NETCONF_BASE_NS), "{rendered}");
    }

    #[test]
    fn negations_render_as_delete_operations() {
        let (running, remediation) = remediate(
            "<c><hostname>r1</hostname><mtu>1500</mtu></c>",
            "<c><hostname>r1</hostname></c>",
        );
        let rendered = to_netconf_xml(&remediation, Some(&running), None).expect("render");
        assert!(rendered.contains(r#"nc:operation="delete""#), "{rendered}");
    }

    #[test]
    fn keyed_entry_deletions_use_their_key_leaf() {
        let (running, remediation) = remediate(
            "<c><i><name>Et1</name><mtu>1500</mtu></i>\
<i><name>Et2</name><mtu>1500</mtu></i></c>",
            "<c><i><name>Et1</name><mtu>1500</mtu></i></c>",
        );
        let rendered = to_netconf_xml(&remediation, Some(&running), None).expect("render");
        assert!(rendered.contains("<name>Et2</name>"), "{rendered}");
        assert!(rendered.contains(r#"nc:operation="delete""#), "{rendered}");
    }

    #[test]
    fn multiple_roots_are_rejected() {
        let mut remediation = Tree::for_platform(Platform::CiscoIos);
        let root = remediation.root;
        remediation.add_child(root, "a", true, true).expect("add");
        remediation.add_child(root, "b", true, true).expect("add");
        assert!(to_netconf_xml(&remediation, None, None).is_err());
    }
}
