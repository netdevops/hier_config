use crate::platforms::PlatformOps;

pub const RULES_JSON: &str = include_str!("rules.json");

#[derive(Debug, Clone, Copy)]
pub struct HpComware5;

impl PlatformOps for HpComware5 {
    fn rules_json(&self) -> &'static str {
        RULES_JSON
    }
}

pub static OPS: HpComware5 = HpComware5;
