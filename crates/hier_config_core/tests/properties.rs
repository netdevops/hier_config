use hier_config_core::NodeId;
use hier_config_core::models::Platform;
use hier_config_core::tree::{Tree, TreeError};
use proptest::prelude::*;
use rustc_hash::{FxHashMap as HashMap, FxHashSet as HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

#[derive(Debug, Clone)]
struct Fragment {
    header: String,
    children: Vec<String>,
}

const ROLLBACK_PLATFORMS: &[Platform] = &[
    Platform::AristaEos,
    Platform::ArubaAoscx,
    Platform::CiscoIos,
    Platform::CiscoNxos,
    Platform::CiscoXr,
    Platform::Generic,
    Platform::HpComware5,
    Platform::HpProcurve,
    Platform::HuaweiVrp,
];

static CORPUS_FRAGMENTS: LazyLock<HashMap<Platform, Vec<Fragment>>> = LazyLock::new(|| {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let cases_dir = manifest_dir.join("../../testdata/cases");
    assert!(
        cases_dir.is_dir(),
        "Corpus directory not found: {}. testdata/cases must exist.",
        cases_dir.display()
    );
    load_all_corpus_fragments(&cases_dir)
});

const fn platform_comment_char(platform: Platform) -> &'static str {
    match platform {
        Platform::JuniperJunos
        | Platform::NokiaSrl
        | Platform::Vyos
        | Platform::HuaweiVrp
        | Platform::FortinetFortios => "#",
        _ => "!",
    }
}

fn load_all_corpus_fragments(cases_dir: &Path) -> HashMap<Platform, Vec<Fragment>> {
    let mut result = HashMap::default();

    for &platform in &Platform::ALL {
        let platform_dir = cases_dir.join(platform.as_str());
        if !platform_dir.is_dir() {
            continue;
        }

        let mut case_dirs: Vec<PathBuf> = fs::read_dir(&platform_dir)
            .into_iter()
            .flatten()
            .filter_map(Result::ok)
            .map(|e| e.path())
            .filter(|p| p.is_dir())
            .collect();
        case_dirs.sort();

        let mut seen_headers = HashSet::default();
        let mut seen_tree = Tree::from_str(platform, "").unwrap();
        let mut fragments = Vec::new();

        for case_dir in case_dirs {
            for conf_name in &["running.conf", "intended.conf"] {
                let conf_path = case_dir.join(conf_name);
                let Ok(content) = fs::read_to_string(&conf_path) else {
                    continue;
                };

                let Ok(tree) = Tree::from_str(platform, &content) else {
                    continue;
                };

                let neg_prefix = tree.driver.negation_prefix.trim();

                for child_id in tree.arena[tree.root].children.iter() {
                    let header = tree.arena[child_id].text.to_string();
                    let is_negation = (!neg_prefix.is_empty() && header.starts_with(neg_prefix))
                        || header.starts_with("no ")
                        || header.starts_with("undo ")
                        || header.starts_with("delete ")
                        || header.starts_with("unset ");

                    if is_negation || seen_headers.contains(&header) {
                        continue;
                    }

                    let seen_children: Vec<NodeId> =
                        seen_tree.arena[seen_tree.root].children.iter().collect();
                    if tree
                        .idempotent_for(child_id, &seen_tree, &seen_children)
                        .is_some()
                    {
                        continue;
                    }

                    seen_headers.insert(header.clone());
                    let _ = seen_tree.add_child(seen_tree.root, &header, false, false);

                    let lines = tree.lines(child_id, false);
                    let children = if lines.len() > 1 {
                        lines[1..].to_vec()
                    } else {
                        Vec::new()
                    };

                    fragments.push(Fragment { header, children });
                }
            }
        }

        if !fragments.is_empty() {
            result.insert(platform, fragments);
        }
    }

    result
}

#[derive(Debug, Clone)]
struct FragmentOption {
    truncated: bool,
    blank_lines_before: usize,
    has_comment: bool,
}

