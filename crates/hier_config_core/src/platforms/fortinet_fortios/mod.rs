use crate::platforms::PlatformOps;
pub const RULES_JSON: &str = include_str!("rules.json");

#[derive(Debug, Clone, Copy)]
pub struct FortinetFortios;

impl PlatformOps for FortinetFortios {
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
}

pub static OPS: FortinetFortios = FortinetFortios;

/// Attempts to swap negation on Fortinet command syntax (`set` <-> `unset`).
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
    } else if let Some(stripped) = text.strip_prefix(declaration_prefix)
        && let Some(first_word) = stripped.split_whitespace().next()
    {
        Ok(format!("{negation_prefix}{first_word}"))
    } else {
        Ok(text.to_string())
    }
}
