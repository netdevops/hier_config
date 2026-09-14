//! Process-wide cache of compiled regular expressions.
//!
//! Rule evaluation, parsing and remediation all match the same handful of patterns
//! against every line and every node of a configuration. Compiling a regex costs
//! orders of magnitude more than running it, so compiling on each use dominates the
//! runtime of every traversal. Patterns are compiled once here and shared thereafter.
//!
//! Each engine retains at most 512 entries, including failed compilations.

use std::collections::HashMap;
use std::sync::{Arc, OnceLock, RwLock};

type Cache<T> = RwLock<HashMap<Box<str>, Option<Arc<T>>>>;
const CACHE_CAPACITY: usize = 512;

fn lookup<T, F>(cache: &Cache<T>, pattern: &str, compile: F) -> Option<Arc<T>>
where
    F: FnOnce(&str) -> Option<T>,
{
    if let Some(cached) = cache.read().unwrap().get(pattern) {
        return cached.clone();
    }

    let compiled = compile(pattern).map(Arc::new);
    let mut entries = cache.write().unwrap();
    // Another thread may have compiled the same pattern while the lock was released.
    if let Some(cached) = entries.get(pattern) {
        return cached.clone();
    }
    if entries.len() >= CACHE_CAPACITY
        && let Some(key) = entries.keys().next().cloned()
    {
        entries.remove(&key);
    }
    entries.insert(pattern.into(), compiled.clone());
    compiled
}

/// Returns a compiled [`regex::Regex`], or `None` when the pattern is invalid.
pub fn regex(pattern: &str) -> Option<Arc<regex::Regex>> {
    static CACHE: OnceLock<Cache<regex::Regex>> = OnceLock::new();
    let cache = CACHE.get_or_init(|| RwLock::new(HashMap::new()));
    lookup(cache, pattern, |p| regex::Regex::new(p).ok())
}

/// Compiles a rule pattern, rejecting syntax that the linear-time engine cannot
/// implement rather than silently omitting a user-supplied rule.
///
/// # Errors
///
/// Returns a descriptive error for invalid or unsupported syntax.
pub fn rule_regex(pattern: &str) -> Result<Arc<regex::Regex>, String> {
    regex(pattern).ok_or_else(|| {
        format!(
            "invalid or unsupported rule regex {pattern:?}; \
             substitutions, idempotency keys and object names require Rust regex syntax"
        )
    })
}

/// Matching-only patterns can use bounded backtracking for lookaround.
#[derive(Clone, Debug)]
pub enum MatchRegex {
    Linear(Arc<regex::Regex>),
    Backtracking(Arc<fancy_regex::Regex>),
}

impl MatchRegex {
    /// # Errors
    ///
    /// Rejects patterns unsupported by either engine.
    pub fn cached(pattern: &str) -> Result<Self, String> {
        regex(pattern)
            .map(Self::Linear)
            .or_else(|| fancy(pattern).map(Self::Backtracking))
            .ok_or_else(|| format!("invalid or unsupported regex {pattern:?}"))
    }

    /// # Errors
    ///
    /// Reports bounded-backtracking failures instead of treating them as nonmatches.
    pub fn is_match(&self, text: &str) -> Result<bool, String> {
        match self {
            Self::Linear(re) => Ok(re.is_match(text)),
            Self::Backtracking(re) => re
                .is_match(text)
                .map_err(|error| format!("regex evaluation failed for {:?}: {error}", re.as_str())),
        }
    }
}

/// Converts a Python `re.sub` replacement to the Rust engine's template syntax.
///
/// # Errors
///
/// Rejects malformed escapes and references to groups absent from `re`.
pub fn python_replacement(re: &regex::Regex, replacement: &str) -> Result<String, String> {
    use std::fmt::Write as _;

    let mut output = String::new();
    let mut chars = replacement.chars().peekable();
    while let Some(character) = chars.next() {
        if character == '$' {
            output.push_str("$$");
            continue;
        }
        if character != '\\' {
            output.push(character);
            continue;
        }
        let escaped = chars.next().ok_or("trailing backslash in replacement")?;
        if let Some(literal) = replacement_literal_escape(escaped) {
            output.push(literal);
            continue;
        }
        let group = match escaped {
            'g' => {
                if chars.next() != Some('<') {
                    return Err("expected < after \\g in replacement".into());
                }
                let mut group = String::new();
                loop {
                    match chars.next() {
                        Some('>') => break,
                        Some(c) => group.push(c),
                        None => return Err("unterminated \\g<...> in replacement".into()),
                    }
                }
                group
            }
            '0'..='9' => {
                let mut digits = String::from(escaped);
                if escaped == '0' {
                    for _ in 0..2 {
                        if let Some(c @ '0'..='7') = chars.peek().copied() {
                            digits.push(c);
                            chars.next();
                        } else {
                            break;
                        }
                    }
                    let value = u8::from_str_radix(&digits, 8).map_err(|e| e.to_string())?;
                    output.push(char::from(value));
                    continue;
                }
                if let Some(c @ '0'..='9') = chars.peek().copied() {
                    digits.push(c);
                    chars.next();
                }
                if digits.len() == 2
                    && digits.chars().all(|c| ('0'..='7').contains(&c))
                    && let Some(c @ '0'..='7') = chars.peek().copied()
                {
                    digits.push(c);
                    chars.next();
                    let value = u8::from_str_radix(&digits, 8)
                        .map_err(|_| "octal replacement escape exceeds 0o377")?;
                    output.push(char::from(value));
                    continue;
                }
                digits
            }
            c if c.is_ascii_alphabetic() => {
                return Err(format!("unsupported replacement escape \\{c}"));
            }
            c => {
                output.push('\\');
                if c == '$' {
                    output.push('$');
                }
                output.push(c);
                continue;
            }
        };
        let group = if !group.is_empty() && group.bytes().all(|c| c.is_ascii_digit()) {
            let index = group.parse::<usize>().map_err(|e| e.to_string())?;
            if index >= re.captures_len() {
                return Err(format!("invalid replacement group {group:?}"));
            }
            index.to_string()
        } else {
            if !re.capture_names().flatten().any(|name| name == group) {
                return Err(format!("unknown replacement group {group:?}"));
            }
            group
        };
        write!(output, "${{{group}}}").expect("writing to String cannot fail");
    }
    Ok(output)
}

