//! XML (e.g. NETCONF payload) documents mapped onto a config tree.
//!
//! Rendering reproduces `xml.etree.ElementTree` byte-for-byte, including its
//! `indent()` whitespace algorithm and its escaping table, because these
//! documents are compared against device output and against fixtures written
//! by the previous Python implementation.

use quick_xml::events::Event;
use quick_xml::name::{NamespaceResolver, ResolveResult};
use std::borrow::Cow;
use std::sync::Arc;

use super::value::{dumps, leaf_value, text_value};
use super::{FormatError, resolve_list_keys};
use crate::arena::NodeId;
use crate::driver::Driver;
use crate::tree::Tree;

use super::json::{format_keys, split_text};

/// An `ElementTree`-shaped element: attributes plus `text` and `tail` slots.
#[derive(Debug, Clone, Default)]
pub(crate) struct Element {
    pub(crate) tag: String,
    pub(crate) attributes: Vec<(String, String)>,
    pub(crate) text: Option<String>,
    pub(crate) tail: Option<String>,
    pub(crate) children: Vec<Self>,
}

impl Element {
    pub(crate) fn new(tag: impl Into<String>) -> Self {
        Self {
            tag: tag.into(),
            ..Self::default()
        }
    }

    pub(crate) fn set(&mut self, name: impl Into<String>, value: impl Into<String>) {
        let name = name.into();
        let value = value.into();
        if let Some(slot) = self
            .attributes
            .iter_mut()
            .find(|(existing, _)| *existing == name)
        {
            slot.1 = value;
        } else {
            self.attributes.push((name, value));
        }
    }
}

/// Builds a config tree from an XML document.
///
/// # Errors
///
/// Returns [`FormatError`] if `source` is not well-formed XML or if a repeated
/// element cannot be identified.
pub fn from_xml(
    driver: Driver,
    source: &str,
    list_keys: Option<&[String]>,
) -> Result<Tree, FormatError> {
    let root_element = parse(source)?;
    let keys = resolve_list_keys(list_keys);
    let mut tree = Tree::new(driver);
    let root = tree.root;
    element_into(&mut tree, root, &root_element, &keys, "")?;
    Ok(tree)
}

/// Renders a tree built by [`from_xml`] back to XML text.
///
/// # Errors
///
/// Returns [`FormatError`] unless the tree has exactly one root node.
pub fn to_xml(tree: &Tree) -> Result<String, FormatError> {
    let root_node = single_root(tree)?;
    let mut element = node_to_element(tree, root_node);
    indent(&mut element);
    Ok(render(&element))
}

/// Returns the tree's single root node, which XML rendering requires.
pub(crate) fn single_root(tree: &Tree) -> Result<NodeId, FormatError> {
    let children = tree.arena[tree.root].children.as_slice();
    match children {
        [only] => Ok(*only),
        _ => Err(FormatError::Invalid(
            "XML rendering requires a single root node".to_owned(),
        )),
    }
}

fn identity_suffix(
    element: &Element,
    list_keys: &[String],
    required: bool,
) -> Result<String, FormatError> {
    for key in list_keys {
        if let Some(identity) = element.children.iter().find(|child| child.tag == *key)
            && let Some(text) = identity.text.as_deref()
            && !text.is_empty()
        {
            return Ok(format!(
                " {}",
                dumps(&serde_json::Value::String(text.trim().to_owned()))
            ));
        }
    }
    if required {
        return Err(FormatError::Invalid(format!(
            "Repeated <{}> elements need a child element named one of {} to \
identify them; pass list_keys= to name the identifying element",
            element.tag,
            format_keys(list_keys)
        )));
    }
    Ok(String::new())
}

fn element_into(
    tree: &mut Tree,
    parent: NodeId,
    element: &Element,
    list_keys: &[String],
    node_suffix: &str,
) -> Result<(), FormatError> {
    let node = tree.add_child(
        parent,
        &format!("{}{node_suffix}", element.tag),
        true,
        false,
    )?;
    for (name, value) in &element.attributes {
        let text = format!(
            "@{name} {}",
            dumps(&serde_json::Value::String(value.clone()))
        );
        tree.add_child(node, &text, true, false)?;
    }
    if let Some(text) = element.text.as_deref().map(str::trim)
        && !text.is_empty()
    {
        let payload = dumps(&serde_json::Value::String(text.to_owned()));
        tree.add_child(node, &format!("#text {payload}"), true, false)?;
    }

    for child in &element.children {
        if child.children.is_empty() && child.attributes.is_empty() {
            let child_text = child.text.as_deref().unwrap_or_default().trim();
            let text = if child_text.is_empty() {
                child.tag.clone()
            } else {
                format!(
                    "{} {}",
                    child.tag,
                    dumps(&serde_json::Value::String(child_text.to_owned()))
                )
            };
            tree.add_child(node, &text, true, false)?;
        } else {
            // Key the node whenever an identifying child exists so entries get
            // the same text regardless of sibling count -- configs with
            // different entry counts must still diff surgically. An identity
            // is only mandatory when the tag actually repeats.
            let repeats = element
                .children
                .iter()
                .filter(|sibling| sibling.tag == child.tag)
                .count()
                > 1;
            let suffix = identity_suffix(child, list_keys, repeats)?;
            element_into(tree, node, child, list_keys, &suffix)?;
        }
    }
    Ok(())
}

