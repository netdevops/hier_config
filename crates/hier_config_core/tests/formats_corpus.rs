//! Holds the Rust format port to the Python reference implementation.
//!
//! `testdata/formats/expected.json` is captured from `hier_config/formats.py`
//! by `scripts/gen_formats_corpus.py`. It is the source of truth: when a case
//! mismatches, fix the Rust port, never the corpus.

use std::collections::BTreeMap;
use std::fs;
use std::path::PathBuf;

use hier_config_core::{
    Driver, GnmiRemediation, Platform, Tree, from_json, from_xml, to_gnmi_json, to_json,
    to_netconf_xml, to_xml,
};
use serde_json::{Map, Value};

/// A case key is `<name>|<PLATFORM>|<list_keys repr>`.
struct CaseKey {
    platform: Platform,
    list_keys: Option<Vec<String>>,
}

/// Python's `ElementTree` and `quick-xml` word parse failures differently, so
/// XML parse errors are compared on this shared prefix only.
const XML_PARSE_PREFIX: &str = "The config is not valid XML:";
/// `serde_json` and Python's `json` word parse failures differently too.
const JSON_PARSE_PREFIX: &str = "The config is not valid JSON:";

fn corpus() -> Map<String, Value> {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/formats/expected.json")
        .canonicalize()
        .expect("corpus path");
    let raw = fs::read_to_string(path).expect("read corpus");
    serde_json::from_str(&raw).expect("parse corpus")
}

fn parse_key(key: &str) -> CaseKey {
    let mut parts = key.splitn(3, '|');
    let _name = parts.next().expect("case name");
    let platform_name = parts.next().expect("platform name");
    let keys_repr = parts.next().expect("list_keys repr");

    let platform = Platform::ALL
        .into_iter()
        .find(|candidate| platform_name_of(*candidate) == platform_name)
        .unwrap_or_else(|| panic!("unknown platform {platform_name}"));

    let list_keys = if keys_repr == "None" {
        None
    } else {
        Some(
            keys_repr
                .trim_matches(|c| c == '(' || c == ')')
                .split(',')
                .map(|part| part.trim().trim_matches('\'').to_owned())
                .filter(|part| !part.is_empty())
                .collect(),
        )
    };

    CaseKey {
        platform,
        list_keys,
    }
}

const fn platform_name_of(platform: Platform) -> &'static str {
    match platform {
        Platform::AristaEos => "ARISTA_EOS",
        Platform::ArubaAoscx => "ARUBA_AOSCX",
        Platform::CiscoIos => "CISCO_IOS",
        Platform::CiscoNxos => "CISCO_NXOS",
        Platform::CiscoXr => "CISCO_XR",
        Platform::FortinetFortios => "FORTINET_FORTIOS",
        Platform::Generic => "GENERIC",
        Platform::HpComware5 => "HP_COMWARE5",
        Platform::HpProcurve => "HP_PROCURVE",
        Platform::HuaweiVrp => "HUAWEI_VRP",
        Platform::JuniperJunos => "JUNIPER_JUNOS",
        Platform::NokiaSrl => "NOKIA_SRL",
        Platform::Vyos => "VYOS",
    }
}

/// Compares one captured outcome against a Rust result.
fn assert_outcome<T, F>(label: &str, expected: &Value, actual: Result<T, String>, render: F)
where
    F: Fn(&T) -> Value,
{
    let expected = expected.as_object().expect("outcome object");
    match (expected.get("ok"), expected.get("err"), actual) {
        (Some(want), None, Ok(got)) => {
            assert_eq!(render(&got), *want, "{label}: value mismatch");
        }
        (None, Some(want), Err(got)) => {
            let want = want
                .as_str()
                .expect("error string")
                .split_once(": ")
                .expect("qualified error")
                .1;
            // Parse-failure wording comes from the underlying parser, which
            // differs between the two implementations.
            if want.starts_with(XML_PARSE_PREFIX) {
                assert!(got.starts_with(XML_PARSE_PREFIX), "{label}: got {got}");
            } else if want.starts_with(JSON_PARSE_PREFIX) {
                assert!(got.starts_with(JSON_PARSE_PREFIX), "{label}: got {got}");
            } else {
                assert_eq!(got, want, "{label}: error mismatch");
            }
        }
        (_, _, Ok(_)) => panic!("{label}: expected an error, got success"),
        (_, _, Err(error)) => panic!("{label}: expected success, got error {error}"),
    }
}

