use crate::models::{
    FullTextSubRule, IdempotentCommandsAvoidRule, IdempotentCommandsRule, IndentAdjustRule,
    MatchRule, NegationDefaultWhenRule, NegationDefaultWithRule, NegationRule, NegationStrategy,
    NegationSubRule, OrderingRule, ParentAllowsDuplicateChildRule, PerLineSubRule, Platform,
    SectionalExitingRule, SectionalOverwriteNoNegateRule, SectionalOverwriteRule, StringPattern,
    UnusedObjectRule,
};
use serde::{Deserialize, Serialize};
use std::fmt::Write as _;
use std::sync::{Arc, OnceLock, RwLock};

/// Collection of all rule sets for a platform driver.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DriverRules {
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub full_text_sub: Vec<FullTextSubRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub idempotent_commands: Vec<IdempotentCommandsRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub idempotent_commands_avoid: Vec<IdempotentCommandsAvoidRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub indent_adjust: Vec<IndentAdjustRule>,
    #[serde(
        default = "default_indentation",
        skip_serializing_if = "is_default_indentation"
    )]
    pub indentation: usize,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub negation_default_when: Vec<NegationDefaultWhenRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub negate_with: Vec<NegationDefaultWithRule>,
    /// Unified, order-sensitive negation rules.
    ///
    /// When non-empty this list drives negation and the three v3 lists are
    /// folded in after it, mirroring `HConfigDriverRules.all_negation_rules()`
    /// on the Python side.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub negation: Vec<NegationRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub ordering: Vec<OrderingRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub parent_allows_duplicate_child: Vec<ParentAllowsDuplicateChildRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub per_line_sub: Vec<PerLineSubRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub sectional_exiting: Vec<SectionalExitingRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub sectional_overwrite: Vec<SectionalOverwriteRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub sectional_overwrite_no_negate: Vec<SectionalOverwriteNoNegateRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub negation_sub: Vec<NegationSubRule>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub unused_objects: Vec<UnusedObjectRule>,
    /// Names of the post-load callbacks that are still enabled.
    ///
    /// `None` means "every callback the platform defines", which is what a
    /// pure-Rust caller wants. The Python bindings set it from the driver's
    /// `post_load_callbacks` so removing a callback there also disables its
    /// core-owned implementation (#286).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub enabled_post_load: Option<Vec<String>>,
}

const fn default_indentation() -> usize {
    2
}

macro_rules! serde_skip_default_copy {
    ($fn_name:ident, $type:ty, $default:expr) => {
        const fn $fn_name(val: &$type) -> bool {
            *val == $default
        }
    };
}
serde_skip_default_copy!(is_default_indentation, usize, default_indentation());

/// Reports whether `s` contains a Python-style regex backreference.
///
/// Used to keep `negate_with` templating opt-in: a `use` string without
/// backreferences is emitted verbatim and never touches the regex engine.
fn has_backreference(s: &str) -> bool {
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\\'
            && let Some(&next_c) = chars.peek()
            && (next_c.is_ascii_digit() || next_c == 'g')
        {
            return true;
        }
    }
    false
}

fn python_to_rust_replacement(s: &str) -> String {
    let mut result = String::new();
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\\'
            && let Some(&next_c) = chars.peek()
        {
            if next_c.is_ascii_digit() {
                chars.next();
                result.push('$');
                result.push(next_c);
                continue;
            } else if next_c == 'g' {
                let remaining: String = chars.clone().collect();
                if remaining.starts_with("g<")
                    && let Some(end_idx) = remaining.find('>')
                {
                    let name = &remaining[2..end_idx];
                    let _ = write!(result, "${{{name}}}");
                    for _ in 0..=end_idx {
                        chars.next();
                    }
                    continue;
                }
            }
        }
        result.push(c);
    }
    result
}

