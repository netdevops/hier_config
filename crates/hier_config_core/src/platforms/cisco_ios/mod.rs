use crate::platforms::functions::expand_range;
use crate::platforms::post_load_enabled;
use crate::tree::Tree;

pub mod view;

pub const RULES_JSON: &str = include_str!("rules.json");

pub fn run_post_load(tree: &mut Tree) {
    if post_load_enabled(tree, "remove_ipv6_acl_sequence_numbers") {
        rm_ipv6_acl_sequence_numbers(tree);
    }
    if post_load_enabled(tree, "remove_ipv4_acl_remarks") {
        remove_ipv4_acl_remarks(tree);
    }
    if post_load_enabled(tree, "add_acl_sequence_numbers") {
        add_acl_sequence_numbers(tree);
    }
    if post_load_enabled(tree, "split_vlan_id_lists") {
        split_vlan_id_lists(tree);
    }
}

pub fn rm_ipv6_acl_sequence_numbers(tree: &mut Tree) {
    let root_children = tree.arena[tree.root].children.as_slice().to_vec();
    for acl_id in root_children {
        if tree.arena[acl_id].text.starts_with("ipv6 access-list ") {
            let entries = tree.arena[acl_id].children.as_slice().to_vec();
            for entry_id in entries {
                let text = &tree.arena[entry_id].text;
                if text.starts_with("sequence ") {
                    let words: Vec<&str> = text.split_whitespace().collect();
                    if words.len() >= 3 {
                        let new_text = words[2..].join(" ");
                        tree.set_text(entry_id, &new_text);
                    }
                }
            }
        }
    }
}

pub fn remove_ipv4_acl_remarks(tree: &mut Tree) {
    let root_children = tree.arena[tree.root].children.as_slice().to_vec();
    for acl_id in root_children {
        if tree.arena[acl_id].text.starts_with("ip access-list ") {
            let entries = tree.arena[acl_id].children.as_slice().to_vec();
            for entry_id in entries {
                if tree.arena[entry_id].text.starts_with("remark ")
                    || tree.arena[entry_id].text.as_ref() == "remark"
                {
                    tree.delete_child(entry_id);
                }
            }
        }
    }
}

pub fn add_acl_sequence_numbers(tree: &mut Tree) {
    let root_children = tree.arena[tree.root].children.as_slice().to_vec();
    for child_id in root_children {
        if tree.arena[child_id].text.starts_with("ip access-list") {
            let mut sequence_number = 10;
            let entries = tree.arena[child_id].children.as_slice().to_vec();
            for sub_id in entries {
                let text = &tree.arena[sub_id].text;
                if text.starts_with("permit ")
                    || text.starts_with("deny ")
                    || &**text == "permit"
                    || &**text == "deny"
                {
                    let new_text = format!("{sequence_number} {text}");
                    tree.set_text(sub_id, &new_text);
                    sequence_number += 10;
                }
            }
        }
    }
}

/// Splits comma-separated or hyphenated VLAN lists under `vlan <list>` nodes into individual nodes.
///
/// # Panics
///
/// Panics if the internal static regular expression fails to compile.
pub fn split_vlan_id_lists(tree: &mut Tree) {
    let vlan_re = crate::regex_cache::regex(r"^vlan \d[\d,\-]*$").expect("static pattern is valid");
    let root_children = tree.arena[tree.root].children.as_slice().to_vec();
    for vlan_id in root_children {
        let text = &tree.arena[vlan_id].text;
        if vlan_re.is_match(text)
            && tree.arena[vlan_id].children.is_empty()
            && let Some((_, spec)) = text.split_once(' ')
            && (spec.contains(',') || spec.contains('-'))
            && let Ok(vlans) = expand_range(spec)
            && !vlans.is_empty()
        {
            for v in vlans {
                let line = format!("vlan {v}");
                let _ = tree.add_child(tree.root, &line, true, true);
            }
            tree.delete_child(vlan_id);
        }
    }
}
