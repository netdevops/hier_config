use crate::platforms::post_load_enabled;
use crate::tree::Tree;

pub mod view;

pub const RULES_JSON: &str = include_str!("rules.json");

pub fn run_post_load(tree: &mut Tree) {
    if post_load_enabled(tree, "fixup_xr_comments") {
        fixup_xr_comments(tree);
    }
}

pub fn fixup_xr_comments(tree: &mut Tree) {
    let all_parents = std::iter::once(tree.root)
        .chain(tree.all_children(tree.root))
        .collect::<Vec<_>>();

    for parent_id in all_parents {
        if !tree.arena.contains(parent_id) {
            continue;
        }
        let siblings = tree.arena[parent_id].children.as_slice().to_vec();
        let mut comment_buffer = Vec::new();
        for sibling_id in siblings {
            if !tree.arena.contains(sibling_id) {
                continue;
            }
            let text = &tree.arena[sibling_id].text;
            if text.starts_with('!') {
                let comment_text = text.trim_start_matches('!').trim_start();
                if !comment_text.is_empty() {
                    comment_buffer.push(comment_text.to_string());
                }
                tree.delete_child(sibling_id);
            } else if !comment_buffer.is_empty() {
                for comment in &comment_buffer {
                    tree.arena[sibling_id]
                        .comments_mut()
                        .insert(comment.clone());
                }
                comment_buffer.clear();
            }
        }
    }
}