impl Default for DriverRules {
    fn default() -> Self {
        Self {
            full_text_sub: Vec::new(),
            idempotent_commands: Vec::new(),
            idempotent_commands_avoid: Vec::new(),
            indent_adjust: Vec::new(),
            indentation: default_indentation(),
            negation_default_when: Vec::new(),
            negate_with: Vec::new(),
            negation: Vec::new(),
            ordering: Vec::new(),
            enabled_post_load: None,
            parent_allows_duplicate_child: Vec::new(),
            per_line_sub: Vec::new(),
            sectional_exiting: Vec::new(),
            sectional_overwrite: Vec::new(),
            sectional_overwrite_no_negate: Vec::new(),
            negation_sub: Vec::new(),
            unused_objects: Vec::new(),
        }
    }
}

impl DriverRules {
    /// Returns negation rules in evaluation order.
    ///
    /// Mirrors `HConfigDriverRules.all_negation_rules()`: when no v3-spelled
    /// rules are present the unified list is used verbatim, otherwise the v3
    /// lists are folded in after it. Returns `None` on the fast path where
    /// there is no unified list at all, letting callers avoid the allocation
    /// and walk the v3 vectors directly.
    pub(crate) fn resolved_negation(&self) -> Option<Vec<NegationRule>> {
        if self.negation.is_empty() {
            return None;
        }
        let mut resolved = self.negation.clone();
        resolved.extend(self.negation_default_when.iter().map(|rule| NegationRule {
            strategy: NegationStrategy::Default,
            match_rules: rule.match_rules.clone(),
            use_cmd: String::new(),
            search: String::new(),
            replace: String::new(),
        }));
        resolved.extend(self.negate_with.iter().map(|rule| NegationRule {
            strategy: NegationStrategy::Replace,
            match_rules: rule.match_rules.clone(),
            use_cmd: rule.use_cmd.clone(),
            search: String::new(),
            replace: String::new(),
        }));
        resolved.extend(self.negation_sub.iter().map(|rule| NegationRule {
            strategy: NegationStrategy::RegexSub,
            match_rules: rule.match_rules.clone(),
            use_cmd: String::new(),
            search: rule.search.clone(),
            replace: rule.replace.clone(),
        }));
        Some(resolved)
    }
}

/// Platform driver holding rules and syntax specifics (e.g. indentation, negation prefixes).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Driver {
    pub platform: Platform,
    pub rules: DriverRules,
    pub negation_prefix: String,
    pub declaration_prefix: String,
}

impl Default for Driver {
    fn default() -> Self {
        Self::for_platform(Platform::Generic)
    }
}

