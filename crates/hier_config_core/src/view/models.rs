//! Data models used by network device configuration views.

use serde::{Deserialize, Serialize};

/// 802.1X / NAC host-mode options ordered from most to least secure.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum NACHostMode {
    SingleHost,
    MultiDomain,
    MultiAuth,
    MultiHost,
}

impl NACHostMode {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::SingleHost => "single-host",
            Self::MultiDomain => "multi-domain",
            Self::MultiAuth => "multi-auth",
            Self::MultiHost => "multi-host",
        }
    }
}

/// 802.1Q encapsulation mode of a switchport interface.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum InterfaceDot1qMode {
    Access,
    Tagged,
    TaggedAll,
}

impl InterfaceDot1qMode {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Access => "access",
            Self::Tagged => "tagged",
            Self::TaggedAll => "tagged_all",
        }
    }
}

/// Physical duplex setting of an Ethernet interface.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum InterfaceDuplex {
    Auto,
    Full,
    Half,
}

impl InterfaceDuplex {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Full => "full",
            Self::Half => "half",
        }
    }
}

/// Identity and priority record for a single switch-stack member.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StackMember {
    pub id: u32,
    pub priority: u32,
    pub mac_address: Option<String>,
    pub model: String,
}

/// Identifier and optional name for a single VLAN.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Vlan {
    pub id: u32,
    pub name: Option<String>,
}