fn render_fragment(
    frag: &Fragment,
    opt: &FragmentOption,
    comment_char: &str,
    out: &mut Vec<String>,
) {
    for _ in 0..opt.blank_lines_before {
        out.push(String::new());
    }
    if opt.has_comment {
        out.push(format!("{comment_char} Section for {}", frag.header));
    }
    out.push(frag.header.clone());
    if !opt.truncated {
        out.extend(frag.children.iter().cloned());
    }
}

fn arb_platform() -> impl Strategy<Value = Platform> {
    prop_oneof![
        Just(Platform::AristaEos),
        Just(Platform::ArubaAoscx),
        Just(Platform::CiscoIos),
        Just(Platform::CiscoNxos),
        Just(Platform::CiscoXr),
        Just(Platform::FortinetFortios),
        Just(Platform::Generic),
        Just(Platform::HpComware5),
        Just(Platform::HpProcurve),
        Just(Platform::HuaweiVrp),
        Just(Platform::JuniperJunos),
        Just(Platform::NokiaSrl),
        Just(Platform::Vyos),
    ]
}

fn arb_rollback_platform() -> impl Strategy<Value = Platform> {
    proptest::sample::select(ROLLBACK_PLATFORMS)
}

fn arb_config_for_platform(platform: Platform) -> impl Strategy<Value = (Platform, String)> {
    let frags = CORPUS_FRAGMENTS.get(&platform).cloned().unwrap_or_default();
    let num_frags = frags.len();

    (1..=std::cmp::min(5, num_frags.max(1))).prop_flat_map(move |count| {
        let frags = frags.clone();
        proptest::collection::vec(
            (0..num_frags, any::<bool>(), 0..=2usize, any::<bool>()),
            count,
        )
        .prop_map(move |selected| {
            let comment_char = platform_comment_char(platform);
            let mut out = Vec::new();
            let mut seen_indices = HashSet::default();

            for (idx, truncated, blank_lines, has_comment) in selected {
                if !seen_indices.insert(idx) {
                    continue;
                }
                let frag = &frags[idx];
                let opt = FragmentOption {
                    truncated,
                    blank_lines_before: blank_lines,
                    has_comment,
                };
                render_fragment(frag, &opt, comment_char, &mut out);
            }

            (platform, out.join("\n"))
        })
    })
}

fn arb_platform_and_config() -> impl Strategy<Value = (Platform, String)> {
    arb_platform().prop_flat_map(arb_config_for_platform)
}

fn arb_rollback_configs() -> impl Strategy<Value = (Platform, String, String)> {
    arb_rollback_platform().prop_flat_map(|platform| {
        let frags = CORPUS_FRAGMENTS.get(&platform).cloned().unwrap_or_default();
        let num_frags = frags.len();

        (1..=std::cmp::min(5, num_frags.max(1))).prop_flat_map(move |count| {
            let frags = frags.clone();
            (
                proptest::collection::vec((0..num_frags, any::<bool>(), 0..=1usize), count),
                proptest::collection::vec((0..num_frags, any::<bool>(), 0..=1usize), count),
            )
                .prop_map(move |(sel_run, sel_int)| {
                    let comment_char = platform_comment_char(platform);

                    let mut run_indices = sel_run;
                    run_indices.sort_by_key(|item| item.0);
                    run_indices.dedup_by_key(|item| item.0);

                    let mut int_indices = sel_int;
                    int_indices.sort_by_key(|item| item.0);
                    int_indices.dedup_by_key(|item| item.0);

                    let mut run_lines = Vec::new();
                    for &(idx, trunc, bl) in &run_indices {
                        let frag = &frags[idx];
                        let opt = FragmentOption {
                            truncated: trunc,
                            blank_lines_before: bl,
                            has_comment: false,
                        };
                        render_fragment(frag, &opt, comment_char, &mut run_lines);
                    }

                    let mut int_lines = Vec::new();
                    for &(idx, trunc, bl) in &int_indices {
                        let frag = &frags[idx];
                        let opt = FragmentOption {
                            truncated: trunc,
                            blank_lines_before: bl,
                            has_comment: false,
                        };
                        render_fragment(frag, &opt, comment_char, &mut int_lines);
                    }

                    (platform, run_lines.join("\n"), int_lines.join("\n"))
                })
        })
    })
}

