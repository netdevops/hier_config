"""Re-export of the native `HConfig` root tree.

The tree, and the v4 ingestion/serialization API (`from_text`, `from_lines`,
`from_dump`, `from_json`, `from_xml`, `to_json`, `to_xml`), live in the Rust
core. Defining them there rather than on a Python subclass means every tree the
core hands back -- including those returned by `future()` and `remediation()` --
carries the full API.
"""

from _hier_config_rust import HConfig

__all__ = ("HConfig",)
