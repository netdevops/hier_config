use crate::arena::NodeId;
use crate::driver::Driver;
use crate::models::{Dump, Platform};
use crate::tree::{Tree, TreeError};
use regex::Regex;
use rustc_hash::FxHashSet as HashSet;
use std::borrow::Cow;
use std::sync::Arc;

/// Substitution rules resolved to compiled regexes once, ahead of the line loop.
///
/// Platforms define up to a few dozen `per_line_sub` rules, each of which would
/// otherwise be looked up in the regex cache — hashing the pattern and taking a
/// lock — for every line of the configuration.
struct PreparedSubs {
    /// Union of every rule pattern, used to reject lines no rule touches in one pass.
    prefilter: Option<Arc<regex::RegexSet>>,
    rules: Vec<(Arc<Regex>, String)>,
}

impl PreparedSubs {
    fn new(rules: &[crate::models::PerLineSubRule]) -> Self {
        let rules: Vec<(Arc<Regex>, String)> = rules
            .iter()
            .filter_map(|rule| {
                crate::regex_cache::regex(&rule.search).map(|re| (re, rule.replace.clone()))
            })
            .collect();
        let prefilter = crate::regex_cache::regex_set(rules.iter().map(|(re, _)| re.as_str()));
        Self { prefilter, rules }
    }

    /// Applies every rule in order, allocating only when a rule actually matches.
    ///
    /// Most configuration lines match none of the rules, so a combined `RegexSet`
    /// rejects them in a single pass instead of scanning once per rule. For a line that
    /// does match, the same set reports *which* rules matched: while the text is still
    /// untouched it is exactly the original line, so a rule the set excluded provably
    /// cannot match and is skipped without running it. Once a rule rewrites the text
    /// that reasoning no longer holds, so every remaining rule runs as before — which
    /// keeps the result identical to a plain sequential pass.
    fn apply<'a>(&self, line: &'a str) -> Cow<'a, str> {
        let candidates = match &self.prefilter {
            Some(prefilter) => {
                if !prefilter.is_match(line) {
                    return Cow::Borrowed(line);
                }
                Some(prefilter.matches(line))
            }
            None => None,
        };

        let mut owned: Option<String> = None;
        for (index, (re, replace)) in self.rules.iter().enumerate() {
            if owned.is_none()
                && let Some(candidates) = &candidates
                && !candidates.matched(index)
            {
                continue;
            }

            let replaced = {
                let current: &str = owned.as_deref().unwrap_or(line);
                match re.replace_all(current, replace.as_str()) {
                    Cow::Borrowed(_) => None,
                    Cow::Owned(replaced) => Some(replaced),
                }
            };
            if let Some(replaced) = replaced {
                owned = Some(replaced);
            }
        }
        owned.map_or(Cow::Borrowed(line), Cow::Owned)
    }
}

/// Converts a Juniper / `VyOS` / Nokia style config string into a list of set commands.
pub fn convert_to_set_commands(config_raw: &str) -> String {
    let mut path: Vec<String> = Vec::new();
    let mut set_commands: Vec<String> = Vec::new();

    for line in config_raw.lines() {
        let stripped = line.trim();
        if stripped.is_empty() {
            continue;
        }

        let stripped = stripped.strip_suffix(';').unwrap_or(stripped);

        // Count indentation spaces to determine depth
        let leading_spaces = line.chars().take_while(|c| *c == ' ').count();
        let level = leading_spaces / 4;

        if level < path.len() {
            path.truncate(level);
        }

        if stripped.ends_with('{') || stripped.ends_with('}') {
            let section = stripped.trim_end_matches(['{', '}']).trim();
            if !section.is_empty() {
                path.push(section.to_string());
            }
        } else if stripped.starts_with("set ") || stripped.starts_with("delete ") {
            set_commands.push(stripped.to_string());
        } else {
            let cmd = if path.is_empty() {
                format!("set {stripped}")
            } else {
                format!("set {} {}", path.join(" "), stripped)
            };
            set_commands.push(cmd);
        }
    }

    set_commands.join("\n")
}

/// Applies platform-specific preprocessor if needed.
///
/// Only the set-command platforms rewrite the text; everything else borrows it, so a
/// large configuration is not copied just to be handed straight back.
pub fn config_preprocessor(platform: Platform, config_text: &str) -> Cow<'_, str> {
    crate::platforms::platform_ops(platform).config_preprocessor(config_text)
}

