use hier_config_core::driver::Driver;
use hier_config_core::models::{MatchRule, OrderingRule, Platform, StringPattern};
use hier_config_core::tree::{Tree, TreeError};

#[test]
fn test_generic_snmp_scenario_2() {
    let raw = "\
snmp-server community <credentials_removed>
snmp-server community <credentials_removed>
snmp-server host 192.2.0.1 trap version v2c community <credentials_removed>
snmp-server host 192.2.0.2 trap version v2c community <credentials_removed>
snmp-server host 192.2.0.3 trap version v2c community <credentials_removed>
";
    // Under generic driver, the root does not allow duplicate children for snmp-server community.
    // Thus loading two identical top-level lines yields a DuplicateChild error.
    let res = Tree::from_str(Platform::Generic, raw);
    match res {
        Err(TreeError::DuplicateChild(path)) => {
            assert_eq!(path, vec!["snmp-server community <credentials_removed>"]);
        }
        other => panic!("Expected DuplicateChild error, got {other:?}"),
    }
}

#[test]
#[allow(clippy::too_many_lines)]
fn test_generic_aaa_scenario_2() {
    let running_raw = "\
aaa group server tacacs TACACS_GROUP1
  server 192.2.0.3
  server 192.2.0.7
aaa group server radius RADIUS_GROUP1
  server 192.2.0.121
";
    let generated_raw = "\
aaa group server tacacs TACACS_GROUP2
  server 192.2.0.3
  server 192.2.0.7
aaa group server radius RADIUS_GROUP2
  server 192.2.0.121
";
    let running_tree = Tree::from_str(Platform::Generic, running_raw).unwrap();
    let generated_tree = Tree::from_str(Platform::Generic, generated_raw).unwrap();

    let mut driver = Driver::for_platform(Platform::Generic);
    driver.rules.ordering = vec![
        OrderingRule {
            match_rules: vec![MatchRule {
                startswith: Some(StringPattern::Single(
                    "aaa group server radius ".to_string(),
                )),
                ..Default::default()
            }],
            weight: 520,
        },
        OrderingRule {
            match_rules: vec![MatchRule {
                re_search: Some("^no aaa group server tacacs ".to_string()),
                ..Default::default()
            }],
            weight: 510,
        },
        OrderingRule {
            match_rules: vec![MatchRule {
                re_search: Some("^no aaa group server radius ".to_string()),
                ..Default::default()
            }],
            weight: 530,
        },
    ];

    let base_remediation = running_tree.config_to_get_to(&generated_tree).unwrap();
    let mut remediation_tree = Tree::new(driver);

    let child_ids: Vec<_> = base_remediation.arena[base_remediation.root]
        .children
        .iter()
        .collect();
    for &child_id in &child_ids {
        let text = base_remediation.arena[child_id].text.as_ref();
        if let Some(rest) = text.strip_prefix("no aaa group server ") {
            let original_text = format!("aaa group server {rest}");
            if let Some(running_section_id) = running_tree.arena[running_tree.root]
                .children
                .get(&original_text)
            {
                let parent = remediation_tree
                    .add_child(remediation_tree.root, &original_text, true, false)
                    .unwrap();
                let rc_ids: Vec<_> = running_tree.arena[running_section_id]
                    .children
                    .iter()
                    .collect();
                for &rc_id in &rc_ids {
                    let rc_text = format!("no {}", running_tree.arena[rc_id].text);
                    remediation_tree
                        .add_child(parent, &rc_text, true, false)
                        .unwrap();
                }
                let words: Vec<&str> = original_text.split_whitespace().take(4).collect();
                let protocol = words.join(" ");
                for &new_id in &child_ids {
                    let new_text = base_remediation.arena[new_id].text.as_ref();
                    if new_text.starts_with(&protocol) && !new_text.starts_with("no ") {
                        remediation_tree
                            .add_deep_copy_of(
                                remediation_tree.root,
                                &base_remediation,
                                new_id,
                                false,
                            )
                            .unwrap();
                    }
                }
                let negated_section = format!("no {original_text}");
                remediation_tree
                    .add_child(remediation_tree.root, &negated_section, true, false)
                    .unwrap();
            }
        }
    }

    remediation_tree.set_order_weight();

    assert_eq!(
        remediation_tree.dump_simple(false),
        vec![
            "aaa group server tacacs TACACS_GROUP1",
            "  no server 192.2.0.3",
            "  no server 192.2.0.7",
            "aaa group server tacacs TACACS_GROUP2",
            "  server 192.2.0.3",
            "  server 192.2.0.7",
            "no aaa group server tacacs TACACS_GROUP1",
            "aaa group server radius RADIUS_GROUP1",
            "  no server 192.2.0.121",
            "aaa group server radius RADIUS_GROUP2",
            "  server 192.2.0.121",
            "no aaa group server radius RADIUS_GROUP1",
        ]
    );
}
