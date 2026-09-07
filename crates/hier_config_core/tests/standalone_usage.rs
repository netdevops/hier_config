//! Standalone Rust usage acceptance test.
//!
//! Exercises the full journey a Rust-only consumer takes -- driver, load,
//! remediate, view -- using nothing but `hier_config_core`. No Python
//! interpreter, no `PyO3`, no JSON snapshot: if this compiles and passes, the
//! crate is usable on its own.

use hier_config_core::{
    ConfigView, Driver, Platform, Tree, WorkflowRemediation, config_from_text, config_view,
    view_ops_for_platform,
};

/// Platforms whose Python sibling has a `view.py`, so a native view exists.
const PLATFORMS_WITH_VIEWS: [Platform; 6] = [
    Platform::AristaEos,
    Platform::ArubaAoscx,
    Platform::CiscoIos,
    Platform::CiscoNxos,
    Platform::CiscoXr,
    Platform::HpProcurve,
];

#[test]
fn every_platform_builds_a_driver_with_rules() {
    for platform in Platform::ALL {
        let driver = Driver::for_platform(platform);
        assert_eq!(driver.platform, platform, "driver reports its platform");
        assert!(
            !driver.negation_prefix.is_empty(),
            "{platform:?} must define a negation prefix"
        );
    }
}

#[test]
fn every_platform_loads_and_remediates_without_python() {
    for platform in Platform::ALL {
        let running = Tree::for_platform(platform);
        let intended = Tree::for_platform(platform);
        let workflow = WorkflowRemediation::new(running, intended)
            .unwrap_or_else(|error| panic!("{platform:?} workflow: {error}"));
        let remediation = workflow
            .remediation_config()
            .unwrap_or_else(|error| panic!("{platform:?} remediation: {error}"));
        assert!(
            remediation.all_children(remediation.root).is_empty(),
            "{platform:?} remediating a config against itself is a no-op"
        );
    }
}

#[test]
fn cisco_ios_round_trips_from_text_to_remediation() {
    let running = config_from_text(
        Platform::CiscoIos,
        "hostname old-name\ninterface GigabitEthernet1/1\n  description old\n",
    )
    .expect("running config parses");
    let intended = config_from_text(
        Platform::CiscoIos,
        "hostname new-name\ninterface GigabitEthernet1/1\n  description new\n",
    )
    .expect("intended config parses");

    let workflow = WorkflowRemediation::new(running, intended).expect("workflow builds");
    let remediation = workflow.remediation_config().expect("remediation builds");
    let lines: Vec<String> = remediation.dump_simple(false);

    assert_eq!(
        lines,
        vec![
            "no hostname old-name".to_owned(),
            "hostname new-name".to_owned(),
            "interface GigabitEthernet1/1".to_owned(),
            // `description` is an idempotent command on IOS, so the driver
            // overwrites it rather than emitting a negation first.
            "  description new".to_owned(),
        ]
    );
}

#[test]
fn every_view_platform_exposes_a_usable_view() {
    for platform in PLATFORMS_WITH_VIEWS {
        let ops = view_ops_for_platform(platform)
            .unwrap_or_else(|| panic!("{platform:?} must expose view hooks"));
        let tree = Tree::for_platform(platform);
        let view = ConfigView::new(&tree, ops);

        // An empty config must answer every question without panicking.
        assert_eq!(view.hostname(), None, "{platform:?} empty hostname");
        assert_eq!(view.ipv4_default_gw(), None, "{platform:?} empty gateway");
        assert_eq!(view.location(), "", "{platform:?} empty location");
        assert!(view.interfaces().is_empty(), "{platform:?} no interfaces");
        assert!(view.vlans().is_empty(), "{platform:?} no vlans");
        assert!(
            view.stack_members().is_empty(),
            "{platform:?} no stack members"
        );
        assert!(
            view.module_numbers().is_empty(),
            "{platform:?} no module numbers"
        );
        assert!(
            view.interface_names_mentioned().is_empty(),
            "{platform:?} no interface names mentioned"
        );
    }
}

#[test]
fn a_rust_only_consumer_can_go_from_text_to_structured_view() {
    let tree = config_from_text(
        Platform::CiscoIos,
        "hostname edge-01\n\
         vlan 10\n\
         \x20 name USERS\n\
         interface GigabitEthernet1/1\n\
         \x20 description uplink\n\
         \x20 switchport mode trunk\n\
         \x20 switchport trunk allowed vlan 10\n",
    )
    .expect("config parses");

    let view = config_view(&tree).expect("cisco_ios has a view");
    assert_eq!(view.hostname().as_deref(), Some("edge-01"));

    let vlans = view.vlans();
    assert_eq!(vlans.len(), 1);
    assert_eq!(vlans[0].id, 10);
    assert_eq!(vlans[0].name.as_deref(), Some("USERS"));

    let interface = view
        .interface_view_by_name("GigabitEthernet1/1")
        .expect("interface is discovered");
    assert_eq!(interface.description(), "uplink");
    assert!(interface.enabled());
    assert_eq!(interface.tagged_vlans(), vec![10]);
    assert_eq!(interface.module_number(), Some(1));
    assert_eq!(interface.port_number(), Some(1));
}
