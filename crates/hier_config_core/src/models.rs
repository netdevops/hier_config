use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

/// String matching pattern that can either be a single string or multiple alternatives.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(untagged)]
pub enum StringPattern {
    Single(String),
    Multiple(Vec<String>),
}

impl StringPattern {
    pub fn matches_equals(&self, text: &str) -> bool {
        match self {
            Self::Single(s) => text == s,
            Self::Multiple(v) => v.iter().any(|s| s == text),
        }
    }

    pub fn matches_startswith(&self, text: &str) -> bool {
        match self {
            Self::Single(s) => text.starts_with(s),
            Self::Multiple(v) => v.iter().any(|s| text.starts_with(s)),
        }
    }

    pub fn matches_endswith(&self, text: &str) -> bool {
        match self {
            Self::Single(s) => text.ends_with(s),
            Self::Multiple(v) => v.iter().any(|s| text.ends_with(s)),
        }
    }

    pub fn matches_contains(&self, text: &str) -> bool {
        match self {
            Self::Single(s) => text.contains(s),
            Self::Multiple(v) => v.iter().any(|s| text.contains(s)),
        }
    }
}

fn matches_regex(pattern: &str, text: &str) -> bool {
    if let Some(re) = crate::regex_cache::regex(pattern) {
        re.is_match(text)
    } else if let Some(re) = crate::regex_cache::fancy(pattern) {
        re.is_match(text).unwrap_or(false)
    } else {
        false
    }
}

impl From<&str> for StringPattern {
    fn from(s: &str) -> Self {
        Self::Single(s.to_string())
    }
}

impl From<String> for StringPattern {
    fn from(s: String) -> Self {
        Self::Single(s)
    }
}

impl From<Vec<String>> for StringPattern {
    fn from(v: Vec<String>) -> Self {
        Self::Multiple(v)
    }
}

impl From<&[&str]> for StringPattern {
    fn from(v: &[&str]) -> Self {
        Self::Multiple(v.iter().map(|s| (*s).to_string()).collect())
    }
}

/// Flexible predicate for matching an `HConfigChild.text` value.
///
/// All fields are optional; when multiple are set, every criterion must match.
///
/// # Example
///
/// ```
/// use hier_config_core::MatchRule;
///
/// let rule = MatchRule::startswith("interface");
/// assert!(rule.is_match("interface GigabitEthernet0/1"));
/// assert!(!rule.is_match("hostname router1"));
///
/// let multi_rule = MatchRule {
///     startswith: Some("interface".into()),
///     contains: Some("Ethernet".into()),
///     ..Default::default()
/// };
/// assert!(multi_rule.is_match("interface GigabitEthernet0/1"));
/// assert!(!multi_rule.is_match("interface Loopback0"));
/// ```
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct MatchRule {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub equals: Option<StringPattern>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub startswith: Option<StringPattern>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub endswith: Option<StringPattern>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub contains: Option<StringPattern>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub re_search: Option<String>,
}

impl MatchRule {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn equals(val: impl Into<StringPattern>) -> Self {
        Self {
            equals: Some(val.into()),
            ..Default::default()
        }
    }

    pub fn startswith(val: impl Into<StringPattern>) -> Self {
        Self {
            startswith: Some(val.into()),
            ..Default::default()
        }
    }

    pub fn endswith(val: impl Into<StringPattern>) -> Self {
        Self {
            endswith: Some(val.into()),
            ..Default::default()
        }
    }

    pub fn contains(val: impl Into<StringPattern>) -> Self {
        Self {
            contains: Some(val.into()),
            ..Default::default()
        }
    }

    pub fn re_search(pattern: impl Into<String>) -> Self {
        Self {
            re_search: Some(pattern.into()),
            ..Default::default()
        }
    }

    /// Evaluates if `text` matches this rule.
    pub fn is_match(&self, text: &str) -> bool {
        if let Some(equals) = &self.equals
            && !equals.matches_equals(text)
        {
            return false;
        }

        if let Some(startswith) = &self.startswith
            && !startswith.matches_startswith(text)
        {
            return false;
        }

        if let Some(re_search) = &self.re_search
            && !matches_regex(re_search, text)
        {
            return false;
        }

        if let Some(endswith) = &self.endswith
            && !endswith.matches_endswith(text)
        {
            return false;
        }

        if let Some(contains) = &self.contains
            && !contains.matches_contains(text)
        {
            return false;
        }

        true
    }
}

