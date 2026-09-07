//! Structured-config interchange: JSON, XML, NETCONF, and gNMI.
//!
//! Network devices increasingly speak structured config over NETCONF and gNMI
//! rather than CLI text. These modules map such documents onto the same
//! [`Tree`](crate::Tree) the CLI parsers produce, so the remediation engine
//! diffs them with no special-casing, and then render the resulting
//! remediation back out in the wire format the device expects.
//!
//! The tree encoding is textual but lossless:
//!
//! | Source construct         | Node text                  |
//! |--------------------------|----------------------------|
//! | object member (branch)   | `key`                      |
//! | scalar member            | `key <json-scalar>`        |
//! | keyed array entry        | `key <json-scalar-of-key>` |
//! | XML attribute            | `@name <json-string>`      |
//! | XML mixed text           | `#text <json-string>`      |

mod gnmi;
mod json;
mod netconf;
mod value;
mod xml;

pub use gnmi::{GnmiRemediation, to_gnmi_json};
pub use json::{from_json, from_json_value, to_json};
pub use netconf::to_netconf_xml;
pub use xml::{from_xml, to_xml};

/// Members consulted, in order, to identify an array entry or repeated element.
pub const DEFAULT_LIST_KEYS: [&str; 2] = ["name", "id"];

/// The NETCONF base namespace bound to the `nc:` prefix on rendered output.
pub const NETCONF_BASE_NS: &str = "urn:ietf:params:xml:ns:netconf:base:1.0";

/// A structured document could not be mapped to or from a config tree.
///
/// Tree failures keep their [`TreeError`](crate::TreeError) identity rather
/// than collapsing to a message, so callers (and the Python bindings) can
/// still distinguish e.g. a duplicate child from a malformed document.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FormatError {
    /// The document itself cannot be mapped onto a config tree.
    Invalid(String),
    /// Building the tree failed.
    Tree(crate::TreeError),
}

impl std::fmt::Display for FormatError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Invalid(message) => f.write_str(message),
            Self::Tree(error) => error.fmt(f),
        }
    }
}

impl std::error::Error for FormatError {}

impl From<crate::TreeError> for FormatError {
    fn from(error: crate::TreeError) -> Self {
        Self::Tree(error)
    }
}

/// Resolves caller-supplied list keys, falling back to [`DEFAULT_LIST_KEYS`].
pub(crate) fn resolve_list_keys(list_keys: Option<&[String]>) -> Vec<String> {
    list_keys.map_or_else(
        || DEFAULT_LIST_KEYS.iter().map(|&k| (*k).to_owned()).collect(),
        <[String]>::to_vec,
    )
}
