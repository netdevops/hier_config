use hier_config_core::parser::{
    convert_to_set_commands, parse_fast_with_callbacks, parse_tree_with_callbacks,
};
use hier_config_core::{Driver, Platform, Tree, TreeError, parse_fast, parse_tree};
use serde_json::json;

#[test]
fn substitutions_are_sequential_even_when_the_original_prefilter_misses_later_rules() {
    let driver = Driver {
        rules: serde_json::from_value(json!({
        "full_text_sub": [{"search": "unmatched", "replace": "unused"}, {"search": "OLD_HEADER", "replace": "parent"}],
        "per_line_sub": [
            {"search": "^unused$", "replace": ""},
            {"search": "first", "replace": "second"},
            {"search": "second", "replace": "third"},
            {"search": "^ *discard$", "replace": ""}
        ]
        })).unwrap(),
        ..Driver::default()
    };
    let parsed = parse_tree(
        driver.clone(),
        "OLD_HEADER\n  first\n  discard\nplain\nunused\n  \n",
    )
    .unwrap();
    assert_eq!(parsed.dump_simple(false), ["parent", "  third", "plain"]);
    let fast = parse_fast(
        driver,
        &["parent", "  first", "  discard", "plain", "unused", "  "],
        false,
    )
    .unwrap();
    assert_eq!(fast.dump_simple(false), parsed.dump_simple(false));
}

#[test]
fn unicode_and_control_whitespace_normalize_without_changing_hierarchy() {
    let lines = [
        "parent",
        "  café\t\u{a0}uplink  ",
        "  address\tvalue",
        "second",
        "  stable",
    ];
    for parsed in [
        parse_tree(Driver::default(), &lines.join("\n")).unwrap(),
        parse_fast(Driver::default(), &lines, false).unwrap(),
    ] {
        assert_eq!(
            parsed.dump_simple(false),
            [
                "parent",
                "  café uplink",
                "  address value",
                "second",
                "  stable"
            ]
        );
    }
}

#[test]
fn custom_callbacks_run_in_order_after_sectional_exit_cleanup() {
    fn first(tree: &mut Tree) {
        assert_eq!(
            tree.dump_simple(false),
            ["interface Ethernet1", "  description link"]
        );
        tree.add_child(tree.root, "first callback", false, false)
            .unwrap();
    }
    fn second(tree: &mut Tree) {
        assert!(tree.arena[tree.root].children.contains("first callback"));
        tree.add_child(tree.root, "second callback", false, false)
            .unwrap();
    }
    let callbacks: [fn(&mut Tree); 2] = [first, second];
    let text = "interface Ethernet1\n  description link\n  exit";
    let full = parse_tree_with_callbacks(Driver::for_platform(Platform::CiscoIos), text, callbacks)
        .unwrap();
    let fast = parse_fast_with_callbacks(
        Driver::for_platform(Platform::CiscoIos),
        &text.lines().collect::<Vec<_>>(),
        false,
        callbacks,
    )
    .unwrap();
    assert_eq!(
        full.dump_simple(false),
        [
            "interface Ethernet1",
            "  description link",
            "first callback",
            "second callback"
        ]
    );
    assert_eq!(fast.dump_simple(false), full.dump_simple(false));
}

#[test]
fn banner_quotes_bang_terminators_and_empty_motd_are_preserved() {
    for (text, expected) in [
        (
            "banner motd \"hello\nworld\"\nhostname edge",
            vec!["banner motd \"hello\nworld\"", "hostname edge"],
        ),
        (
            "banner login\nhello\n!\nhostname edge",
            vec!["banner login\nhello", "hostname edge"],
        ),
        (
            "banner motd ##\nhostname edge",
            vec!["banner motd ##", "hostname edge"],
        ),
    ] {
        let tree = parse_tree(Driver::default(), text).unwrap();
        assert_eq!(tree.dump_simple(false), expected);
    }
    assert!(
        matches!(parse_tree(Driver::default(), "banner login\nunfinished"), Err(TreeError::UnterminatedBanner(line)) if line == "banner login")
    );
}

#[test]
fn hierarchical_set_conversion_handles_siblings_and_preformatted_commands() {
    let text = "\nsystem {\n    name old;\n    nested {\n        value 1;\n    }\n    other 2;\n}\nset outside value\ndelete outside old\nbare leaf;\n";
    let expected = "set system name old\nset system nested value 1\nset system other 2\nset outside value\ndelete outside old\nset bare leaf";
    assert_eq!(convert_to_set_commands(text), expected);
    for platform in [Platform::JuniperJunos, Platform::Vyos, Platform::NokiaSrl] {
        assert_eq!(
            parse_tree(Driver::for_platform(platform), text)
                .unwrap()
                .dump_simple(false),
            expected.lines().collect::<Vec<_>>()
        );
    }
}
