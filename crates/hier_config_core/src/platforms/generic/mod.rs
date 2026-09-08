use crate::platforms::PlatformOps;

pub const RULES_JSON: &str = include_str!("rules.json");

#[derive(Debug, Clone, Copy)]
pub struct Generic;

impl PlatformOps for Generic {
    fn rules_json(&self) -> &'static str {
        RULES_JSON
    }
}

pub static OPS: Generic = Generic;