const fn replacement_literal_escape(escaped: char) -> Option<char> {
    match escaped {
        '\\' => Some('\\'),
        'a' => Some('\x07'),
        'b' => Some('\x08'),
        'f' => Some('\x0c'),
        'n' => Some('\n'),
        'r' => Some('\r'),
        't' => Some('\t'),
        'v' => Some('\x0b'),
        _ => None,
    }
}

/// Compiles a one-off [`regex::Regex`] that is deliberately **not** cached, or
/// `None` when the pattern is invalid.
///
/// Some patterns interpolate input-controlled text (for example an object name),
/// so they are effectively unique on every call. Routing those through the
/// process-wide cache would never produce a hit and would grow the cache without
/// bound on attacker-controlled input. Compile such a pattern once here, outside
/// any per-node loop, so this stays off the hot path.
pub fn compile_uncached(pattern: &str) -> Option<regex::Regex> {
    regex::Regex::new(pattern).ok()
}

/// Returns a compiled [`regex::RegexSet`] for `patterns`, or `None` when any is invalid.
///
/// JSON encoding keeps the cache key unambiguous even if a pattern contains NUL.
///
/// # Panics
///
/// Panics if the cache lock is poisoned or serializing strings unexpectedly fails.
pub fn regex_set<'a, I>(patterns: I) -> Option<Arc<regex::RegexSet>>
where
    I: IntoIterator<Item = &'a str>,
{
    static CACHE: OnceLock<Cache<regex::RegexSet>> = OnceLock::new();
    let cache = CACHE.get_or_init(|| RwLock::new(HashMap::new()));
    let patterns: Vec<_> = patterns.into_iter().collect();
    let key = serde_json::to_string(&patterns).expect("strings are JSON serializable");
    lookup(cache, &key, |_| regex::RegexSet::new(&patterns).ok())
}

/// Returns a compiled [`fancy_regex::Regex`], or `None` when the pattern is invalid.
///
/// Used only for patterns the default engine rejects, such as those with lookaround.
///
/// A `backtrack_limit` caps the backtracking work fancy-regex will do on a single
/// match attempt, so a pathological pattern/input pair (catastrophic backtracking)
/// fails the match with an error the callers already treat as "no match" instead of
/// hanging the process.
pub fn fancy(pattern: &str) -> Option<Arc<fancy_regex::Regex>> {
    /// Maximum backtracking steps per match. Config lines are short, so legitimate
    /// lookaround/backreference patterns stay far below this; catastrophic backtracking
    /// hits it and bails out.
    const BACKTRACK_LIMIT: usize = 100_000;

    static CACHE: OnceLock<Cache<fancy_regex::Regex>> = OnceLock::new();
    let cache = CACHE.get_or_init(|| RwLock::new(HashMap::new()));
    lookup(cache, pattern, |p| {
        fancy_regex::RegexBuilder::new(p)
            .backtrack_limit(BACKTRACK_LIMIT)
            .build()
            .ok()
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compiles_and_reuses_the_same_instance() {
        let first = regex(r"^interface \S+$").expect("valid pattern");
        let second = regex(r"^interface \S+$").expect("valid pattern");
        assert!(Arc::ptr_eq(&first, &second));
        assert!(first.is_match("interface Ethernet1"));
    }

    #[test]
    fn invalid_patterns_return_none_and_stay_cached() {
        assert!(regex("(unclosed").is_none());
        assert!(regex("(unclosed").is_none());
    }

    #[test]
    fn regex_sets_are_cached_and_keyed_on_all_patterns() {
        let first = regex_set(["^foo", "^bar"]).expect("valid patterns");
        let second = regex_set(["^foo", "^bar"]).expect("valid patterns");
        assert!(Arc::ptr_eq(&first, &second));
        assert!(first.is_match("foobar"));

        let different = regex_set(["^foo"]).expect("valid patterns");
        assert!(!Arc::ptr_eq(&first, &different));
        assert!(!different.is_match("bar"));
    }

    #[test]
    fn fancy_supports_lookaround() {
        let re = fancy(r"^foo(?!bar)").expect("valid pattern");
        assert!(re.is_match("foobaz").unwrap_or(false));
        assert!(!re.is_match("foobar").unwrap_or(true));
    }

    #[test]
    fn cache_bounds_successes_and_failures_without_invalidating_live_references() {
        let cache = RwLock::new(HashMap::new());
        let retained = lookup(&cache, "original", |_| Some(42)).unwrap();
        for i in 0..CACHE_CAPACITY * 3 {
            lookup(&cache, &format!("pattern-{i}"), |_| {
                (i % 2 == 0).then_some(i)
            });
            assert!(cache.read().unwrap().len() <= CACHE_CAPACITY);
        }
        assert_eq!(*retained, 42);
        assert!(cache.read().unwrap().values().any(Option::is_none));
    }

    #[test]
    fn regex_set_keys_distinguish_embedded_nul_from_multiple_patterns() {
        let single = regex_set(["foo\0bar"]).unwrap();
        let multiple = regex_set(["foo", "bar"]).unwrap();
        assert!(!single.is_match("foo"));
        assert!(multiple.is_match("foo"));
    }
}
