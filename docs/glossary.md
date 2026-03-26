# Glossary

This page defines hier_config-specific terminology used throughout the documentation and source code.

---

## Declaration prefix

The string that precedes a *positive* (enabling) command in platforms that use explicit declarations, such as JunOS (`set`) and VyOS (`set`).  The driver's `declaration_prefix` property returns this string; `HConfigDriverBase` defaults to an empty string (Cisco-style platforms have no explicit declaration keyword).

**Example:** In JunOS, `set interfaces ge-0/0/0 description uplink` — the declaration prefix is `"set "`.

---

## Driver / HConfigDriverBase

A Python class that encodes all operating-system-specific behaviour for one network platform.  Every driver subclasses `HConfigDriverBase` and provides an `HConfigDriverRules` instance via `_instantiate_rules()`.  Drivers are selected by passing a `Platform` enum value to `get_hconfig()` or `get_hconfig_driver()`.

**Example:** `HConfigDriverCiscoIOS`, `HConfigDriverJuniperJUNOS`.

---

## Idempotent command

A configuration command where only the *last* value applied takes effect — applying the same command twice with different values results in only the second value being active.  Typical examples: `hostname`, `ip address`, `description`.

hier_config uses `IdempotentCommandsRule` to identify these commands.  During `remediation()`, when both the running and intended configs contain a command that matches an idempotency rule, the running value is **not** negated before the new value is applied (the new value simply overwrites it).

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

A set of `IdempotentCommandsAvoidRule` entries that *prevent* specific commands from being treated as idempotent even if they would otherwise match an `IdempotentCommandsRule`.  Useful for commands like secondary IP addresses, where applying the same `startswith` prefix would incorrectly deduplicate distinct entries.

**Example:** Avoiding idempotency for `ip address ... secondary` on Cisco NX-OS.

---

## Indent adjust

A pair of `IndentAdjustRule` entries (`start_expression` / `end_expression`) that temporarily shift the indentation level between the two markers.  Used on Cisco IOS XR for inline templates whose body is indented differently from the surrounding context.

---

## Match rule

A `MatchRule` Pydantic model that acts as a predicate on an `HConfigChild.text` value.  All fields (`equals`, `startswith`, `endswith`, `contains`, `re_search`) are optional; when multiple are set every criterion must match.  Match rules are composed into tuples to describe a full lineage path.

**Example:** Match any `neighbor X.X.X.X description` line under a BGP section:

```python
MatchRule(startswith="router bgp"),
MatchRule(re_search=r"neighbor \S+ description"),
```

---

## Negation prefix

The string prepended to a command to negate (remove) it.  `HConfigDriverBase.negation_prefix` defaults to `"no "` for Cisco-style platforms.  Platforms that use a different convention override this property.

| Platform | Negation prefix |
|----------|----------------|
| Cisco IOS / EOS / NX-OS | `"no "` |
| HP Comware5 / H3C | `"undo "` |
| JunOS / VyOS | `"delete "` |

---

## Negation — default when

A `NegationDefaultWhenRule` that causes hier_config to use the `default <command>` form of negation instead of `no <command>`.  Some IOS and EOS commands behave differently when defaulted vs negated (e.g. `logging event link-status`).

---

## Negation — negate with

A `NegationDefaultWithRule` that replaces the standard negation with a fixed command string.  Used when a command cannot be simply prepended with `"no "` — for example, `logging console debugging` is the correct way to reset the console logging level rather than `no logging console`.

---

## Parent allows duplicate child

A `ParentAllowsDuplicateChildRule` that permits multiple `HConfigChild` objects with the same `text` value under a single parent.  Required for constructs such as `address-family` blocks inside `router bgp` on some platforms, or `endif` tokens in IOS XR route-policies.

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

A `SectionalExitingRule` that instructs hier_config to emit a closing token at the end of a configuration section when rendering output.  Different platforms require different exit syntax.

| Platform / section | Exit token |
|-------------------|-----------|
| Cisco IOS BGP peer-policy | `exit-peer-policy` |
| Cisco IOS XR route-policy | `end-policy` |
| Cisco IOS XR prefix-set | `end-set` |
| Most sections (default) | `exit` |

---

## Sectional overwrite

A `SectionalOverwriteRule` that tells `remediation()` to **negate the entire section** and then re-create it from the intended config rather than performing a line-by-line diff.  Appropriate for configuration blocks where the order of entries matters globally or where partial changes are not supported by the OS.

---

## Sectional overwrite no negate

A `SectionalOverwriteNoNegateRule` similar to sectional overwrite, but the existing section is **deleted without negation** before the new version is written.  Used for blocks like `prefix-set` and `route-policy` on Cisco IOS XR where issuing a `no` is not the correct removal mechanism.

---

## Tag rules

`TagRule` entries that apply a named tag (`apply_tags`) to all `HConfigChild` nodes whose lineage matches `match_rules`.  Tags are used by `WorkflowRemediation.apply_remediation_tag_rules()` to annotate the remediation config for selective filtering via `remediation_config_filtered_text()`.

**Example use case:** Tag all interface changes as `"interfaces"` and all BGP changes as `"bgp"` so that changes can be deployed separately.

---

## WorkflowRemediation

The primary user-facing class for computing the delta between a running and an intended configuration.  Exposes:

- `remediation_config` — the commands to apply to bring the device into compliance.
- `rollback_config` — the commands to revert the device back to its original state.
- `apply_remediation_tag_rules()` — annotate remediation lines with tags.
- `remediation_config_filtered_text()` — render tagged subset of the remediation.
