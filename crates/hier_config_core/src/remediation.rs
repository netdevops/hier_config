use crate::arena::NodeId;
use crate::tree::{Tree, TreeError};
use rustc_hash::{FxHashMap as HashMap, FxHashSet as HashSet};
use std::sync::Arc;

/// Computes the delta configuration needed to transition from `source` to `target`.
///
/// # Errors
///
/// Returns [`TreeError`] if the delta tree cannot be built, for example when a
/// remediation line cannot be inserted under its parent.
pub fn config_to_get_to(source: &Tree, target: &Tree) -> Result<Tree, TreeError> {
    let mut delta = Tree::new(source.driver.clone());
    config_to_get_to_into(source, target, &mut delta)?;
    Ok(delta)
}

/// Computes the delta configuration needed to transition from `source` to `target`, populating `delta`.
///
/// # Errors
///
/// Returns [`TreeError`] if a remediation line cannot be inserted into `delta`.
pub fn config_to_get_to_into(
    source: &Tree,
    target: &Tree,
    delta: &mut Tree,
) -> Result<(), TreeError> {
    let delta_root = delta.root;
    config_to_get_to_node(source, source.root, target, target.root, delta, delta_root)
}

fn config_to_get_to_node(
    source: &Tree,
    source_node: NodeId,
    target: &Tree,
    target_node: NodeId,
    delta: &mut Tree,
    delta_node: NodeId,
) -> Result<(), TreeError> {
    config_to_get_to_left(source, source_node, target, target_node, delta, delta_node)?;
    config_to_get_to_right(source, source_node, target, target_node, delta, delta_node)?;
    Ok(())
}

fn config_to_get_to_left(
    source: &Tree,
    source_node: NodeId,
    target: &Tree,
    target_node: NodeId,
    delta: &mut Tree,
    delta_node: NodeId,
) -> Result<(), TreeError> {
    let target_children: Vec<NodeId> = target.arena[target_node].children.iter().collect();

    for self_child_id in source.arena[source_node].children.iter() {
        let self_text = &source.arena[self_child_id].text;

        if target.arena[target_node].children.contains(self_text) {
            continue;
        }

        if source.is_idempotent_command(self_child_id, target, &target_children) {
            continue;
        }

        let negated_text = source.compute_negation(self_child_id);
        let negated_id = delta.add_child(delta_node, &negated_text, false, false)?;

        let child_count = source.arena[self_child_id].children.len();
        if child_count > 0 {
            delta.arena[negated_id]
                .comments_mut()
                .insert(format!("removes {} lines", child_count + 1));
        }
    }

    Ok(())
}

fn config_to_get_to_right(
    source: &Tree,
    source_node: NodeId,
    target: &Tree,
    target_node: NodeId,
    delta: &mut Tree,
    delta_node: NodeId,
) -> Result<(), TreeError> {
    for target_child_id in target.arena[target_node].children.iter() {
        let target_text = &target.arena[target_child_id].text;

        if let Some(self_child_id) = source.arena[source_node].children.get(target_text) {
            if source.use_sectional_overwrite(self_child_id) {
                overwrite_with(
                    source,
                    self_child_id,
                    target,
                    target_child_id,
                    delta,
                    delta_node,
                    true,
                )?;
                continue;
            }

            if source.use_sectional_overwrite_without_negation(self_child_id) {
                overwrite_with(
                    source,
                    self_child_id,
                    target,
                    target_child_id,
                    delta,
                    delta_node,
                    false,
                )?;
                continue;
            }

            // Create temporary child in delta to collect subtree changes
            let subtree_id = delta.add_child(delta_node, target_text, false, false)?;
            config_to_get_to_node(
                source,
                self_child_id,
                target,
                target_child_id,
                delta,
                subtree_id,
            )?;

            if delta.arena[subtree_id].children.is_empty() {
                delta.delete_child(subtree_id);
            }
        } else {
            // Target child is absent from source
            if delta.arena[delta_node].children.contains(target_text) {
                continue;
            }

            let new_item_id = delta.add_deep_copy_of(delta_node, target, target_child_id, false)?;
            delta.arena[new_item_id].new_in_config = true;
            for desc_id in delta.all_children(new_item_id) {
                delta.arena[desc_id].new_in_config = true;
            }
            if !delta.arena[new_item_id].children.is_empty() {
                delta.arena[new_item_id]
                    .comments_mut()
                    .insert("new section".to_string());
            }
        }
    }

    Ok(())
}

