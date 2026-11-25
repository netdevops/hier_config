//! Fast string predicate matching (equals, startswith, endswith, contains, regex).

/// High-performance string predicate matcher with cached regex support.
#[derive(Debug, Clone, Copy)]
pub struct TextMatch;

impl TextMatch {
    #[inline]
    pub fn equals(target: &str, expression: &str) -> bool {
        target == expression
    }

    #[inline]
    pub fn startswith(target: &str, expression: &str) -> bool {
        target.starts_with(expression)
    }

    #[inline]
    pub fn endswith(target: &str, expression: &str) -> bool {
        target.ends_with(expression)
    }

    #[inline]
    pub fn contains(target: &str, expression: &str) -> bool {
        target.contains(expression)
    }

    #[inline]
    pub fn contains_or_endswith(target: &str, expression: &str) -> bool {
        Self::contains(target, expression) || Self::endswith(target, expression)
    }

    /// Matches `target` against `pattern`, reusing the process-wide compiled-regex cache.
    ///
    /// Rules are evaluated against every node, so compiling here would dominate the
    /// cost of a traversal.
    /// # Errors
    ///
    /// Returns [`regex::Error`] if `pattern` is not a valid regular expression.
    pub fn re_search(target: &str, pattern: &str) -> Result<bool, regex::Error> {
        let re = crate::regex_cache::regex(pattern)
            .ok_or_else(|| regex::Error::Syntax(format!("invalid pattern: {pattern}")))?;
        Ok(re.is_match(target))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_predicates() {
        assert!(TextMatch::equals("vlan 10", "vlan 10"));
        assert!(!TextMatch::equals("vlan 10", "vlan 20"));

        assert!(TextMatch::startswith(
            "interface GigabitEthernet0/1",
            "interface"
        ));
        assert!(!TextMatch::startswith(
            "interface GigabitEthernet0/1",
            "router"
        ));

        assert!(TextMatch::endswith("no shutdown", "shutdown"));
        assert!(!TextMatch::endswith("no shutdown", "up"));

        assert!(TextMatch::contains(
            "ip address 10.0.0.1 255.255.255.0",
            "10.0.0.1"
        ));
        assert!(!TextMatch::contains(
            "ip address 10.0.0.1 255.255.255.0",
            "192.168"
        ));

        assert!(TextMatch::re_search("interface GigabitEthernet0/1", r"^interface\s+\S+").unwrap());
        assert!(!TextMatch::re_search("router ospf 1", r"^interface\s+\S+").unwrap());
    }
}