/// Tests if a line terminates a banner.
fn is_end_of_banner(
    config_line: &str,
    banner_end_lines: &HashSet<String>,
    banner_end_contains: &[String],
) -> bool {
    if config_line.starts_with('^') {
        return true;
    }
    if banner_end_lines.contains(config_line) {
        return true;
    }
    banner_end_contains.iter().any(|c| config_line.contains(c))
}

/// Cursor tracking the current insertion position in a [`Tree`].
#[derive(Debug, Clone, Copy)]
pub struct ParserCursor {
    pub current_section: NodeId,
    pub most_recent_item: NodeId,
}

impl ParserCursor {
    /// Creates a cursor positioned at `root`.
    #[must_use]
    pub const fn new(root: NodeId) -> Self {
        Self {
            current_section: root,
            most_recent_item: root,
        }
    }

    /// Inserts a new line into the tree at the appropriate hierarchy level given its indentation.
    ///
    /// # Errors
    ///
    /// Returns [`TreeError`] if the child cannot be attached, such as a duplicate child.
    pub fn record_line(
        &mut self,
        tree: &mut Tree,
        indent: i32,
        line: &str,
    ) -> Result<NodeId, TreeError> {
        // Walks back up the tree
        while indent <= tree.arena[self.current_section].real_indent_level
            && self.current_section != tree.root
        {
            if let Some(parent) = tree.arena[self.current_section].parent {
                self.current_section = parent;
            } else {
                break;
            }
        }

        // Walks down the tree by one step
        if indent > tree.arena[self.most_recent_item].real_indent_level {
            self.current_section = self.most_recent_item;
        }

        let new_child = tree.add_child(self.current_section, line, true, false)?;
        tree.arena[new_child].real_indent_level = indent;
        self.most_recent_item = new_child;

        Ok(new_child)
    }

    /// Resets the cursor to the tree root following a banner or section reset.
    pub const fn reset_to_root(&mut self, root: NodeId, most_recent_item: NodeId) {
        self.current_section = root;
        self.most_recent_item = most_recent_item;
    }
}

fn adjust_indent(
    prepared: &[(Arc<Regex>, String)],
    line: &str,
    mut indent_adjust: i32,
    mut end_indent_adjust: Vec<String>,
) -> (i32, Vec<String>) {
    for (re, end_expression) in prepared {
        if re.is_match(line) {
            indent_adjust += 1;
            end_indent_adjust.push(end_expression.clone());
            return (indent_adjust, end_indent_adjust);
        }
    }
    (indent_adjust, end_indent_adjust)
}

/// Loads configuration lines into a `Tree`, then applies the post-load stages.
/// Loads configuration text into a `Tree`, running stock post-load callbacks
/// followed additively by the provided custom callbacks.
///
/// # Errors
///
/// Returns [`TreeError`] if a line cannot be attached to the tree, most commonly
/// [`TreeError::DuplicateChild`] when the configuration repeats a section that the
/// platform driver does not permit to be duplicated.
pub fn load_from_str_with_callbacks<F>(
    tree: &mut Tree,
    config_raw: &str,
    callbacks: impl IntoIterator<Item = F>,
) -> Result<(), TreeError>
where
    F: Fn(&mut Tree),
{
    parse_into_tree(tree, config_raw)?;
    crate::post_load::delete_sectional_exit_recursive(tree);
    crate::post_load::run_post_load_callbacks(tree);
    for cb in callbacks {
        cb(tree);
    }
    Ok(())
}

///
/// # Errors
///
/// Returns [`TreeError`] if a line cannot be attached to the tree, most commonly
/// [`TreeError::DuplicateChild`] when the configuration repeats a section that the
/// platform driver does not permit to be duplicated.
pub fn load_from_str(tree: &mut Tree, config_raw: &str) -> Result<(), TreeError> {
    load_from_str_with_callbacks::<fn(&mut Tree)>(tree, config_raw, [])
}