/// Replaces the children of `target_child_id` with those of `source_child_id`.
///
/// # Errors
///
/// Returns [`TreeError`] if either node id is not present in its tree, or if a
/// copied child cannot be inserted.
pub fn overwrite_with(
    source: &Tree,
    source_child_id: NodeId,
    target: &Tree,
    target_child_id: NodeId,
    delta: &mut Tree,
    delta_node: NodeId,
    negate: bool,
) -> Result<(), TreeError> {
    if !children_equal(source, source_child_id, target, target_child_id) {
        let self_text = &source.arena[source_child_id].text;

        if negate {
            let new_neg_text = source.compute_negation(source_child_id);
            let neg_id = if let Some(existing_id) = delta.arena[delta_node].children.get(self_text)
            {
                delta.set_text(existing_id, &new_neg_text);
                existing_id
            } else {
                delta.add_child(delta_node, &new_neg_text, false, false)?
            };
            delta.arena[neg_id]
                .comments_mut()
                .insert("dropping section".to_string());
        } else if let Some(existing_id) = delta.arena[delta_node].children.get(self_text) {
            delta.delete_child(existing_id);
        }

        let new_item_id = delta.add_deep_copy_of(delta_node, target, target_child_id, false)?;
        delta.arena[new_item_id]
            .comments_mut()
            .insert("re-create section".to_string());
    }
    Ok(())
}

/// Recursively compares whether the child hierarchies of two nodes are equivalent.
pub fn children_equal(tree_a: &Tree, a: NodeId, tree_b: &Tree, b: NodeId) -> bool {
    let sorted_a = tree_a.sorted_children(a);
    let sorted_b = tree_b.sorted_children(b);

    if sorted_a.len() != sorted_b.len() {
        return false;
    }

    for (child_a, child_b) in sorted_a.into_iter().zip(sorted_b) {
        let node_a = &tree_a.arena[child_a];
        let node_b = &tree_b.arena[child_b];

        if node_a.text != node_b.text
            || node_a.order_weight != node_b.order_weight
            || node_a.tags() != node_b.tags()
            || node_a.comments() != node_b.comments()
            || node_a.new_in_config != node_b.new_in_config
        {
            return false;
        }

        if !children_equal(tree_a, child_a, tree_b, child_b) {
            return false;
        }
    }

    true
}

/// Predicts the future configuration resulting from applying `config` to `source`.
///
/// # Errors
///
/// Returns [`TreeError`] if the predicted tree cannot be assembled.
pub fn future(source: &Tree, config: &Tree, prune_empty_branches: bool) -> Result<Tree, TreeError> {
    let mut future_config = Tree::new(source.driver.clone());
    let future_root = future_config.root;
    future_node(
        source,
        source.root,
        config,
        config.root,
        &mut future_config,
        future_root,
    )?;

    if prune_empty_branches {
        prune_emptied_branches(source, source.root, &mut future_config, future_root);
    }

    Ok(future_config)
}

fn future_pre(
    source: &Tree,
    source_node: NodeId,
    config: &Tree,
    config_node: NodeId,
) -> (HashSet<Arc<str>>, HashSet<Arc<str>>) {
    let mut negated_or_recursed = HashSet::default();
    let mut config_children_ignore = HashSet::default();

    for self_child_id in source.arena[source_node].children.iter() {
        let self_text = &source.arena[self_child_id].text;
        if let Some(negation_text) = source.negate_with(self_child_id)
            && let Some(config_child_id) = config.arena[config_node].children.get(&negation_text)
        {
            negated_or_recursed.insert(Arc::clone(self_text));
            config_children_ignore.insert(Arc::clone(&config.arena[config_child_id].text));
        }
    }

    (negated_or_recursed, config_children_ignore)
}

