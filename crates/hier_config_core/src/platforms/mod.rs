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

use crate::models::Platform;
use crate::tree::Tree;

/// Returns the embedded raw JSON string defining the platform rules for `platform`.
#[must_use]
pub const fn rules_json_for_platform(platform: Platform) -> &'static str {
    match platform {
        Platform::AristaEos => arista_eos::RULES_JSON,
        Platform::ArubaAoscx => aruba_aoscx::RULES_JSON,
        Platform::CiscoIos => cisco_ios::RULES_JSON,
        Platform::CiscoNxos => cisco_nxos::RULES_JSON,
        Platform::CiscoXr => cisco_xr::RULES_JSON,
        Platform::FortinetFortios => fortinet_fortios::RULES_JSON,
        Platform::Generic => generic::RULES_JSON,
        Platform::HpComware5 => hp_comware5::RULES_JSON,
        Platform::HpProcurve => hp_procurve::RULES_JSON,
        Platform::HuaweiVrp => huawei_vrp::RULES_JSON,
        Platform::JuniperJunos => juniper_junos::RULES_JSON,
        Platform::NokiaSrl => nokia_srl::RULES_JSON,
        Platform::Vyos => vyos::RULES_JSON,
    }
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
    match tree.driver.platform {
        Platform::CiscoIos => cisco_ios::run_post_load(tree),
        Platform::CiscoXr => cisco_xr::run_post_load(tree),
        Platform::HpProcurve => hp_procurve::run_post_load(tree),
        Platform::ArubaAoscx => aruba_aoscx::run_post_load(tree),
        _ => {}
    }
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
    match platform {
        Platform::FortinetFortios => {
            fortinet_fortios::try_swap_negation(negation_prefix, declaration_prefix, text)
        }
        Platform::JuniperJunos => {
            juniper_junos::try_swap_negation(negation_prefix, declaration_prefix, text)
        }
        Platform::Vyos => vyos::try_swap_negation(negation_prefix, declaration_prefix, text),
        Platform::NokiaSrl => {
            nokia_srl::try_swap_negation(negation_prefix, declaration_prefix, text)
        }
        Platform::HuaweiVrp => huawei_vrp::try_swap_negation(negation_prefix, text),
        _ => {
            if let Some(stripped) = text.strip_prefix(negation_prefix) {
                Ok(stripped.to_string())
            } else {
                Ok(format!("{negation_prefix}{text}"))
            }
        }
    }
}

/// Returns the default sectional exit command for a platform.
#[must_use]
pub const fn default_sectional_exit(platform: Platform) -> &'static str {
    match platform {
        Platform::HuaweiVrp => huawei_vrp::sectional_exit(),
        _ => "exit",
    }
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