/// Parses configuration text into a `Tree` without running any post-load stage.
///
/// Callers that need to interleave their own post-load behaviour — such as the
/// Python bindings, which may have to defer to user-supplied callbacks — drive the
/// stages themselves rather than paying for the built-in ones twice.
/// Tests whether a line already satisfies the whitespace normalization the parser
/// would otherwise produce.
///
/// The overwhelming majority of real configuration lines are already normalized, so a
/// single non-allocating scan lets the parser borrow the input line instead of
/// rebuilding it word by word. Any non-ASCII byte takes the slow path, because
/// `split_whitespace` is Unicode-aware and this scan is not.
fn is_already_normalized(rest: &[u8]) -> bool {
    let mut prev_space = false;
    for &b in rest {
        if !b.is_ascii() {
            return false;
        }
        if b == b' ' {
            if prev_space {
                return false;
            }
            prev_space = true;
        } else {
            if b.is_ascii_whitespace() {
                return false;
            }
            prev_space = false;
        }
    }
    !prev_space
}

fn normalize_whitespace<'a>(raw_line: &'a str, buffer: &'a mut String) -> &'a str {
    let leading_spaces = raw_line.len() - raw_line.trim_start_matches(' ').len();
    if is_already_normalized(&raw_line.as_bytes()[leading_spaces..]) {
        raw_line
    } else {
        buffer.clear();
        for _ in 0..leading_spaces {
            buffer.push(' ');
        }
        let mut first = true;
        for word in raw_line.split_whitespace() {
            if !first {
                buffer.push(' ');
            }
            buffer.push_str(word);
            first = false;
        }
        buffer
    }
}

fn apply_full_text_subs<'a>(driver: &Driver, mut config_text: Cow<'a, str>) -> Cow<'a, str> {
    for rule in &driver.rules.full_text_sub {
        if let Some(re) = crate::regex_cache::regex(&rule.search)
            && let Cow::Owned(replaced) = re.replace_all(&config_text, rule.replace.as_str())
        {
            config_text = Cow::Owned(replaced);
        }
    }
    config_text
}

struct BannerState {
    in_banner: bool,
    temp_banner: Vec<String>,
    banner_end_lines: HashSet<String>,
    banner_end_contains: Vec<String>,
}

impl BannerState {
    fn new() -> Self {
        Self {
            in_banner: false,
            temp_banner: Vec::new(),
            banner_end_lines: ["EOF", "%", "!"].iter().map(|s| (*s).to_string()).collect(),
            banner_end_contains: Vec::new(),
        }
    }

    fn check_start(&mut self, raw_line: &str) -> bool {
        if raw_line.starts_with("banner ") && raw_line != "banner motd ##" {
            self.in_banner = true;
            self.temp_banner.push(raw_line.to_string());
            let words: Vec<&str> = raw_line.split_whitespace().collect();
            if words.len() >= 3 {
                let delim = words[2];
                self.banner_end_contains.push(delim.to_string());
                if delim.starts_with('"') {
                    self.banner_end_contains.push("\"".to_string());
                }
                if !delim.is_empty() {
                    self.banner_end_lines
                        .insert(delim.chars().take(1).collect::<String>());
                    self.banner_end_lines
                        .insert(delim.chars().take(2).collect::<String>());
                }
            }
            return true;
        }
        false
    }
}

/// Tracks dynamic indentation adjustments triggered by platform indent rules.
struct IndentTracker {
    adjust: i32,
    end_expressions: Vec<String>,
}

impl IndentTracker {
    const fn new() -> Self {
        Self {
            adjust: 0,
            end_expressions: Vec::new(),
        }
    }

    fn update(&mut self, indent_rules: &[(Arc<Regex>, String)], line_content: &str) {
        if !indent_rules.is_empty() {
            let (adj, ends) = adjust_indent(
                indent_rules,
                line_content,
                self.adjust,
                std::mem::take(&mut self.end_expressions),
            );
            self.adjust = adj;
            self.end_expressions = ends;
        }

        if !self.end_expressions.is_empty()
            && let Some(re) = crate::regex_cache::regex(&self.end_expressions[0])
            && re.is_match(line_content)
        {
            self.adjust -= 1;
            self.end_expressions.remove(0);
        }
    }
}

/// Encapsulates mutable parsing state across configuration lines.
struct ParserState {
    cursor: ParserCursor,
    indent: IndentTracker,
    banner: BannerState,
    normalized: String,
}

impl ParserState {
    fn new(root: NodeId) -> Self {
        Self {
            cursor: ParserCursor::new(root),
            indent: IndentTracker::new(),
            banner: BannerState::new(),
            normalized: String::with_capacity(256),
        }
    }

