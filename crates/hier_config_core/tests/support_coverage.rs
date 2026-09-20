use std::collections::BTreeSet;
use std::str::FromStr;

use hier_config_core::formats::FormatError;
use hier_config_core::{
    MatchRule, Platform, StringPattern, TagRule, Tree, WorkflowError, WorkflowRemediation,
};

fn vlan_tag(text: &str) -> TagRule {
    TagRule {
        match_rules: vec![MatchRule::equals(text)],
        apply_tags: BTreeSet::from(["maintenance".to_owned()]),
    }
}

#[test]
fn workflow_take_preserves_cached_edits_then_recomputes_from_inputs() {
    let mut workflow =
        WorkflowRemediation::from_strings(Platform::CiscoIos, "vlan 10", "vlan 20").unwrap();
    workflow
        .apply_remediation_tag_rules(&[vlan_tag("vlan 20")])
        .unwrap();
    workflow
        .rollback_config_mut()
        .unwrap()
        .apply_tag_rules(&[vlan_tag("vlan 10")]);
    assert_eq!(
        workflow.remediation_text(&["maintenance"], &[]).unwrap(),
        "vlan 20"
    );
    assert_eq!(
        workflow.rollback_text(&["maintenance"], &[]).unwrap(),
        "vlan 10"
    );
    assert!(std::ptr::eq(
        workflow.rollback_config().unwrap(),
        workflow.rollback_config().unwrap()
    ));

    let remediation = workflow.take_remediation().unwrap();
    let rollback = workflow.take_rollback().unwrap();
    assert_eq!(
        remediation.rendered_text_by_tags(&["maintenance"], &[]),
        "vlan 20"
    );
    assert_eq!(
        rollback.rendered_text_by_tags(&["maintenance"], &[]),
        "vlan 10"
    );
    assert_eq!(
        workflow.remediation_text(&["maintenance"], &[]).unwrap(),
        ""
    );
    assert_eq!(workflow.rollback_text(&["maintenance"], &[]).unwrap(), "");
    assert_eq!(
        workflow.remediation_text(&[], &[]).unwrap(),
        "no vlan 10\nvlan 20"
    );
    assert_eq!(
        workflow.rollback_text(&[], &[]).unwrap(),
        "no vlan 20\nvlan 10"
    );
    assert_eq!(workflow.running_config.dump_simple(false), ["vlan 10"]);
    assert_eq!(workflow.generated_config.dump_simple(false), ["vlan 20"]);
}

#[test]
fn borrowed_workflow_rejects_platform_mismatch_without_mutating_inputs() {
    let running = Tree::from_str(Platform::CiscoIos, "hostname before").unwrap();
    let generated = Tree::from_str(Platform::AristaEos, "hostname after").unwrap();
    let error = WorkflowRemediation::from_borrowed(&running, &generated).unwrap_err();
    assert_eq!(
        error,
        WorkflowError::DriverMismatch {
            running: Platform::CiscoIos,
            generated: Platform::AristaEos
        }
    );
    assert!(error.to_string().contains("same driver"));
    assert_eq!(running.dump_simple(false), ["hostname before"]);
    assert_eq!(generated.dump_simple(false), ["hostname after"]);
}

#[test]
fn workflow_structured_renderers_surface_attribute_deletion_errors() {
    let running = Tree::from_xml(Platform::Generic, "<c a=\"old\"/>", None).unwrap();
    let generated = Tree::from_xml(Platform::Generic, "<c/>", None).unwrap();
    let workflow = WorkflowRemediation::new(running, generated).unwrap();
    for error in [
        workflow.remediation_netconf_xml(None).unwrap_err(),
        workflow.remediation_gnmi(None).unwrap_err(),
    ] {
        assert!(matches!(
            error,
            WorkflowError::Format(FormatError::Invalid(_))
        ));
        assert!(
            error
                .to_string()
                .contains("Attribute changes cannot be expressed")
        );
    }
}

#[test]
fn workflow_custom_keys_keep_deletions_addressed_to_the_correct_entry() {
    let keys = ["port".to_owned()];
    let running = Tree::from_json(
        Platform::Generic,
        r#"{"interfaces":[{"port":"eth0","mtu":1500},{"port":"eth1","mtu":9000}]}"#,
        Some(&keys),
    )
    .unwrap();
    let generated = Tree::from_json(
        Platform::Generic,
        r#"{"interfaces":[{"port":"eth1","mtu":9000}]}"#,
        Some(&keys),
    )
    .unwrap();
    let workflow = WorkflowRemediation::new(running, generated).unwrap();
    let remediation = workflow.remediation_gnmi(Some(&keys)).unwrap();
    assert_eq!(remediation.delete, ["interfaces[port=eth0]"]);
    assert!(remediation.update.is_empty());
}

