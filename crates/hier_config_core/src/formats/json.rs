//! JSON (e.g. `OpenConfig`) documents mapped onto a config tree.

use serde_json::{Map, Value};

use super::value::{dumps, dumps_indented, leaf_value};
use super::{FormatError, resolve_list_keys};
use crate::arena::NodeId;
use crate::driver::Driver;
use crate::tree::Tree;

/// Builds a config tree from JSON text.
///
/// # Errors
///
/// Returns [`FormatError`] if `data` is not a valid JSON object, if a key is
/// unusable as node text, or if an array entry cannot be identified.
pub fn from_json(
    driver: Driver,
    data: &str,
    list_keys: Option<&[String]>,
) -> Result<Tree, FormatError> {
    let parsed: Value = serde_json::from_str(data)
        .map_err(|error| FormatError::Invalid(format!("The config is not valid JSON: {error}")))?;
    from_json_value(driver, &parsed, list_keys)
}

/// Builds a config tree from an already-parsed JSON value.
///
/// # Errors
///
/// Returns [`FormatError`] if `data` is not an object, if a key is unusable as
/// node text, or if an array entry cannot be identified.
pub fn from_json_value(
    driver: Driver,
    data: &Value,
    list_keys: Option<&[String]>,
) -> Result<Tree, FormatError> {
    let Value::Object(members) = data else {
        return Err(FormatError::Invalid(
            "The top-level JSON value must be an object".to_owned(),
        ));
    };
    let keys = resolve_list_keys(list_keys);
    let mut tree = Tree::new(driver);
    let root = tree.root;
    json_into(&mut tree, root, members, &keys)?;
    Ok(tree)
}

/// Renders a tree built by [`from_json`] back to JSON text.
///
/// `indent` of `None` produces the compact single-line form.
pub fn to_json(tree: &Tree, indent: Option<usize>) -> String {
    dumps_indented(&Value::Object(node_to_object(tree, tree.root)), indent)
}

fn json_key(key: &str) -> Result<&str, FormatError> {
    if key.is_empty() || key.chars().any(char::is_whitespace) {
        return Err(FormatError::Invalid(format!(
            "Unsupported JSON key: '{key}' (keys must be non-empty strings \
without whitespace)"
        )));
    }
    Ok(key)
}

fn json_into(
    tree: &mut Tree,
    parent: NodeId,
    mapping: &Map<String, Value>,
    list_keys: &[String],
) -> Result<(), FormatError> {
    for (raw_key, value) in mapping {
        let key = json_key(raw_key)?;
        match value {
            Value::Object(members) => {
                let branch = tree.add_child(parent, key, true, false)?;
                json_into(tree, branch, members, list_keys)?;
            }
            Value::Array(items) => json_list_into(tree, parent, key, items, list_keys)?,
            scalar => {
                tree.add_child(parent, &format!("{key} {}", dumps(scalar)), true, false)?;
            }
        }
    }
    Ok(())
}

fn json_list_into(
    tree: &mut Tree,
    parent: NodeId,
    key: &str,
    items: &[Value],
    list_keys: &[String],
) -> Result<(), FormatError> {
    for item in items {
        match item {
            Value::Object(members) => {
                let identity_key = list_keys
                    .iter()
                    .find(|candidate| members.contains_key(candidate.as_str()))
                    .ok_or_else(|| {
                        FormatError::Invalid(format!(
                            "List entries under '{key}' need one of {} to identify \
them; pass list_keys= to name the identifying member",
                            format_keys(list_keys)
                        ))
                    })?;
                let identity = dumps(&members[identity_key]);
                let entry = tree.add_child(parent, &format!("{key} {identity}"), true, false)?;
                json_into(tree, entry, members, list_keys)?;
            }
            Value::Array(_) => {
                return Err(FormatError::Invalid(format!(
                    "Nested JSON arrays are not supported (under '{key}')"
                )));
            }
            scalar => {
                tree.add_child(parent, &format!("{key} {}", dumps(scalar)), true, false)?;
            }
        }
    }
    Ok(())
}

/// Renders key names the way a Python tuple repr would, for message parity.
pub(crate) fn format_keys(list_keys: &[String]) -> String {
    let mut rendered = String::from("(");
    for (position, key) in list_keys.iter().enumerate() {
        if position > 0 {
            rendered.push_str(", ");
        }
        rendered.push('\'');
        rendered.push_str(key);
        rendered.push('\'');
    }
    if list_keys.len() == 1 {
        rendered.push(',');
    }
    rendered.push(')');
    rendered
}

