//! gNMI-style set payloads rendered from a remediation tree.

use serde_json::{Map, Value};
use std::sync::Arc;

use super::json::{split_text, store_member};
use super::netconf::{matching_list_key, running_entry_key};
use super::value::{leaf_value, text_value};
use super::{FormatError, resolve_list_keys};
use crate::arena::NodeId;
use crate::tree::Tree;

/// A gNMI-style set: members to merge, plus paths to remove.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct GnmiRemediation {
    /// Members to merge, shaped like the source JSON config.
    pub update: Map<String, Value>,
    /// `xpath`-ish paths to delete.
    pub delete: Vec<String>,
}

/// Renders a remediation between [`from_json`](super::from_json) trees as gNMI sets.
///
/// Negated nodes become `xpath`-ish delete paths; everything else renders
/// into `update` via the JSON mapping. When `running` is given, deletions of
/// keyed list entries get `[key=value]` selectors (keys found via
/// `list_keys`); without it they fall back to bare leaf paths.
///
/// # Errors
///
/// Returns [`FormatError`] if a negated node is an XML attribute, which has no
/// gNMI path equivalent.
pub fn to_gnmi_json(
    remediation: &Tree,
    running: Option<&Tree>,
    list_keys: Option<&[String]>,
) -> Result<GnmiRemediation, FormatError> {
    let mut result = GnmiRemediation::default();
    let context = Context {
        negation_prefix: remediation.driver.negation_prefix.clone(),
        list_keys: resolve_list_keys(list_keys),
    };
    let running_root = running.map(|tree| (tree, tree.root));
    let mut update = Map::new();
    gnmi_into(
        remediation,
        remediation.root,
        &mut update,
        &[],
        running_root,
        &context,
        &mut result.delete,
    )?;
    result.update = update;
    Ok(result)
}

struct Context {
    negation_prefix: String,
    list_keys: Vec<String>,
}

type RunningRef<'a> = Option<(&'a Tree, NodeId)>;

fn gnmi_into(
    tree: &Tree,
    node_id: NodeId,
    update: &mut Map<String, Value>,
    path: &[String],
    running: RunningRef<'_>,
    context: &Context,
    delete: &mut Vec<String>,
) -> Result<(), FormatError> {
    for child_id in tree.arena[node_id].children.iter() {
        let text = Arc::clone(&tree.arena[child_id].text);
        if let Some(positive) = text.strip_prefix(context.negation_prefix.as_str()) {
            // A negated child is resolved against the parent's running node.
            delete.push(delete_path(path, positive, running, &context.list_keys)?);
            continue;
        }
        let (key, payload) = split_text(&text);
        if tree.arena[child_id].children.is_empty() {
            let value = payload.map_or_else(|| Value::Object(Map::new()), leaf_value);
            store_member(update, key, value, false);
            continue;
        }
        let running_child = running.and_then(|(running_tree, running_id)| {
            running_tree
                .get_child_by_text(running_id, &text)
                .map(|id| (running_tree, id))
        });
        let mut key_name: Option<String> = None;
        let segment = match payload {
            None => key.to_owned(),
            Some(raw) => {
                key_name = identity_key(tree, child_id, running_child, raw, &context.list_keys);
                format!(
                    "{key}[{}={}]",
                    key_name
                        .clone()
                        .unwrap_or_else(|| context.list_keys[0].clone()),
                    selector_value(raw)
                )
            }
        };
        let mut child_path = path.to_vec();
        child_path.push(segment);
        let mut child_update = Map::new();
        gnmi_into(
            tree,
            child_id,
            &mut child_update,
            &child_path,
            running_child,
            context,
            delete,
        )?;
        if child_update.is_empty() {
            // The branch contained only deletions.
            continue;
        }
        if let Some(name) = &key_name
            && !child_update.contains_key(name)
        {
            let mut keyed = Map::new();
            keyed.insert(name.clone(), leaf_value(payload.unwrap_or_default()));
            keyed.extend(child_update);
            child_update = keyed;
        }
        store_member(update, key, Value::Object(child_update), payload.is_some());
    }
    Ok(())
}

fn identity_key(
    tree: &Tree,
    entry_id: NodeId,
    running_entry: RunningRef<'_>,
    raw_value: &str,
    list_keys: &[String],
) -> Option<String> {
    matching_list_key(tree, entry_id, raw_value, list_keys).or_else(|| {
        running_entry.and_then(|(running_tree, running_id)| {
            matching_list_key(running_tree, running_id, raw_value, list_keys)
        })
    })
}

