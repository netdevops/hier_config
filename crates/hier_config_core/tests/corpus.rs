use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;
use serde::Deserialize;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize)]
struct CaseManifest {
    platform: String,
    #[serde(default)]
    assert_rollback: Option<bool>,
}

struct CorpusCase {
    name: String,
    manifest: CaseManifest,
    running: String,
    intended: String,
    expected_remediation: Vec<String>,
}

fn discover_cases(cases_dir: &Path) -> Result<Vec<CorpusCase>, String> {
    if !cases_dir.is_dir() {
        return Err(format!(
            "Corpus cases directory does not exist: {}",
            cases_dir.display()
        ));
    }

    let mut cases = Vec::new();
    let mut platform_entries: Vec<PathBuf> = fs::read_dir(cases_dir)
        .map_err(|e| format!("Failed to read {}: {e}", cases_dir.display()))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .collect();
    platform_entries.sort();

    for platform_dir in platform_entries {
        let mut case_entries: Vec<PathBuf> = fs::read_dir(&platform_dir)
            .map_err(|e| format!("Failed to read {}: {e}", platform_dir.display()))?
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .filter(|path| path.is_dir())
            .collect();
        case_entries.sort();

        for case_dir in case_entries {
            let manifest_path = case_dir.join("case.json");
            if !manifest_path.is_file() {
                continue;
            }

            let manifest_str = fs::read_to_string(&manifest_path)
                .map_err(|e| format!("Failed to read {}: {e}", manifest_path.display()))?;
            let manifest: CaseManifest = serde_json::from_str(&manifest_str)
                .map_err(|e| format!("Invalid JSON in {}: {e}", manifest_path.display()))?;

            let running_path = case_dir.join("running.conf");
            let running = fs::read_to_string(&running_path)
                .map_err(|e| format!("Missing or unreadable {}: {e}", running_path.display()))?;

            let intended_path = case_dir.join("intended.conf");
            let intended = fs::read_to_string(&intended_path)
                .map_err(|e| format!("Missing or unreadable {}: {e}", intended_path.display()))?;

            let remediation_path = case_dir.join("remediation.conf");
            let expected_remediation = if remediation_path.is_file() {
                let content = fs::read_to_string(&remediation_path)
                    .map_err(|e| format!("Failed to read {}: {e}", remediation_path.display()))?;
                content.lines().map(ToString::to_string).collect()
            } else {
                Vec::new()
            };

            let platform_name = platform_dir
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or_default();
            let case_sub = case_dir
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or_default();
            let case_name = format!("{platform_name}/{case_sub}");

            cases.push(CorpusCase {
                name: case_name,
                manifest,
                running,
                intended,
                expected_remediation,
            });
        }
    }

    Ok(cases)
}

fn run_case(case: &CorpusCase) -> Result<(), String> {
    let platform: Platform = case.manifest.platform.parse().map_err(|_| {
        format!(
            "[{}] Unknown platform: {}",
            case.name, case.manifest.platform
        )
    })?;

    let running = Tree::from_str(platform, &case.running)
        .map_err(|e| format!("[{}] Failed to parse running.conf: {e}", case.name))?;
    let intended = Tree::from_str(platform, &case.intended)
        .map_err(|e| format!("[{}] Failed to parse intended.conf: {e}", case.name))?;

    let remediation = running
        .config_to_get_to(&intended)
        .map_err(|e| format!("[{}] Remediation calculation failed: {e}", case.name))?;
    let actual_lines = remediation.dump_simple(false);

    if actual_lines != case.expected_remediation {
        let expected_str = case.expected_remediation.join("\n");
        let actual_str = actual_lines.join("\n");
        return Err(format!(
            "[{}] Remediation output mismatch:\n=== Expected ===\n{}\n=== Actual ===\n{}",
            case.name, expected_str, actual_str
        ));
    }

    let assert_rollback = case.manifest.assert_rollback.unwrap_or(true);
    if assert_rollback {
        let future = running
            .future(&remediation, false)
            .map_err(|e| format!("[{}] Running future() failed: {e}", case.name))?;
        let rollback = future
            .config_to_get_to(&running)
            .map_err(|e| format!("[{}] Rollback calculation failed: {e}", case.name))?;
        let restored = future
            .future(&rollback, false)
            .map_err(|e| format!("[{}] Rollback future() failed: {e}", case.name))?;
        let diff = restored.unified_diff(&running);
        if !diff.is_empty() {
            return Err(format!(
                "[{}] Rollback did not cleanly restore running config:\n{}",
                case.name,
                diff.join("\n")
            ));
        }
    }

    Ok(())
}

#[test]
fn test_corpus_round_trip() {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let cases_dir = manifest_dir.join("../../testdata/cases");

    let cases = discover_cases(&cases_dir).expect("Corpus directory should be valid");
    assert!(
        !cases.is_empty(),
        "Corpus is empty - testdata/cases/ contains no case.json"
    );

    let mut failures = Vec::new();
    for case in &cases {
        if let Err(err) = run_case(case) {
            failures.push(err);
        }
    }

    assert!(
        failures.is_empty(),
        "Corpus test failures ({} of {} failed):\n\n{}",
        failures.len(),
        cases.len(),
        failures.join("\n\n")
    );
}