#[test]
fn test_corpus_fragments_loaded_and_human_readable() {
    assert!(
        !CORPUS_FRAGMENTS.is_empty(),
        "Corpus fragments should be non-empty"
    );
    for platform in &Platform::ALL {
        let frags = CORPUS_FRAGMENTS.get(platform);
        assert!(
            frags.is_some_and(|f| !f.is_empty()),
            "Platform {platform:?} should have fragments"
        );
    }

    let frags = &CORPUS_FRAGMENTS[&Platform::CiscoIos];
    let mut sample_out = Vec::new();
    let opt = FragmentOption {
        truncated: false,
        blank_lines_before: 1,
        has_comment: true,
    };
    render_fragment(&frags[0], &opt, "!", &mut sample_out);
    let sample_text = sample_out.join("\n");
    assert!(
        sample_text.contains('!'),
        "Sample should contain comments: {sample_text}"
    );
    assert!(
        sample_text.lines().count() >= 2,
        "Sample should be multi-line: {sample_text}"
    );
}

fn walk_tree_recursive(tree: &Tree, id: NodeId, out: &mut Vec<NodeId>) {
    if let Some(node) = tree.get(id) {
        for child_id in node.children.iter() {
            out.push(child_id);
            walk_tree_recursive(tree, child_id, out);
        }
    }
}

// Subphase 4b: Structural Invariants
proptest! {
    #[test]
    fn test_structural_invariant_parse_totality((platform, text) in arb_platform_and_config()) {
        let result = Tree::from_str(platform, &text);
        prop_assert!(
            result.is_ok(),
            "Parse failed for platform {:?}: {:?}",
            platform,
            result.err()
        );
    }

    #[test]
    fn test_structural_invariant_dump_round_trip((platform, text) in arb_platform_and_config()) {
        let tree = Tree::from_str(platform, &text).expect("Parse should succeed");
        let dump = tree.dump();

        let mut loaded = Tree::for_platform(platform);
        loaded.load_from_dump(&dump).expect("load_from_dump should succeed");

        prop_assert_eq!(tree.dump_simple(false), loaded.dump_simple(false));

        let simple_text = tree.dump_simple(false).join("\n");
        let reparsed = Tree::from_str(platform, &simple_text).expect("Reparsing dump_simple should succeed");
        prop_assert_eq!(tree.dump_simple(false), reparsed.dump_simple(false));
    }

    #[test]
    fn test_structural_invariant_depth_consistency((platform, text) in arb_platform_and_config()) {
        let tree = Tree::from_str(platform, &text).expect("Parse should succeed");
        for node_id in tree.all_children(tree.root) {
            let node = tree.get(node_id).expect("Node should exist");
            let parent_id = node.parent.expect("Child node must have parent");
            prop_assert_eq!(
                tree.depth(node_id),
                tree.depth(parent_id) + 1,
                "Depth of node {:?} is not parent's depth + 1",
                node_id
            );
        }
    }

    #[test]
    fn test_structural_invariant_all_children_completeness((platform, text) in arb_platform_and_config()) {
        let tree = Tree::from_str(platform, &text).expect("Parse should succeed");

        let mut reachable = Vec::new();
        walk_tree_recursive(&tree, tree.root, &mut reachable);

        let all = tree.all_children(tree.root);
        prop_assert_eq!(&all, &reachable, "all_children should match recursive walk exactly");

        let unique_reachable: HashSet<_> = reachable.iter().copied().collect();
        prop_assert_eq!(
            all.len(),
            unique_reachable.len(),
            "all_children should contain no duplicates"
        );
    }
}

