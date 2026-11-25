//! Guards against reintroducing regex compilation on hot paths.
//!
//! Compiling a regex costs ~10-100us; running an already-compiled one costs
//! ~25ns. Building a `Regex` inside a per-line or per-node loop is therefore a
//! ~1000x pessimisation, and it is completely invisible to the test suite --
//! every result stays correct, the code just crawls.
//!
//! This is not hypothetical. 19 sites once compiled their regexes per call.
//! Routing them all through `regex_cache` took a 10k-line parse from 7354ms to
//! 16ms, a 460x improvement, and no functional test noticed either way.
//!
//! So the rule is mechanical: `regex_cache` is the only module allowed to call
//! a regex constructor. Everything else goes through its process-wide cache.

use std::fs;
use std::path::{Path, PathBuf};

/// Modules permitted to construct a regex directly.
const ALLOWED: &[&str] = &["regex_cache.rs"];

/// Constructors that compile a pattern at runtime.
const CONSTRUCTORS: &[&str] = &["Regex::new", "RegexBuilder::new", "RegexSet::new"];

fn rust_sources(dir: &Path, out: &mut Vec<PathBuf>) {
    let entries = fs::read_dir(dir).expect("failed to read source directory");
    for entry in entries {
        let path = entry.expect("failed to read directory entry").path();
        if path.is_dir() {
            rust_sources(&path, out);
        } else if path.extension().is_some_and(|ext| ext == "rs") {
            out.push(path);
        }
    }
}

#[test]
fn regexes_are_only_compiled_through_the_cache() {
    let src = Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
    let mut files = Vec::new();
    rust_sources(&src, &mut files);
    assert!(!files.is_empty(), "no Rust sources found under {src:?}");

    let mut offenders = Vec::new();

    for file in &files {
        let name = file
            .file_name()
            .and_then(|n| n.to_str())
            .expect("source file has a valid name");
        if ALLOWED.contains(&name) {
            continue;
        }

        let contents = fs::read_to_string(file).expect("failed to read source file");
        for (lineno, line) in contents.lines().enumerate() {
            // Doc comments and ordinary comments legitimately mention the API.
            let trimmed = line.trim_start();
            if trimmed.starts_with("//") {
                continue;
            }
            for ctor in CONSTRUCTORS {
                if line.contains(ctor) {
                    offenders.push(format!("{}:{}: {}", name, lineno + 1, trimmed));
                }
            }
        }
    }

    assert!(
        offenders.is_empty(),
        "regexes must be compiled once via `crate::regex_cache`, never inline.\n\
         Compiling in a loop is ~1000x slower and no functional test will catch it.\n\
         Use `regex_cache::regex(..)` or `regex_cache::fancy(..)` instead.\n\
         Offending sites:\n  {}",
        offenders.join("\n  ")
    );
}
