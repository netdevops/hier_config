//! Parsing and derivation helpers shared by every platform view.
//!
//! These mirror `hier_config/platforms/functions.py` and the concrete
//! (non-abstract) helpers on the Python view base classes.

use std::net::Ipv4Addr;

use crate::view::models::{InterfaceDot1qMode, Ipv4Interface};

/// Parse the address words of an interface IPv4 address command.
///
/// Handles the three common forms, matching `parse_ipv4_interface` in
/// `hier_config/platforms/functions.py`:
///
/// - a single CIDR word: `10.0.0.1/24`
/// - an address and a slash-prefixed length: `10.0.0.1 /24`
/// - an address and a netmask: `10.0.0.1 255.255.255.0`
///
/// Returns `None` when the words do not form a valid IPv4 interface.
#[must_use]
pub fn parse_ipv4_interface(words: &[&str]) -> Option<Ipv4Interface> {
    let first = words.first()?;
    if words.len() == 1 || first.contains('/') {
        parse_ipv4_interface_str(first)
    } else {
        let second = words[1];
        let joined = if second.starts_with('/') {
            format!("{first}{second}")
        } else {
            format!("{first}/{second}")
        };
        parse_ipv4_interface_str(&joined)
    }
}

/// Parse a single `address/prefix`, `address/netmask` or bare `address` token.
///
/// A bare address is treated as a `/32` host route, matching Python's
/// `ipaddress.IPv4Interface`.
#[must_use]
pub fn parse_ipv4_interface_str(text: &str) -> Option<Ipv4Interface> {
    let (address_part, prefix_part) = match text.split_once('/') {
        Some((address, prefix)) => (address, Some(prefix)),
        None => (text, None),
    };

    let address: Ipv4Addr = address_part.parse().ok()?;
    let Some(prefix) = prefix_part else {
        return Ipv4Interface::new(address, 32);
    };

    // A prefix may be written either as a length or as a dotted-quad netmask.
    let prefix_len = if prefix.contains('.') {
        Ipv4Interface::prefix_len_from_netmask(prefix.parse().ok()?)?
    } else {
        prefix.parse().ok()?
    };

    Ipv4Interface::new(address, prefix_len)
}

/// Derive the 802.1Q mode implied by the given VLAN membership data.
///
/// Mirrors `HConfigViewBase.dot1q_mode_from_vlans`.
#[must_use]
pub const fn dot1q_mode_from_vlans(
    untagged_vlan: Option<u32>,
    tagged_vlans: &[u32],
    tagged_all: bool,
) -> Option<InterfaceDot1qMode> {
    if tagged_all {
        return Some(InterfaceDot1qMode::TaggedAll);
    }
    if !tagged_vlans.is_empty() {
        return Some(InterfaceDot1qMode::Tagged);
    }
    if untagged_vlan.is_some() {
        return Some(InterfaceDot1qMode::Access);
    }
    None
}

/// Strip the leading letters and hyphens from an interface name.
///
/// Equivalent to Python's `sub(r"^[a-zA-Z-]+", "", name)`, leaving just the
/// numbers and separators: `GigabitEthernet1/0/1` becomes `1/0/1`.
#[must_use]
pub fn interface_number(name: &str) -> &str {
    name.trim_start_matches(|c: char| c.is_ascii_alphabetic() || c == '-')
}

/// Determine whether an interface name denotes a subinterface.
#[must_use]
pub fn is_subinterface(name: &str) -> bool {
    name.contains('.')
}

/// Determine the parent interface name of a subinterface.
#[must_use]
pub fn parent_interface_name(name: &str) -> Option<&str> {
    if is_subinterface(name) {
        name.split('.').next()
    } else {
        None
    }
}

/// Determine the sub-interface number, if the name denotes a subinterface.
#[must_use]
pub fn subinterface_number(name: &str) -> Option<u32> {
    if !is_subinterface(name) {
        return None;
    }
    name.rsplit('.').next()?.trim().parse().ok()
}

/// Determine the interface port number.
///
/// Python raises `ValueError` for a name without a numeric port; the view layer
/// must be total, so this yields `None` instead.
#[must_use]
pub fn port_number_from_number(number: &str) -> Option<u32> {
    number
        .rsplit('/')
        .next()?
        .split('.')
        .next()?
        .trim()
        .parse()
        .ok()
}

/// The port number of `name`, e.g. `1` for `GigabitEthernet1/0/1.100`.
#[must_use]
pub fn port_number(name: &str) -> Option<u32> {
    let number = interface_number(name);
    let last_segment = number.rsplit('/').next()?;
    let without_subinterface = last_segment.split('.').next()?;
    without_subinterface.trim().parse().ok()
}