    fn handle_banner_continuation(
        &mut self,
        tree: &mut Tree,
        raw_line: &str,
    ) -> Result<(), TreeError> {
        if raw_line != "!" {
            self.banner.temp_banner.push(raw_line.to_string());
        }

        if is_end_of_banner(
            raw_line,
            &self.banner.banner_end_lines,
            &self.banner.banner_end_contains,
        ) {
            self.banner.in_banner = false;
            let banner_text = self.banner.temp_banner.join("\n");
            let child = tree.add_child(tree.root, &banner_text, true, false)?;
            tree.arena[child].real_indent_level = 0;
            self.cursor.reset_to_root(tree.root, child);
            self.banner.temp_banner.clear();
        }
        Ok(())
    }
}

/// Parses `config_raw` into `tree` without running the post-load stages.
///
/// # Errors
///
/// Returns [`TreeError`] if a parsed line cannot be inserted, most commonly
/// [`TreeError::DuplicateChild`].
pub fn parse_into_tree(tree: &mut Tree, config_raw: &str) -> Result<(), TreeError> {
    let config_text = apply_full_text_subs(&tree.driver, Cow::Borrowed(config_raw));
    let config_text = config_preprocessor(tree.driver.platform, &config_text);

    // Resolve every regex used inside the line loop up front.
    let per_line_subs = PreparedSubs::new(&tree.driver.rules.per_line_sub);
    let indent_rules: Vec<(Arc<Regex>, String)> = tree
        .driver
        .rules
        .indent_adjust
        .iter()
        .filter_map(|expression| {
            crate::regex_cache::regex(&expression.start_expression)
                .map(|re| (re, expression.end_expression.clone()))
        })
        .collect();

    let mut state = ParserState::new(tree.root);

    // Most lines become a node, so sizing the arena up front avoids repeatedly
    // reallocating and copying the node table while parsing a large configuration.
    tree.arena.reserve(config_text.lines().count());

    for raw_line in config_text.lines() {
        if state.banner.in_banner {
            state.handle_banner_continuation(tree, raw_line)?;
            continue;
        }

        if state.banner.check_start(raw_line) {
            continue;
        }

        let normalized_line = normalize_whitespace(raw_line, &mut state.normalized);
        let line = per_line_subs.apply(normalized_line);
        let line_trimmed_right = line.trim_end();
        if line_trimmed_right.is_empty() {
            continue;
        }

        let actual_indent =
            line_trimmed_right.len() - line_trimmed_right.trim_start_matches(' ').len();
        let this_indent = i32::try_from(actual_indent).unwrap_or(i32::MAX) + state.indent.adjust;
        let line_content = line_trimmed_right.trim_start();

        state.cursor.record_line(tree, this_indent, line_content)?;

        state.indent.update(&indent_rules, line_content);
    }

    if state.banner.in_banner {
        return Err(TreeError::UnterminatedBanner(
            state
                .banner
                .temp_banner
                .first()
                .cloned()
                .unwrap_or_default(),
        ));
    }

    Ok(())
}

/// Fast load parser for clean/pre-formatted configurations.
///
/// Unlike [`load_from_str`] this applies only `per_line_sub` rules and assumes the
/// input needs no preprocessing, so it skips banner and comment handling.
///
/// Pass `run_post_load = false` when the caller supplies its own post-load
/// callbacks, as the Python bindings do for drivers that override the stock set.
///
/// # Errors
///
/// Returns [`TreeError`] if a line cannot be inserted into the tree.
pub fn load_fast(tree: &mut Tree, lines: &[&str], run_post_load: bool) -> Result<(), TreeError> {
    let mut cursor = ParserCursor::new(tree.root);

    let per_line_subs = PreparedSubs::new(&tree.driver.rules.per_line_sub);
    // Reused across lines so the slow path allocates at most once for the whole parse.
    let mut normalized = String::with_capacity(256);

    // Nearly every line becomes a node, so sizing the arena up front avoids the
    // repeated grow-and-copy of a node table whose entries are hundreds of bytes.
    tree.arena.reserve(lines.len());

    for original_line in lines {
        let trimmed_left = original_line.trim_start();
        if trimmed_left.is_empty() {
            continue;
        }

        let processed_line = per_line_subs.apply(original_line);

        let processed_trimmed = processed_line.trim_start();
        if processed_trimmed.is_empty() {
            continue;
        }

        let indent =
            i32::try_from(processed_line.len() - processed_trimmed.len()).unwrap_or(i32::MAX);

        // Mirrors the full parser: lines that already have single-space separators and
        // no trailing whitespace — nearly all of them — are borrowed as-is instead of
        // being rebuilt word by word.
        let normalized_line: &str = if is_already_normalized(processed_trimmed.as_bytes()) {
            processed_trimmed
        } else {
            normalized.clear();
            for word in processed_trimmed.split_whitespace() {
                if !normalized.is_empty() {
                    normalized.push(' ');
                }
                normalized.push_str(word);
            }
            &normalized
        };

        cursor.record_line(tree, indent, normalized_line)?;
    }

    crate::post_load::delete_sectional_exit_recursive(tree);
    if run_post_load {
        crate::post_load::run_post_load_callbacks(tree);
    }

    Ok(())
}

