//! Process-wide cache of compiled regular expressions.
//!
//! Rule evaluation, parsing and remediation all match the same handful of patterns
//! against every line and every node of a configuration. Compiling a regex costs
//! orders of magnitude more than running it, so compiling on each use dominates the
//! runtime of every traversal. Patterns are compiled once here and shared thereafter.
//!
//! Failures are cached too: an invalid pattern stays invalid, and callers treat a
//! `None` result exactly as they previously treated a compilation error.

use std::collections::HashMap;
use std::sync::{Arc, OnceLock, RwLock};

type Cache<T> = RwLock<HashMap<Box<str>, Option<Arc<T>>>>;

fn lookup<T, F>(cache: &Cache<T>, pattern: &str, compile: F) -> Option<Arc<T>>
where
    F: FnOnce(&str) -> Option<T>,
{
    if let Some(cached) = cache.read().unwrap().get(pattern) {
        return cached.clone();
    }

    let compiled = compile(pattern).map(Arc::new);
    cache
        .write()
        .unwrap()
        .insert(pattern.into(), compiled.clone());
    compiled
}

/// Returns a compiled [`regex::Regex`], or `None` when the pattern is invalid.
pub fn regex(pattern: &str) -> Option<Arc<regex::Regex>> {
    static CACHE: OnceLock<Cache<regex::Regex>> = OnceLock::new();
    let cache = CACHE.get_or_init(|| RwLock::new(HashMap::new()));
    lookup(cache, pattern, |p| regex::Regex::new(p).ok())
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
/// The set is keyed on the patterns joined by a NUL byte, which cannot occur inside a
/// pattern, so distinct rule sets never collide.
pub fn regex_set<'a, I>(patterns: I) -> Option<Arc<regex::RegexSet>>
where
    I: IntoIterator<Item = &'a str>,
{
    static CACHE: OnceLock<Cache<regex::RegexSet>> = OnceLock::new();
    let cache = CACHE.get_or_init(|| RwLock::new(HashMap::new()));
    let key = patterns.into_iter().collect::<Vec<_>>().join("\0");
    lookup(cache, &key, |k| regex::RegexSet::new(k.split('\0')).ok())
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
}