#[test]
fn workflow_parse_errors_preserve_duplicate_child_identity() {
    for (running, generated) in [("a\na", "b"), ("a", "b\nb")] {
        let error =
            WorkflowRemediation::from_strings(Platform::Generic, running, generated).unwrap_err();
        assert!(matches!(error, WorkflowError::Tree(_)));
        assert!(error.to_string().contains("duplicate"));
    }
    let error = Tree::from_json(
        Platform::Generic,
        r#"{"ports":[{"name":"eth0"},{"name":"eth0"}]}"#,
        None,
    )
    .unwrap_err();
    assert!(matches!(error, FormatError::Tree(_)));
    assert!(error.to_string().contains("duplicate"));
    let workflow_error = WorkflowError::from(error);
    assert!(matches!(
        workflow_error,
        WorkflowError::Format(FormatError::Tree(_))
    ));
    assert!(workflow_error.to_string().contains("duplicate"));
}

#[test]
fn match_rule_conjunction_enforces_every_string_predicate() {
    let rule = MatchRule {
        equals: Some(vec!["interface eth0".to_owned(), "interface eth1".to_owned()].into()),
        startswith: Some(StringPattern::from("interface ".to_owned())),
        endswith: Some(StringPattern::from(&["0", "2"][..])),
        contains: Some(StringPattern::from(&["eth", "Ethernet"][..])),
        re_search: Some(r"\d$".to_owned()),
    };
    for (text, expected) in [
        ("interface eth0", true),
        ("interface eth1", false),
        ("interface eth2", false),
        ("eth0", false),
        ("", false),
    ] {
        assert_eq!(rule.is_match(text), expected, "{text}");
    }
    assert!(MatchRule::new().is_match(""));
}

#[test]
fn string_pattern_alternatives_and_empty_patterns_have_python_semantics() {
    for (pattern, matches) in [
        (StringPattern::from("eth"), true),
        (StringPattern::from(&["wan", "eth"][..]), true),
        (StringPattern::from(Vec::<String>::new()), false),
    ] {
        assert_eq!(pattern.matches_equals("eth"), matches);
        assert_eq!(pattern.matches_startswith("eth0"), matches);
        assert_eq!(pattern.matches_endswith("Gigabiteth"), matches);
        assert_eq!(pattern.matches_contains("interface eth0"), matches);
    }
    let empty = StringPattern::from("");
    assert!(empty.matches_startswith("anything"));
    assert!(empty.matches_endswith("anything"));
    assert!(empty.matches_contains("anything"));
    assert!(!empty.matches_equals("anything"));
    assert!(MatchRule::endswith("0").is_match("eth0"));
    assert!(!MatchRule::endswith("0").is_match("eth1"));
    assert!(MatchRule::contains("eth").is_match("interface eth0"));
    assert!(!MatchRule::contains("eth").is_match("interface lo0"));
}

#[test]
fn regex_rules_support_python_lookaround_and_reject_invalid_patterns() {
    for (pattern, text, expected) in [
        (r"(?<=interface )eth\d", "interface eth0", true),
        (r"(?<=interface )eth\d", "address eth0", false),
        (r"(?=eth)\w+", "eth0", true),
        (r"([a-z]+) \1", "foo foo", true),
        ("[", "anything", false),
        ("^eth", "interface eth0", false),
    ] {
        assert_eq!(MatchRule::re_search(pattern).is_match(text), expected);
    }
}

#[test]
fn platform_names_and_aliases_normalize_to_the_correct_driver() {
    for (input, expected, canonical) in [
        (" EOS ", Platform::AristaEos, "arista_eos"),
        ("2", Platform::ArubaAoscx, "aruba_aoscx"),
        ("cisco-IOS", Platform::CiscoIos, "cisco_ios"),
        ("nxos", Platform::CiscoNxos, "cisco_nxos"),
        ("ios-xr", Platform::CiscoXr, "cisco_xr"),
        ("fortios", Platform::FortinetFortios, "fortinet_fortios"),
        ("generic", Platform::Generic, "generic"),
        ("comware5", Platform::HpComware5, "hp_comware5"),
        ("PROCURVE", Platform::HpProcurve, "hp_procurve"),
        ("vrp", Platform::HuaweiVrp, "huawei_vrp"),
        ("JUNOS", Platform::JuniperJunos, "juniper_junos"),
        ("srl", Platform::NokiaSrl, "nokia_srl"),
        ("13", Platform::RuckusFastiron, "ruckus_fastiron"),
        ("ICX", Platform::RuckusFastiron, "ruckus_fastiron"),
        ("fastiron", Platform::RuckusFastiron, "ruckus_fastiron"),
        ("14", Platform::Vyos, "vyos"),
    ] {
        let platform = Platform::from_str(input).unwrap();
        assert_eq!(platform, expected);
        assert_eq!(platform.as_str(), canonical);
        assert_eq!(Tree::for_platform(platform).driver.platform, expected);
    }
    for invalid in ["", "0", "15", "nonexistent", "AOSC X"] {
        assert!(
            Platform::from_str(invalid)
                .unwrap_err()
                .contains("Unknown platform")
        );
    }
}