impl Driver {
    /// Returns the embedded raw JSON string defining the platform rules for `platform`.
    #[must_use]
    pub fn rules_json_for_platform(platform: Platform) -> &'static str {
        crate::platforms::rules_json_for_platform(platform)
    }

    /// Creates a driver for the specified platform with its default rules.
    ///
    /// # Panics
    ///
    /// Panics if the platform rules JSON compiled into the binary is malformed. This
    /// is a build-time invariant: the files are validated by the test suite, so a
    /// panic here indicates a corrupted build artifact rather than bad input.
    ///
    /// # Example
    ///
    /// ```
    /// use hier_config_core::{Driver, Platform};
    ///
    /// let driver = Driver::for_platform(Platform::CiscoIos);
    /// assert_eq!(driver.platform, Platform::CiscoIos);
    /// assert_eq!(driver.negation_prefix, "no ");
    /// assert!(!driver.rules.idempotent_commands.is_empty());
    /// ```
    pub fn for_platform(platform: Platform) -> Self {
        #[derive(Deserialize)]
        struct PlatformData {
            #[serde(default)]
            platform: Option<Platform>,
            rules: DriverRules,
            negation_prefix: String,
            #[serde(default)]
            declaration_prefix: Option<String>,
        }

        let rules_json = Self::rules_json_for_platform(platform);

        let parsed: PlatformData =
            serde_json::from_str(rules_json).expect("Valid embedded platform rules JSON");

        if let Some(embedded_platform) = parsed.platform {
            debug_assert_eq!(
                embedded_platform, platform,
                "Embedded rules JSON platform tag does not match requested platform"
            );
        }

        let declaration_prefix = parsed.declaration_prefix.unwrap_or_default();

        Self {
            platform,
            rules: parsed.rules,
            negation_prefix: parsed.negation_prefix,
            declaration_prefix,
        }
    }

    /// Returns a cached, shared [`Driver`] for `platform`.
    ///
    /// `for_platform` deserializes the platform's entire embedded rules JSON on every
    /// call. Call sites that only need a driver's syntax (e.g. negation/declaration
    /// prefixes) rather than a one-off owned `Driver` — such as the per-call
    /// `driver_swap_negation` Python binding — should use this instead so the
    /// deserialization happens once per platform for the life of the process.
    ///
    /// # Panics
    ///
    /// Panics if the internal cache lock is poisoned, which only happens if another
    /// thread already panicked while holding it.
    pub fn cached_for_platform(platform: Platform) -> Arc<Self> {
        static CACHE: OnceLock<RwLock<std::collections::HashMap<Platform, Arc<Driver>>>> =
            OnceLock::new();
        let cache = CACHE.get_or_init(|| RwLock::new(std::collections::HashMap::new()));

        if let Some(driver) = cache.read().unwrap().get(&platform) {
            return Arc::clone(driver);
        }

        let driver = Arc::new(Self::for_platform(platform));
        Arc::clone(
            cache
                .write()
                .unwrap()
                .entry(platform)
                .or_insert_with(|| driver),
        )
    }

    /// Strips the negation prefix from `text`.
    pub fn text_without_negation<'a>(&self, text: &'a str) -> &'a str {
        text.strip_prefix(&self.negation_prefix).unwrap_or(text)
    }

    /// Toggles the negation prefix on `text`, returning an error if the syntax is invalid for the platform.
    ///
    /// # Errors
    ///
    /// Returns an error message if the command does not start with an expected prefix (e.g. on `JunOS`).
    pub fn try_swap_negation(&self, text: &str) -> Result<String, String> {
        crate::platforms::try_swap_negation(
            self.platform,
            &self.negation_prefix,
            &self.declaration_prefix,
            text,
        )
    }

    /// Toggles the negation prefix on `text`.
    pub fn swap_negation(&self, text: &str) -> String {
        self.try_swap_negation(text)
            .unwrap_or_else(|_| text.to_string())
    }

    /// Computes the negation string for `text` given its lineage.
    pub fn compute_negation(
        &self,
        text: &str,
        is_lineage_match: impl Fn(&[MatchRule]) -> bool,
    ) -> String {
        if let Some(resolved) = self.rules.resolved_negation() {
            return self.compute_negation_unified(text, &resolved, is_lineage_match);
        }

        // 1. negate_with rule
        for rule in &self.rules.negate_with {
            if is_lineage_match(&rule.match_rules) {
                return Self::expand_negate_with(text, rule);
            }
        }

        // 2. negation_default_when rule
        for rule in &self.rules.negation_default_when {
            if is_lineage_match(&rule.match_rules) {
                let stripped = self.text_without_negation(text);
                return format!("default {stripped}");
            }
        }

        // 3. negation_sub rule
        for rule in &self.rules.negation_sub {
            if is_lineage_match(&rule.match_rules) {
                let negated = format!("{}{}", self.negation_prefix, text);
                if let Some(re) = crate::regex_cache::regex(&rule.search) {
                    let rust_replace = python_to_rust_replacement(&rule.replace);
                    return re.replace(&negated, rust_replace.as_str()).to_string();
                }
            }
        }

        // 4. swap negation
        self.swap_negation(text)
    }

    /// Resolves negation against the unified rule list.
    ///
    /// `Replace` wins over everything, matching the Python contract where
    /// `negate_with()` is consulted before the remaining strategies; the rest
    /// are then evaluated in declaration order rather than grouped by kind.
    fn compute_negation_unified(
        &self,
        text: &str,
        resolved: &[NegationRule],
        is_lineage_match: impl Fn(&[MatchRule]) -> bool,
    ) -> String {
        for rule in resolved {
            if rule.strategy == NegationStrategy::Replace && is_lineage_match(&rule.match_rules) {
                return Self::expand_negate_with(text, &rule.as_default_with());
            }
        }

        for rule in resolved {
            if !is_lineage_match(&rule.match_rules) {
                continue;
            }
            match rule.strategy {
                NegationStrategy::Replace => {}
                NegationStrategy::Default => {
                    let stripped = self.text_without_negation(text);
                    return format!("default {stripped}");
                }
                NegationStrategy::RegexSub => {
                    let negated = format!("{}{}", self.negation_prefix, text);
                    if let Some(re) = crate::regex_cache::regex(&rule.search) {
                        let rust_replace = python_to_rust_replacement(&rule.replace);
                        return re.replace(&negated, rust_replace.as_str()).to_string();
                    }
                }
            }
        }

        self.swap_negation(text)
    }

    /// Resolves a [`NegationDefaultWithRule`]'s replacement command.
    ///
    /// When `use` contains Python-style backreferences (`\1`, `\g<name>`) they are
    /// interpolated from the capture groups of the last `match_rules` entry that
    /// carries an `re_search` pattern — that entry is the one matching the node
    /// itself rather than an ancestor. Templates let a single rule express the
    /// "keep the first N words, then substitute the tail" shape that previously
    /// required an imperative `negate_with()` override.
    ///
    /// Falls back to the literal `use` string when there are no backreferences,
    /// when no `re_search` is present, or when the pattern does not match.
    pub(crate) fn expand_negate_with(text: &str, rule: &NegationDefaultWithRule) -> String {
        if !has_backreference(&rule.use_cmd) {
            return rule.use_cmd.clone();
        }
        let Some(pattern) = rule
            .match_rules
            .iter()
            .rev()
            .find_map(|match_rule| match_rule.re_search.as_deref())
        else {
            return rule.use_cmd.clone();
        };
        let Some(re) = crate::regex_cache::regex(pattern) else {
            return rule.use_cmd.clone();
        };
        let Some(captures) = re.captures(text) else {
            return rule.use_cmd.clone();
        };
        // `expand` builds the command from the template alone, so an unanchored
        // pattern cannot leak unmatched leading/trailing text into the result.
        let mut expanded = String::new();
        captures.expand(&python_to_rust_replacement(&rule.use_cmd), &mut expanded);
        expanded
    }

    /// Determines the exit command for a section.
    pub fn sectional_exit(
        &self,
        has_children: bool,
        is_lineage_match: impl Fn(&[MatchRule]) -> bool,
    ) -> Option<String> {
        for exit_rule in &self.rules.sectional_exiting {
            if is_lineage_match(&exit_rule.match_rules) {
                if !exit_rule.exit_text.is_empty() {
                    return Some(exit_rule.exit_text.clone());
                }
                return None;
            }
        }
        if has_children {
            Some(crate::platforms::default_sectional_exit(self.platform).to_string())
        } else {
            None
        }
    }

    /// Computes the idempotency key for a node's lineage.
    pub fn idempotency_key(
        &self,
        lineage_texts: &[&str],
        match_rules: &[MatchRule],
    ) -> Vec<String> {
        if lineage_texts.len() != match_rules.len() {
            return Vec::new();
        }

        lineage_texts
            .iter()
            .zip(match_rules.iter())
            .map(|(text, rule)| self.idempotency_component_key(text, rule))
            .collect()
    }

    fn idempotency_component_key(&self, text: &str, rule: &MatchRule) -> String {
        let normalized_text = self.text_without_negation(text);
        let mut parts = Vec::new();

        // equals
        if let Some(equals) = &rule.equals {
            match equals {
                StringPattern::Single(s) => parts.push(format!("equals|{s}")),
                StringPattern::Multiple(_) => parts.push(format!("equals|{text}")),
            }
        }

        // startswith
        if let Some(startswith) = &rule.startswith
            && let Some(matched) = match_prefix(normalized_text, startswith)
        {
            parts.push(format!("startswith|{matched}"));
        }

        // endswith
        if let Some(endswith) = &rule.endswith
            && let Some(matched) = match_suffix(normalized_text, endswith)
        {
            parts.push(format!("endswith|{matched}"));
        }

        // contains
        if let Some(contains) = &rule.contains
            && let Some(matched) = match_contains(normalized_text, contains)
        {
            parts.push(format!("contains|{matched}"));
        }

        // regex
        if let Some(pattern) = &rule.re_search
            && let Some(key) = Self::key_from_regex(pattern, normalized_text, text)
        {
            parts.push(format!("re|{key}"));
        }

        if parts.is_empty() {
            parts.push(format!("text|{normalized_text}"));
        }

        parts.join(";")
    }

    fn key_from_regex(pattern: &str, normalized_text: &str, original_text: &str) -> Option<String> {
        let re = crate::regex_cache::regex(pattern)?;
        let (matched, source) = if let Some(m) = re.find(normalized_text) {
            (m, normalized_text)
        } else {
            let m = re.find(original_text)?;
            (m, original_text)
        };

        if re.captures_len() > 1
            && let Some(caps) = re.captures(source)
        {
            let groups: Vec<&str> = caps
                .iter()
                .skip(1)
                .flatten()
                .map(|m| m.as_str().trim())
                .filter(|s| !s.is_empty())
                .collect();
            if !groups.is_empty() {
                return Some(groups.join("|"));
            }
        }

        let trimmed_pattern = pattern.trim_end_matches('$');
        for suffix in &[".*", ".+"] {
            if let Some(candidate_pattern) = trimmed_pattern.strip_suffix(suffix) {
                if candidate_pattern.is_empty() {
                    break;
                }
                if let Some(candidate_re) = crate::regex_cache::regex(candidate_pattern)
                    && let Some(m) = candidate_re.find(source)
                {
                    let candidate = m.as_str().trim();
                    if !candidate.is_empty() {
                        return Some(candidate.to_string());
                    }
                }
                break;
            }
        }

        Some(matched.as_str().trim().to_string())
    }
}

