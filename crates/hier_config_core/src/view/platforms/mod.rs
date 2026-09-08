//! Per-platform view hooks.
//!
//! Each module supplies the [`ConfigOps`] and
//! [`InterfaceOps`](crate::view::interface::InterfaceOps) implementations for
//! one platform, mirroring the corresponding Python view classes.

pub mod arista_eos;
pub mod aruba_aoscx;
pub mod cisco_ios;
pub mod cisco_nxos;
pub mod cisco_xr;
pub mod hp_procurve;

use crate::models::Platform;
use crate::view::config::ConfigOps;

/// The view hooks for `platform`, when it has a view implementation.
///
/// Platforms without a Python view sibling return `None` so that Rust cannot
/// grow a view surface that no shared test corpus can verify.
#[must_use]
pub fn view_ops_for_platform(platform: Platform) -> Option<&'static dyn ConfigOps> {
    crate::platforms::platform_ops(platform).view_ops()
}

#[cfg(test)]
mod tests {
    use super::{Platform, view_ops_for_platform};

    /// Platforms whose Python `hier_config/platforms/<name>/view.py` exists.
    const PLATFORMS_WITH_VIEWS: [Platform; 6] = [
        Platform::AristaEos,
        Platform::ArubaAoscx,
        Platform::CiscoIos,
        Platform::CiscoNxos,
        Platform::CiscoXr,
        Platform::HpProcurve,
    ];

    #[test]
    fn every_platform_with_a_python_view_dispatches() {
        for platform in PLATFORMS_WITH_VIEWS {
            assert!(
                view_ops_for_platform(platform).is_some(),
                "{platform:?} has a Python view but no native view hooks"
            );
        }
    }

    #[test]
    fn view_less_platforms_return_none() {
        for platform in Platform::ALL {
            if PLATFORMS_WITH_VIEWS.contains(&platform) {
                continue;
            }
            assert!(
                view_ops_for_platform(platform).is_none(),
                "{platform:?} has no Python view, so it must not expose native \
                 view hooks that no shared corpus can verify"
            );
        }
    }

    #[test]
    fn dispatch_is_stable_across_calls() {
        for platform in PLATFORMS_WITH_VIEWS {
            let first = view_ops_for_platform(platform).expect("hooks");
            let second = view_ops_for_platform(platform).expect("hooks");
            assert!(std::ptr::eq(first, second), "{platform:?} hooks are static");
        }
    }
}
