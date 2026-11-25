//! One-call entry points for standalone Rust use.
//!
//! These mirror the helpers in `hier_config/constructors.py` so a Rust-only
//! consumer gets the same guard rails as a Python one: structured formats are
//! rejected with the same message rather than being silently mis-parsed as CLI
//! text, and a parsed tree can be turned into a structured view in one step.

use std::fmt;

use crate::models::Platform;
use crate::tree::{Tree, TreeError};
use crate::view::config::ConfigView;
use crate::view::view_ops_for_platform;

/// A structured configuration format the indented-CLI parser cannot ingest.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StructuredFormat {
    /// A JSON document.
    Json,
    /// An XML document.
    Xml,
}

impl StructuredFormat {
    /// The format's name as it appears in the rejection message.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Json => "JSON",
            Self::Xml => "XML",
        }
    }
}

impl fmt::Display for StructuredFormat {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// An error raised by the one-call constructors.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConstructorError {
    /// The text is a structured document, not indented CLI configuration.
    StructuredConfig(StructuredFormat),
    /// The text is CLI configuration but could not be parsed.
    Tree(TreeError),
}

impl fmt::Display for ConstructorError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::StructuredConfig(format) => write!(
                f,
                "The config appears to be {format}. Use HConfig.from_xml() or \
HConfig.from_json() for structured formats, or convert to the platform's \
indented CLI text (set-style configs are supported natively by the Juniper \
JunOS, VyOS, and Nokia SRL drivers)."
            ),
            Self::Tree(error) => error.fmt(f),
        }
    }
}

impl std::error::Error for ConstructorError {}

impl From<TreeError> for ConstructorError {
    fn from(error: TreeError) -> Self {
        Self::Tree(error)
    }
}

/// The number of leading characters inspected when sniffing a format.
const SNIFF_LEN: usize = 64;

/// Detects a structured configuration format the text parser cannot ingest.
///
/// Mirrors `hier_config.constructors._detect_structured_format`: only the
/// leading characters are inspected, and a JSON verdict additionally requires
/// the whole document to parse, so a CLI config that merely opens with a brace
/// is not misreported.
#[must_use]
pub fn detect_structured_format(config_text: &str) -> Option<StructuredFormat> {
    // Python slices by character, not byte, so take chars to stay identical
    // on non-ASCII input.
    let prefix: String = config_text.chars().take(SNIFF_LEN).collect();
    let prefix = prefix.trim_start();

    if prefix.starts_with('<') {
        return Some(StructuredFormat::Xml);
    }
    if prefix.starts_with(['{', '['])
        && serde_json::from_str::<serde_json::Value>(config_text).is_ok()
    {
        return Some(StructuredFormat::Json);
    }
    None
}

/// Rejects `config_text` when it is a structured document.
///
/// # Errors
///
/// Returns [`ConstructorError::StructuredConfig`] when the text looks like JSON
/// or XML rather than indented CLI configuration.
pub fn reject_structured_format(config_text: &str) -> Result<(), ConstructorError> {
    detect_structured_format(config_text).map_or(Ok(()), |format| {
        Err(ConstructorError::StructuredConfig(format))
    })
}

/// Parses `config_text` as indented CLI configuration for `platform`.
///
/// This is the Rust counterpart of `HConfig.from_text`: it applies the same
/// structured-format guard before parsing.
///
/// # Errors
///
/// Returns an error when the text is a structured document or cannot be parsed.
pub fn config_from_text(platform: Platform, config_text: &str) -> Result<Tree, ConstructorError> {
    reject_structured_format(config_text)?;
    Ok(Tree::from_str(platform, config_text)?)
}

/// Builds a structured view over `tree`, when its platform has one.
///
/// Returns `None` for platforms that deliberately have no view implementation.
#[must_use]
pub fn config_view(tree: &Tree) -> Option<ConfigView<'_>> {
    view_ops_for_platform(tree.driver.platform).map(|ops| ConfigView::new(tree, ops))
}

#[cfg(test)]
mod tests {
    use super::{
        ConstructorError, StructuredFormat, config_from_text, config_view,
        detect_structured_format, reject_structured_format,
    };
    use crate::models::Platform;

    #[test]
    fn detects_json_documents() {
        assert_eq!(
            detect_structured_format(r#"{"interfaces": []}"#),
            Some(StructuredFormat::Json)
        );
        assert_eq!(
            detect_structured_format("  [\n  1,\n  2\n]\n"),
            Some(StructuredFormat::Json)
        );
    }

    #[test]
    fn detects_xml_documents() {
        assert_eq!(
            detect_structured_format("<?xml version=\"1.0\"?><config/>"),
            Some(StructuredFormat::Xml)
        );
    }

    #[test]
    fn leaves_cli_text_alone() {
        assert_eq!(detect_structured_format("hostname sw1\n"), None);
        assert_eq!(detect_structured_format(""), None);
        // Opens like JSON but is not valid JSON, so it stays CLI text.
        assert_eq!(detect_structured_format("{ not json\n"), None);
        // A set-style config is CLI text even though it is machine-ish.
        assert_eq!(detect_structured_format("set system host-name sw1\n"), None);
    }

    #[test]
    fn rejection_message_matches_python() {
        let error = reject_structured_format("{}").expect_err("rejected");
        assert_eq!(
            error.to_string(),
            "The config appears to be JSON. Use HConfig.from_xml() or \
HConfig.from_json() for structured formats, or convert to the platform's \
indented CLI text (set-style configs are supported natively by the Juniper \
JunOS, VyOS, and Nokia SRL drivers)."
        );
    }

    #[test]
    fn config_from_text_guards_then_parses() {
        let error = config_from_text(Platform::CiscoIos, "<config/>")
            .expect_err("structured config is rejected");
        assert_eq!(
            error,
            ConstructorError::StructuredConfig(StructuredFormat::Xml)
        );

        let tree = config_from_text(Platform::CiscoIos, "hostname sw1\n").expect("cli text parses");
        assert_eq!(tree.driver.platform, Platform::CiscoIos);
    }

    #[test]
    fn config_view_follows_platform_support() {
        let ios = config_from_text(Platform::CiscoIos, "hostname sw1\n").expect("parses");
        let view = config_view(&ios).expect("cisco_ios has a view");
        assert_eq!(view.hostname().as_deref(), Some("sw1"));

        let generic = config_from_text(Platform::Generic, "hostname sw1\n").expect("parses");
        assert!(config_view(&generic).is_none());
    }
}
