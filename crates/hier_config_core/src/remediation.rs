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
    RemediationContext::new(source, target, delta).compute()
}

/// Context managing the computation of remediation changes between a source and target tree into a delta tree.
#[derive(Debug)]
pub struct RemediationContext<'a> {
    pub source: &'a Tree,
    pub target: &'a Tree,
    pub delta: &'a mut Tree,
}

impl<'a> RemediationContext<'a> {
    /// Creates a new remediation context.
    pub const fn new(source: &'a Tree, target: &'a Tree, delta: &'a mut Tree) -> Self {
        Self {
            source,
            target,
            delta,
        }
    }

    /// Computes the delta from source root to target root into the delta root.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if constructing the remediation tree fails.
    pub fn compute(&mut self) -> Result<(), TreeError> {
        let delta_root = self.delta.root;
        self.compute_node(self.source.root, self.target.root, delta_root)
    }

    fn compute_node(
        &mut self,
        source_node: NodeId,
        target_node: NodeId,
        delta_node: NodeId,
    ) -> Result<(), TreeError> {
        self.compute_left(source_node, target_node, delta_node)?;
        self.compute_right(source_node, target_node, delta_node)?;
        Ok(())
    }

    fn compute_left(
        &mut self,
        source_node: NodeId,
        target_node: NodeId,
        delta_node: NodeId,
    ) -> Result<(), TreeError> {
        let target_children: Vec<NodeId> = self.target.arena[target_node].children.iter().collect();

        for self_child_id in self.source.arena[source_node].children.iter() {
            let self_text = &self.source.arena[self_child_id].text;

            if self.target.arena[target_node].children.contains(self_text) {
                continue;
            }

            if self
                .source
                .is_idempotent_command(self_child_id, self.target, &target_children)
            {
                continue;
            }

            let negated_text = self.source.compute_negation(self_child_id);
            let negated_id = self
                .delta
                .add_child(delta_node, &negated_text, false, false)?;

            let child_count = self.source.arena[self_child_id].children.len();
            if child_count > 0 {
                self.delta.arena[negated_id]
                    .comments_mut()
                    .insert(format!("removes {} lines", child_count + 1));
            }
        }

        Ok(())
    }