fn future_node(
    source: &Tree,
    source_node: NodeId,
    config: &Tree,
    config_node: NodeId,
    future_config: &mut Tree,
    future_node_id: NodeId,
) -> Result<(), TreeError> {
    let (mut negated_or_recursed, config_children_ignore) =
        future_pre(source, source_node, config, config_node);

    let source_children: Vec<NodeId> = source.arena[source_node].children.iter().collect();

    for config_child_id in config.arena[config_node].children.iter() {
        let config_text = &config.arena[config_child_id].text;

        if config_children_ignore.contains(&**config_text) {
            continue;
        }

        let is_negation = config_text.starts_with(&source.driver.negation_prefix);
        let text_without_neg = source.driver.text_without_negation(config_text);

        if config.use_sectional_overwrite(config_child_id)
            || config.use_sectional_overwrite_without_negation(config_child_id)
        {
            future_config.add_deep_copy_of(future_node_id, config, config_child_id, false)?;
        } else if is_negation
            && source.arena[source_node]
                .children
                .contains(text_without_neg)
        {
            negated_or_recursed.insert(Arc::from(text_without_neg));
        } else if let Some(self_child_id) =
            config.idempotent_for(config_child_id, source, &source_children)
        {
            future_config.add_deep_copy_of(future_node_id, config, config_child_id, false)?;
            negated_or_recursed.insert(Arc::clone(&source.arena[self_child_id].text));
        } else if is_negation
            && source.arena[source_node].children.iter().any(|id| {
                source.arena[id]
                    .text
                    .starts_with(&format!("{text_without_neg} "))
            })
        {
            for id in source.arena[source_node].children.iter() {
                if source.arena[id]
                    .text
                    .starts_with(&format!("{text_without_neg} "))
                {
                    negated_or_recursed.insert(Arc::clone(&source.arena[id].text));
                }
            }
        } else if let Some(self_child_id) = source.arena[source_node].children.get(config_text) {
            let future_child =
                future_config.add_shallow_copy_of(future_node_id, source, self_child_id, false)?;
            future_node(
                source,
                self_child_id,
                config,
                config_child_id,
                future_config,
                future_child,
            )?;
            negated_or_recursed.insert(Arc::clone(config_text));
        } else if is_negation {
            future_config.add_shallow_copy_of(future_node_id, config, config_child_id, false)?;
        } else if let Some(self_child_id) = source.arena[source_node]
            .children
            .get(&format!("{}{}", source.driver.negation_prefix, config_text))
        {
            negated_or_recursed.insert(Arc::clone(&source.arena[self_child_id].text));
        } else {
            future_config.add_deep_copy_of(future_node_id, config, config_child_id, false)?;
        }
    }

    for self_child_id in source.arena[source_node].children.iter() {
        let self_text = &source.arena[self_child_id].text;
        if negated_or_recursed.contains(&**self_text) {
            continue;
        }
        future_config.add_deep_copy_of(future_node_id, source, self_child_id, false)?;
    }

    Ok(())
}

fn prune_emptied_branches(
    source: &Tree,
    source_node: NodeId,
    future: &mut Tree,
    future_node_id: NodeId,
) {
    let children: Vec<NodeId> = future.arena[future_node_id].children.iter().collect();

    for child_id in children {
        let child_text = &future.arena[child_id].text;
        if let Some(src_child_id) = source.arena[source_node].children.get(child_text) {
            prune_emptied_branches(source, src_child_id, future, child_id);
            if future.arena[child_id].children.is_empty()
                && !source.arena[src_child_id].children.is_empty()
            {
                future.delete_child(child_id);
            }
        }
    }
}

/// Strips leading sequence number from ACL entry line text.
pub fn strip_acl_sequence_number(text: &str) -> String {
    let mut words: Vec<&str> = text.split_whitespace().collect();
    if !words.is_empty() && words[0].chars().all(|c| c.is_ascii_digit()) {
        words.remove(0);
    }
    words.join(" ")
}