fn selector_value(raw: &str) -> String {
    text_value(raw).replace('\\', "\\\\").replace(']', "\\]")
}

fn delete_path(
    parent_path: &[String],
    positive_text: &str,
    running: RunningRef<'_>,
    list_keys: &[String],
) -> Result<String, FormatError> {
    let (key, payload) = split_text(positive_text);
    if key.starts_with('@') {
        return Err(FormatError::Invalid(format!(
            "Attribute changes cannot be expressed as gNMI delete paths: \
'{positive_text}'"
        )));
    }
    // A keyed list entry (branch in the running config) deletes by selector;
    // a scalar leaf deletes by its bare path (the value is dropped).
    let segment = match payload {
        Some(raw) => running_entry_key(running, positive_text, raw, list_keys).map_or_else(
            || key.to_owned(),
            |found| format!("{key}[{found}={}]", selector_value(raw)),
        ),
        None => key.to_owned(),
    };
    let mut segments = parent_path.to_vec();
    segments.push(segment);
    Ok(segments.join("/"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::driver::Driver;
    use crate::formats::from_json;
    use crate::models::Platform;

    fn remediate(running: &str, intended: &str) -> (Tree, Tree) {
        let driver = || Driver::for_platform(Platform::CiscoIos);
        let running_tree = from_json(driver(), running, None).expect("valid JSON");
        let intended_tree = from_json(driver(), intended, None).expect("valid JSON");
        let remediation = running_tree.config_to_get_to(&intended_tree).expect("diff");
        (running_tree, remediation)
    }

    #[test]
    fn changed_scalars_land_in_update() {
        let (running, remediation) = remediate(r#"{"hostname": "r1"}"#, r#"{"hostname": "r2"}"#);
        let result = to_gnmi_json(&remediation, Some(&running), None).expect("render");
        assert_eq!(result.update["hostname"], Value::String("r2".to_owned()));
        assert_eq!(result.delete, vec!["hostname".to_owned()]);
    }

    #[test]
    fn removed_scalars_become_delete_paths() {
        let (running, remediation) = remediate(
            r#"{"hostname": "r1", "mtu": 1500}"#,
            r#"{"hostname": "r1"}"#,
        );
        let result = to_gnmi_json(&remediation, Some(&running), None).expect("render");
        assert_eq!(result.delete, vec!["mtu".to_owned()]);
    }

    #[test]
    fn keyed_entries_get_selector_segments() {
        let (running, remediation) = remediate(
            r#"{"iface": [{"name": "Et1", "mtu": 1500}]}"#,
            r#"{"iface": [{"name": "Et1", "mtu": 9000}]}"#,
        );
        let result = to_gnmi_json(&remediation, Some(&running), None).expect("render");
        let entries = result.update["iface"].as_array().expect("array");
        assert_eq!(entries[0]["name"], Value::String("Et1".to_owned()));
        assert_eq!(entries[0]["mtu"], Value::from(9000));
    }

    #[test]
    fn removed_entries_delete_by_selector() {
        let (running, remediation) = remediate(
            r#"{"iface": [{"name": "Et1", "mtu": 1}, {"name": "Et2", "mtu": 1}]}"#,
            r#"{"iface": [{"name": "Et1", "mtu": 1}]}"#,
        );
        let result = to_gnmi_json(&remediation, Some(&running), None).expect("render");
        assert_eq!(result.delete, vec!["iface[name=Et2]".to_owned()]);
    }

    #[test]
    fn branches_holding_only_deletions_produce_no_update() {
        let (running, remediation) = remediate(
            r#"{"iface": [{"name": "Et1", "mtu": 1, "desc": "x"}]}"#,
            r#"{"iface": [{"name": "Et1", "mtu": 1}]}"#,
        );
        let result = to_gnmi_json(&remediation, Some(&running), None).expect("render");
        assert!(result.update.is_empty(), "{:?}", result.update);
        assert_eq!(result.delete, vec!["iface[name=Et1]/desc".to_owned()]);
    }

    #[test]
    fn selector_values_escape_brackets() {
        assert_eq!(selector_value(r#""a]b""#), r"a\]b");
        assert_eq!(selector_value(r#""a\\b""#), r"a\\b");
    }
}
