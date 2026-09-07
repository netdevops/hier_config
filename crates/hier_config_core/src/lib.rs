//! Core data model and algorithms for hierarchical configuration tree manipulation.
//!
//! Provides the arena-based [`Tree`] data structure, high-performance string matching
//! via [`TextMatch`], parsing, rule evaluation, and hierarchical remediation diffing.

#![forbid(unsafe_code)]

pub mod arena;
pub mod constructors;
pub mod driver;
pub mod formats;
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
pub use constructors::{
    ConstructorError, StructuredFormat, config_from_text, config_view, detect_structured_format,
    reject_structured_format,
};
pub use driver::{Driver, DriverRules};
pub use formats::{
    FormatError, GnmiRemediation, from_json, from_json_value, from_xml, to_gnmi_json, to_json,
    to_netconf_xml, to_xml,
};
pub use models::*;
pub use parser::{
    ParserCursor, config_preprocessor, convert_to_set_commands, from_dump, load_fast,
    load_fast_with_callbacks, load_from_str, load_from_str_with_callbacks, parse_fast,
    parse_fast_with_callbacks, parse_tree, parse_tree_with_callbacks,
};
pub use text_match::TextMatch;
pub use tree::{Children, Node, Tree, TreeError};
pub use view::config::{ConfigOps, ConfigView};
pub use view::interface::{InterfaceOps, InterfaceView};
pub use view::models::{
    InterfaceDot1qMode, InterfaceDuplex, Ipv4Interface, NacHostMode, StackMember, Vlan,
};
pub use view::view_ops_for_platform;
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
