//! Exception types and error conversions for `PyO3` bindings.

use hier_config_core::formats::FormatError;
use hier_config_core::tree::TreeError;
use pyo3::exceptions::{PyException, PyRecursionError, PyValueError};
use pyo3::prelude::*;
use pyo3_stub_gen::create_exception;

create_exception!(
    hier_config._hier_config_rust,
    HierConfigError,
    PyException,
    "Base exception for hierarchical configuration errors."
);
create_exception!(
    hier_config._hier_config_rust,
    DuplicateChildError,
    HierConfigError,
    "A child with this text already exists in the destination."
);
create_exception!(
    hier_config._hier_config_rust,
    InvalidConfigError,
    HierConfigError,
    "The supplied configuration is malformed."
);

/// Converts a core [`TreeError`] into the matching Python exception.
///
/// The message always comes from the error's `Display` impl so the Rust and
/// Python surfaces cannot drift apart; only the exception *type* is chosen here.
pub(crate) fn to_py_err(err: TreeError) -> PyErr {
    let message = err.to_string();
    match err {
        TreeError::DuplicateChild(_) => DuplicateChildError::new_err(message),
        TreeError::UnterminatedBanner(_) => InvalidConfigError::new_err(message),
        // v3 hit Python's own recursion limit on pathologically deep configs;
        // the explicit depth guard keeps that observable behaviour.
        TreeError::MaxDepthExceeded(_) => PyRecursionError::new_err(message),
        _ => PyValueError::new_err(message),
    }
}

/// Converts a core [`FormatError`] into the matching Python exception.
///
/// A malformed document is an `InvalidConfigError`; a tree failure keeps the
/// type it would have had outside the format layer, so e.g. duplicate array
/// entries still raise `DuplicateChildError`.
pub(crate) fn format_err(err: &FormatError) -> PyErr {
    match err {
        FormatError::Invalid(message) => InvalidConfigError::new_err(message.clone()),
        FormatError::Tree(error) => to_py_err(error.clone()),
    }
}

#[cfg(test)]
mod tests {
    use super::{DuplicateChildError, InvalidConfigError, to_py_err};
    use hier_config_core::tree::{MAX_TREE_DEPTH, TreeError};
    use pyo3::exceptions::{PyRecursionError, PyValueError};
    use pyo3::prelude::*;

    #[test]
    fn max_depth_exceeded_maps_to_recursion_error() {
        Python::initialize();
        Python::attach(|py| {
            let err = to_py_err(TreeError::MaxDepthExceeded(MAX_TREE_DEPTH));

            assert!(err.is_instance_of::<PyRecursionError>(py));
            assert!(err.to_string().contains(&MAX_TREE_DEPTH.to_string()));
        });
    }

    #[test]
    fn other_tree_errors_keep_their_existing_mapping() {
        Python::initialize();
        Python::attach(|py| {
            let duplicate = to_py_err(TreeError::DuplicateChild(vec!["acl".to_owned()]));
            let banner = to_py_err(TreeError::UnterminatedBanner("banner motd".to_owned()));

            assert!(duplicate.is_instance_of::<DuplicateChildError>(py));
            assert!(banner.is_instance_of::<InvalidConfigError>(py));
            assert!(!duplicate.is_instance_of::<PyValueError>(py));
        });
    }
}
