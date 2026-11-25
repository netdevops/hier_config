use crate::platforms::PlatformOps;
use crate::view::config::ConfigOps;

pub const RULES_JSON: &str = include_str!("rules.json");

#[derive(Debug, Clone, Copy)]
pub struct AristaEos;

impl PlatformOps for AristaEos {
    fn rules_json(&self) -> &'static str {
        RULES_JSON
    }

    fn view_ops(&self) -> Option<&'static dyn ConfigOps> {
        Some(&crate::view::platforms::arista_eos::CONFIG_OPS)
    }
}

pub static OPS: AristaEos = AristaEos;
