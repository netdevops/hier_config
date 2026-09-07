//! Core data model and algorithms for hierarchical configuration tree manipulation.
//!
//! Provides the arena-based [`Tree`] data structure, high-performance string matching
//! via [`TextMatch`], parsing, rule evaluation, and hierarchical remediation diffing.

#![forbid(unsafe_code)]

pub mod arena;
pub mod driver;
pub mod models;
pub mod parser;
pub mod platforms;
pub mod post_load;
pub mod regex_cache;
pub mod remediation;
pub mod text_match;
pub mod tree;
pub mod view;
pub mod workflow;

pub use arena::{Arena, NodeId};
pub use driver::{Driver, DriverRules};
pub use models::*;
pub use parser::{
    config_preprocessor, convert_to_set_commands, from_dump, load_fast, load_fast_with_callbacks,
    load_from_str, load_from_str_with_callbacks,
};
pub use text_match::TextMatch;
pub use tree::{Children, Node, Tree, TreeError};
pub use workflow::{WorkflowError, WorkflowRemediation};

/// Placeholder version check
pub const fn core_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_core_version() {
        // Tracks the crate version rather than a literal so pre-release bumps
        // (e.g. "4.0.0-beta.4") don't require editing this assertion.
        assert_eq!(core_version(), env!("CARGO_PKG_VERSION"));
        assert!(core_version().starts_with("4."));
    }
}
