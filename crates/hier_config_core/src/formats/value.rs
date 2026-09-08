//! Python-compatible JSON scalar encoding.
//!
//! Node text embeds JSON scalars, so the encoder has to agree byte-for-byte
//! with what `json.dumps` produced when these trees were first written by the
//! Python implementation -- a config that round-trips through a different
//! escaping convention would diff against itself. Two `serde_json` defaults
//! differ from `json.dumps` and are overridden here:
//!
//! * `json.dumps` defaults to `ensure_ascii=True`, escaping every non-ASCII
//!   character as `\uXXXX` (astral planes as surrogate pairs).
//! * `json.dumps` emits `Infinity`/`NaN`, which `serde_json` refuses to
//!   represent at all.

use serde_json::Value;
use std::fmt::Write;

/// Renders a JSON value the way `json.dumps` would with no `indent`.
pub(crate) fn dumps(value: &Value) -> String {
    let mut out = String::new();
    write_value(&mut out, value, None, 0);
    out
}

/// Renders a JSON value the way `json.dumps` would with `indent` spaces.
pub(crate) fn dumps_indented(value: &Value, indent: Option<usize>) -> String {
    let mut out = String::new();
    write_value(&mut out, value, indent, 0);
    out
}

/// Parses node-text payload back into a value, falling back to the raw text.
///
/// Mirrors Python's `loads`-with-`except JSONDecodeError` idiom: text that is
/// not valid JSON is simply an unquoted string that was never JSON to start
/// with, which is the common case for CLI-derived values.
pub(crate) fn leaf_value(raw: &str) -> Value {
    serde_json::from_str(raw).unwrap_or_else(|_| Value::String(raw.to_owned()))
}

/// Unwraps a leaf payload to a plain string, preserving non-string values.
pub(crate) fn text_value(raw: &str) -> String {
    match leaf_value(raw) {
        Value::String(text) => text,
        _ => raw.to_owned(),
    }
}

fn write_value(out: &mut String, value: &Value, indent: Option<usize>, depth: usize) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(number) => write_number(out, number),
        Value::String(text) => write_string(out, text),
        Value::Array(items) => {
            write_seq(out, items.iter().map(Entry::Item), indent, depth, '[', ']');
        }
        Value::Object(members) => write_seq(
            out,
            members.iter().map(|(k, v)| Entry::Member(k, v)),
            indent,
            depth,
            '{',
            '}',
        ),
    }
}

enum Entry<'a> {
    Item(&'a Value),
    Member(&'a str, &'a Value),
}

fn write_seq<'a>(
    out: &mut String,
    entries: impl ExactSizeIterator<Item = Entry<'a>>,
    indent: Option<usize>,
    depth: usize,
    open: char,
    close: char,
) {
    out.push(open);
    if entries.len() == 0 {
        out.push(close);
        return;
    }
    let inner = depth + 1;
    for (position, entry) in entries.enumerate() {
        if position > 0 {
            out.push(',');
            // `json.dumps` separators: `", "` when compact, `","` plus the
            // newline break when indented.
            if indent.is_none() {
                out.push(' ');
            }
        }
        write_break(out, indent, inner);
        match entry {
            Entry::Item(value) => write_value(out, value, indent, inner),
            Entry::Member(key, value) => {
                write_string(out, key);
                out.push_str(": ");
                write_value(out, value, indent, inner);
            }
        }
    }
    write_break(out, indent, depth);
    out.push(close);
}

fn write_break(out: &mut String, indent: Option<usize>, depth: usize) {
    if let Some(width) = indent {
        out.push('\n');
        for _ in 0..(width * depth) {
            out.push(' ');
        }
    }
}

fn write_number(out: &mut String, number: &serde_json::Number) {
    if let Some(float) = number.as_f64()
        && !float.is_finite()
    {
        // `json.dumps` emits these bare tokens rather than failing.
        out.push_str(if float.is_nan() {
            "NaN"
        } else if float > 0.0 {
            "Infinity"
        } else {
            "-Infinity"
        });
        return;
    }
    out.push_str(&number.to_string());
}

fn write_string(out: &mut String, text: &str) {
    out.push('"');
    for character in text.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            _ if !(' '..='\u{7e}').contains(&character) => write_escaped(out, character),
            _ => out.push(character),
        }
    }
    out.push('"');
}

fn write_escaped(out: &mut String, character: char) {
    let code = character as u32;
    if let Ok(unit) = u16::try_from(code) {
        let _ = write!(out, "\\u{unit:04x}");
        return;
    }
    // Astral plane: `ensure_ascii` emits a UTF-16 surrogate pair.
    let mut units = [0_u16; 2];
    for unit in character.encode_utf16(&mut units) {
        let _ = write!(out, "\\u{unit:04x}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn non_ascii_is_escaped_like_ensure_ascii() {
        assert_eq!(dumps(&json!("café")), r#""caf\u00e9""#);
        assert_eq!(dumps(&json!("—")), r#""\u2014""#);
    }

    #[test]
    fn astral_characters_become_surrogate_pairs() {
        assert_eq!(dumps(&json!("😀")), r#""\ud83d\ude00""#);
    }

    #[test]
    fn control_characters_use_short_escapes() {
        assert_eq!(dumps(&json!("a\nb\tc\u{1}")), r#""a\nb\tc\u0001""#);
    }

    #[test]
    fn floats_keep_their_trailing_zero() {
        assert_eq!(dumps(&json!(1.0)), "1.0");
    }

    #[test]
    fn empty_containers_stay_on_one_line_when_indented() {
        assert_eq!(dumps_indented(&json!({}), Some(2)), "{}");
        assert_eq!(
            dumps_indented(&json!({"a": []}), Some(2)),
            "{\n  \"a\": []\n}"
        );
    }

    #[test]
    fn indent_matches_python_separators() {
        assert_eq!(
            dumps_indented(&json!({"a": 1, "b": {"c": 2}}), Some(2)),
            "{\n  \"a\": 1,\n  \"b\": {\n    \"c\": 2\n  }\n}"
        );
    }

    #[test]
    fn compact_form_uses_python_separators() {
        assert_eq!(
            dumps(&json!({"a": 1, "b": [1, 2]})),
            r#"{"a": 1, "b": [1, 2]}"#
        );
    }

    #[test]
    fn leaf_value_falls_back_to_raw_text() {
        assert_eq!(leaf_value("Et1"), json!("Et1"));
        assert_eq!(leaf_value("1500"), json!(1500));
        assert_eq!(leaf_value("\"quoted\""), json!("quoted"));
    }

    #[test]
    fn text_value_unwraps_only_strings() {
        assert_eq!(text_value("\"Et1\""), "Et1");
        assert_eq!(text_value("1500"), "1500");
    }
}