/// Parses pre-formatted lines into a `Tree`, running stock post-load callbacks (if enabled)
/// followed additively by the provided custom callbacks.
///
/// # Errors
///
/// Returns [`TreeError`] if a line cannot be inserted into the tree.
pub fn load_fast_with_callbacks<F>(
    tree: &mut Tree,
    lines: &[&str],
    run_post_load: bool,
    callbacks: impl IntoIterator<Item = F>,
) -> Result<(), TreeError>
where
    F: Fn(&mut Tree),
{
    load_fast(tree, lines, run_post_load)?;
    for cb in callbacks {
        cb(tree);
    }
    Ok(())
}

/// Parses configuration text into a new [`Tree`], applying all post-load stages.
///
/// This provides a pure, transactional constructor: on failure no partially-populated
/// tree is left behind.
///
/// # Errors
///
/// Returns [`TreeError`] if a line cannot be parsed or attached to the tree.
pub fn parse_tree(driver: Driver, config_raw: &str) -> Result<Tree, TreeError> {
    let mut tree = Tree::new(driver);
    load_from_str(&mut tree, config_raw)?;
    Ok(tree)
}

/// Parses configuration text into a new [`Tree`], running stock post-load callbacks
/// followed additively by the provided custom callbacks.
///
/// # Errors
///
/// Returns [`TreeError`] if a line cannot be parsed or attached to the tree.
pub fn parse_tree_with_callbacks<F>(
    driver: Driver,
    config_raw: &str,
    callbacks: impl IntoIterator<Item = F>,
) -> Result<Tree, TreeError>
where
    F: Fn(&mut Tree),
{
    let mut tree = Tree::new(driver);
    load_from_str_with_callbacks(&mut tree, config_raw, callbacks)?;
    Ok(tree)
}

/// Parses pre-formatted lines into a new [`Tree`], running post-load stages as requested.
///
/// # Errors
///
/// Returns [`TreeError`] if a line cannot be parsed or attached to the tree.
pub fn parse_fast(driver: Driver, lines: &[&str], run_post_load: bool) -> Result<Tree, TreeError> {
    let mut tree = Tree::new(driver);
    load_fast(&mut tree, lines, run_post_load)?;
    Ok(tree)
}

/// Parses pre-formatted lines into a new [`Tree`], running stock post-load callbacks (if enabled)
/// followed additively by the provided custom callbacks.
///
/// # Errors
///
/// Returns [`TreeError`] if a line cannot be parsed or attached to the tree.
pub fn parse_fast_with_callbacks<F>(
    driver: Driver,
    lines: &[&str],
    run_post_load: bool,
    callbacks: impl IntoIterator<Item = F>,
) -> Result<Tree, TreeError>
where
    F: Fn(&mut Tree),
{
    let mut tree = Tree::new(driver);
    load_fast_with_callbacks(&mut tree, lines, run_post_load, callbacks)?;
    Ok(tree)
}

