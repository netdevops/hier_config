pub mod arista_eos;
pub mod aruba_aoscx;
pub mod cisco_ios;
pub mod cisco_nxos;
pub mod cisco_xr;
pub mod fortinet_fortios;
pub mod functions;
pub mod generic;
pub mod hp_comware5;
pub mod hp_procurve;
pub mod huawei_vrp;
pub mod juniper_junos;
pub mod nokia_srl;
pub mod vyos;

use std::borrow::Cow;

use crate::models::Platform;
use crate::tree::Tree;
use crate::view::config::ConfigOps;

/// Operations and customizations specific to a network operating system platform.
pub trait PlatformOps: Send + Sync {
    /// Returns the embedded raw JSON string defining the platform rules.
    fn rules_json(&self) -> &'static str;

    /// Dispatches post-load transformations for this platform.
    fn run_post_load(&self, _tree: &mut Tree) {}

    /// Swaps the negation prefix of a command string according to platform syntax rules.
    ///
    /// # Errors
    ///
    /// Returns an error message if the command does not start with an expected prefix.
    fn try_swap_negation(
        &self,
        negation_prefix: &str,
        _declaration_prefix: &str,
        text: &str,
    ) -> Result<String, String> {
        if let Some(stripped) = text.strip_prefix(negation_prefix) {
            Ok(stripped.to_string())
        } else {
            Ok(format!("{negation_prefix}{text}"))
        }
    }

    /// Returns the default sectional exit command for this platform.
    fn default_sectional_exit(&self) -> &'static str {
        "exit"
    }

    /// Applies platform-specific preprocessor transformations to configuration text.
    fn config_preprocessor<'a>(&self, text: &'a str) -> Cow<'a, str> {
        Cow::Borrowed(text)
    }

    /// Returns native view hooks if available for this platform.
    fn view_ops(&self) -> Option<&'static dyn ConfigOps> {
        None
    }
}

/// Returns the static [`PlatformOps`] implementation for `platform`.
#[must_use]
pub fn platform_ops(platform: Platform) -> &'static dyn PlatformOps {
    match platform {
        Platform::AristaEos => &arista_eos::OPS,
        Platform::ArubaAoscx => &aruba_aoscx::OPS,
        Platform::CiscoIos => &cisco_ios::OPS,
        Platform::CiscoNxos => &cisco_nxos::OPS,
        Platform::CiscoXr => &cisco_xr::OPS,
        Platform::FortinetFortios => &fortinet_fortios::OPS,
        Platform::Generic => &generic::OPS,
        Platform::HpComware5 => &hp_comware5::OPS,
        Platform::HpProcurve => &hp_procurve::OPS,
        Platform::HuaweiVrp => &huawei_vrp::OPS,
        Platform::JuniperJunos => &juniper_junos::OPS,
        Platform::NokiaSrl => &nokia_srl::OPS,
        Platform::Vyos => &vyos::OPS,
    }
}

/// Returns the embedded raw JSON string defining the platform rules for `platform`.
#[must_use]
pub fn rules_json_for_platform(platform: Platform) -> &'static str {
    platform_ops(platform).rules_json()
}

/// Reports whether the named post-load callback is still enabled on `tree`.
///
/// Drivers expose these callbacks as removable list entries, so a caller that
/// drops one from `post_load_callbacks` must also stop the core from applying
/// it (#286).
pub fn post_load_enabled(tree: &Tree, name: &str) -> bool {
    tree.driver
        .rules
        .enabled_post_load
        .as_ref()
        .is_none_or(|enabled| enabled.iter().any(|entry| entry == name))
}

/// Dispatches post-load transformations for a given platform.
pub fn run_post_load_callbacks(tree: &mut Tree) {
    platform_ops(tree.driver.platform).run_post_load(tree);
}

/// Swaps the negation prefix of a command string for a platform according to its driver syntax rules.
///
/// # Errors
///
/// Returns an error message if the command does not start with an expected prefix (e.g. on `JunOS`).
pub fn try_swap_negation(
    platform: Platform,
    negation_prefix: &str,
    declaration_prefix: &str,
    text: &str,
) -> Result<String, String> {
    platform_ops(platform).try_swap_negation(negation_prefix, declaration_prefix, text)
}

/// Returns the default sectional exit command for a platform.
#[must_use]
pub fn default_sectional_exit(platform: Platform) -> &'static str {
    platform_ops(platform).default_sectional_exit()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_post_load_enabled_defaults_to_every_callback() {
        // Pure-Rust callers never populate `enabled_post_load`, so `None` must
        // mean "run everything" rather than "run nothing".
        let tree = Tree::for_platform(Platform::CiscoIos);
        assert!(tree.driver.rules.enabled_post_load.is_none());
        assert!(post_load_enabled(&tree, "remove_ipv4_acl_remarks"));
    }

    #[test]
    fn test_post_load_enabled_honors_an_explicit_allow_list() {
        // Python drivers publish the callbacks they still hold, so removing one
        // there must stop the core running its own copy.
        let mut tree = Tree::for_platform(Platform::CiscoIos);
        tree.driver.rules.enabled_post_load = Some(vec!["add_acl_sequence_numbers".to_string()]);

        assert!(post_load_enabled(&tree, "add_acl_sequence_numbers"));
        assert!(!post_load_enabled(&tree, "remove_ipv4_acl_remarks"));
    }
}
