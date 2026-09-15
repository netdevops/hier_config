//! Render the canonical stub from the metadata compiled with the bindings.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode, Stdio};

fn ruff(
    input: &[u8],
    arguments: &[&str],
    root: &Path,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let mut child = Command::new("uv")
        .args(["run", "--no-sync", "ruff"])
        .args(arguments)
        .args(["--stdin-filename", "hier_config/_hier_config_rust.pyi", "-"])
        .current_dir(root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    let written = child
        .stdin
        .take()
        .ok_or("Ruff stdin is unavailable")?
        .write_all(input);
    let output = child.wait_with_output()?;
    if !output.status.success() {
        return Err(format!(
            "Ruff normalization failed ({}): {}",
            output.status,
            String::from_utf8_lossy(&output.stderr),
        )
        .into());
    }
    written?;
    Ok(output.stdout)
}

/// Name and local bases of a top-level class in the rendered stub.
struct ClassBlock {
    name: String,
    bases: Vec<String>,
    lines: Vec<String>,
}

/// Parse `class Name(Base, Other):` into its name and base names.
fn parse_class_header(line: &str) -> Option<(String, Vec<String>)> {
    let declaration = line.strip_prefix("class ")?;
    let (name, rest) = declaration.split_at(declaration.find(['(', ':'])?);
    let bases = rest
        .trim_start_matches('(')
        .trim_end_matches(&[':', ')'][..])
        .split(',')
        .map(|base| base.trim().to_owned())
        .filter(|base| !base.is_empty())
        .collect();
    Some((name.trim().to_owned(), bases))
}

/// Emit every class after the classes it inherits from.
///
/// pyo3-stub-gen orders classes alphabetically. Astroid resolves a base class
/// by scanning names declared *earlier* in the module, so a subclass rendered
/// above its base silently loses its inherited members and Pylint stops
/// reporting invalid attribute access on it.
fn order_classes_by_dependency(source: &str) -> String {
    let lines: Vec<&str> = source.lines().collect();
    let starts: Vec<usize> = (0..lines.len())
        .filter(|index| lines[*index].starts_with("class "))
        .map(|index| {
            let mut start = index;
            while start > 0 && lines[start - 1].starts_with('@') {
                start -= 1;
            }
            start
        })
        .collect();
    let (Some(&first), Some(&last)) = (starts.first(), starts.last()) else {
        return source.to_owned();
    };
    let end = (last..lines.len())
        .find(|index| lines[*index].starts_with("def ") || lines[*index].starts_with("async def "))
        .unwrap_or(lines.len());

    let mut blocks = Vec::new();
    for (position, &start) in starts.iter().enumerate() {
        let stop = starts.get(position + 1).copied().unwrap_or(end);
        let header = lines[start..stop]
            .iter()
            .find(|line| line.starts_with("class "))
            .expect("a class block always contains its header");
        let (name, bases) = parse_class_header(header).expect("headers are rendered canonically");
        blocks.push(ClassBlock {
            name,
            bases,
            lines: lines[start..stop]
                .iter()
                .map(|&line| line.to_owned())
                .collect(),
        });
    }

    let local: std::collections::HashSet<&str> =
        blocks.iter().map(|block| block.name.as_str()).collect();
    let mut emitted: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut ordered: Vec<&ClassBlock> = Vec::with_capacity(blocks.len());
    while ordered.len() < blocks.len() {
        let ready: Vec<&ClassBlock> = blocks
            .iter()
            .filter(|block| !emitted.contains(&block.name))
            .filter(|block| {
                block
                    .bases
                    .iter()
                    .all(|base| !local.contains(base.as_str()) || emitted.contains(base))
            })
            .collect();
        if ready.is_empty() {
            // A cycle cannot be ordered; leave the remainder as rendered.
            ordered.extend(blocks.iter().filter(|block| !emitted.contains(&block.name)));
            break;
        }
        for block in ready {
            emitted.insert(block.name.clone());
            ordered.push(block);
        }
    }

    let mut rendered: Vec<String> = lines[..first].iter().map(|&line| line.to_owned()).collect();
    for block in ordered {
        rendered.extend(block.lines.iter().cloned());
    }
    rendered.extend(lines[end..].iter().map(|&line| line.to_owned()));
    let mut text = rendered.join("\n");
    text.push('\n');
    text
}

/// Slot methods whose parameters `CPython` always treats as positional-only.
///
/// pyo3-stub-gen renders them as ordinary positional-or-keyword parameters, so
/// the generated stub disagrees with the runtime until the marker is added.
/// `__init__` and `__new__` are deliberately absent: `PyO3` accepts keywords for
/// those, so they are not positional-only.
const POSITIONAL_ONLY_SLOTS: &[&str] = &[
    "__contains__",
    "__delitem__",
    "__eq__",
    "__ge__",
    "__getitem__",
    "__gt__",
    "__le__",
    "__lt__",
    "__ne__",
    "__setitem__",
];

/// Close the paren opened at `open`, returning the index of its match.
fn closing_paren(source: &str, open: usize) -> Option<usize> {
    let mut depth = 0_usize;
    for (offset, character) in source[open..].char_indices() {
        match character {
            '(' => depth += 1,
            ')' => {
                depth -= 1;
                if depth == 0 {
                    return Some(open + offset);
                }
            }
            _ => (),
        }
    }
    None
}

/// Mark the parameters of `CPython` slot methods positional-only.
fn mark_slot_parameters_positional_only(source: &str) -> String {
    let mut rendered = source.to_owned();
    for slot in POSITIONAL_ONLY_SLOTS {
        let needle = format!("def {slot}(");
        let mut cursor = 0;
        while let Some(found) = rendered[cursor..].find(&needle) {
            let open = cursor + found + needle.len() - 1;
            let Some(close) = closing_paren(&rendered, open) else {
                break;
            };
            let parameters = &rendered[open + 1..close];
            if parameters.contains(',') && !parameters.contains('/') && !parameters.contains('*') {
                rendered.insert_str(close, ", /");
                cursor = close + 4;
            } else {
                cursor = close;
            }
        }
    }
    rendered
}

fn write_or_check(
    output: &Path,
    rendered: &str,
    check: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    if check {
        let current = std::fs::read_to_string(output)?;
        if current != rendered {
            return Err(format!("{} is stale; regenerate native stubs", output.display()).into());
        }
    } else {
        std::fs::write(output, rendered)?;
    }
    Ok(())
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let mut check = false;
    let mut output =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../hier_config/_hier_config_rust.pyi");
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--check" => check = true,
            "--output" => output = args.next().ok_or("--output requires a path")?.into(),
            _ => return Err(format!("unknown argument: {arg}").into()),
        }
    }
    pyo3::Python::initialize();
    let info = _hier_config_rust::stub_info()?;
    let module = info
        .modules
        .get("hier_config._hier_config_rust")
        .ok_or("native module metadata is missing")?;
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let marked = mark_slot_parameters_positional_only(&module.to_string());
    let ordered = order_classes_by_dependency(&marked);
    let formatted = ruff(ordered.as_bytes(), &["format", "--quiet"], &root)?;
    let fixed = ruff(&formatted, &["check", "--fix", "--quiet"], &root)?;
    let rendered = String::from_utf8(ruff(&fixed, &["format", "--quiet"], &root)?)?;
    write_or_check(&output, &rendered, check)
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        mark_slot_parameters_positional_only, order_classes_by_dependency, write_or_check,
    };

    #[test]
    fn bases_are_emitted_before_their_subclasses() {
        let rendered = order_classes_by_dependency(concat!(
            "import builtins\n",
            "class Child(Base):\n",
            "    pass\n",
            "@typing.final\n",
            "class Base:\n",
            "    pass\n",
            "def helper() -> None: ...\n",
        ));

        assert_eq!(
            rendered,
            concat!(
                "import builtins\n",
                "@typing.final\n",
                "class Base:\n",
                "    pass\n",
                "class Child(Base):\n",
                "    pass\n",
                "def helper() -> None: ...\n",
            )
        );
    }

    #[test]
    fn foreign_bases_never_reorder_a_class() {
        let source = concat!(
            "class Alpha(builtins.Exception):\n",
            "    pass\n",
            "class Beta(builtins.Exception):\n",
            "    pass\n",
        );

        assert_eq!(order_classes_by_dependency(source), source);
    }

    #[test]
    fn a_cycle_leaves_the_rendered_order_untouched() {
        let source = concat!(
            "class Alpha(Beta):\n",
            "    pass\n",
            "class Beta(Alpha):\n",
            "    pass\n",
        );

        assert_eq!(order_classes_by_dependency(source), source);
    }

    #[test]
    fn a_stub_without_classes_is_returned_unchanged() {
        let source = "import builtins\ndef helper() -> None: ...\n";

        assert_eq!(order_classes_by_dependency(source), source);
    }

    #[test]
    fn slot_parameters_become_positional_only() {
        let rendered = mark_slot_parameters_positional_only(
            "    def __eq__(self, other: object) -> bool: ...\n",
        );

        assert_eq!(
            rendered,
            "    def __eq__(self, other: object, /) -> bool: ...\n"
        );
    }

    #[test]
    fn nested_parentheses_do_not_confuse_the_marker() {
        let rendered = mark_slot_parameters_positional_only(
            "    def __setitem__(self, item: int, value: Callable[(int,), str]) -> None: ...\n",
        );

        assert_eq!(
            rendered,
            "    def __setitem__(self, item: int, value: Callable[(int,), str], /) -> None: ...\n"
        );
    }

    #[test]
    fn existing_markers_and_lone_self_are_left_alone() {
        let source = concat!(
            "    def __getitem__(self, item: int, /) -> str: ...\n",
            "    def __eq__(self, *others: object) -> bool: ...\n",
            "    def __contains__(self) -> bool: ...\n",
            "    def __init__(self, text: str) -> None: ...\n",
        );

        assert_eq!(mark_slot_parameters_positional_only(source), source);
    }

    #[test]
    fn every_occurrence_of_a_slot_is_marked() {
        let rendered = mark_slot_parameters_positional_only(concat!(
            "    def __ne__(self, other: object) -> bool: ...\n",
            "    def __ne__(self, other: int) -> bool: ...\n",
        ));

        assert_eq!(
            rendered,
            concat!(
                "    def __ne__(self, other: object, /) -> bool: ...\n",
                "    def __ne__(self, other: int, /) -> bool: ...\n",
            )
        );
    }

    #[test]
    fn stale_check_preserves_existing_bytes() {
        let directory = tempfile::tempdir_in(env!("CARGO_MANIFEST_DIR")).unwrap();
        let output = directory.path().join("native.pyi");
        let original = b"# stale content\r\n";
        std::fs::write(&output, original).unwrap();

        let error = write_or_check(&output, "# current content\n", true).unwrap_err();

        assert!(error.to_string().contains("is stale"));
        assert_eq!(std::fs::read(&output).unwrap(), original);
    }

    #[test]
    fn missing_output_check_does_not_create_the_file() {
        let directory = tempfile::tempdir_in(env!("CARGO_MANIFEST_DIR")).unwrap();
        let output = directory.path().join("missing.pyi");

        assert!(write_or_check(&output, "# current content\n", true).is_err());
        assert!(!output.exists());
    }

    #[test]
    fn writing_then_checking_preserves_current_output() {
        let directory = tempfile::tempdir_in(env!("CARGO_MANIFEST_DIR")).unwrap();
        let output = directory.path().join("native.pyi");
        let rendered = "# current content\n";

        write_or_check(&output, rendered, false).unwrap();
        write_or_check(&output, rendered, true).unwrap();

        assert_eq!(std::fs::read_to_string(output).unwrap(), rendered);
    }
}
