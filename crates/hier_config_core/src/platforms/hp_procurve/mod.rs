use crate::platforms::functions::{MAX_RANGE_SPAN, MAX_RANGE_TOTAL};
use crate::platforms::post_load_enabled;
use crate::tree::Tree;
use rustc_hash::FxHashSet as HashSet;
use std::sync::Arc;

pub const RULES_JSON: &str = include_str!("rules.json");

pub fn run_post_load(tree: &mut Tree) {
    if post_load_enabled(tree, "fixup_hp_procurve_aaa_port_access") {
        fixup_hp_procurve_aaa_port_access_fixup(tree);
    }
    if post_load_enabled(tree, "fixup_hp_procurve_device_profile") {
        fixup_hp_procurve_device_profile(tree);
    }
    if post_load_enabled(tree, "fixup_hp_procurve_vlan") {
        fixup_hp_procurve_vlan(tree);
    }
}

/// Expands HP `ProCurve` interface ranges like "1/2-5,2/22-45" or "Trk1-Trk4".
///
/// # Errors
///
/// Returns a static message if a segment does not match a supported
/// `ProCurve` interface-range form.
pub fn hp_procurve_expand_range(interface_range_str: &str) -> Result<Vec<String>, &'static str> {
    let mut interfaces = Vec::new();
    for segment in interface_range_str.split(',') {
        hp_procurve_expand_range_segment(segment, &mut interfaces)?;
    }
    let unique: HashSet<_> = interfaces.iter().collect();
    if unique.len() != interfaces.len() {
        return Err("duplicate interface in range");
    }
    Ok(interfaces)
}

fn hp_procurve_expand_range_segment(
    segment: &str,
    out: &mut Vec<String>,
) -> Result<(), &'static str> {
    let start_stop: Vec<&str> = segment.split('-').collect();
    if start_stop.len() != 2 {
        if out.len() as u64 >= MAX_RANGE_TOTAL {
            return Err("port range too large");
        }
        out.push(segment.to_string());
        return Ok(());
    }

    let first = start_stop[0];
    let second = start_stop[1];

    let (stack_member, start_port_prefix, start_port_number, end_port_number) =
        if let Some(stripped) = first.strip_prefix("Trk") {
            let end_stripped = second.strip_prefix("Trk").unwrap_or(second);
            (
                "Trk".to_string(),
                String::new(),
                stripped.to_string(),
                end_stripped.to_string(),
            )
        } else if let Some((stack, port_part)) = first.split_once('/') {
            let stack_str = format!("{stack}/");
            let end_port_part = second.split('/').next_back().unwrap_or(second);

            let mut prefix = String::new();
            let mut start_num = port_part.to_string();
            let mut end_num = end_port_part.to_string();

            for letter in ["A", "B", "C", "D"] {
                if start_num.starts_with(letter) {
                    prefix = letter.to_string();
                    start_num = start_num.strip_prefix(letter).unwrap().to_string();
                    if !end_num.starts_with(letter) {
                        return Err("end port does not start with same letter");
                    }
                    end_num = end_num.strip_prefix(letter).unwrap().to_string();
                    break;
                }
            }
            (stack_str, prefix, start_num, end_num)
        } else {
            (
                String::new(),
                String::new(),
                first.to_string(),
                second.to_string(),
            )
        };

    let start_int: u32 = start_port_number
        .parse()
        .map_err(|_| "parse start port error")?;
    let end_int: u32 = end_port_number
        .parse()
        .map_err(|_| "parse end port error")?;
    if end_int < start_int {
        return Err("reversed port range");
    }
    if end_int - start_int >= MAX_RANGE_SPAN {
        return Err("port range too large");
    }
    if out.len() as u64 + u64::from(end_int - start_int) + 1 > MAX_RANGE_TOTAL {
        return Err("port range too large");
    }

    for port in start_int..=end_int {
        out.push(format!("{stack_member}{start_port_prefix}{port}"));
    }
    Ok(())
}