fn match_prefix<'a>(value: &'a str, pattern: &'a StringPattern) -> Option<&'a str> {
    match pattern {
        StringPattern::Single(s) => {
            if value.starts_with(s) {
                Some(s.as_str())
            } else {
                None
            }
        }
        StringPattern::Multiple(v) => v
            .iter()
            .filter(|s| value.starts_with(s.as_str()))
            .max_by_key(|s| s.len())
            .map(String::as_str),
    }
}

fn match_suffix<'a>(value: &'a str, pattern: &'a StringPattern) -> Option<&'a str> {
    match pattern {
        StringPattern::Single(s) => {
            if value.ends_with(s) {
                Some(s.as_str())
            } else {
                None
            }
        }
        StringPattern::Multiple(v) => v
            .iter()
            .filter(|s| value.ends_with(s.as_str()))
            .max_by_key(|s| s.len())
            .map(String::as_str),
    }
}

fn match_contains<'a>(value: &'a str, pattern: &'a StringPattern) -> Option<&'a str> {
    match pattern {
        StringPattern::Single(s) => {
            if value.contains(s) {
                Some(s.as_str())
            } else {
                None
            }
        }
        StringPattern::Multiple(v) => v
            .iter()
            .filter(|s| value.contains(s.as_str()))
            .max_by_key(|s| s.len())
            .map(String::as_str),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unified(strategy: NegationStrategy, equals: &str) -> NegationRule {
        NegationRule {
            strategy,
            match_rules: vec![MatchRule::equals(equals)],
            use_cmd: String::new(),
            search: String::new(),
            replace: String::new(),
        }
    }

    #[test]
    fn test_unified_negation_rules_are_evaluated_in_declaration_order() {
        let mut driver = Driver::for_platform(Platform::Generic);
        let mut regex_sub = unified(NegationStrategy::RegexSub, "ip access-list foo");
        regex_sub.search = r"^no ip access-list (\S+)$".to_string();
        regex_sub.replace = r"no ip access-list extended \1".to_string();
        // REGEX_SUB is declared first, so it must win over the later DEFAULT
        // rule even though the legacy engine grouped DEFAULT ahead of it.
        driver.rules.negation = vec![
            regex_sub,
            unified(NegationStrategy::Default, "ip access-list foo"),
        ];

        let negated = driver.compute_negation("ip access-list foo", |rules| {
            rules.iter().all(|r| r.equals.is_some())
        });

        assert_eq!(negated, "no ip access-list extended foo");
    }

    #[test]
    fn test_replace_strategy_is_consulted_before_earlier_rules() {
        let mut driver = Driver::for_platform(Platform::Generic);
        let mut replace = unified(NegationStrategy::Replace, "shutdown");
        replace.use_cmd = "no shutdown".to_string();
        // REPLACE is declared last but must still win, mirroring the Python
        // contract where `negate_with()` runs before the other strategies.
        driver.rules.negation = vec![unified(NegationStrategy::Default, "shutdown"), replace];

        let negated =
            driver.compute_negation("shutdown", |rules| rules.iter().all(|r| r.equals.is_some()));

        assert_eq!(negated, "no shutdown");
    }

    #[test]
    fn test_v3_rules_are_folded_in_after_the_unified_list() {
        let mut driver = Driver::for_platform(Platform::Generic);
        driver.rules.negation = vec![unified(NegationStrategy::Default, "other")];
        driver.rules.negation_default_when = vec![NegationDefaultWhenRule {
            match_rules: vec![MatchRule::equals("shutdown")],
        }];

        let negated = driver.compute_negation("shutdown", |rules| {
            rules.iter().any(|r| {
                r.equals
                    .as_ref()
                    .is_some_and(|p| p.matches_equals("shutdown"))
            })
        });

        assert_eq!(negated, "default shutdown");
    }

    #[test]
    fn test_driver_negation() {
        let driver = Driver::for_platform(Platform::Generic);
        assert_eq!(driver.swap_negation("shutdown"), "no shutdown");
        assert_eq!(driver.swap_negation("no shutdown"), "shutdown");
        assert_eq!(driver.text_without_negation("no shutdown"), "shutdown");
    }

    #[test]
    fn test_negate_with_interpolates_capture_groups_from_the_last_match_rule() {
        let mut driver = Driver::for_platform(Platform::Generic);
        driver.rules.negate_with.insert(
            0,
            NegationDefaultWithRule {
                match_rules: vec![MatchRule::re_search(
                    r"^(aaa port-access authenticator \S+ tx-period) \d+$",
                )],
                use_cmd: r"\1 30".to_string(),
            },
        );
        assert_eq!(
            driver.compute_negation("aaa port-access authenticator 1/1 tx-period 3", |_| true),
            "aaa port-access authenticator 1/1 tx-period 30"
        );
    }

    #[test]
    fn test_negate_with_without_backreferences_stays_literal() {
        let mut driver = Driver::for_platform(Platform::Generic);
        driver.rules.negate_with.insert(
            0,
            NegationDefaultWithRule {
                match_rules: vec![MatchRule::equals("disable")],
                use_cmd: "enable".to_string(),
            },
        );
        assert_eq!(driver.compute_negation("disable", |_| true), "enable");
    }

    #[test]
    fn test_negate_with_backreference_falls_back_to_literal_when_regex_does_not_match() {
        let mut driver = Driver::for_platform(Platform::Generic);
        driver.rules.negate_with.insert(
            0,
            NegationDefaultWithRule {
                match_rules: vec![MatchRule::re_search(r"^(never matches this)$")],
                use_cmd: r"\1 30".to_string(),
            },
        );
        assert_eq!(
            driver.compute_negation("some other line", |_| true),
            r"\1 30"
        );
    }

    #[test]
    fn test_driver_idempotency_key() {
        let driver = Driver::for_platform(Platform::CiscoIos);
        let rules = vec![MatchRule::startswith("description ")];
        let key1 = driver.idempotency_key(&["description Primary link"], &rules);
        let key2 = driver.idempotency_key(&["description Backup link"], &rules);
        assert_eq!(key1, key2);
        assert_eq!(key1, vec!["startswith|description ".to_string()]);
    }

    #[test]
    fn test_all_13_platforms_embedded_rules_load_and_match() {
        for platform in Platform::ALL {
            let driver = Driver::for_platform(platform);
            assert_eq!(driver.platform, platform);
        }
    }

    #[test]
    fn test_embedded_platform_json_field_matches_requested_platform() {
        // `for_platform` only cross-checks the embedded `"platform"` field against the
        // caller-supplied platform via `debug_assert_eq!`, which release builds compile
        // out. This test independently parses the raw JSON so a stale/copy-pasted
        // `"platform"` value is caught by the test suite regardless of build profile.
        for platform in Platform::ALL {
            let raw = Driver::rules_json_for_platform(platform);
            let value: serde_json::Value =
                serde_json::from_str(raw).expect("valid embedded platform rules JSON");
            let embedded_platform: Platform = serde_json::from_value(value["platform"].clone())
                .expect("embedded rules JSON must have a valid \"platform\" field");
            assert_eq!(
                embedded_platform, platform,
                "embedded \"platform\" field in {platform:?}'s rules JSON does not match"
            );
        }
    }

    #[test]
    fn test_declaration_prefix_platforms() {
        assert_eq!(
            Driver::for_platform(Platform::JuniperJunos).declaration_prefix,
            "set "
        );
        assert_eq!(
            Driver::for_platform(Platform::Vyos).declaration_prefix,
            "set "
        );
        assert_eq!(
            Driver::for_platform(Platform::NokiaSrl).declaration_prefix,
            "set "
        );
        assert_eq!(
            Driver::for_platform(Platform::FortinetFortios).declaration_prefix,
            "set "
        );
        assert_eq!(
            Driver::for_platform(Platform::CiscoIos).declaration_prefix,
            ""
        );
        assert_eq!(
            Driver::for_platform(Platform::Generic).declaration_prefix,
            ""
        );
    }

    #[test]
    fn test_try_swap_negation_junos() {
        let driver = Driver::for_platform(Platform::JuniperJunos);
        assert_eq!(
            driver.try_swap_negation("set vlans test_vlan vlan-id 100"),
            Ok("delete vlans test_vlan vlan-id 100".to_string())
        );
        assert_eq!(
            driver.try_swap_negation("delete vlans test_vlan vlan-id 100"),
            Ok("set vlans test_vlan vlan-id 100".to_string())
        );
        assert!(
            driver
                .try_swap_negation("vlans test_vlan vlan-id 100")
                .is_err()
        );
        let err = driver
            .try_swap_negation("vlans test_vlan vlan-id 100")
            .unwrap_err();
        assert!(err.contains("did not start with"));
        assert!(err.contains("delete "));
        assert!(err.contains("set "));
    }

    #[test]
    fn test_try_swap_negation_fortinet() {
        let driver = Driver::for_platform(Platform::FortinetFortios);
        assert_eq!(
            driver.try_swap_negation("set ip 10.0.0.1 255.255.255.0"),
            Ok("unset ip".to_string())
        );
        assert_eq!(
            driver.try_swap_negation("unset ip"),
            Ok("set ip".to_string())
        );
    }

    #[test]
    fn test_try_swap_negation_vyos_and_nokia_srl_no_match_returns_unchanged() {
        for platform in [Platform::Vyos, Platform::NokiaSrl] {
            let driver = Driver::for_platform(platform);
            assert_eq!(
                driver.try_swap_negation("interfaces ethernet eth0 address 192.168.1.1/24"),
                Ok("interfaces ethernet eth0 address 192.168.1.1/24".to_string())
            );
        }
    }

    #[test]
    fn test_try_swap_negation_huawei() {
        let driver = Driver::for_platform(Platform::HuaweiVrp);
        assert_eq!(
            driver.try_swap_negation("undo description Uplink"),
            Ok("description Uplink".to_string())
        );
        assert_eq!(
            driver.try_swap_negation("description Uplink"),
            Ok("undo description".to_string())
        );
        assert_eq!(
            driver.try_swap_negation("alias test"),
            Ok("undo alias".to_string())
        );
        assert_eq!(
            driver.try_swap_negation("rule 5 remark Important rule"),
            Ok("undo rule 5 remark".to_string())
        );
    }

    #[test]
    fn test_cached_for_platform_reuses_the_same_instance_and_matches_for_platform() {
        let cached_first = Driver::cached_for_platform(Platform::CiscoIos);
        let cached_second = Driver::cached_for_platform(Platform::CiscoIos);
        assert!(Arc::ptr_eq(&cached_first, &cached_second));
        assert_eq!(*cached_first, Driver::for_platform(Platform::CiscoIos));
    }
}
