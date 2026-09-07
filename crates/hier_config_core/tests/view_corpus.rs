//! Shared view corpus: assert the native Rust view matches the Python reference.
//!
//! Snapshots under `testdata/views` are generated from the Python view layer by
//! `scripts/gen_view_corpus.py`. This test serializes the Rust view into the
//! same shape and compares. Snapshots are never regenerated from Rust.

use hier_config_core::models::Platform;
use hier_config_core::tree::Tree;
use hier_config_core::view::{ConfigView, InterfaceView, view_ops_for_platform};
use serde_json::{Map, Value, json};
use std::fs;
use std::path::{Path, PathBuf};

fn platform_from_dir(name: &str) -> Option<Platform> {
    match name {
        "arista_eos" => Some(Platform::AristaEos),
        "aruba_aoscx" => Some(Platform::ArubaAoscx),
        "cisco_ios" => Some(Platform::CiscoIos),
        "cisco_nxos" => Some(Platform::CiscoNxos),
        "cisco_xr" => Some(Platform::CiscoXr),
        "hp_procurve" => Some(Platform::HpProcurve),
        _ => None,
    }
}

fn opt_string(value: Option<String>) -> Value {
    value.map_or(Value::Null, Value::String)
}

fn opt_u32(value: Option<u32>) -> Value {
    value.map_or(Value::Null, |number| json!(number))
}

fn serialize_interface(view: &InterfaceView<'_>) -> Value {
    let ops = view.ops();
    let mut map = Map::new();
    map.insert("name".into(), json!(view.name()));
    map.insert("number".into(), json!(view.number()));
    map.insert("parent_name".into(), opt_string(view.parent_name()));
    map.insert("description".into(), json!(view.description()));
    map.insert("enabled".into(), json!(view.enabled()));
    map.insert("is_bundle".into(), json!(view.is_bundle()));
    map.insert("is_subinterface".into(), json!(view.is_subinterface()));
    map.insert("is_loopback".into(), json!(view.is_loopback()));
    map.insert("is_svi".into(), json!(view.is_svi()));
    map.insert("module_number".into(), opt_u32(view.module_number()));
    map.insert("port_number".into(), opt_u32(view.port_number()));
    map.insert(
        "subinterface_number".into(),
        opt_u32(view.subinterface_number()),
    );
    map.insert(
        "ipv4_interfaces".into(),
        Value::Array(
            view.ipv4_interfaces()
                .into_iter()
                .map(|address| json!(format!("{}/{}", address.address, address.prefix_len)))
                .collect(),
        ),
    );
    map.insert("vrf".into(), json!(view.vrf()));
    map.insert("bundle_id".into(), opt_string(view.bundle_id()));
    map.insert("bundle_name".into(), opt_string(view.bundle_name()));
    map.insert(
        "bundle_member_interfaces".into(),
        json!(view.bundle_member_interfaces()),
    );
    map.insert("native_vlan".into(), opt_u32(view.native_vlan()));
    map.insert("tagged_all".into(), json!(view.tagged_all()));
    map.insert("tagged_vlans".into(), json!(view.tagged_vlans()));
    map.insert(
        "dot1q_mode".into(),
        view.dot1q_mode()
            .map_or(Value::Null, |mode| json!(mode.as_str())),
    );

    if ops.supports_nac() {
        map.insert("has_nac".into(), json!(view.has_nac()));
        map.insert(
            "nac_control_direction_in".into(),
            json!(view.nac_control_direction_in()),
        );
        map.insert(
            "nac_host_mode".into(),
            view.nac_host_mode()
                .map_or(Value::Null, |mode| json!(mode.as_str())),
        );
        map.insert("nac_mab_first".into(), json!(view.nac_mab_first()));
        map.insert(
            "nac_max_dot1x_clients".into(),
            opt_u32(view.nac_max_dot1x_clients()),
        );
        map.insert(
            "nac_max_mab_clients".into(),
            opt_u32(view.nac_max_mab_clients()),
        );
    }

    if ops.supports_physical() {
        map.insert(
            "duplex".into(),
            view.duplex()
                .map_or(Value::Null, |duplex| json!(duplex.as_str())),
        );
        map.insert(
            "poe".into(),
            view.poe().map_or(Value::Null, |poe| json!(poe)),
        );
        map.insert(
            "speed".into(),
            view.speed().map_or(Value::Null, |speed| json!(speed)),
        );
    }

    Value::Object(map)
}

fn serialize_view(view: &ConfigView<'_>) -> Value {
    json!({
        "hostname": opt_string(view.hostname()),
        "ipv4_default_gw": view
            .ipv4_default_gw()
            .map_or(Value::Null, |gateway| json!(gateway.to_string())),
        "location": view.location(),
        "module_numbers": view.module_numbers(),
        "stack_members": view
            .stack_members()
            .into_iter()
            .map(|member| json!({
                "id": member.id,
                "priority": member.priority,
                "mac_address": opt_string(member.mac_address),
                "model": member.model,
            }))
            .collect::<Vec<_>>(),
        "vlans": view
            .vlans()
            .into_iter()
            .map(|vlan| json!({"id": vlan.id, "name": opt_string(vlan.name)}))
            .collect::<Vec<_>>(),
        "interface_names_mentioned": view
            .interface_names_mentioned()
            .into_iter()
            .collect::<Vec<_>>(),
        "interfaces": view
            .interface_views()
            .iter()
            .map(serialize_interface)
            .collect::<Vec<_>>(),
    })
}

