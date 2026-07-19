# Loading Configurations

This page covers every way to build an `HConfig` tree: from raw text, from pre-split lines, from a serialized dump, and from structured JSON or XML documents. Read it when plain `HConfig.from_text()` is not enough — or when you want to round-trip configurations through serialization.

## Choosing a platform

Every constructor takes a platform (or driver) as its first argument. Three forms are accepted:

```python
from hier_config import HConfig, Platform, get_hconfig_driver

# 1. A Platform enum member
config = HConfig.from_text(Platform.CISCO_IOS, config_text)

# 2. A platform name string (case-insensitive; includes custom registered platforms)
config = HConfig.from_text("cisco_ios", config_text)

# 3. A driver instance (useful when you have customized the driver's rules)
driver = get_hconfig_driver(Platform.CISCO_IOS)
config = HConfig.from_text(driver, config_text)
```

See [Supported Platforms](../admin/platforms.md) for the full platform list and [Custom Drivers and Registration](../admin/custom-drivers.md) for registering your own platform names.

## From raw text: `from_text()`

The primary constructor. Accepts a string of configuration text or a `pathlib.Path` to a file:

```python
from pathlib import Path

from hier_config import HConfig, Platform

# From a string
config = HConfig.from_text(Platform.CISCO_IOS, config_text)

# From a file path
config = HConfig.from_text(Platform.CISCO_IOS, Path("running_config.conf"))
```

`from_text()` runs the full driver pipeline: full-text and per-line substitutions, the platform's `config_preprocessor` (e.g. JunOS curly-brace flattening), tree construction, and post-load callbacks.

## From pre-split lines: `from_lines()`

If your configuration is already split into lines — for example, streamed from an API — `from_lines()` skips the text-splitting step and loads faster:

```python
config = HConfig.from_lines(Platform.CISCO_IOS, ["hostname router1", "interface Vlan2", " no shutdown"])
```

It accepts a list of strings, a tuple of strings, or a single string.

## Serialization round-trip: `dump()` and `from_dump()`

`HConfig.dump()` serializes a tree — including per-line tags, comments, and `new_in_config` flags — into a `Dump` Pydantic model that can be stored as JSON and reconstructed later:

```python
from hier_config.models import Dump

# Serialize
dump = config.dump()
serialized = dump.model_dump_json()

# ... store, transmit, etc. ...

# Reconstruct
restored = HConfig.from_dump(
    Platform.CISCO_IOS,
    Dump.model_validate_json(serialized),
)
```

This is the recommended way to persist a tree with its metadata (e.g. an already-tagged remediation) between processes.

## Structured formats: JSON and XML

Structured configurations — OpenConfig-style JSON or NETCONF-style XML — can be mapped onto the same tree model, so they can be diffed and predicted exactly like CLI text.

### `from_json()` / `to_json()`

```python
config = HConfig.from_json(Platform.GENERIC, json_text_or_dict)
print(config.to_json(indent=2))
```

Mapping rules:

- object key + scalar → leaf `key <json-encoded scalar>`
- object key + object → node `key` with the object's members as children
- object key + list of scalars → one leaf per item
- object key + list of objects → one node per entry, identified by a key leaf (see below)

### `from_xml()` / `to_xml()`

```python
config = HConfig.from_xml(Platform.GENERIC, xml_text)
print(config.to_xml())
```

XML elements become nodes; attributes and text content become specially-encoded leaves. Treat the trees as opaque between `from_xml()` and `to_xml()` — the internal line encoding may change.

### The `list_keys` concept

Lists of objects (JSON) and repeated sibling elements (XML) need a member that identifies each entry — OpenConfig-style keyed lists. By default, hier_config looks for a member named `name` or `id`. If your data uses different key names, pass them via `list_keys`:

```python
config = HConfig.from_json(
    Platform.GENERIC,
    data,
    list_keys=("interface-name", "name", "id"),
)
```

Entries without any of the named keys raise `InvalidConfigError`.

Both mappings are invertible via `to_json()` / `to_xml()`, with a few caveats (documented in `hier_config.formats`): a single-item scalar list renders back as a bare scalar, and empty lists are dropped.

Remediation between two `from_xml()` trees can also be rendered as a NETCONF `edit-config` payload — see [Remediation Workflows](remediation-workflows.md#netconf-remediation-payloads).

## Format detection errors

`from_text()` guards against being fed structured data. If the text looks like XML or JSON, it raises `InvalidConfigError` and points you at the right constructor:

```python
>>> HConfig.from_text(Platform.GENERIC, '{"interfaces": {}}')
Traceback (most recent call last):
...
hier_config.exceptions.InvalidConfigError: The config appears to be JSON. Use HConfig.from_xml() or HConfig.from_json() for structured formats, ...
```

## Next steps

- [Remediation Workflows](remediation-workflows.md) — compute remediation between the trees you loaded.
- [Set-Style Platforms](set-style-platforms.md) — how JunOS/VyOS/Nokia SRL configs are preprocessed on load.
- [API Reference](../dev/api-reference.md) — full constructor signatures.
