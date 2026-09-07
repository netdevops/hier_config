//! Exception types and error conversions for `PyO3` bindings.

use hier_config_core::tree::TreeError;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;

create_exception!(_hier_config_rust, HierConfigError, PyException);
create_exception!(_hier_config_rust, DuplicateChildError, HierConfigError);

/// Converts a core [`TreeError`] into the matching Python exception.
///
/// The message always comes from the error's `Display` impl so the Rust and
/// Python surfaces cannot drift apart; only the exception *type* is chosen here.
pub(crate) fn to_py_err(err: TreeError) -> PyErr {
    let message = err.to_string();
    if matches!(err, TreeError::DuplicateChild(_)) {
        DuplicateChildError::new_err(message)
    } else {
        PyValueError::new_err(message)
    }
}