/// Python view properties that raise instead of returning a value.
///
/// A raising property has no reference value to compare against, so the corpus
/// records the exception type and this test skips the value comparison. Listing
/// them here keeps every Python/Rust divergence explicit: a newly raising
/// property fails the test until it is triaged and added.
const EXPECTED_PYTHON_RAISES: &[(&str, &str, &str)] = &[
    // Arista, NX-OS and XR views have no physical mixin, so `module_number`
    // does not exist on them at all.
    ("arista_eos", "module_number", "AttributeError"),
    ("cisco_nxos", "module_number", "AttributeError"),
    ("cisco_xr", "module_number", "AttributeError"),
    // Both platforms deliberately declare these NAC limits unsupported.
    (
        "aruba_aoscx",
        "nac_max_dot1x_clients",
        "NotImplementedError",
    ),
    ("aruba_aoscx", "nac_max_mab_clients", "NotImplementedError"),
    ("cisco_ios", "nac_max_dot1x_clients", "NotImplementedError"),
    ("cisco_ios", "nac_max_mab_clients", "NotImplementedError"),
    // Python raises for every interface that is not part of a trunk, including
    // ordinary access ports. Rust returns an empty list instead.
    ("hp_procurve", "bundle_member_interfaces", "ValueError"),
];

/// Read the informational `raises` map recorded by the Python generator.
fn raised_properties(platform: &str, snapshot: &Value) -> Vec<String> {
    let Some(Value::Object(raises)) = snapshot.get("raises") else {
        return Vec::new();
    };
    for (property, exception) in raises {
        let exception = exception.as_str().unwrap_or_default();
        assert!(
            EXPECTED_PYTHON_RAISES.contains(&(platform, property.as_str(), exception)),
            "{platform}: undocumented Python divergence: {property} raises {exception}. \
             Triage it and add it to EXPECTED_PYTHON_RAISES."
        );
    }
    raises.keys().cloned().collect()
}

/// Collect the paths at which two snapshots differ, so failures stay readable.
fn collect_diffs(
    platform: &str,
    path: &str,
    expected: &Value,
    actual: &Value,
    out: &mut Vec<String>,
) {
    match (expected, actual) {
        (Value::Object(left), Value::Object(right)) => {
            let skip = raised_properties(platform, expected);
            let mut keys: Vec<&String> = left.keys().chain(right.keys()).collect();
            keys.sort_unstable();
            keys.dedup();
            for key in keys {
                if key == "raises" || skip.iter().any(|name| name == key) {
                    continue;
                }
                let child = format!("{path}.{key}");
                match (left.get(key), right.get(key)) {
                    (Some(lhs), Some(rhs)) => collect_diffs(platform, &child, lhs, rhs, out),
                    (lhs, rhs) => out.push(format!(
                        "{child}: expected {:?}, actual {:?}",
                        lhs.map(ToString::to_string),
                        rhs.map(ToString::to_string)
                    )),
                }
            }
        }
        (Value::Array(left), Value::Array(right)) if left.len() == right.len() => {
            for (index, (lhs, rhs)) in left.iter().zip(right.iter()).enumerate() {
                collect_diffs(platform, &format!("{path}[{index}]"), lhs, rhs, out);
            }
        }
        _ => {
            if expected != actual {
                out.push(format!("{path}: expected {expected}, actual {actual}"));
            }
        }
    }
}

fn corpus_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .join("testdata/views")
}

#[test]
fn view_corpus_matches_python_reference() {
    let corpus = corpus_dir();
    assert!(
        corpus.is_dir(),
        "view corpus directory missing: {}",
        corpus.display()
    );

    let mut case_dirs: Vec<PathBuf> = fs::read_dir(&corpus)
        .expect("read view corpus dir")
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .collect();
    case_dirs.sort();
    assert!(!case_dirs.is_empty(), "view corpus is empty");

    let mut failures = Vec::new();
    for case_dir in case_dirs {
        let name = case_dir
            .file_name()
            .and_then(|value| value.to_str())
            .expect("case dir name")
            .to_owned();
        let platform = platform_from_dir(&name)
            .unwrap_or_else(|| panic!("unknown view corpus platform: {name}"));
        let ops = view_ops_for_platform(platform)
            .unwrap_or_else(|| panic!("no native view for platform: {name}"));

        let config_text =
            fs::read_to_string(case_dir.join("config.txt")).expect("read case config");
        let expected: Value = serde_json::from_str(
            &fs::read_to_string(case_dir.join("expected.json")).expect("read case snapshot"),
        )
        .expect("parse case snapshot");

        let tree = Tree::from_str(platform, &config_text).expect("load case config");
        let view = ConfigView::new(&tree, ops);
        let actual = serialize_view(&view);

        let mut diffs = Vec::new();
        collect_diffs(&name, &name, &expected, &actual, &mut diffs);
        if !diffs.is_empty() {
            failures.push(diffs.join("\n"));
        }
    }

    assert!(failures.is_empty(), "{}", failures.join("\n\n"));
}