fn node_to_element(tree: &Tree, node_id: NodeId) -> Element {
    let (tag, payload) = split_text(&tree.arena[node_id].text);
    let mut element = Element::new(tag);
    if tree.arena[node_id].children.is_empty() {
        element.text = payload.map(xml_text);
        return element;
    }
    for child_id in tree.arena[node_id].children.iter() {
        let child_text = Arc::clone(&tree.arena[child_id].text);
        if !tree.arena[child_id].children.is_empty() {
            element.children.push(node_to_element(tree, child_id));
        } else if let Some(name) = child_text.strip_prefix('@') {
            let (name, raw) = name.split_once(' ').unwrap_or((name, ""));
            element.set(name, python_str(raw));
        } else if let Some(raw) = child_text.strip_prefix("#text ") {
            element.text = Some(python_str(raw));
        } else {
            element.children.push(node_to_element(tree, child_id));
        }
    }
    element
}

/// Unwraps a leaf payload for use as element text, keeping non-strings raw.
pub(crate) fn xml_text(raw: &str) -> String {
    text_value(raw)
}

/// Renders a leaf payload the way Python's `str()` would.
///
/// Attribute and `#text` values reach `ElementTree` through `str()`, so a
/// payload that decoded to a non-string renders in Python's repr style rather
/// than as JSON.
fn python_str(raw: &str) -> String {
    match leaf_value(raw) {
        serde_json::Value::String(text) => text,
        serde_json::Value::Null => "None".to_owned(),
        serde_json::Value::Bool(true) => "True".to_owned(),
        serde_json::Value::Bool(false) => "False".to_owned(),
        other => dumps(&other),
    }
}

/// Applies `ElementTree.indent`'s whitespace algorithm in place.
pub(crate) fn indent(element: &mut Element) {
    if !element.children.is_empty() {
        indent_children(element, 0);
    }
}

fn indent_children(element: &mut Element, level: usize) {
    let own_indentation = format!("\n{}", "  ".repeat(level));
    let child_indentation = format!("{own_indentation}  ");

    if element
        .text
        .as_deref()
        .is_none_or(|text| text.trim().is_empty())
    {
        element.text = Some(child_indentation.clone());
    }
    let last = element.children.len() - 1;
    for (position, child) in element.children.iter_mut().enumerate() {
        if !child.children.is_empty() {
            indent_children(child, level + 1);
        }
        if child
            .tail
            .as_deref()
            .is_none_or(|tail| tail.trim().is_empty())
        {
            child.tail = Some(if position == last {
                own_indentation.clone()
            } else {
                child_indentation.clone()
            });
        }
    }
}

/// Serializes an element the way `ElementTree.tostring` does.
pub(crate) fn render(element: &Element) -> String {
    let mut namespaces = Vec::new();
    collect_namespaces(element, &mut namespaces);
    namespaces.sort_by(|(_, left), (_, right)| left.cmp(right));
    let mut out = String::new();
    write_element(&mut out, element, &namespaces, true);
    out
}

fn collect_namespaces(element: &Element, namespaces: &mut Vec<(String, String)>) {
    for name in std::iter::once(&element.tag).chain(element.attributes.iter().map(|(name, _)| name))
    {
        if let Some((uri, _)) = expanded_name(name)
            && !namespaces.iter().any(|(existing, _)| existing == uri)
        {
            let prefix = match uri {
                "http://www.w3.org/XML/1998/namespace" => "xml".to_owned(),
                "http://www.w3.org/1999/xhtml" => "html".to_owned(),
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#" => "rdf".to_owned(),
                "http://schemas.xmlsoap.org/wsdl/" => "wsdl".to_owned(),
                "http://www.w3.org/2001/XMLSchema" => "xs".to_owned(),
                "http://www.w3.org/2001/XMLSchema-instance" => "xsi".to_owned(),
                "http://purl.org/dc/elements/1.1/" => "dc".to_owned(),
                _ => format!("ns{}", namespaces.len()),
            };
            namespaces.push((uri.to_owned(), prefix));
        }
    }
    for child in &element.children {
        collect_namespaces(child, namespaces);
    }
}