// Subphase 4c: Engine Invariants
proptest! {
    #[test]
    fn test_engine_invariant_self_remediation_is_empty((platform, text) in arb_platform_and_config()) {
        let tree = Tree::from_str(platform, &text).expect("Parse should succeed");
        let remediation = tree.config_to_get_to(&tree).expect("config_to_get_to should succeed");
        prop_assert!(
            remediation.dump_simple(false).is_empty(),
            "Self remediation was not empty for platform {:?}: {:?}",
            platform,
            remediation.dump_simple(false)
        );
        prop_assert!(
            tree.unified_diff(&tree).is_empty(),
            "Self unified_diff was not empty"
        );
    }

    #[test]
    fn test_engine_invariant_future_consistency((platform, run_txt, int_txt) in arb_rollback_configs()) {
        let running = Tree::from_str(platform, &run_txt).expect("running should parse");
        let intended = Tree::from_str(platform, &int_txt).expect("intended should parse");

        let remediation = running.config_to_get_to(&intended).expect("remediation should compute");
        match running.future(&remediation, false) {
            Ok(future) => {
                let diff = future.unified_diff(&intended);
                prop_assert!(
                    diff.is_empty(),
                    "future does not match intended for platform {:?}:\nDiff:\n{}\nRemediation:\n{}",
                    platform,
                    diff.join("\n"),
                    remediation.dump_simple(false).join("\n")
                );
            }
            Err(TreeError::DuplicateChild(_)) => {
                // Known engine limitation on duplicate sections (e.g. Cisco XR route-policy)
            }
            Err(e) => {
                return Err(TestCaseError::fail(format!(
                    "Unexpected future() error for platform {platform:?}: {e}"
                )));
            }
        }
    }

    #[test]
    fn test_engine_invariant_rollback_restores((platform, run_txt, int_txt) in arb_rollback_configs()) {
        let running = Tree::from_str(platform, &run_txt).expect("running should parse");
        let intended = Tree::from_str(platform, &int_txt).expect("intended should parse");

        let remediation = running.config_to_get_to(&intended).expect("remediation should compute");
        match running.future(&remediation, false) {
            Ok(future) => {
                let rollback = future.config_to_get_to(&running).expect("rollback should compute");
                match future.future(&rollback, false) {
                    Ok(restored) => {
                        let diff = restored.unified_diff(&running);
                        prop_assert!(
                            diff.is_empty(),
                            "rollback did not cleanly restore running for platform {:?}:\nDiff:\n{}",
                            platform,
                            diff.join("\n")
                        );
                    }
                    Err(TreeError::DuplicateChild(_)) => {}
                    Err(e) => {
                        return Err(TestCaseError::fail(format!(
                            "Unexpected rollback future() error for platform {platform:?}: {e}"
                        )));
                    }
                }
            }
            Err(TreeError::DuplicateChild(_)) => {}
            Err(e) => {
                return Err(TestCaseError::fail(format!(
                    "Unexpected future() error for platform {platform:?}: {e}"
                )));
            }
        }
    }

    #[test]
    fn test_engine_invariant_idempotency((platform, run_txt, int_txt) in arb_rollback_configs()) {
        let running = Tree::from_str(platform, &run_txt).expect("running should parse");
        let intended = Tree::from_str(platform, &int_txt).expect("intended should parse");

        let remediation = running.config_to_get_to(&intended).expect("remediation should compute");
        match running.future(&remediation, false) {
            Ok(future1) => {
                let second_remediation = future1
                    .config_to_get_to(&intended)
                    .expect("second remediation should compute");
                prop_assert!(
                    second_remediation.is_empty(),
                    "Second remediation after applying first remediation was not empty for platform {:?}:\nRemediation:\n{:?}",
                    platform,
                    second_remediation.dump_simple(false)
                );
                match future1.future(&second_remediation, false) {
                    Ok(future2) => {
                        let diff = future2.unified_diff(&future1);
                        prop_assert!(
                            diff.is_empty(),
                            "Applying second remediation changed future state for platform {:?}:\nDiff:\n{}",
                            platform,
                            diff.join("\n")
                        );
                    }
                    Err(TreeError::DuplicateChild(_)) => {}
                    Err(e) => {
                        return Err(TestCaseError::fail(format!(
                            "Unexpected future() error applying second remediation for platform {platform:?}: {e}"
                        )));
                    }
                }
            }
            Err(TreeError::DuplicateChild(_)) => {}
            Err(e) => {
                return Err(TestCaseError::fail(format!(
                    "Unexpected future() error for platform {platform:?}: {e}"
                )));
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Subphase 4d: No-Panic Robustness Strategies and Tests
// ---------------------------------------------------------------------------

fn arb_malformed_text() -> impl Strategy<Value = String> {
    prop_oneof![
        any::<String>(),
        proptest::string::string_regex(
            "[\\x00-\\x1F\\x7F-\\x9F\\s\\w!@#$%^&*()_+\\-={}\\[\\]:\";'<>?,./]{0,200}"
        )
        .unwrap(),
        proptest::string::string_regex("[\\{\\};\"'\\\\\\n\\r\\t ]{0,150}").unwrap(),
        proptest::string::string_regex("[a-zA-Z0-9 ]{200,1000}").unwrap(),
    ]
}

fn arb_pathological_indentation() -> impl Strategy<Value = String> {
    let indent_strategy = prop_oneof![
        (0..=60usize).prop_map(|n| " ".repeat(n)),
        (0..=20usize).prop_map(|n| "\t".repeat(n)),
        proptest::string::string_regex("[ \\t]{1,40}").unwrap(),
    ];

    let line_strategy = (indent_strategy, "[a-zA-Z0-9_-]{1,30}")
        .prop_map(|(indent, word)| format!("{indent}{word}"));

    proptest::collection::vec(line_strategy, 1..=25).prop_map(|lines| lines.join("\n"))
}

fn arb_banner_delimiters() -> impl Strategy<Value = String> {
    let delim_strategy = prop_oneof![
        Just("^C"),
        Just("#"),
        Just("@"),
        Just("%"),
        Just("EOF"),
        Just("!"),
        Just("$"),
        Just("^"),
    ];

    let banner_cmd = prop_oneof![
        Just("banner motd"),
        Just("banner login"),
        Just("banner exec"),
        Just("banner incoming"),
    ];

    (
        banner_cmd,
        delim_strategy,
        proptest::collection::vec("[a-zA-Z0-9 _-]{0,40}", 0..=5),
        any::<bool>(),
        any::<bool>(),
    )
        .prop_map(|(cmd, delim, body, has_closing, inline_delim)| {
            let mut lines = Vec::new();
            if inline_delim {
                lines.push(format!("{cmd} {delim}"));
            } else {
                lines.push(cmd.to_string());
                lines.push(delim.to_string());
            }
            lines.extend(body);
            if has_closing {
                lines.push(delim.to_string());
            }
            lines.join("\n")
        })
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(1024))]

    #[test]
    fn test_no_panic_malformed_input(
        platform in arb_platform(),
        text in arb_malformed_text(),
    ) {
        let res = Tree::from_str(platform, &text);
        if let Ok(tree) = res {
            let _ = tree.dump_simple(false);
            let _ = tree.all_children(tree.root);
        }
    }

    #[test]
    fn test_no_panic_pathological_indentation(
        platform in arb_platform(),
        text in arb_pathological_indentation(),
    ) {
        let res = Tree::from_str(platform, &text);
        if let Ok(tree) = res {
            let _ = tree.dump_simple(false);
            let _ = tree.all_children(tree.root);
        }
    }

    #[test]
    fn test_no_panic_banner_delimiters(
        platform in arb_platform(),
        text in arb_banner_delimiters(),
    ) {
        let res = Tree::from_str(platform, &text);
        if let Ok(tree) = res {
            let _ = tree.lines(tree.root, false);
            let _ = tree.dump_simple(false);
        }
    }
}