/// Adds `value` under `key`, collecting repeats into an array.
pub(crate) fn store_member(
    result: &mut Map<String, Value>,
    key: &str,
    value: Value,
    force_list: bool,
) {
    match result.get_mut(key) {
        Some(Value::Array(existing)) => existing.push(value),
        Some(slot) => {
            let existing = slot.take();
            *slot = Value::Array(vec![existing, value]);
        }
        None if force_list => {
            result.insert(key.to_owned(), Value::Array(vec![value]));
        }
        None => {
            result.insert(key.to_owned(), value);
        }
    }
}

/// Splits node text into its key and optional value payload.
pub(crate) fn split_text(text: &str) -> (&str, Option<&str>) {
    text.split_once(char::is_whitespace)
        .map_or((text, None), |(key, rest)| {
            (key, Some(rest.trim_start_matches(char::is_whitespace)))
        })
}

fn node_to_object(tree: &Tree, node_id: NodeId) -> Map<String, Value> {
    let mut result = Map::new();
    for child_id in tree.arena[node_id].children.iter() {
        let (key, payload) = split_text(&tree.arena[child_id].text);
        if tree.arena[child_id].children.is_empty() {
            match payload {
                Some(raw) => store_member(&mut result, key, leaf_value(raw), false),
                // `from_json` only emits a single-word childless node for an
                // empty object; scalar leaves always carry a value word.
                None => store_member(&mut result, key, Value::Object(Map::new()), false),
            }
        } else {
            // A multi-word branch is a keyed list entry, so it groups.
            store_member(
                &mut result,
                key,
                Value::Object(node_to_object(tree, child_id)),
                payload.is_some(),
            );
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::Platform;

    fn tree_from(source: &str) -> Tree {
        from_json(Driver::for_platform(Platform::CiscoIos), source, None).expect("valid JSON")
    }

    #[test]
    fn scalars_become_value_bearing_leaves() {
        let tree = tree_from(r#"{"mtu": 1500, "up": true, "name": "Et1"}"#);
        assert_eq!(
            tree.dump_simple(false),
            vec!["mtu 1500", "up true", "name \"Et1\""]
        );
    }

    #[test]
    fn nested_objects_become_branches() {
        let tree = tree_from(r#"{"interface": {"mtu": 1500}}"#);
        assert_eq!(tree.dump_simple(false), vec!["interface", "  mtu 1500"]);
    }

    #[test]
    fn keyed_list_entries_carry_their_identity() {
        let tree = tree_from(r#"{"interface": [{"name": "Et1", "mtu": 1500}]}"#);
        assert_eq!(
            tree.dump_simple(false),
            vec!["interface \"Et1\"", "  name \"Et1\"", "  mtu 1500"]
        );
    }

    #[test]
    fn unidentifiable_list_entries_are_rejected() {
        let error = from_json(
            Driver::for_platform(Platform::CiscoIos),
            r#"{"interface": [{"mtu": 1500}]}"#,
            None,
        )
        .expect_err("no identity member");
        assert!(
            error.to_string().contains("('name', 'id')"),
            "{}",
            error.to_string()
        );
    }

    #[test]
    fn nested_arrays_are_rejected() {
        let error = from_json(
            Driver::for_platform(Platform::CiscoIos),
            r#"{"a": [[1]]}"#,
            None,
        )
        .expect_err("nested array");
        assert!(
            error.to_string().contains("Nested JSON arrays"),
            "{}",
            error.to_string()
        );
    }

    #[test]
    fn keys_with_whitespace_are_rejected() {
        let error = from_json(
            Driver::for_platform(Platform::CiscoIos),
            r#"{"a b": 1}"#,
            None,
        )
        .expect_err("whitespace key");
        assert!(
            error.to_string().contains("Unsupported JSON key"),
            "{}",
            error.to_string()
        );
    }

    #[test]
    fn non_object_roots_are_rejected() {
        let error = from_json(Driver::for_platform(Platform::CiscoIos), "[1]", None)
            .expect_err("array root");
        assert_eq!(
            error.to_string(),
            "The top-level JSON value must be an object"
        );
    }

    #[test]
    fn round_trip_preserves_the_document() {
        let source = r#"{"interface": [{"name": "Et1", "mtu": 1500}], "up": true}"#;
        let tree = tree_from(source);
        assert_eq!(to_json(&tree, None), source);
    }

    #[test]
    fn empty_objects_survive_the_round_trip() {
        let tree = tree_from(r#"{"a": {}}"#);
        assert_eq!(to_json(&tree, None), r#"{"a": {}}"#);
    }

    #[test]
    fn single_key_tuples_keep_the_python_trailing_comma() {
        assert_eq!(format_keys(&["id".to_owned()]), "('id',)");
    }
}