/// Loads a `Tree` from a serialized `Dump`.
///
/// # Errors
///
/// Returns [`TreeError`] if the dump describes a structure that cannot be
/// reconstructed, such as a child whose recorded depth has no matching parent.
pub fn from_dump(driver: Driver, dump: &Dump) -> Result<Tree, TreeError> {
    let mut tree = Tree::new(driver);
    let mut last_item = tree.root;

    for item in &dump.lines {
        let parent = if item.depth == 1 {
            tree.root
        } else if tree.depth(last_item) == item.depth {
            tree.arena[last_item].parent.unwrap_or(tree.root)
        } else if tree.depth(last_item) + 1 == item.depth {
            last_item
        } else {
            let lineage = tree.lineage(last_item);
            if item.depth >= 2 && item.depth - 2 < lineage.len() {
                lineage[item.depth - 2]
            } else {
                tree.root
            }
        };

        let new_id = tree.add_child(parent, &item.text, false, false)?;
        let node = &mut tree.arena[new_id];
        // Only touch the extras block when the dump actually carries something,
        // so the common unadorned line never allocates one.
        if !item.tags.is_empty() {
            node.tags_mut().extend(item.tags.iter().cloned());
        }
        if !item.comments.is_empty() {
            node.comments_mut().extend(item.comments.iter().cloned());
        }
        node.new_in_config = item.new_in_config;
        node.real_indent_level = i32::try_from(item.depth).unwrap_or(i32::MAX) - 1;
        last_item = new_id;
    }

    Ok(tree)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_end_of_banner() {
        let end_lines: HashSet<String> =
            ["EOF", "%", "!"].iter().map(|s| (*s).to_string()).collect();
        let contains = vec!["^C".to_string()];
        let no_end_lines: HashSet<String> = HashSet::default();

        // A caret-prefixed line always terminates a banner.
        assert!(is_end_of_banner("^C", &end_lines, &contains));
        // Exact matches against the configured end lines terminate it.
        assert!(is_end_of_banner("%", &end_lines, &[]));
        assert!(is_end_of_banner("!", &end_lines, &[]));
        // So does a trailing delimiter on a content line.
        assert!(is_end_of_banner(
            "This is banner text^C",
            &no_end_lines,
            &contains
        ));
        // Ordinary banner content does not.
        assert!(!is_end_of_banner(
            "This is just regular text",
            &no_end_lines,
            &[]
        ));
    }

    #[test]
    fn test_adjust_indent() {
        let prepared = vec![(
            crate::regex_cache::regex("^policy-map").unwrap(),
            "^ *class".to_string(),
        )];

        // A matching line opens a new virtual indent level.
        let (indent, ends) = adjust_indent(&prepared, "policy-map test", 0, Vec::new());
        assert_eq!(indent, 1);
        assert_eq!(ends, vec!["^ *class".to_string()]);

        // A non-matching line leaves both accumulators untouched.
        let (plain_indent, plain_ends) =
            adjust_indent(&prepared, "hostname Router1", 0, Vec::new());
        assert_eq!(plain_indent, 0);
        assert!(plain_ends.is_empty());

        // With no rules configured there is nothing to adjust.
        let (unruled_indent, unruled_ends) = adjust_indent(&[], "policy-map test", 0, Vec::new());
        assert_eq!(unruled_indent, 0);
        assert!(unruled_ends.is_empty());
    }

    #[test]
    fn test_parse_simple_cisco_config() {
        let config = "
hostname Router1
!
interface GigabitEthernet0/1
 description Uplink
 ip address 10.0.0.1 255.255.255.0
!
router bgp 65000
 neighbor 10.0.0.2 remote-as 65001
";
        let mut tree = Tree::for_platform(Platform::CiscoIos);
        load_from_str(&mut tree, config).unwrap();

        assert_eq!(tree.arena[tree.root].children.len(), 3);
        let iface = tree.arena[tree.root]
            .children
            .get("interface GigabitEthernet0/1")
            .unwrap();
        assert_eq!(tree.arena[iface].children.len(), 2);
        assert!(
            tree.arena[iface]
                .children
                .get("description Uplink")
                .is_some()
        );
        assert!(
            tree.arena[iface]
                .children
                .get("ip address 10.0.0.1 255.255.255.0")
                .is_some()
        );
    }

    #[test]
    fn test_parse_banner() {
        let config = "
hostname Router1
banner motd ^
WARNING: Authorized Access Only!
Disconnect immediately if unauthorized.
^
interface Loopback0
";
        let mut tree = Tree::for_platform(Platform::CiscoIos);
        load_from_str(&mut tree, config).unwrap();

        assert_eq!(tree.arena[tree.root].children.len(), 3);
        let banner_node = tree.arena[tree.root].children.as_slice()[1];
        assert!(tree.arena[banner_node].text.starts_with("banner motd ^"));
        assert!(
            tree.arena[banner_node]
                .text
                .contains("Authorized Access Only!")
        );
    }

    #[test]
    fn test_dump_roundtrip() {
        let config = "
interface GigabitEthernet0/1
 description Link
";
        let mut tree = Tree::for_platform(Platform::Generic);
        load_from_str(&mut tree, config).unwrap();

        let dump = tree.dump();
        assert_eq!(dump.lines.len(), 2);
        assert_eq!(dump.lines[0].text, "interface GigabitEthernet0/1");
        assert_eq!(dump.lines[1].text, "description Link");

        let reloaded = from_dump(Driver::for_platform(Platform::Generic), &dump).unwrap();
        assert_eq!(reloaded.dump().lines.len(), 2);
    }

    #[test]
    fn test_unterminated_banner_reports_the_offending_line() {
        // Regression: reaching EOF inside a banner used to surface as
        // `InvalidParent(NodeId { .. })`, which told the user nothing about
        // what went wrong. v3 raised "we are still in a banner", so the error
        // must name the banner it failed to close.
        let mut tree = Tree::default();
        let err = load_from_str(&mut tree, "banner motd \"Hello\"\nvlan 10\n")
            .expect_err("an unterminated banner must be rejected");

        assert!(matches!(err, TreeError::UnterminatedBanner(_)), "{err:?}");
        let message = err.to_string();
        assert!(message.contains("Unterminated banner"), "{message}");
        assert!(message.contains("banner motd"), "{message}");
    }

    #[test]
    fn test_parse_banner_with_multibyte_delimiter_does_not_panic() {
        // Regression: the banner delimiter used to be byte-sliced (`delim[..1]`,
        // `delim[..2]`), which panics when the delimiter starts with a multibyte
        // character such as the euro sign. Parsing must not panic on arbitrary input.
        let config = "hostname Router1\nbanner motd \u{20ac}\nAuthorized only\n\u{20ac}\ninterface Loopback0\n";
        let mut tree = Tree::for_platform(Platform::CiscoIos);
        load_from_str(&mut tree, config).unwrap();
        assert!(
            tree.arena[tree.root]
                .children
                .iter()
                .any(|id| tree.arena[id].text.starts_with("banner motd"))
        );
    }

    #[test]
    fn test_pure_parse_tree_and_parse_fast() {
        use std::cell::Cell;

        let config = "hostname Router1\ninterface GigabitEthernet0/1\n description Link\n";
        let tree = parse_tree(Driver::for_platform(Platform::CiscoIos), config).unwrap();
        assert_eq!(tree.len(), 3);

        let custom_run = Cell::new(false);
        let tree_with_cb = parse_tree_with_callbacks(
            Driver::for_platform(Platform::CiscoIos),
            config,
            [&|_t: &mut Tree| {
                custom_run.set(true);
            }],
        )
        .unwrap();
        assert!(custom_run.get());
        assert_eq!(tree_with_cb.len(), 3);

        let lines = ["hostname FastRouter", "interface Fast0/0"];
        let fast_tree = parse_fast(Driver::for_platform(Platform::CiscoIos), &lines, true).unwrap();
        assert_eq!(fast_tree.len(), 2);

        let fast_cb_run = Cell::new(false);
        let fast_tree_cb = parse_fast_with_callbacks(
            Driver::for_platform(Platform::CiscoIos),
            &lines,
            true,
            [&|_t: &mut Tree| {
                fast_cb_run.set(true);
            }],
        )
        .unwrap();
        assert!(fast_cb_run.get());
        assert_eq!(fast_tree_cb.len(), 2);
    }

    #[test]
    fn test_parser_cursor_walks_hierarchy() {
        let mut tree = Tree::for_platform(Platform::Generic);
        let mut cursor = ParserCursor::new(tree.root);

        let top1 = cursor.record_line(&mut tree, 0, "parent1").unwrap();
        assert_eq!(cursor.current_section, tree.root);
        assert_eq!(cursor.most_recent_item, top1);

        let child1 = cursor.record_line(&mut tree, 1, "child1").unwrap();
        assert_eq!(cursor.current_section, top1);
        assert_eq!(cursor.most_recent_item, child1);

        let child2 = cursor.record_line(&mut tree, 1, "child2").unwrap();
        assert_eq!(cursor.current_section, top1);
        assert_eq!(cursor.most_recent_item, child2);

        let top2 = cursor.record_line(&mut tree, 0, "parent2").unwrap();
        assert_eq!(cursor.current_section, tree.root);
        assert_eq!(cursor.most_recent_item, top2);
    }
}
