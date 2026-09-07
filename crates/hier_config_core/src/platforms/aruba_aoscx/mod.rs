use crate::platforms::functions::expand_range;
use crate::platforms::post_load_enabled;
use crate::tree::Tree;
use std::sync::Arc;

pub const RULES_JSON: &str = include_str!("rules.json");

pub fn run_post_load(tree: &mut Tree) {
    if post_load_enabled(tree, "split_vlan_id_lists") {
        crate::platforms::cisco_ios::split_vlan_id_lists(tree);
    }
    if post_load_enabled(tree, "split_interface_vlan_trunk_allowed") {
        split_interface_vlan_trunk_allowed(tree);
    }
}

fn split_interface_vlan_trunk_allowed(tree: &mut Tree) {
    let root_children = tree.arena[tree.root].children.as_slice().to_vec();
    for iface_id in root_children {
        if tree.arena[iface_id].text.starts_with("interface ") {
            let entries = tree.arena[iface_id].children.as_slice().to_vec();
            for entry_id in entries {
                let text = Arc::<str>::clone(&tree.arena[entry_id].text);
                if text.starts_with("vlan trunk allowed ") {
                    let words: Vec<&str> = text.split_whitespace().collect();
                    if words.len() == 4 {
                        let spec = words[3];
                        if spec != "all"
                            && spec != "none"
                            && (spec.contains(',') || spec.contains('-'))
                            && let Ok(vlans) = expand_range(spec)
                            && !vlans.is_empty()
                        {
                            for vlan_id in vlans {
                                let line = format!("vlan trunk allowed {vlan_id}");
                                let _ = tree.add_child(iface_id, &line, true, true);
                            }
                            tree.delete_child(entry_id);
                        }
                    }
                }
            }
        }
    }
}
