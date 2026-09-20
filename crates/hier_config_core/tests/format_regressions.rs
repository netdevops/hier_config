use hier_config_core::formats::{FormatError, to_gnmi_json, to_netconf_xml, to_xml};
use hier_config_core::{Platform, Tree};

#[test]
fn empty_list_keys_use_default_identity_keys_for_json_and_gnmi() {
    let source = r#"{"interface":[{"name":"eth0","mtu":1500}]}"#;
    let tree = Tree::from_json(Platform::Generic, source, Some(&[])).unwrap();
    assert_eq!(
        tree.dump_simple(false),
        ["interface \"eth0\"", "  name \"eth0\"", "  mtu 1500"]
    );
    let update = to_gnmi_json(&tree, None, Some(&[])).unwrap();
    assert_eq!(
        serde_json::Value::Object(update.update),
        serde_json::json!({"interface": [{"name": "eth0", "mtu": 1500}]})
    );
    assert!(update.delete.is_empty());
}

#[test]
fn empty_list_keys_use_default_identity_keys_for_xml_and_netconf() {
    let source = "<c><i><name>eth0</name></i><i><name>eth1</name></i></c>";
    let running = Tree::from_xml(Platform::Generic, source, Some(&[])).unwrap();
    let remediation = Tree::from_str(Platform::Generic, "c\n  no i \"eth0\"").unwrap();
    assert_eq!(
        to_netconf_xml(&remediation, Some(&running), Some(&[])).unwrap(),
        "<c xmlns:nc=\"urn:ietf:params:xml:ns:netconf:base:1.0\">\n  \
<i nc:operation=\"delete\">\n    <name>eth0</name>\n  </i>\n</c>"
    );
    assert_eq!(
        to_gnmi_json(&remediation, Some(&running), Some(&[]))
            .unwrap()
            .delete,
        ["c/i[name=eth0]"]
    );
}

#[test]
fn xml_namespace_attributes_keep_their_expanded_names() {
    let tree = Tree::from_xml(
        Platform::Generic,
        r#"<c xmlns="urn:x" xmlns:a="urn:attrs" a:mode="on"><a:item xml:lang="en">1</a:item></c>"#,
        None,
    )
    .unwrap();
    assert_eq!(
        tree.dump_simple(false),
        [
            "{urn:x}c",
            "  @{urn:attrs}mode \"on\"",
            "  {urn:attrs}item",
            "    @{http://www.w3.org/XML/1998/namespace}lang \"en\"",
            "    #text \"1\"",
        ]
    );
}

#[test]
fn xml_namespaces_render_like_element_tree_and_round_trip() {
    let tree = Tree::from_xml(
        Platform::Generic,
        r#"<c xmlns="urn:x" xmlns:a="urn:attrs" a:mode="on"><a:item xml:lang="en">1</a:item></c>"#,
        None,
    )
    .unwrap();
    let rendered = to_xml(&tree).unwrap();
    assert_eq!(
        rendered,
        "<ns0:c xmlns:ns0=\"urn:x\" xmlns:ns1=\"urn:attrs\" ns1:mode=\"on\">\n  \
<ns1:item xml:lang=\"en\">1</ns1:item>\n</ns0:c>"
    );
    let reparsed = Tree::from_xml(Platform::Generic, &rendered, None).unwrap();
    assert_eq!(reparsed.dump_simple(false), tree.dump_simple(false));
}

#[test]
fn invalid_namespace_attributes_are_rejected() {
    for source in [
        r#"<c unknown:a="1"/>"#,
        r#"<c xmlns:a="urn:x" xmlns:b="urn:x" a:k="1" b:k="2"/>"#,
    ] {
        assert!(
            matches!(
                Tree::from_xml(Platform::Generic, source, None),
                Err(FormatError::Invalid(_))
            ),
            "{source}"
        );
    }
}

#[test]
fn xml_character_data_and_attributes_round_trip_escaped_values() {
    let source = "<?xml version=\"1.0\"?>\n<!--before--><c a=\"&lt;&gt;&amp;&quot;&#13;&#10;&#9;\">\
    <![CDATA[first <second>]]>&amp;&#65;&#x42;<child>value</child>ignored tail</c><!--after-->\n";
    let tree = Tree::from_xml(Platform::Generic, source, None).unwrap();
    assert_eq!(
        to_xml(&tree).unwrap(),
        "<c a=\"&lt;&gt;&amp;&quot;&#13;&#10;&#09;\">first &lt;second&gt;&amp;AB\
    <child>value</child>\n</c>"
    );
}

