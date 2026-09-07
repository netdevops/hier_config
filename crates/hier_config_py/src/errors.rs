//! Exception types and error conversions for `PyO3` bindings.

use hier_config_core::formats::FormatError;
use hier_config_core::tree::TreeError;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;

create_exception!(_hier_config_rust, HierConfigError, PyException);
create_exception!(_hier_config_rust, DuplicateChildError, HierConfigError);
create_exception!(_hier_config_rust, InvalidConfigError, HierConfigError);

/// Converts a core [`TreeError`] into the matching Python exception.
///
/// The message always comes from the error's `Display` impl so the Rust and
/// Python surfaces cannot drift apart; only the exception *type* is chosen here.
pub(crate) fn to_py_err(err: TreeError) -> PyErr {
    let message = err.to_string();
    match err {
        TreeError::DuplicateChild(_) => DuplicateChildError::new_err(message),
        TreeError::UnterminatedBanner(_) => InvalidConfigError::new_err(message),
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