/// Computes the difference configuration of `source` not present in `target`.
///
/// # Errors
///
/// Returns [`TreeError`] if the difference tree cannot be assembled.
pub fn difference(source: &Tree, target: &Tree) -> Result<Tree, TreeError> {
    let mut delta = Tree::new(source.driver.clone());
    let delta_root = delta.root;
    let mut trees = DiffTrees {
        source,
        target,
        delta: &mut delta,
    };
    difference_node(
        &mut trees,
        source.root,
        target.root,
        delta_root,
        None,
        false,
    )?;
    Ok(delta)
}

struct DiffTrees<'a> {
    source: &'a Tree,
    target: &'a Tree,
    delta: &'a mut Tree,
}

fn difference_node(
    trees: &mut DiffTrees<'_>,
    source_node: NodeId,
    target_node: NodeId,
    delta_node: NodeId,
    target_acl_children: Option<&HashMap<String, NodeId>>,
    in_acl: bool,
) -> Result<(), TreeError> {
    let acl_prefixes = ["ip access-list ", "ipv4 access-list ", "ipv6 access-list "];

    for self_child_id in trees.source.arena[source_node].children.iter() {
        let self_text = &trees.source.arena[self_child_id].text;

        if self_text.starts_with(&trees.source.driver.negation_prefix)
            || self_text.starts_with("default ")
        {
            continue;
        }

        let target_child = if in_acl {
            let stripped = strip_acl_sequence_number(self_text);
            target_acl_children.and_then(|map| map.get(&stripped).copied())
        } else {
            trees.target.arena[target_node].children.get(self_text)
        };

        if let Some(target_child_id) = target_child {
            let delta_child = trees.delta.add_child(delta_node, self_text, false, false)?;

            if acl_prefixes
                .iter()
                .any(|prefix| self_text.starts_with(prefix))
            {
                let mut acl_map = HashMap::default();
                for c_id in trees.target.arena[target_child_id].children.iter() {
                    let stripped = strip_acl_sequence_number(&trees.target.arena[c_id].text);
                    acl_map.insert(stripped, c_id);
                }

                difference_node(
                    trees,
                    self_child_id,
                    target_child_id,
                    delta_child,
                    Some(&acl_map),
                    true,
                )?;
            } else {
                difference_node(
                    trees,
                    self_child_id,
                    target_child_id,
                    delta_child,
                    None,
                    false,
                )?;
            }

            if trees.delta.arena[delta_child].children.is_empty() {
                trees.delta.delete_child(delta_child);
            }
        } else {
            trees
                .delta
                .add_deep_copy_of(delta_node, trees.source, self_child_id, false)?;
        }
    }

    Ok(())
}

/// Computes unified diff comparison lines between `source` and `target`.
pub fn unified_diff(source: &Tree, target: &Tree) -> Vec<String> {
    unified_diff_node(source, source.root, target, target.root)
}

fn unified_diff_node(
    source: &Tree,
    source_node: NodeId,
    target: &Tree,
    target_node: NodeId,
) -> Vec<String> {
    let mut lines = Vec::new();

    // Elements in source
    for self_child in source.arena[source_node].children.iter() {
        let self_text = &source.arena[self_child].text;
        if let Some(target_child) = target.arena[target_node].children.get(self_text) {
            let child_diff = unified_diff_node(source, self_child, target, target_child);
            if !child_diff.is_empty() {
                lines.push(format!("{}{}", source.indentation(self_child), self_text));
                lines.extend(child_diff);
            }
        } else {
            lines.push(format!("{}- {}", source.indentation(self_child), self_text));
            for desc_id in source.all_children_sorted(self_child) {
                lines.push(format!(
                    "{}- {}",
                    source.indentation(desc_id),
                    source.arena[desc_id].text
                ));
            }
        }
    }

    // Elements in target missing from source
    for target_child in target.arena[target_node].children.iter() {
        let target_text = &target.arena[target_child].text;
        if !source.arena[source_node].children.contains(target_text) {
            lines.push(format!(
                "{}+ {}",
                target.indentation(target_child),
                target_text
            ));
            for desc_id in target.all_children_sorted(target_child) {
                lines.push(format!(
                    "{}+ {}",
                    target.indentation(desc_id),
                    target.arena[desc_id].text
                ));
            }
        }
    }

    lines
}
