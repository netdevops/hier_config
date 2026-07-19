# Glossary

This page defines hier_config-specific terminology used throughout the documentation and source code.

---

## Declaration prefix

The string that precedes a *positive* (enabling) command in platforms that use explicit declarations, such as JunOS (`set`) and VyOS (`set`). The driver's `declaration_prefix` property returns this string; `HConfigDriverBase` defaults to an empty string (Cisco-style platforms have no explicit declaration keyword).

**Example:** In JunOS, `set interfaces ge-0/0/0 description uplink` — the declaration prefix is `"set "`.

---

## Driver / HConfigDriverBase

A Python class that encodes all operating-system-specific behaviour for one network platform. Every driver subclasses `HConfigDriverBase` and provides an `HConfigDriverRules` instance via `_instantiate_rules()`. Drivers are resolved through the driver registry by passing a `Platform` enum value (or registered platform name string) to `HConfig.from_text()` or `get_hconfig_driver()`.

**Example:** `HConfigDriverCiscoIOS`, `HConfigDriverJuniperJUNOS`.

---

## Idempotent command

A configuration command where only the *last* value applied takes effect — applying the same command twice with different values results in only the second value being active. Typical examples: `hostname`, `ip address`, `description`.

hier_config uses `IdempotentCommandsRule` to identify these commands. During `remediation()`, when both the running and intended configs contain a command that matches an idempotency rule, the running value is **not** negated before the new value is applied (the new value simply overwrites it).

**Example rule:**

```python
IdempotentCommandsRule(
    match_rules=(
        MatchRule(startswith="interface "),
        MatchRule(startswith="description "),
    )
)
```

---

## Idempotent command avoid list

A set of `IdempotentCommandsAvoidRule` entries that *prevent* specific commands from being treated as idempotent even if they would otherwise match an `IdempotentCommandsRule`. Useful for commands like secondary IP addresses, where applying the same `startswith` prefix would incorrectly deduplicate distinct entries.

**Example:** Avoiding idempotency for `ip address ... secondary` on Cisco NX-OS.

---

## Indent adjust

A pair of `IndentAdjustRule` entries (`start_expression` / `end_expression`) that temporarily shift the indentation level between the two markers. Used on Cisco IOS XR for inline templates whose body is indented differently from the surrounding context.

---

## Match rule

A `MatchRule` Pydantic model that acts as a predicate on an `HConfigChild.text` value. All fields (`equals`, `startswith`, `endswith`, `contains`, `re_search`) are optional; when multiple are set every criterion must match. Match rules are composed into tuples to describe a full lineage path.

**Example:** Match any `neighbor X.X.X.X description` line under a BGP section:

```python
MatchRule(startswith="router bgp"),
MatchRule(re_search=r"neighbor \S+ description"),
```

---

## Negation prefix

The string prepended to a command to negate (remove) it. `HConfigDriverBase.negation_prefix` defaults to `"no "` for Cisco-style platforms. Platforms that use a different convention override this property.

| Platform | Negation prefix |
|----------|----------------|
| Cisco IOS / EOS / NX-OS | `"no "` |
| HP Comware5 / H3C / Huawei VRP | `"undo "` |
| JunOS / VyOS / Nokia SRL | `"delete "` |

---

## Negation rule

A `NegationRule` describes commands that cannot simply be prefixed with the negation prefix. Each rule carries a `NegationStrategy`:

- **`NegationStrategy.REPLACE`** — replace the negation with the fixed command string in `use`. Used when a command has a dedicated reset form — for example, `logging console debugging` is the correct way to reset the console logging level rather than `no logging console`.
- **`NegationStrategy.DEFAULT`** — rewrite the command to its `default <command>` form. Some IOS and EOS commands behave differently when defaulted vs negated (e.g. `logging event link-status`).
- **`NegationStrategy.REGEX_SUB`** — apply `re.sub(search, replace, ...)` to the already-negated text, e.g. to truncate a negation after a keyword (`no snmp-server user bob ...` → `no snmp-server user bob`).

Rules are evaluated in list order; the first matching rule wins. (`NegationRule` replaces the earlier `NegationDefaultWithRule`, `NegationDefaultWhenRule`, and `NegationSubRule` models.)

---

## Parent allows duplicate child

A `ParentAllowsDuplicateChildRule` that permits multiple `HConfigChild` objects with the same `text` value under a single parent. Required for constructs such as `address-family` blocks inside `router bgp` on some platforms, or `endif` tokens in IOS XR route-policies. A rule with empty `match_rules` applies to the root of the tree.

---

## Per-line sub / full-text sub

Regex substitution rules applied to configuration text at load time before it is parsed into the tree:

- `PerLineSubRule` — applies the substitution to each line individually (useful for removing inline comments, `!`, timestamp headers).
- `FullTextSubRule` — applies the substitution across the entire text block (useful for multi-line patterns).

**Example:** Strip `Building configuration...` banners:

```python
PerLineSubRule(search="^Building configuration.*", replace="")
```

---

## Sectional exiting

A `SectionalExitingRule` that instructs hier_config to emit a closing token at the end of a configuration section when rendering output. Different platforms require different exit syntax.

| Platform / section | Exit token |
|-------------------|-----------|
| Cisco IOS BGP peer-policy | `exit-peer-policy` |
| Cisco IOS XR route-policy | `end-policy` |
| Cisco IOS XR prefix-set | `end-set` |
| Huawei VRP sections | `quit` |
| Most sections (default) | `exit` |

---

## Sectional overwrite

A `SectionalOverwriteRule` that tells `remediation()` to **negate the entire section** and then re-create it from the intended config rather than performing a line-by-line diff. Appropriate for configuration blocks where the order of entries matters globally or where partial changes are not supported by the OS.

---

## Sectional overwrite no negate

A `SectionalOverwriteNoNegateRule` similar to sectional overwrite, but the existing section is **deleted without negation** before the new version is written. Used for blocks like `prefix-set` and `route-policy` on Cisco IOS XR where issuing a `no` is not the correct removal mechanism.

---

## Tag rules

`TagRule` entries that apply named tags (`apply_tags`) to all `HConfigChild` nodes whose lineage matches `match_rules`. Tags are used by `WorkflowRemediation.apply_remediation_tag_rules()` to annotate the remediation config for selective filtering via `remediation_config_filtered_text()`, and by `RemediationReporter.apply_tag_rules()` for tag-based reporting.

**Example use case:** Tag all interface changes as `"interfaces"` and all BGP changes as `"bgp"` so that changes can be deployed separately.

---

## Unused object rule

An `UnusedObjectRule` that identifies named object definitions (ACLs, prefix lists, ...) via `match_rules`, extracts each object's name with `name_re`, and searches the locations described by `reference_locations` for references. Objects with zero references are yielded by `HConfig.unused_objects()`. Not enabled in any driver by default.

---

## WorkflowRemediation

The primary user-facing class for computing the delta between a running and an intended configuration. Exposes:

- `remediation_config` — the commands to apply to bring the device into compliance.
- `rollback_config` — the commands to revert the device back to its original state.
- `remediation_netconf_xml()` — the remediation rendered as a NETCONF `edit-config` payload (for XML-sourced configs).
- `apply_remediation_tag_rules()` — annotate remediation lines with tags.
- `remediation_config_filtered_text()` — render a tagged subset of the remediation.
- `plugins` — user-supplied transforms applied to the computed remediation.