/// Rule that applies a set of tags to children matching `match_rules`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TagRule {
    pub match_rules: Vec<MatchRule>,
    pub apply_tags: BTreeSet<String>,
}

/// Rule defining the exit command for a hierarchical configuration section.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SectionalExitingRule {
    pub match_rules: Vec<MatchRule>,
    pub exit_text: String,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub exit_text_parent_level: bool,
}

/// Rule marking a section for full negation + re-creation during remediation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SectionalOverwriteRule {
    pub match_rules: Vec<MatchRule>,
}

/// Rule marking a section for re-creation without prior negation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SectionalOverwriteNoNegateRule {
    pub match_rules: Vec<MatchRule>,
}

/// Rule assigning an integer weight to commands to control apply order.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OrderingRule {
    pub match_rules: Vec<MatchRule>,
    pub weight: i32,
}

/// Rule defining start/end expressions that shift the indentation level.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IndentAdjustRule {
    pub start_expression: String,
    pub end_expression: String,
}

/// Rule permitting multiple children with identical text under a parent.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ParentAllowsDuplicateChildRule {
    pub match_rules: Vec<MatchRule>,
}

/// Regex substitution applied to the entire configuration text block.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FullTextSubRule {
    pub search: String,
    pub replace: String,
}

/// Regex substitution applied to each line of configuration text.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PerLineSubRule {
    pub search: String,
    pub replace: String,
}

/// Rule declaring that a command family is idempotent (last value wins).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IdempotentCommandsRule {
    pub match_rules: Vec<MatchRule>,
}

/// Rule preventing specific commands from being treated as idempotent.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IdempotentCommandsAvoidRule {
    pub match_rules: Vec<MatchRule>,
}

/// Rule specifying when negation should use the `default` form.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NegationDefaultWhenRule {
    pub match_rules: Vec<MatchRule>,
}

/// Rule replacing negation with a fixed custom command string.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NegationDefaultWithRule {
    pub match_rules: Vec<MatchRule>,
    #[serde(rename = "use")]
    pub use_cmd: String,
}

/// Regex substitution applied to a command during negation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NegationSubRule {
    pub match_rules: Vec<MatchRule>,
    pub search: String,
    pub replace: String,
}

/// How a matching command is negated.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NegationStrategy {
    /// Replace the command with the fixed string in `use`.
    Replace,
    /// Rewrite the command to its `default` form.
    Default,
    /// Apply a regex substitution to the already-negated text.
    RegexSub,
}

/// Unified negation rule.
///
/// Supersedes the three separate v3 rule types. The v3 spellings remain
/// supported on the wire and are folded into this shape by
/// `DriverRules::resolved_negation`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NegationRule {
    pub strategy: NegationStrategy,
    pub match_rules: Vec<MatchRule>,
    #[serde(rename = "use", default)]
    pub use_cmd: String,
    #[serde(default)]
    pub search: String,
    #[serde(default)]
    pub replace: String,
}

impl NegationRule {
    /// Views this rule as a [`NegationDefaultWithRule`] for `use` expansion.
    pub(crate) fn as_default_with(&self) -> NegationDefaultWithRule {
        NegationDefaultWithRule {
            match_rules: self.match_rules.clone(),
            use_cmd: self.use_cmd.clone(),
        }
    }
}

/// A location in the config tree where object name references are searched.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReferenceLocation {
    pub match_rules: Vec<MatchRule>,
    pub reference_re: String,
}

/// Rule for detecting unused named objects in a configuration.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct UnusedObjectRule {
    pub match_rules: Vec<MatchRule>,
    pub name_re: String,
    pub reference_locations: Vec<ReferenceLocation>,
}

/// Metadata snapshot for a single `HConfig` instance used in merged views.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Instance {
    pub id: u64,
    pub comments: BTreeSet<String>,
    pub tags: BTreeSet<String>,
}

