use crate::platforms::PlatformOps;
use std::borrow::Cow;

pub const RULES_JSON: &str = include_str!("rules.json");

#[derive(Debug, Clone, Copy)]
pub struct NokiaSrl;

impl PlatformOps for NokiaSrl {
    fn rules_json(&self) -> &'static str {
        RULES_JSON
    }

    fn try_swap_negation(
        &self,
        negation_prefix: &str,
        declaration_prefix: &str,
        text: &str,
    ) -> Result<String, String> {
        try_swap_negation(negation_prefix, declaration_prefix, text)
    }

    fn config_preprocessor<'a>(&self, text: &'a str) -> Cow<'a, str> {
        Cow::Owned(crate::parser::convert_to_set_commands(text))
    }
}

pub static OPS: NokiaSrl = NokiaSrl;

/// Attempts to swap negation on Nokia SRL command syntax (`enter candidate` etc.).
///
/// # Errors
///
/// Never returns an error in the current implementation, but returns `Result` for uniform signature.
pub fn try_swap_negation(
    negation_prefix: &str,
    declaration_prefix: &str,
    text: &str,
) -> Result<String, String> {
    if let Some(stripped) = text.strip_prefix(negation_prefix) {
        Ok(format!("{declaration_prefix}{stripped}"))
    } else if let Some(stripped) = text.strip_prefix(declaration_prefix) {
        Ok(format!("{negation_prefix}{stripped}"))
    } else {
        Ok(text.to_string())
    }
}
