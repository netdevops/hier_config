use hier_config_core::remediation::future_with_report;
use hier_config_core::{Platform, Tree};

#[test]
fn interface_replacements_round_trip_across_cli_vendors() {
    let cases = [
        (
            Platform::CiscoIos,
            "interface Ethernet1",
            "description",
            "no",
            true,
        ),
        (
            Platform::CiscoNxos,
            "interface Ethernet1/1",
            "description",
            "no",
            false,
        ),
        (
            Platform::CiscoXr,
            "interface GigabitEthernet0/0/0/0",
            "description",
            "no",
            false,
        ),
        (
            Platform::AristaEos,
            "interface Ethernet1",
            "description",
            "no",
            false,
        ),
        (
            Platform::HpComware5,
            "interface GigabitEthernet1/0/1",
            "description",
            "undo",
            false,
        ),
        (Platform::HpProcurve, "interface 1", "name", "no", true),
        (
            Platform::ArubaAoscx,
            "interface 1/1/1",
            "description",
            "no",
            true,
        ),
    ];
    for (platform, interface, command, negation, idempotent) in cases {
        let source = Tree::from_str(
            platform,
            &format!("{interface}\n  {command} old\n  mtu 1500"),
        )
        .unwrap();
        let target = Tree::from_str(
            platform,
            &format!("{interface}\n  {command} new\n  mtu 1500"),
        )
        .unwrap();
        let delta = source.config_to_get_to(&target).unwrap();
        let mut expected = vec![interface.to_owned()];
        if !idempotent {
            expected.push(format!("  {negation} {command} old"));
        }
        expected.push(format!("  {command} new"));
        assert_eq!(delta.dump_simple(false), expected, "{platform:?}");
        let (projected, report) = future_with_report(&source, &delta, false).unwrap();
        assert!(projected.unified_diff(&target).is_empty(), "{platform:?}");
        assert!(report.unresolved_negations.is_empty(), "{platform:?}");
        let rollback = projected.config_to_get_to(&source).unwrap();
        let mut expected_rollback = vec![interface.to_owned()];
        if !idempotent {
            expected_rollback.push(format!("  {negation} {command} new"));
        }
        expected_rollback.push(format!("  {command} old"));
        assert_eq!(
            rollback.dump_simple(false),
            expected_rollback,
            "{platform:?}"
        );
        assert!(
            projected
                .future(&rollback, false)
                .unwrap()
                .unified_diff(&source)
                .is_empty(),
            "{platform:?}"
        );
    }
}

#[test]
fn fortios_parameter_replacement_is_idempotent_and_reversible() {
    let source = Tree::from_str(Platform::FortinetFortios, "config system interface\n  edit port1\n    set status up\n    set description 'retained'\n  next\nend").unwrap();
    let target = Tree::from_str(Platform::FortinetFortios, "config system interface\n  edit port1\n    set status down\n    set description 'retained'\n  next\nend").unwrap();
    let delta = source.config_to_get_to(&target).unwrap();
    assert_eq!(
        delta.dump_simple(false),
        [
            "config system interface",
            "  edit port1",
            "    set status down"
        ]
    );
    let projected = source.future(&delta, false).unwrap();
    assert!(projected.unified_diff(&target).is_empty());
    let rollback = projected.config_to_get_to(&source).unwrap();
    assert_eq!(
        rollback.dump_simple(false),
        [
            "config system interface",
            "  edit port1",
            "    set status up"
        ]
    );
    assert!(
        projected
            .future(&rollback, false)
            .unwrap()
            .unified_diff(&source)
            .is_empty()
    );
}

#[test]
fn procurve_explicit_negation_replacement_removes_parameterized_name() {
    let source = Tree::from_str(
        Platform::HpProcurve,
        "interface 1\n  name uplink\n  mtu 1500",
    )
    .unwrap();
    let target = Tree::from_str(Platform::HpProcurve, "interface 1\n  mtu 1500").unwrap();
    let delta = source.config_to_get_to(&target).unwrap();
    assert_eq!(delta.dump_simple(false), ["interface 1", "  no name"]);
    let (projected, report) = future_with_report(&source, &delta, false).unwrap();
    assert!(projected.unified_diff(&target).is_empty());
    assert!(report.unresolved_negations.is_empty());
    let rollback = projected.config_to_get_to(&source).unwrap();
    assert_eq!(
        rollback.dump_simple(false),
        ["interface 1", "  name uplink"]
    );
    assert!(
        projected
            .future(&rollback, false)
            .unwrap()
            .unified_diff(&source)
            .is_empty()
    );
}

#[test]
fn set_style_forward_and_rollback_retain_upstream_prediction_limitation() {
    // These platforms' shared corpus cases disable assert_rollback. The
    // upstream compute_future strips "delete " without restoring "set ", so
    // an old set command is not consumed. Do not silently repair Python parity.
    for (platform, setting) in [
        (Platform::JuniperJunos, "system host-name"),
        (Platform::Vyos, "system host-name"),
        (Platform::NokiaSrl, "system name host-name"),
    ] {
        let old = format!("set {setting} old-router");
        let new = format!("set {setting} new-router");
        let delete_old = format!("delete {setting} old-router");
        let delete_new = format!("delete {setting} new-router");
        let source = Tree::from_str(platform, &old).unwrap();
        let target = Tree::from_str(platform, &new).unwrap();
        let delta = source.config_to_get_to(&target).unwrap();
        assert_eq!(
            delta.dump_simple(false),
            [delete_old.as_str(), new.as_str()],
            "{platform:?}"
        );
        let (projected, report) = future_with_report(&source, &delta, false).unwrap();
        assert_eq!(
            projected.dump_simple(false),
            [delete_old.as_str(), new.as_str(), old.as_str()],
            "{platform:?}"
        );
        assert_eq!(report.unresolved_negations.len(), 1);
        assert_eq!(
            &*projected.arena[report.unresolved_negations[0]].text,
            delete_old
        );
        let rollback = projected.config_to_get_to(&source).unwrap();
        assert_eq!(
            rollback.dump_simple(false),
            [old.as_str(), delete_new.as_str()],
            "{platform:?}"
        );
        let restored = projected.future(&rollback, false).unwrap();
        assert_eq!(
            restored.dump_simple(false),
            [
                old.as_str(),
                delete_new.as_str(),
                delete_old.as_str(),
                new.as_str()
            ],
            "{platform:?}"
        );
    }
}