fn keys_slice(list_keys: Option<&Vec<String>>) -> Option<&[String]> {
    list_keys.map(Vec::as_slice)
}

fn simple(tree: &Tree) -> Value {
    Value::Array(
        tree.dump_simple(false)
            .into_iter()
            .map(Value::String)
            .collect(),
    )
}

fn gnmi_value(result: &GnmiRemediation) -> Value {
    let mut map = Map::new();
    map.insert("update".to_owned(), Value::Object(result.update.clone()));
    map.insert(
        "delete".to_owned(),
        Value::Array(
            result
                .delete
                .iter()
                .cloned()
                .map(Value::String)
                .collect::<Vec<_>>(),
        ),
    );
    Value::Object(map)
}

/// Sorts object keys so comparisons match the corpus, which is written with
/// `sort_keys=True`.
fn sorted(value: &Value) -> Value {
    match value {
        Value::Object(members) => Value::Object(
            members
                .iter()
                .map(|(key, member)| (key.clone(), sorted(member)))
                .collect::<BTreeMap<_, _>>()
                .into_iter()
                .collect(),
        ),
        Value::Array(items) => Value::Array(items.iter().map(sorted).collect()),
        other => other.clone(),
    }
}

#[test]
fn json_cases_match_python() {
    let corpus = corpus();
    let cases = corpus["json"].as_object().expect("json section");
    for (key, expected) in cases {
        let case = parse_key(key);
        let driver = Driver::for_platform(case.platform);
        let keys = keys_slice(case.list_keys.as_ref());
        let parsed = from_json(
            driver.clone(),
            source_of(&corpus, "json", key, "config"),
            keys,
        );

        assert_outcome(
            key,
            expected,
            parsed.map_err(|error| error.to_string()),
            |tree| {
                let mut map = Map::new();
                map.insert("simple".to_owned(), simple(tree));
                map.insert(
                    "to_json".to_owned(),
                    ok(Value::String(to_json(tree, Some(2)))),
                );
                map.insert(
                    "to_json_flat".to_owned(),
                    ok(Value::String(to_json(tree, None))),
                );
                Value::Object(map)
            },
        );
    }
}

#[test]
fn xml_cases_match_python() {
    let corpus = corpus();
    let cases = corpus["xml"].as_object().expect("xml section");
    for (key, expected) in cases {
        let case = parse_key(key);
        let driver = Driver::for_platform(case.platform);
        let keys = keys_slice(case.list_keys.as_ref());
        let parsed = from_xml(
            driver.clone(),
            source_of(&corpus, "xml", key, "config"),
            keys,
        );

        assert_outcome(
            key,
            expected,
            parsed.map_err(|error| error.to_string()),
            |tree| {
                let mut map = Map::new();
                map.insert("simple".to_owned(), simple(tree));
                map.insert(
                    "to_xml".to_owned(),
                    match to_xml(tree) {
                        Ok(text) => ok(Value::String(text)),
                        Err(error) => err(&error.to_string()),
                    },
                );
                Value::Object(map)
            },
        );
    }
}