#[test]
fn xml_invalid_entities_and_document_shapes_return_format_errors() {
    for source in [
        "",
        "<c>",
        "<c></x>",
        "<c/><d/>",
        "<c>&unknown;</c>",
        "<c>&#x110000;</c>",
        "<c>&#notanumber;</c>",
        "<c a=\"&unknown;\"/>",
        "<c a=\"1\" a=\"2\"/>",
        "<c a=unquoted/>",
        "\u{a0}<c/>",
    ] {
        assert!(
            matches!(
                Tree::from_xml(Platform::Generic, source, None),
                Err(FormatError::Invalid(_))
            ),
            "{source}"
        );
    }
}

#[test]
fn namespace_shadowing_does_not_change_unprefixed_attributes() {
    let tree = Tree::from_xml(
        Platform::Generic,
        r#"<c xmlns="urn:outer" x="plain"><d xmlns="urn:inner" x="local"/><e xmlns=""/></c>"#,
        None,
    )
    .unwrap();
    assert_eq!(
        tree.dump_simple(false),
        [
            "{urn:outer}c",
            "  @x \"plain\"",
            "  {urn:inner}d",
            "    @x \"local\"",
            "  e",
        ]
    );
    assert_eq!(
        to_xml(&tree).unwrap(),
        "<ns0:c xmlns:ns0=\"urn:outer\" xmlns:ns1=\"urn:inner\" x=\"plain\">\n  \
    <ns1:d x=\"local\" />\n  <e />\n</ns0:c>"
    );
}

#[test]
fn standard_namespace_prefixes_match_element_tree_defaults() {
    for (uri, prefix) in [
        ("http://www.w3.org/1999/xhtml", "html"),
        ("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf"),
        ("http://schemas.xmlsoap.org/wsdl/", "wsdl"),
        ("http://www.w3.org/2001/XMLSchema", "xs"),
        ("http://www.w3.org/2001/XMLSchema-instance", "xsi"),
        ("http://purl.org/dc/elements/1.1/", "dc"),
    ] {
        let tree =
            Tree::from_xml(Platform::Generic, &format!("<c xmlns=\"{uri}\"/>"), None).unwrap();
        assert_eq!(
            to_xml(&tree).unwrap(),
            format!("<{prefix}:c xmlns:{prefix}=\"{uri}\" />")
        );
    }
}

#[test]
fn xml_rendering_preserves_python_scalar_coercion_for_metadata() {
    let tree = Tree::from_str(
        Platform::Generic,
        "c\n  @enabled true\n  @disabled false\n  @missing null\n  @count 3\n  #text true",
    )
    .unwrap();
    assert_eq!(
        to_xml(&tree).unwrap(),
        "<c enabled=\"True\" disabled=\"False\" missing=\"None\" count=\"3\">True</c>"
    );
}

#[test]
fn namespaced_netconf_payload_preserves_the_deletion_namespace() {
    let keys = ["{urn:if}name".to_owned()];
    let running = Tree::from_xml(
        Platform::Generic,
        "<config xmlns=\"urn:if\"><interface><name>eth0</name></interface></config>",
        Some(&keys),
    )
    .unwrap();
    let remediation = Tree::from_str(
        Platform::Generic,
        "{urn:if}config\n  no {urn:if}interface \"eth0\"",
    )
    .unwrap();
    let payload = to_netconf_xml(&remediation, Some(&running), Some(&keys)).unwrap();
    assert_eq!(
        payload,
        "<ns0:config xmlns:ns0=\"urn:if\" xmlns:nc=\"urn:ietf:params:xml:ns:netconf:base:1.0\">\n  \
    <ns0:interface nc:operation=\"delete\">\n    <ns0:name>eth0</ns0:name>\n  \
    </ns0:interface>\n</ns0:config>"
    );
    let reparsed = Tree::from_xml(Platform::Generic, &payload, Some(&keys)).unwrap();
    assert!(reparsed.dump_simple(false).contains(
        &"    @{urn:ietf:params:xml:ns:netconf:base:1.0}operation \"delete\"".to_owned()
    ));
}
#[test]
fn malformed_xml_outside_the_document_element_is_rejected() {
    for source in [
        "<c/>trailing",
        "leading<c/>",
        "<c/><unclosed>",
        "<c/>&amp;",
        "<c/><![CDATA[junk]]>",
        "<unbound:c/>",
    ] {
        let error = Tree::from_xml(Platform::Generic, source, None).expect_err(source);
        assert!(
            matches!(error, FormatError::Invalid(ref text)
                if text.starts_with("The config is not valid XML:")),
            "{source}: {error}"
        );
    }
}