/// Determine the module number of an interface, if it has one.
///
/// Names without a `/` separator (such as `Vlan10`) have no module.
#[must_use]
pub fn module_number(name: &str) -> Option<u32> {
    module_number_from_number(interface_number(name))
}

/// Determine the module number of an already-stripped interface number.
#[must_use]
pub fn module_number_from_number(number: &str) -> Option<u32> {
    let (module, _) = number.split_once('/')?;
    module.trim().parse().ok()
}

#[cfg(test)]
mod tests {
    use super::{
        dot1q_mode_from_vlans, interface_number, is_subinterface, module_number,
        parent_interface_name, parse_ipv4_interface, parse_ipv4_interface_str, port_number,
        subinterface_number,
    };
    use crate::view::models::InterfaceDot1qMode;

    /// Every expectation here was captured from the live Python implementation.
    #[test]
    fn parse_ipv4_interface_handles_the_three_documented_forms() {
        assert_eq!(
            parse_ipv4_interface(&["10.0.0.1/24"]).map(|i| i.to_string()),
            Some("10.0.0.1/24".to_owned())
        );
        assert_eq!(
            parse_ipv4_interface(&["10.0.0.1", "/24"]).map(|i| i.to_string()),
            Some("10.0.0.1/24".to_owned())
        );
        assert_eq!(
            parse_ipv4_interface(&["10.0.0.1", "255.255.255.0"]).map(|i| i.to_string()),
            Some("10.0.0.1/24".to_owned())
        );
    }

    #[test]
    fn parse_ipv4_interface_rejects_bad_input_like_python() {
        assert_eq!(parse_ipv4_interface(&[]), None);
        assert_eq!(parse_ipv4_interface(&["bad"]), None);
        // Non-contiguous netmask: Python raises ValueError, we return None.
        assert_eq!(parse_ipv4_interface(&["10.0.0.1", "255.255.0.255"]), None);
        assert_eq!(parse_ipv4_interface(&["10.0.0.1", "/33"]), None);
    }

    #[test]
    fn a_bare_address_is_a_host_route() {
        let iface = parse_ipv4_interface_str("192.0.2.5").unwrap();
        assert_eq!(iface.prefix_len, 32);
    }

    #[test]
    fn dot1q_mode_precedence_matches_python() {
        assert_eq!(
            dot1q_mode_from_vlans(None, &[], true),
            Some(InterfaceDot1qMode::TaggedAll)
        );
        // tagged_all wins over tagged vlans and an untagged vlan.
        assert_eq!(
            dot1q_mode_from_vlans(Some(1), &[10, 20], true),
            Some(InterfaceDot1qMode::TaggedAll)
        );
        assert_eq!(
            dot1q_mode_from_vlans(Some(1), &[10], false),
            Some(InterfaceDot1qMode::Tagged)
        );
        assert_eq!(
            dot1q_mode_from_vlans(Some(1), &[], false),
            Some(InterfaceDot1qMode::Access)
        );
        assert_eq!(dot1q_mode_from_vlans(None, &[], false), None);
    }

    #[test]
    fn interface_number_strips_leading_letters_and_hyphens() {
        assert_eq!(interface_number("GigabitEthernet1/0/1"), "1/0/1");
        assert_eq!(interface_number("Vlan10"), "10");
        assert_eq!(interface_number("Te-Bundle3"), "3");
        assert_eq!(interface_number("Bundle-Ether100"), "100");
        assert_eq!(interface_number("1/0/1"), "1/0/1");
    }

    #[test]
    fn subinterface_helpers_match_python() {
        assert!(is_subinterface("GigabitEthernet0/0.100"));
        assert!(!is_subinterface("GigabitEthernet0/0"));
        assert_eq!(
            parent_interface_name("GigabitEthernet0/0.100"),
            Some("GigabitEthernet0/0")
        );
        assert_eq!(parent_interface_name("GigabitEthernet0/0"), None);
        assert_eq!(subinterface_number("GigabitEthernet0/0.100"), Some(100));
        assert_eq!(subinterface_number("GigabitEthernet0/0"), None);
    }

    #[test]
    fn port_and_module_numbers_match_python() {
        assert_eq!(port_number("GigabitEthernet1/0/24"), Some(24));
        assert_eq!(port_number("GigabitEthernet0/0.100"), Some(0));
        assert_eq!(port_number("Vlan10"), Some(10));
        assert_eq!(module_number("GigabitEthernet1/0/24"), Some(1));
        // No "/" separator means no module number.
        assert_eq!(module_number("Vlan10"), None);
    }

    #[test]
    fn totality_is_preserved_for_names_without_numbers() {
        assert_eq!(port_number("Management"), None);
        assert_eq!(module_number("Management"), None);
    }
}