#[test]
fn netconf_cases_match_python() {
    let corpus = corpus();
    let cases = corpus["netconf"].as_object().expect("netconf section");
    for (key, expected) in cases {
        let case = parse_key(key);
        let driver = Driver::for_platform(case.platform);
        let keys = keys_slice(case.list_keys.as_ref());
        let running = from_xml(
            driver.clone(),
            source_of(&corpus, "xml", key, "config"),
            keys,
        )
        .expect("running parses");
        let target = from_xml(driver, source_of(&corpus, "xml", key, "target"), keys)
            .expect("target parses");
        let remediation = running.config_to_get_to(&target).expect("diff");

        assert_eq!(
            simple(&remediation),
            expected["remediation"],
            "{key}: remediation mismatch"
        );
        assert_outcome(
            &format!("{key}/no_running"),
            &expected["no_running"],
            to_netconf_xml(&remediation, None, keys).map_err(|error| error.to_string()),
            |text| Value::String(text.clone()),
        );
        assert_outcome(
            &format!("{key}/with_running"),
            &expected["with_running"],
            to_netconf_xml(&remediation, Some(&running), keys).map_err(|error| error.to_string()),
            |text| Value::String(text.clone()),
        );
    }
}

#[test]
fn gnmi_cases_match_python() {
    let corpus = corpus();
    let cases = corpus["gnmi"].as_object().expect("gnmi section");
    for (key, expected) in cases {
        let case = parse_key(key);
        let driver = Driver::for_platform(case.platform);
        let keys = keys_slice(case.list_keys.as_ref());
        let running = from_json(
            driver.clone(),
            source_of(&corpus, "json", key, "config"),
            keys,
        )
        .expect("running parses");
        let target = from_json(driver, source_of(&corpus, "json", key, "target"), keys)
            .expect("target parses");
        let remediation = running.config_to_get_to(&target).expect("diff");

        assert_eq!(
            simple(&remediation),
            expected["remediation"],
            "{key}: remediation mismatch"
        );
        assert_outcome(
            &format!("{key}/no_running"),
            &expected["no_running"],
            to_gnmi_json(&remediation, None, keys).map_err(|error| error.to_string()),
            |result| sorted(&gnmi_value(result)),
        );
        assert_outcome(
            &format!("{key}/with_running"),
            &expected["with_running"],
            to_gnmi_json(&remediation, Some(&running), keys).map_err(|error| error.to_string()),
            |result| sorted(&gnmi_value(result)),
        );
    }
}

#[test]
fn error_cases_match_python() {
    let corpus = corpus();
    let cases = corpus["errors"].as_object().expect("errors section");
    let driver = Driver::for_platform(Platform::CiscoIos);
    for (name, expected) in cases {
        let actual = match name.as_str() {
            "bad-json" => from_json(driver.clone(), "{bad}", None).map(|_| ()),
            "json-not-obj" => from_json(driver.clone(), "[1, 2]", None).map(|_| ()),
            "empty-key" => from_json(driver.clone(), r#"{"": 1}"#, None).map(|_| ()),
            "ws-key" => from_json(driver.clone(), r#"{"a b": 1}"#, None).map(|_| ()),
            "unkeyed-list" => {
                from_json(driver.clone(), r#"{"a": [{"x": 1}, {"x": 2}]}"#, None).map(|_| ())
            }
            "nested-array" => from_json(driver.clone(), r#"{"a": [[1]]}"#, None).map(|_| ()),
            "bad-xml" => from_xml(driver.clone(), "<a>", None).map(|_| ()),
            other => panic!("unknown error case {other}"),
        };
        assert_outcome(
            name,
            expected,
            actual.map_err(|error| error.to_string()),
            |()| Value::Null,
        );
    }
}

fn ok(value: Value) -> Value {
    let mut map = Map::new();
    map.insert("ok".to_owned(), value);
    Value::Object(map)
}

fn err(message: &str) -> Value {
    let mut map = Map::new();
    map.insert(
        "err".to_owned(),
        Value::String(format!("InvalidConfigError: {message}")),
    );
    Value::Object(map)
}

/// Reads a case's input config back out of the corpus.
fn source_of<'a>(corpus: &'a Map<String, Value>, section: &str, key: &str, slot: &str) -> &'a str {
    let name = key.split('|').next().expect("case name");
    corpus["sources"][section][name][slot]
        .as_str()
        .unwrap_or_else(|| panic!("missing {section}/{name}/{slot} source"))
}