fn fixup_hp_procurve_aaa_port_access_fixup(tree: &mut Tree) {
    let re =
        crate::regex_cache::regex(r"^aaa port-access (authenticator|mac-based) [0-9,/\-Ttrk]+$")
            .expect("static pattern is valid");
    let root_children = tree.arena[tree.root].children.as_slice().to_vec();
    for child_id in root_children {
        let text = Arc::<str>::clone(&tree.arena[child_id].text);
        if re.is_match(&text) {
            let words: Vec<&str> = text.split_whitespace().collect();
            if words.len() >= 4
                && (words[3].contains('-') || words[3].contains(','))
                && let Ok(interfaces) = hp_procurve_expand_range(words[3])
            {
                for iface in interfaces {
                    let line = format!("aaa port-access {} {}", words[2], iface);
                    let _ = tree.add_child(tree.root, &line, true, false);
                }
                tree.delete_child(child_id);
            }
        }
    }
}

fn fixup_hp_procurve_device_profile(tree: &mut Tree) {
    let root_children = tree.arena[tree.root].children.as_slice().to_vec();
    for dp_id in root_children {
        if tree.arena[dp_id].text.starts_with("device-profile name ") {
            let dp_children = tree.arena[dp_id].children.as_slice().to_vec();
            for sub_id in dp_children {
                let text = Arc::<str>::clone(&tree.arena[sub_id].text);
                if text.starts_with("tagged-vlan ") {
                    let words: Vec<&str> = text.split_whitespace().collect();
                    if words.len() >= 2
                        && (words[1].contains('-') || words[1].contains(','))
                        && let Ok(mut vlans) = hp_procurve_expand_range(words[1])
                    {
                        vlans.sort();
                        for vlan in vlans {
                            let line = format!("tagged-vlan {vlan}");
                            let _ = tree.add_child(dp_id, &line, true, false);
                        }
                        tree.delete_child(sub_id);
                    }
                }
            }
        }
    }
}

fn fixup_hp_procurve_vlan(tree: &mut Tree) {
    let root_children = tree.arena[tree.root].children.as_slice().to_vec();
    for vlan_id in root_children {
        let vlan_text = Arc::<str>::clone(&tree.arena[vlan_id].text);
        if vlan_text.starts_with("vlan ") {
            let words: Vec<&str> = vlan_text.split_whitespace().collect();
            if words.len() < 2 {
                continue;
            }
            let vlan_num = words[1];

            // untagged
            let sub_children = tree.arena[vlan_id].children.as_slice().to_vec();
            for sub_id in sub_children {
                if !tree.arena.contains(sub_id) {
                    continue;
                }
                let text = Arc::<str>::clone(&tree.arena[sub_id].text);
                if text.starts_with("untagged ") {
                    let u_words: Vec<&str> = text.split_whitespace().collect();
                    if u_words.len() >= 2
                        && let Ok(mut ifaces) = hp_procurve_expand_range(u_words[1])
                    {
                        ifaces.sort();
                        for iface in ifaces {
                            let _ = tree.add_children_deep(
                                tree.root,
                                &[
                                    &format!("interface {iface}"),
                                    &format!("untagged vlan {vlan_num}"),
                                ],
                            );
                        }
                        tree.delete_child(sub_id);
                    }
                } else if text.starts_with("tagged ") {
                    let t_words: Vec<&str> = text.split_whitespace().collect();
                    if t_words.len() >= 2
                        && let Ok(mut ifaces) = hp_procurve_expand_range(t_words[1])
                    {
                        ifaces.sort();
                        for iface in ifaces {
                            let _ = tree.add_children_deep(
                                tree.root,
                                &[
                                    &format!("interface {iface}"),
                                    &format!("tagged vlan {vlan_num}"),
                                ],
                            );
                        }
                        tree.delete_child(sub_id);
                    }
                } else if text.starts_with("no untagged ") {
                    tree.delete_child(sub_id);
                }
            }
        }
    }
}
