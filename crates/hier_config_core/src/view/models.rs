//! Typed value objects returned by the configuration view layer.
//!
//! These are faithful Rust equivalents of `hier_config/platforms/models.py`.
//! The `serde` representations deliberately match the Python values (not the
//! Rust variant names) so that the shared view corpus under `testdata/views/`
//! compares equal across both implementations.

use std::fmt;
use std::net::Ipv4Addr;

use serde::Serialize;

/// 802.1X / NAC host-mode options ordered from most to least secure.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize)]
#[serde(into = "String")]
pub enum NacHostMode {
    SingleHost,
    MultiDomain,
    MultiAuth,
    MultiHost,
}

impl NacHostMode {
    /// The wire value used by the Python `NACHostMode` enum.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::SingleHost => "single-host",
            Self::MultiDomain => "multi-domain",
            Self::MultiAuth => "multi-auth",
            Self::MultiHost => "multi-host",
        }
    }

    /// Parse a NAC host mode from its configured spelling.
    #[must_use]
    pub fn from_config_word(word: &str) -> Option<Self> {
        match word {
            "single-host" => Some(Self::SingleHost),
            "multi-domain" => Some(Self::MultiDomain),
            "multi-auth" => Some(Self::MultiAuth),
            "multi-host" => Some(Self::MultiHost),
            _ => None,
        }
    }
}

impl fmt::Display for NacHostMode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl From<NacHostMode> for String {
    fn from(value: NacHostMode) -> Self {
        value.as_str().to_owned()
    }
}

/// 802.1Q encapsulation mode of a switchport interface.
///
/// Python declares this as `class InterfaceDot1qMode(str, Enum)` with `auto()`,
/// which yields the string values `"1"`, `"2"` and `"3"` rather than the
/// lowercased member names. [`InterfaceDot1qMode::as_str`] reproduces those
/// values exactly so the shared corpus compares equal.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize)]
#[serde(into = "String")]
pub enum InterfaceDot1qMode {
    Access,
    Tagged,
    TaggedAll,
}

impl InterfaceDot1qMode {
    /// The wire value used by the Python `InterfaceDot1qMode` enum.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Access => "1",
            Self::Tagged => "2",
            Self::TaggedAll => "3",
        }
    }
}

impl fmt::Display for InterfaceDot1qMode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl From<InterfaceDot1qMode> for String {
    fn from(value: InterfaceDot1qMode) -> Self {
        value.as_str().to_owned()
    }
}

/// Physical duplex setting of an Ethernet interface.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize)]
#[serde(into = "String")]
pub enum InterfaceDuplex {
    Auto,
    Full,
    Half,
}

impl InterfaceDuplex {
    /// The wire value used by the Python `InterfaceDuplex` enum.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Full => "full",
            Self::Half => "half",
        }
    }

    /// Parse a duplex setting from its configured spelling.
    ///
    /// Unlike the Python constructor, an unrecognised word yields `None`
    /// instead of raising, because the view layer must be total.
    #[must_use]
    pub fn from_config_word(word: &str) -> Option<Self> {
        match word {
            "auto" => Some(Self::Auto),
            "full" => Some(Self::Full),
            "half" => Some(Self::Half),
            _ => None,
        }
    }
}

impl fmt::Display for InterfaceDuplex {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

impl From<InterfaceDuplex> for String {
    fn from(value: InterfaceDuplex) -> Self {
        value.as_str().to_owned()
    }
}

/// Identity and priority record for a single switch-stack member.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize)]
pub struct StackMember {
    pub id: u32,
    pub priority: u32,
    /// Not defined for `cisco_ios` stacks.
    pub mac_address: Option<String>,
    pub model: String,
}

/// Identifier and optional name for a single VLAN.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize)]
pub struct Vlan {
    pub id: u32,
    pub name: Option<String>,
}

/// An IPv4 address together with its prefix length.
///
/// Equivalent to Python's `ipaddress.IPv4Interface`. Implemented on
/// [`std::net::Ipv4Addr`] rather than pulling in an IP-network crate, because
/// the project forbids new runtime dependencies.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize)]
#[serde(into = "String")]
pub struct Ipv4Interface {
    pub address: Ipv4Addr,
    pub prefix_len: u8,
}

impl Ipv4Interface {
    /// Build an interface from an address and a prefix length.
    ///
    /// Returns `None` when `prefix_len` exceeds 32, matching Python's
    /// `ValueError` for the same input.
    #[must_use]
    pub const fn new(address: Ipv4Addr, prefix_len: u8) -> Option<Self> {
        if prefix_len > 32 {
            return None;
        }
        Some(Self {
            address,
            prefix_len,
        })
    }

    /// Convert a dotted-quad netmask to a prefix length.
    ///
    /// Returns `None` for a non-contiguous mask such as `255.255.0.255`, which
    /// Python also rejects.
    #[must_use]
    pub fn prefix_len_from_netmask(netmask: Ipv4Addr) -> Option<u8> {
        let bits = u32::from(netmask);
        let leading = bits.leading_ones();
        // A contiguous mask is exactly `leading` ones followed by zeroes.
        if bits.count_ones() == leading {
            u8::try_from(leading).ok()
        } else {
            None
        }
    }

    /// The netmask implied by the prefix length.
    #[must_use]
    pub fn netmask(self) -> Ipv4Addr {
        let bits = if self.prefix_len == 0 {
            0
        } else {
            u32::MAX << (32 - u32::from(self.prefix_len))
        };
        Ipv4Addr::from(bits)
    }

