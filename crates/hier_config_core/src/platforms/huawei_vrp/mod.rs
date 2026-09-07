pub const RULES_JSON: &str = include_str!("rules.json");

#[must_use]
pub const fn sectional_exit() -> &'static str {
    "quit"
}

/// Attempts to swap negation on Huawei command syntax (`undo <cmd>` <-> `<cmd>`).
///
/// # Errors
///
/// Never returns an error in the current implementation, but returns `Result` for uniform signature.
pub fn try_swap_negation(negation_prefix: &str, text: &str) -> Result<String, String> {
    if let Some(stripped) = text.strip_prefix(negation_prefix) {
        return Ok(stripped.to_string());
    }
    let mut mod_text = text.to_string();
    if text.starts_with("description ") {
        mod_text = "description".to_string();
    } else if text.starts_with("alias ") {
        mod_text = "alias".to_string();
    } else if text.contains(" remark ") || text.starts_with("remark ") {
        if let Some(re) = crate::regex_cache::regex(r"^(.*?remark) .*") {
            mod_text = re.replace(text, "$1").to_string();
        }
    } else if text.starts_with("snmp-agent community ")
        && let Some(re) =
            crate::regex_cache::regex(r"^(snmp-agent community (?:read |write )?(?:cipher )?\S+).*")
    {
        mod_text = re.replace(text, "$1").to_string();
    }
    Ok(format!("{negation_prefix}{mod_text}"))
}