fn expanded_name(name: &str) -> Option<(&str, &str)> {
    name.strip_prefix('{')?.rsplit_once('}')
}

fn qualified_name<'a>(name: &'a str, namespaces: &[(String, String)]) -> Cow<'a, str> {
    if let Some((uri, local)) = expanded_name(name) {
        let (_, prefix) = namespaces
            .iter()
            .find(|(namespace, _)| namespace == uri)
            .expect("namespace collected before rendering");
        Cow::Owned(format!("{prefix}:{local}"))
    } else {
        Cow::Borrowed(name)
    }
}

fn write_element(out: &mut String, element: &Element, namespaces: &[(String, String)], root: bool) {
    let tag = qualified_name(&element.tag, namespaces);
    out.push('<');
    out.push_str(&tag);
    if root {
        for (uri, prefix) in namespaces {
            if prefix != "xml" {
                out.push_str(" xmlns:");
                out.push_str(prefix);
                out.push_str("=\"");
                escape_attribute(out, uri);
                out.push('"');
            }
        }
    }
    for (name, value) in &element.attributes {
        out.push(' ');
        out.push_str(&qualified_name(name, namespaces));
        out.push_str("=\"");
        escape_attribute(out, value);
        out.push('"');
    }
    if element.text.is_none() && element.children.is_empty() {
        out.push_str(" />");
    } else {
        out.push('>');
        if let Some(text) = &element.text {
            escape_text(out, text);
        }
        for child in &element.children {
            write_element(out, child, namespaces, false);
        }
        out.push_str("</");
        out.push_str(&tag);
        out.push('>');
    }
    if let Some(tail) = &element.tail {
        escape_text(out, tail);
    }
}

fn escape_text(out: &mut String, text: &str) {
    for character in text.chars() {
        match character {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            _ => out.push(character),
        }
    }
}

fn escape_attribute(out: &mut String, text: &str) {
    for character in text.chars() {
        match character {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\r' => out.push_str("&#13;"),
            '\n' => out.push_str("&#10;"),
            '\t' => out.push_str("&#09;"),
            _ => out.push(character),
        }
    }
}

/// Handles an `Event::Start`, enforcing the document-element and nesting-depth
/// invariants before pushing the new element onto `stack`.
fn push_start(
    stack: &mut Vec<Element>,
    root: Option<&Element>,
    start: &quick_xml::events::BytesStart<'_>,
    resolver: &NamespaceResolver,
) -> Result<(), FormatError> {
    if stack.is_empty() && root.is_some() {
        return Err(FormatError::Invalid(
            "The config is not valid XML: junk after document element".to_owned(),
        ));
    }
    // Bound nesting before the element tree is built: both the recursive walk in
    // `element_into` and `Element`'s recursive drop glue overflow the stack
    // (SIGSEGV) on deeply nested documents.
    if stack.len() >= crate::tree::MAX_TREE_DEPTH {
        return Err(FormatError::Invalid(format!(
            "The config is not valid XML: nesting exceeds the maximum \
supported depth of {}",
            crate::tree::MAX_TREE_DEPTH
        )));
    }
    stack.push(open(start, resolver)?);
    Ok(())
}