    /// The network address implied by the address and prefix length.
    #[must_use]
    pub fn network(self) -> Ipv4Addr {
        Ipv4Addr::from(u32::from(self.address) & u32::from(self.netmask()))
    }
}

impl fmt::Display for Ipv4Interface {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}/{}", self.address, self.prefix_len)
    }
}

impl From<Ipv4Interface> for String {
    fn from(value: Ipv4Interface) -> Self {
        value.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::{
        InterfaceDot1qMode, InterfaceDuplex, Ipv4Interface, NacHostMode, StackMember, Vlan,
    };
    use std::net::Ipv4Addr;

    /// Pinned against the live Python enum, whose `auto()` values are "1"/"2"/"3"
    /// rather than the lowercased member names.
    #[test]
    fn dot1q_mode_wire_values_match_python() {
        assert_eq!(InterfaceDot1qMode::Access.as_str(), "1");
        assert_eq!(InterfaceDot1qMode::Tagged.as_str(), "2");
        assert_eq!(InterfaceDot1qMode::TaggedAll.as_str(), "3");
    }

    #[test]
    fn nac_host_mode_wire_values_match_python() {
        assert_eq!(NacHostMode::SingleHost.as_str(), "single-host");
        assert_eq!(NacHostMode::MultiDomain.as_str(), "multi-domain");
        assert_eq!(NacHostMode::MultiAuth.as_str(), "multi-auth");
        assert_eq!(NacHostMode::MultiHost.as_str(), "multi-host");
    }

    #[test]
    fn nac_host_mode_round_trips_through_config_word() {
        for mode in [
            NacHostMode::SingleHost,
            NacHostMode::MultiDomain,
            NacHostMode::MultiAuth,
            NacHostMode::MultiHost,
        ] {
            assert_eq!(NacHostMode::from_config_word(mode.as_str()), Some(mode));
        }
        assert_eq!(NacHostMode::from_config_word("nonsense"), None);
    }

    #[test]
    fn duplex_wire_values_match_python() {
        assert_eq!(InterfaceDuplex::Auto.as_str(), "auto");
        assert_eq!(InterfaceDuplex::Full.as_str(), "full");
        assert_eq!(InterfaceDuplex::Half.as_str(), "half");
        assert_eq!(
            InterfaceDuplex::from_config_word("half"),
            Some(InterfaceDuplex::Half)
        );
        assert_eq!(InterfaceDuplex::from_config_word("nonsense"), None);
    }

    #[test]
    fn ipv4_interface_displays_like_python() {
        let iface = Ipv4Interface::new(Ipv4Addr::new(10, 0, 0, 1), 24).unwrap();
        assert_eq!(iface.to_string(), "10.0.0.1/24");
        assert_eq!(iface.netmask(), Ipv4Addr::new(255, 255, 255, 0));
        assert_eq!(iface.network(), Ipv4Addr::new(10, 0, 0, 0));
    }

    #[test]
    fn ipv4_interface_rejects_oversized_prefix() {
        assert!(Ipv4Interface::new(Ipv4Addr::new(10, 0, 0, 1), 33).is_none());
    }

    #[test]
    fn ipv4_interface_handles_edge_prefixes() {
        let zero = Ipv4Interface::new(Ipv4Addr::new(10, 0, 0, 1), 0).unwrap();
        assert_eq!(zero.netmask(), Ipv4Addr::UNSPECIFIED);
        assert_eq!(zero.network(), Ipv4Addr::UNSPECIFIED);

        let host = Ipv4Interface::new(Ipv4Addr::new(10, 0, 0, 1), 32).unwrap();
        assert_eq!(host.netmask(), Ipv4Addr::BROADCAST);
        assert_eq!(host.network(), Ipv4Addr::new(10, 0, 0, 1));
    }

    /// Python rejects non-contiguous netmasks with a `ValueError`; the view
    /// layer must be total, so this yields `None` instead.
    #[test]
    fn netmask_conversion_rejects_non_contiguous_masks() {
        assert_eq!(
            Ipv4Interface::prefix_len_from_netmask(Ipv4Addr::new(255, 255, 255, 0)),
            Some(24)
        );
        assert_eq!(
            Ipv4Interface::prefix_len_from_netmask(Ipv4Addr::UNSPECIFIED),
            Some(0)
        );
        assert_eq!(
            Ipv4Interface::prefix_len_from_netmask(Ipv4Addr::BROADCAST),
            Some(32)
        );
        assert_eq!(
            Ipv4Interface::prefix_len_from_netmask(Ipv4Addr::new(255, 255, 0, 255)),
            None
        );
    }

    #[test]
    fn value_objects_serialize_with_python_field_names() {
        let member = StackMember {
            id: 1,
            priority: 255,
            mac_address: None,
            model: "JL123".to_owned(),
        };
        let json = serde_json::to_string(&member).unwrap();
        assert_eq!(
            json,
            r#"{"id":1,"priority":255,"mac_address":null,"model":"JL123"}"#
        );

        let vlan = Vlan {
            id: 10,
            name: Some("users".to_owned()),
        };
        assert_eq!(
            serde_json::to_string(&vlan).unwrap(),
            r#"{"id":10,"name":"users"}"#
        );
    }

    #[test]
    fn enums_serialize_to_their_python_values() {
        assert_eq!(
            serde_json::to_string(&InterfaceDot1qMode::TaggedAll).unwrap(),
            r#""3""#
        );
        assert_eq!(
            serde_json::to_string(&NacHostMode::MultiAuth).unwrap(),
            r#""multi-auth""#
        );
        let iface = Ipv4Interface::new(Ipv4Addr::new(192, 0, 2, 1), 30).unwrap();
        assert_eq!(serde_json::to_string(&iface).unwrap(), r#""192.0.2.1/30""#);
    }
}
