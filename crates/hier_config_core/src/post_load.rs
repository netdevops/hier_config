use crate::tree::Tree;

pub use crate::platforms::functions::{MAX_RANGE_SPAN, MAX_RANGE_TOTAL, expand_range};
pub use crate::platforms::hp_procurve::hp_procurve_expand_range;
pub use crate::platforms::run_post_load_callbacks;

/// Recursively removes trailing sectional exit lines matching the driver's exit command.
pub fn delete_sectional_exit_recursive(tree: &mut Tree) {
    let all_nodes = tree.all_children(tree.root);
    for node_id in all_nodes {
        tree.delete_sectional_exit(node_id);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::Platform;

    #[test]
    fn expand_range_accepts_normal_ranges() {
        assert_eq!(expand_range("2-5,8").unwrap(), vec![2, 3, 4, 5, 8]);
    }

    #[test]
    fn expand_range_rejects_oversized_span() {
        // Regression: an unbounded `start..=stop` would try to allocate billions of
        // elements for input like `1-4000000000` and exhaust memory. Oversized spans
        // must return an error so the caller leaves the line untouched.
        assert!(expand_range("1-4000000000").is_err());
        assert!(expand_range("0-1000000").is_err());
        // Just under the cap still succeeds.
        assert!(expand_range("1-1000000").is_ok());
    }

    #[test]
    fn expand_range_rejects_oversized_total_across_segments() {
        // Regression: the per-segment cap alone was bypassable. Each segment here is
        // individually under `MAX_RANGE_SPAN`, but the aggregate is unbounded -- a
        // 76-byte line expanded to ~5 million elements before this was capped.
        let segments: Vec<String> = (0..5)
            .map(|i| format!("{}-{}", i * 999_999, (i + 1) * 999_999 - 1))
            .collect();
        assert!(expand_range(&segments.join(",")).is_err());
    }

    #[test]
    fn expand_range_rejects_repeated_segments_that_dedup_small() {
        // The de-duplicating `seen` set means output length alone is not a safe bound:
        // these segments collapse to 1M unique values but would visit 5M, burning CPU.
        // The cap counts values *visited*, so this is rejected.
        let repeated = ["0-999999"; 5].join(",");
        assert!(expand_range(&repeated).is_err());
    }

    #[test]
    fn expand_range_accepts_multi_segment_within_total() {
        // The cumulative cap must not break ordinary multi-segment ranges.
        assert_eq!(
            expand_range("2-5,8,22-25").unwrap(),
            vec![2, 3, 4, 5, 8, 22, 23, 24, 25]
        );
    }

    #[test]
    fn hp_procurve_expand_range_rejects_oversized_span() {
        assert!(hp_procurve_expand_range("1-4000000000").is_err());
    }

    #[test]
    fn hp_procurve_expand_range_rejects_oversized_total_across_segments() {
        // Same cumulative bypass as `expand_range`, but worse: this accumulates
        // `String`s rather than `u32`s.
        let segments: Vec<String> = (0..5)
            .map(|i| format!("{}-{}", i * 999_999, (i + 1) * 999_999 - 1))
            .collect();
        assert!(hp_procurve_expand_range(&segments.join(",")).is_err());
    }

    #[test]
    fn test_stock_callbacks_run_automatically_and_custom_callbacks_are_additive() {
        let config = "vlan 10,20\n";
        let custom_cb = |tree: &mut Tree| {
            let _ = tree.add_child(tree.root, "custom extra line", true, false);
        };

        let tree = Tree::from_str_with_callbacks(Platform::CiscoIos, config, [&custom_cb])
            .expect("parse error");

        let child_texts: Vec<&str> = tree.arena[tree.root]
            .children
            .iter()
            .map(|id| tree.arena[id].text.as_ref())
            .collect();

        // Stock callback split vlan 10,20 into vlan 10 and vlan 20
        assert!(child_texts.contains(&"vlan 10"));
        assert!(child_texts.contains(&"vlan 20"));
        assert!(!child_texts.contains(&"vlan 10,20"));

        // Custom callback ran additively
        assert!(child_texts.contains(&"custom extra line"));
    }
}