fn parse(source: &str) -> Result<Element, FormatError> {
    let mut reader = quick_xml::NsReader::from_str(source);
    reader.config_mut().trim_text(false);
    let mut stack: Vec<Element> = Vec::new();
    let mut root: Option<Element> = None;

    loop {
        let event = reader.read_event().map_err(|error| {
            FormatError::Invalid(format!("The config is not valid XML: {error}"))
        })?;
        match event {
            Event::Start(start) => {
                push_start(&mut stack, root.as_ref(), &start, reader.resolver())?;
            }
            Event::Empty(start) => {
                let element = open(&start, reader.resolver())?;
                close(&mut stack, &mut root, element)?;
            }
            Event::End(_) => {
                let element = stack.pop().ok_or_else(|| {
                    FormatError::Invalid("The config is not valid XML: unbalanced tags".to_owned())
                })?;
                close(&mut stack, &mut root, element)?;
            }
            Event::Text(text) => {
                let raw = text.xml10_content().map_err(|error| {
                    FormatError::Invalid(format!("The config is not valid XML: {error}"))
                })?;
                if stack.is_empty() {
                    if raw
                        .chars()
                        .any(|ch| !matches!(ch, ' ' | '\t' | '\r' | '\n'))
                    {
                        return Err(FormatError::Invalid(
                            "The config is not valid XML: text outside document element".to_owned(),
                        ));
                    }
                    continue;
                }
                let decoded = quick_xml::escape::unescape(&raw)
                    .map_err(|error| {
                        FormatError::Invalid(format!("The config is not valid XML: {error}"))
                    })?
                    .into_owned();
                append_characters(&mut stack, &decoded);
            }
            Event::GeneralRef(entity_ref) if !stack.is_empty() => {
                let resolved = if let Some(ch) = entity_ref.resolve_char_ref().map_err(|error| {
                    FormatError::Invalid(format!("The config is not valid XML: {error}"))
                })? {
                    ch.to_string()
                } else {
                    let name = entity_ref.decode().map_err(|error| {
                        FormatError::Invalid(format!("The config is not valid XML: {error}"))
                    })?;
                    quick_xml::escape::resolve_xml_entity(&name)
                        .ok_or_else(|| {
                            FormatError::Invalid(format!(
                                "The config is not valid XML: unknown entity &{name};"
                            ))
                        })?
                        .to_owned()
                };
                append_characters(&mut stack, &resolved);
            }
            // `ElementTree` surfaces CDATA content verbatim as character data.
            Event::CData(data) if !stack.is_empty() => {
                let decoded = std::str::from_utf8(&data)
                    .map_err(|error| {
                        FormatError::Invalid(format!("The config is not valid XML: {error}"))
                    })?
                    .to_owned();
                append_characters(&mut stack, &decoded);
            }
            Event::GeneralRef(_) | Event::CData(_) => {
                return Err(FormatError::Invalid(
                    "The config is not valid XML: character data outside document element"
                        .to_owned(),
                ));
            }
            Event::Eof => {
                if !stack.is_empty() {
                    return Err(FormatError::Invalid(
                        "The config is not valid XML: unclosed element".to_owned(),
                    ));
                }
                break;
            }
            _ => {}
        }
    }

    root.ok_or_else(|| {
        FormatError::Invalid("The config is not valid XML: no element found".to_owned())
    })
}

fn open(
    start: &quick_xml::events::BytesStart<'_>,
    resolver: &NamespaceResolver,
) -> Result<Element, FormatError> {
    let local = std::str::from_utf8(start.local_name().into_inner())
        .map_err(|error| FormatError::Invalid(format!("The config is not valid XML: {error}")))?
        .to_owned();
    let (namespace, _) = resolver.resolve_element(start.name());
    let mut element = Element::new(qualify(&namespace, &local)?);
    for attribute in start.attributes() {
        let attribute = attribute.map_err(|error| {
            FormatError::Invalid(format!("The config is not valid XML: {error}"))
        })?;
        let key = std::str::from_utf8(attribute.key.into_inner()).map_err(|error| {
            FormatError::Invalid(format!("The config is not valid XML: {error}"))
        })?;
        // `ElementTree` consumes namespace declarations rather than
        // surfacing them as attributes.
        if key == "xmlns" || key.starts_with("xmlns:") {
            continue;
        }
        let (attribute_namespace, attribute_local) = resolver.resolve_attribute(attribute.key);
        let attribute_local =
            std::str::from_utf8(attribute_local.into_inner()).map_err(|error| {
                FormatError::Invalid(format!("The config is not valid XML: {error}"))
            })?;
        let name = qualify(&attribute_namespace, attribute_local)?;
        if element
            .attributes
            .iter()
            .any(|(existing, _)| *existing == name)
        {
            return Err(FormatError::Invalid(
                "The config is not valid XML: duplicate attribute".to_owned(),
            ));
        }
        let value = attribute
            .normalized_value(quick_xml::XmlVersion::Implicit1_0)
            .map_err(|error| FormatError::Invalid(format!("The config is not valid XML: {error}")))?
            .into_owned();
        element.set(name, value);
    }
    Ok(element)
}

fn qualify(namespace: &ResolveResult<'_>, local: &str) -> Result<String, FormatError> {
    // `ElementTree` reports namespaced names in Clark notation.
    match namespace {
        ResolveResult::Bound(uri) => {
            let uri = std::str::from_utf8(uri.into_inner()).map_err(|error| {
                FormatError::Invalid(format!("The config is not valid XML: {error}"))
            })?;
            Ok(format!("{{{uri}}}{local}"))
        }
        ResolveResult::Unbound => Ok(local.to_owned()),
        ResolveResult::Unknown(_) => Err(FormatError::Invalid(
            "The config is not valid XML: unbound namespace prefix".to_owned(),
        )),
    }
}

