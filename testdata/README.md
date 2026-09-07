# hier_config Test Corpus

This directory contains a language-neutral test corpus of configuration
remediation test cases. These cases are executed by both:
- Native Rust tests (`crates/hier_config_core/tests/corpus.rs`)
- Python pytest suite (`tests/test_corpus.py`)

## Directory Layout

Each case lives in its own subdirectory grouped by platform:

```
testdata/
  cases/
    <platform>/
      <case_name>/
        case.json
        running.conf
        intended.conf
        remediation.conf
```

## `case.json` Schema

```json
{
  "platform": "ARISTA_EOS",
  "description": "Interface description and VLAN changes remediate and roll back cleanly",
  "tags": ["interface", "vlan"],
  "assert_rollback": true
}
```

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `platform` | string | **yes** | — | Uppercase `Platform` member name, e.g. `ARISTA_EOS`, `CISCO_IOS`, `CISCO_XR`. |
| `description` | string | **yes** | — | One sentence explaining what the case pins down. |
| `tags` | array of string | no | `[]` | Free-form grouping (e.g. `["bgp", "post_load"]`). |
| `assert_rollback` | bool | no | `true` | When `false`, the harness asserts remediation only and skips the `future()`/rollback verification. |

## Config Files

| File | Required | Meaning |
|---|---|---|
| `running.conf` | **yes** | The device's current configuration. |
| `intended.conf` | **yes** | The desired configuration. |
| `remediation.conf` | no | Expected `dump_simple(sectional_exiting=false)` output, one line per entry. **Omit** to assert the remediation is empty. |

Leading whitespace and indentation in `remediation.conf` are semantically meaningful.
Trailing newlines at end-of-file are ignored during line comparison.
