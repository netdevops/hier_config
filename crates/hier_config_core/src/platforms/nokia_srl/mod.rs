pub const RULES_JSON: &str = include_str!("rules.json");

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