fn append_characters(stack: &mut [Element], decoded: &str) {
    let Some(current) = stack.last_mut() else {
        return;
    };
    // `ElementTree` puts character data before the first child in `text` and
    // everything after a child in that child's `tail`.
    if let Some(last_child) = current.children.last_mut() {
        last_child
            .tail
            .get_or_insert_with(String::new)
            .push_str(decoded);
    } else {
        current
            .text
            .get_or_insert_with(String::new)
            .push_str(decoded);
    }
}

fn close(
    stack: &mut [Element],
    root: &mut Option<Element>,
    element: Element,
) -> Result<(), FormatError> {
    if let Some(parent) = stack.last_mut() {
        parent.children.push(element);
        return Ok(());
    }
    if root.is_some() {
        return Err(FormatError::Invalid(
            "The config is not valid XML: junk after document element".to_owned(),
        ));
    }
    *root = Some(element);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::Platform;

    fn tree_from(source: &str) -> Tree {
        from_xml(Driver::for_platform(Platform::CiscoIos), source, None).expect("valid XML")
    }

    #[test]
    fn leaf_elements_become_value_bearing_nodes() {
        let tree = tree_from("<config><hostname>r1</hostname></config>");
        assert_eq!(tree.dump_simple(false), vec!["config", "  hostname \"r1\""]);
    }

    #[test]
    fn attributes_and_mixed_text_get_sigils() {
        let tree = tree_from(r#"<config><a x="1">hi<b/></a></config>"#);
        assert_eq!(
            tree.dump_simple(false),
            vec!["config", "  a", "    @x \"1\"", "    #text \"hi\"", "    b"]
        );
    }

    #[test]
    fn repeated_elements_need_an_identity() {
        let error = from_xml(
            Driver::for_platform(Platform::CiscoIos),
            "<c><i><m>1</m></i><i><m>2</m></i></c>",
            None,
        )
        .expect_err("no identity child");
        assert!(
            error.to_string().contains("Repeated <i>"),
            "{}",
            error.to_string()
        );
    }

    #[test]
    fn repeated_elements_key_on_their_identity_child() {
        let tree = tree_from("<c><i><name>Et1</name></i><i><name>Et2</name></i></c>");
        assert_eq!(
            tree.dump_simple(false),
            vec![
                "c",
                "  i \"Et1\"",
                "    name \"Et1\"",
                "  i \"Et2\"",
                "    name \"Et2\"",
            ]
        );
    }

    #[test]
    fn malformed_documents_are_rejected() {
        let error = from_xml(Driver::for_platform(Platform::CiscoIos), "<a>", None)
            .expect_err("unclosed tag");
        assert!(
            error.to_string().starts_with("The config is not valid XML"),
            "{}",
            error.to_string()
        );
    }

    #[test]
    fn round_trip_reproduces_element_tree_output() {
        let tree = tree_from("<config><hostname>r1</hostname></config>");
        assert_eq!(
            to_xml(&tree).expect("single root"),
            "<config>\n  <hostname>r1</hostname>\n</config>"
        );
    }

    #[test]
    fn empty_elements_render_self_closing() {
        let tree = tree_from("<config><shutdown/></config>");
        assert_eq!(
            to_xml(&tree).expect("single root"),
            "<config>\n  <shutdown />\n</config>"
        );
    }

    #[test]
    fn special_characters_are_escaped() {
        let tree = tree_from(r#"<c a="&quot;q&quot;">a &lt; b</c>"#);
        assert_eq!(
            to_xml(&tree).expect("single root"),
            r#"<c a="&quot;q&quot;">a &lt; b</c>"#
        );
    }

    #[test]
    fn namespaces_use_clark_notation() {
        let tree = tree_from(r#"<c xmlns="urn:x"><h>r1</h></c>"#);
        assert_eq!(
            tree.dump_simple(false),
            vec!["{urn:x}c", "  {urn:x}h \"r1\""]
        );
    }

    #[test]
    fn multiple_roots_are_rejected_on_render() {
        let mut tree = Tree::for_platform(Platform::CiscoIos);
        let root = tree.root;
        tree.add_child(root, "a", true, true).expect("add");
        tree.add_child(root, "b", true, true).expect("add");
        assert!(to_xml(&tree).is_err());
    }
}
