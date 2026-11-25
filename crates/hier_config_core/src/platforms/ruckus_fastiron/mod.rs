use crate::platforms::PlatformOps;

pub const RULES_JSON: &str = include_str!("rules.json");

/// Vendor operations for Ruckus/Brocade `FastIron` (ICX) switches.
///
/// `FastIron` negates with the default `no ` prefix and exits a section with
/// `exit`, so the trait defaults apply. The platform keeps its normalization of
/// VLAN headers, VLAN and LAG port membership, and stack configuration in the
/// Python driver's `post_load_callbacks`, which the core does not own.
#[derive(Debug, Clone, Copy)]
pub struct RuckusFastiron;

impl PlatformOps for RuckusFastiron {
    fn rules_json(&self) -> &'static str {
        RULES_JSON
    }
}

pub static OPS: RuckusFastiron = RuckusFastiron;