/// Enumeration of supported network operating system platforms.
///
/// # Example
///
/// ```
/// use std::str::FromStr;
/// use hier_config_core::Platform;
///
/// // Parse a platform from its standard name
/// let platform = Platform::from_str("cisco_ios").expect("valid platform name");
/// assert_eq!(platform, Platform::CiscoIos);
/// assert_eq!(platform.as_str(), "cisco_ios");
///
/// // Platform variants can also be matched directly
/// match platform {
///     Platform::CiscoIos => assert!(true),
///     _ => unreachable!(),
/// }
/// ```
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Platform {
    AristaEos,
    ArubaAoscx,
    CiscoIos,
    CiscoNxos,
    CiscoXr,
    FortinetFortios,
    #[default]
    Generic,
    HpComware5,
    HpProcurve,
    HuaweiVrp,
    JuniperJunos,
    NokiaSrl,
    Vyos,
}

impl Platform {
    pub const ALL: [Self; 13] = [
        Self::AristaEos,
        Self::ArubaAoscx,
        Self::CiscoIos,
        Self::CiscoNxos,
        Self::CiscoXr,
        Self::FortinetFortios,
        Self::Generic,
        Self::HpComware5,
        Self::HpProcurve,
        Self::HuaweiVrp,
        Self::JuniperJunos,
        Self::NokiaSrl,
        Self::Vyos,
    ];

    /// Exhaustively matches every variant so that adding a new [`Platform`] without
    /// also adding it to [`Self::ALL`] is a compile error instead of a silent gap in
    /// `for platform in Platform::ALL` coverage.
    const fn assert_all_is_exhaustive(platform: Self) {
        match platform {
            Self::AristaEos
            | Self::ArubaAoscx
            | Self::CiscoIos
            | Self::CiscoNxos
            | Self::CiscoXr
            | Self::FortinetFortios
            | Self::Generic
            | Self::HpComware5
            | Self::HpProcurve
            | Self::HuaweiVrp
            | Self::JuniperJunos
            | Self::NokiaSrl
            | Self::Vyos => {}
        }
    }

    pub const fn as_str(&self) -> &'static str {
        match self {
            Self::AristaEos => "arista_eos",
            Self::ArubaAoscx => "aruba_aoscx",
            Self::CiscoIos => "cisco_ios",
            Self::CiscoNxos => "cisco_nxos",
            Self::CiscoXr => "cisco_xr",
            Self::FortinetFortios => "fortinet_fortios",
            Self::Generic => "generic",
            Self::HpComware5 => "hp_comware5",
            Self::HpProcurve => "hp_procurve",
            Self::HuaweiVrp => "huawei_vrp",
            Self::JuniperJunos => "juniper_junos",
            Self::NokiaSrl => "nokia_srl",
            Self::Vyos => "vyos",
        }
    }
}

const _: () = Platform::assert_all_is_exhaustive(Platform::Generic);

impl std::str::FromStr for Platform {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let normalized = s.trim().to_lowercase().replace('-', "_");
        match normalized.as_str() {
            "1" | "arista_eos" | "eos" => Ok(Self::AristaEos),
            "2" | "aruba_aoscx" | "aoscx" => Ok(Self::ArubaAoscx),
            "3" | "cisco_ios" | "ios" => Ok(Self::CiscoIos),
            "4" | "cisco_nxos" | "nxos" => Ok(Self::CiscoNxos),
            "5" | "cisco_xr" | "iosxr" | "ios_xr" | "xr" => Ok(Self::CiscoXr),
            "6" | "fortinet_fortios" | "fortios" => Ok(Self::FortinetFortios),
            "7" | "generic" => Ok(Self::Generic),
            "8" | "hp_comware5" | "comware5" => Ok(Self::HpComware5),
            "9" | "hp_procurve" | "procurve" => Ok(Self::HpProcurve),
            "10" | "huawei_vrp" | "vrp" => Ok(Self::HuaweiVrp),
            "11" | "juniper_junos" | "junos" => Ok(Self::JuniperJunos),
            "12" | "nokia_srl" | "srl" => Ok(Self::NokiaSrl),
            "13" | "vyos" => Ok(Self::Vyos),
            other => Err(format!("Unknown platform: {other}")),
        }
    }
}

/// Serialized representation of a single line.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DumpLine {
    pub depth: usize,
    pub text: String,
    pub tags: BTreeSet<String>,
    pub comments: BTreeSet<String>,
    pub new_in_config: bool,
}

/// Serialized representation of an entire `HConfig` tree.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Dump {
    pub lines: Vec<DumpLine>,
}

/// Text formatting style for Cisco-like rendered lines.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TextStyle {
    #[default]
    WithoutComments,
    Merged,
    WithComments,
}