    fn compute_right(
        &mut self,
        source_node: NodeId,
        target_node: NodeId,
        delta_node: NodeId,
    ) -> Result<(), TreeError> {
        for target_child_id in self.target.arena[target_node].children.iter() {
            let target_text = &self.target.arena[target_child_id].text;

            if let Some(self_child_id) = self.source.arena[source_node].children.get(target_text) {
                if self.source.use_sectional_overwrite(self_child_id) {
                    self.overwrite_with(self_child_id, target_child_id, delta_node, true)?;
                    continue;
                }

                if self
                    .source
                    .use_sectional_overwrite_without_negation(self_child_id)
                {
                    self.overwrite_with(self_child_id, target_child_id, delta_node, false)?;
                    continue;
                }

                // Create temporary child in delta to collect subtree changes
                let subtree_id = self
                    .delta
                    .add_child(delta_node, target_text, false, false)?;
                self.compute_node(self_child_id, target_child_id, subtree_id)?;

                if self.delta.arena[subtree_id].children.is_empty() {
                    self.delta.delete_child(subtree_id);
                }
            } else {
                // Target child is absent from source
                if self.delta.arena[delta_node].children.contains(target_text) {
                    continue;
                }

                let new_item_id =
                    self.delta
                        .add_deep_copy_of(delta_node, self.target, target_child_id, false)?;
                self.delta.arena[new_item_id].new_in_config = true;
                for desc_id in self.delta.all_children(new_item_id) {
                    self.delta.arena[desc_id].new_in_config = true;
                }
                if !self.delta.arena[new_item_id].children.is_empty() {
                    self.delta.arena[new_item_id]
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
    /// Returns [`TreeError`] if modifying the delta tree fails.
    pub fn overwrite_with(
        &mut self,
        source_child_id: NodeId,
        target_child_id: NodeId,
        delta_node: NodeId,
        negate: bool,
    ) -> Result<(), TreeError> {
        if !children_equal(self.source, source_child_id, self.target, target_child_id) {
            let self_text = &self.source.arena[source_child_id].text;

            if negate {
                let new_neg_text = self.source.compute_negation(source_child_id);
                let neg_id = if let Some(existing_id) =
                    self.delta.arena[delta_node].children.get(self_text)
                {
                    self.delta.set_text(existing_id, &new_neg_text);
                    existing_id
                } else {
                    self.delta
                        .add_child(delta_node, &new_neg_text, false, false)?
                };
                self.delta.arena[neg_id]
                    .comments_mut()
                    .insert("dropping section".to_string());
            } else if let Some(existing_id) = self.delta.arena[delta_node].children.get(self_text) {
                self.delta.delete_child(existing_id);
            }

            let new_item_id =
                self.delta
                    .add_deep_copy_of(delta_node, self.target, target_child_id, false)?;
            self.delta.arena[new_item_id]
                .comments_mut()
                .insert("re-create section".to_string());
        }
        Ok(())
    }
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
    RemediationContext::new(source, target, delta).overwrite_with(
        source_child_id,
        target_child_id,
        delta_node,
        negate,
    )
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
    let (future_config, _) = future_with_report(source, config, prune_empty_branches)?;
    Ok(future_config)
}

/// How `future()` resolved the change's negations (#285).
///
/// The node ids reference the returned future config tree, so callers can
/// resolve them back to nodes for surrounding context.
#[derive(Debug, Default, Clone)]
pub struct FutureReport {
    /// Kept negation lines whose positive form matched nothing in the source
    /// config -- the change did not apply cleanly.
    pub unresolved_negations: Vec<NodeId>,
    /// Negation lines that persisted by replacing an idempotency-tracked
    /// counterpart (e.g. IOS `no logging console`).
    pub idempotency_replacements: Vec<NodeId>,
}

/// Like [`future`], but also reports how negations resolved.
///
/// # Errors
///
/// Returns [`TreeError`] if the projected tree cannot be built.
pub fn future_with_report(
    source: &Tree,
    config: &Tree,
    prune_empty_branches: bool,
) -> Result<(Tree, FutureReport), TreeError> {
    let mut future_config = Tree::new(source.driver.clone());
    let mut report = FutureReport::default();
    {
        let mut ctx = FutureContext::new(source, config, &mut future_config, &mut report);
        ctx.compute()?;
        if prune_empty_branches {
            let future_root = ctx.future_config.root;
            ctx.prune_emptied_branches(source.root, future_root);
        }
    }
    Ok((future_config, report))
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

/// Context managing the projection of configuration changes onto a source tree and tracking negation resolution.
#[derive(Debug)]
pub struct FutureContext<'a> {
    pub source: &'a Tree,
    pub config: &'a Tree,
    pub future_config: &'a mut Tree,
    pub report: &'a mut FutureReport,
}

impl<'a> FutureContext<'a> {
    /// Creates a new future projection context.
    pub const fn new(
        source: &'a Tree,
        config: &'a Tree,
        future_config: &'a mut Tree,
        report: &'a mut FutureReport,
    ) -> Self {
        Self {
            source,
            config,
            future_config,
            report,
        }
    }

    /// Projects the configuration changes from `config` onto `source`.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if modifying the projected tree fails.
    pub fn compute(&mut self) -> Result<(), TreeError> {
        let future_root = self.future_config.root;
        self.compute_node(self.source.root, self.config.root, future_root)
    }

    fn compute_node(
        &mut self,
        source_node: NodeId,
        config_node: NodeId,
        future_node_id: NodeId,
    ) -> Result<(), TreeError> {
        let (mut negated_or_recursed, config_children_ignore) =
            future_pre(self.source, source_node, self.config, config_node);

        let source_children: Vec<NodeId> = self.source.arena[source_node].children.iter().collect();

        for config_child_id in self.config.arena[config_node].children.iter() {
            let config_text = &self.config.arena[config_child_id].text;

            if config_children_ignore.contains(&**config_text) {
                continue;
            }

            let is_negation = config_text.starts_with(&self.source.driver.negation_prefix);
            let text_without_neg = self.source.driver.text_without_negation(config_text);

            if self.config.use_sectional_overwrite(config_child_id)
                || self
                    .config
                    .use_sectional_overwrite_without_negation(config_child_id)
            {
                self.future_config.add_deep_copy_of(
                    future_node_id,
                    self.config,
                    config_child_id,
                    false,
                )?;
            } else if is_negation
                && self.source.arena[source_node]
                    .children
                    .contains(text_without_neg)
            {
                negated_or_recursed.insert(Arc::from(text_without_neg));
            } else if let Some(self_child_id) =
                self.config
                    .idempotent_for(config_child_id, self.source, &source_children)
            {
                let added = self.future_config.add_deep_copy_of(
                    future_node_id,
                    self.config,
                    config_child_id,
                    false,
                )?;
                if is_negation {
                    self.report.idempotency_replacements.push(added);
                }
                negated_or_recursed.insert(Arc::clone(&self.source.arena[self_child_id].text));
            } else if is_negation
                && Self::match_prefix_negations(
                    self.source,
                    source_node,
                    &format!("{text_without_neg} "),
                    &mut negated_or_recursed,
                )
            {
                // Prefix negations inserted by helper
            } else if let Some(self_child_id) =
                self.source.arena[source_node].children.get(config_text)
            {
                let future_child = self.future_config.add_shallow_copy_of(
                    future_node_id,
                    self.source,
                    self_child_id,
                    false,
                )?;
                self.compute_node(self_child_id, config_child_id, future_child)?;
                negated_or_recursed.insert(Arc::clone(config_text));
            } else if is_negation {
                let added = self.future_config.add_shallow_copy_of(
                    future_node_id,
                    self.config,
                    config_child_id,
                    false,
                )?;
                self.report.unresolved_negations.push(added);
            } else if let Some(self_child_id) = self.source.arena[source_node].children.get(
                &format!("{}{}", self.source.driver.negation_prefix, config_text),
            ) {
                negated_or_recursed.insert(Arc::clone(&self.source.arena[self_child_id].text));
            } else {
                self.future_config.add_deep_copy_of(
                    future_node_id,
                    self.config,
                    config_child_id,
                    false,
                )?;
            }
        }

        for self_child_id in self.source.arena[source_node].children.iter() {
            let self_text = &self.source.arena[self_child_id].text;
            if negated_or_recursed.contains(&**self_text) {
                continue;
            }
            self.future_config.add_deep_copy_of(
                future_node_id,
                self.source,
                self_child_id,
                false,
            )?;
        }

        Ok(())
    }

    /// Recursively prunes emptied branches where children in source were negated.
    pub fn prune_emptied_branches(&mut self, source_node: NodeId, future_node_id: NodeId) {
        let children: Vec<NodeId> = self.future_config.arena[future_node_id]
            .children
            .iter()
            .collect();

        for child_id in children {
            let child_text = &self.future_config.arena[child_id].text;
            if let Some(src_child_id) = self.source.arena[source_node].children.get(child_text) {
                self.prune_emptied_branches(src_child_id, child_id);
                if self.future_config.arena[child_id].children.is_empty()
                    && !self.source.arena[src_child_id].children.is_empty()
                {
                    self.future_config.delete_child(child_id);
                }
            }
        }
    }

    fn match_prefix_negations(
        source: &Tree,
        source_node: NodeId,
        prefix: &str,
        negated_or_recursed: &mut HashSet<Arc<str>>,
    ) -> bool {
        let mut matched = false;
        for id in source.arena[source_node].children.iter() {
            if source.arena[id].text.starts_with(prefix) {
                negated_or_recursed.insert(Arc::clone(&source.arena[id].text));
                matched = true;
            }
        }
        matched
    }
}

/// Strips leading sequence number from ACL entry line text.
#[must_use]
pub fn strip_acl_sequence_number(text: &str) -> String {
    let words: Vec<&str> = text.split_whitespace().collect();
    if let Some((first, rest)) = words.split_first()
        && first.chars().all(|c| c.is_ascii_digit())
    {
        return rest.join(" ");
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
    let mut trees = DiffTrees {
        source,
        target,
        delta: &mut delta,
    };
    trees.compute()?;
    Ok(delta)
}

struct DiffTrees<'a> {
    source: &'a Tree,
    target: &'a Tree,
    delta: &'a mut Tree,
}

impl DiffTrees<'_> {
    fn compute(&mut self) -> Result<(), TreeError> {
        let delta_root = self.delta.root;
        self.compute_node(self.source.root, self.target.root, delta_root, None, false)
    }

    fn compute_node(
        &mut self,
        source_node: NodeId,
        target_node: NodeId,
        delta_node: NodeId,
        target_acl_children: Option<&HashMap<String, NodeId>>,
        in_acl: bool,
    ) -> Result<(), TreeError> {
        let acl_prefixes = ["ip access-list ", "ipv4 access-list ", "ipv6 access-list "];

        for self_child_id in self.source.arena[source_node].children.iter() {
            let self_text = &self.source.arena[self_child_id].text;

            if self_text.starts_with(&self.source.driver.negation_prefix)
                || self_text.starts_with("default ")
            {
                continue;
            }

            let target_child = if in_acl {
                let stripped = strip_acl_sequence_number(self_text);
                target_acl_children.and_then(|map| map.get(&stripped).copied())
            } else {
                self.target.arena[target_node].children.get(self_text)
            };

            if let Some(target_child_id) = target_child {
                let delta_child = self.delta.add_child(delta_node, self_text, false, false)?;

                if acl_prefixes
                    .iter()
                    .any(|prefix| self_text.starts_with(prefix))
                {
                    let mut acl_map = HashMap::default();
                    for c_id in self.target.arena[target_child_id].children.iter() {
                        let stripped = strip_acl_sequence_number(&self.target.arena[c_id].text);
                        acl_map.insert(stripped, c_id);
                    }

                    self.compute_node(
                        self_child_id,
                        target_child_id,
                        delta_child,
                        Some(&acl_map),
                        true,
                    )?;
                } else {
                    self.compute_node(self_child_id, target_child_id, delta_child, None, false)?;
                }

                if self.delta.arena[delta_child].children.is_empty() {
                    self.delta.delete_child(delta_child);
                }
            } else {
                self.delta
                    .add_deep_copy_of(delta_node, self.source, self_child_id, false)?;
            }
        }

        Ok(())
    }
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
            for desc_id in source.descendants_sorted(self_child) {
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
            for desc_id in target.descendants_sorted(target_child) {
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
