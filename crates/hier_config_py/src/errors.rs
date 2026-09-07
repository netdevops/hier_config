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
    match err {
        TreeError::DuplicateChild(_) => DuplicateChildError::new_err(message),
        // `InvalidConfigError` is defined in Python, so it can only be raised by
        // importing it at the point of failure.
        TreeError::UnterminatedBanner(_) => Python::with_gil(|py| {
            python_error(py, "InvalidConfigError", &message)
                .unwrap_or_else(|| PyValueError::new_err(message))
        }),
        _ => PyValueError::new_err(message),
    }
}

/// Instantiates one of the Python-side exception classes from `hier_config`.
///
/// Returns `None` when the class cannot be imported so callers can fall back
/// to a native exception rather than masking the original failure.
pub(crate) fn python_error(py: Python<'_>, name: &str, message: &str) -> Option<PyErr> {
    let cls = py
        .import("hier_config.exceptions")
        .and_then(|m| m.getattr(name))
        .ok()?;
    let instance = cls.call1((message,)).ok()?;
    Some(PyErr::from_value(instance))
}
