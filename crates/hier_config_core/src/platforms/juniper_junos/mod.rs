pub const RULES_JSON: &str = include_str!("rules.json");

/// Attempts to swap negation on `JunOS` command syntax (`set` <-> `delete`).
///
/// # Errors
///
/// Returns an error message if the command text does not start with `negation_prefix` or `declaration_prefix`.
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
        Err(format!(
            "child.text='{text}' did not start with {negation_prefix} or {declaration_prefix}."
        ))
    }
}
