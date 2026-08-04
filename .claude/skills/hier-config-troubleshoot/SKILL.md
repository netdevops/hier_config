---
name: hier-config-troubleshoot
description: Use when hier_config produces wrong or unexpected output — incorrect remediation commands, missing or extra negations, repeated commands, lines nested under the wrong parent, DuplicateChildError, inaccurate future() or rollback results, or config lines parsed incorrectly.
---

# Troubleshoot hier_config Behavior

Diagnose why hier_config produced unexpected output. Work from a minimal reproduction, identify which layer is responsible (parsing → driver rules → diff algorithm), then fix at the source with a regression test.

## Step 1: Reproduce Minimally

Reduce the problem to the smallest config pair that shows it, using inline tuples — no fixture files needed:

```python
from hier_config import Platform, get_hconfig_fast_load

running_config = get_hconfig_fast_load(Platform.CISCO_IOS, ("hostname foo",))
generated_config = get_hconfig_fast_load(Platform.CISCO_IOS, ("hostname bar",))
print("\n".join(running_config.config_to_get_to(generated_config).dump_simple()))
```

Bisect: delete config lines until removing one more makes the symptom disappear. That line (and its ancestry) is where to look. If the report compares platforms ("works on X, broken on Y"), reproduce **both** platforms — claimed-working references are often wrong, and the platforms that actually differ tell you which rule is responsible. If the raw config parses differently than expected, compare `get_hconfig()` (full parse with preprocessing) against `get_hconfig_fast_load()` (no preprocessing) — a difference means a `per_line_sub`/`full_text_sub`/`config_preprocessor` or indentation issue.

## Step 2: Inspect the Tree, Not the Text

- `config.dump_simple()` — the parsed tree as indented lines; wrong nesting is visible immediately.
- `running_config.unified_diff(generated_config)` — structure-aware diff.
- `config.driver.rules` — the live rule set; check what the platform driver actually matches.

## Step 3: Match Symptom to Layer

| Symptom | Likely cause | Where to look |
|---------|-------------|---------------|
| Command emitted as `no X` + `Y` instead of just `Y` | Missing idempotency rule — the command is last-write-wins on the device but the driver doesn't know | `idempotent_commands` in the platform driver; add `IdempotentCommandsRule` |
| Negation has the wrong form (`no shutdown` vs `default shutdown` vs truncated args) | Negation rules | `negate_with` (`NegationDefaultWithRule`), `negation_default_when`, or the driver's `swap_negation` override |
| Lines nested under the wrong parent; everything after line X collapses under it | Irregular indentation in vendor output; an `IndentAdjustRule` matching too broadly or missing | `indent_adjust` rules. Real cases: XR `template` blocks; Huawei `peer-public-key end` (see git log for #205, #268) |
| `DuplicateChildError` | Platform legitimately repeats a child text under one parent | Add `ParentAllowsDuplicateChildRule` (see #266 for a real example) |
| Section replaced wholesale (or should be, but isn't) | Sectional overwrite | `sectional_overwrite` / `sectional_overwrite_no_negate` (XR `route-policy` is the canonical case) |
| Missing/wrong exit token after a section (`exit`, `quit`, `end-policy`) | Sectional exiting | `sectional_exiting` rules; `exit_text_parent_level` for unindented exits |
| Commands in an order the device rejects | Ordering weights | `ordering` rules (lower weight applies first) |
| Junk lines in the tree (banners, comments, timestamps) | Load-time substitutions | `per_line_sub` / `full_text_sub` |
| `future()` or rollback doesn't match real device behavior | Known algorithm limitations | `docs/user/future-config.md#known-limitations` — duplicate children and order-dependent sections (ACLs need sequence numbers) are documented limits |
| Wrong platform behavior entirely | Wrong driver selected | Confirm the `Platform` enum member; `GENERIC` has almost no rules |

Rule semantics reference: `docs/user/custom-drivers.md#driver-rule-types`. Layer responsibilities: `docs/dev/architecture.md`.

## Step 4: Confirm Which Rule Fires

Rules match on full ancestry via `MatchRule` tuples (fields AND together; tuple entries match root→leaf lineage). Test a hypothesis directly:

```python
from hier_config.models import MatchRule

child = running_config.get_child_deep((MatchRule(startswith="interface"), MatchRule(startswith="ip address")))
if child is None:
    print("no child matched — the lineage tuple is wrong or the line parsed differently")
else:
    print(child, child.is_lineage_match((MatchRule(startswith="interface"),)))
```

If a driver rule should match but doesn't, print the rule set (`config.driver.rules.idempotent_commands`, etc.) and check each `MatchRule` field against the actual line text — trailing whitespace and `startswith` vs `equals` mismatches are the usual culprits.

## Step 5: Fix at the Source

- Driver rule gap (most common): add/adjust the rule in the platform driver's `_instantiate_rules()` — recipe in `docs/dev/extending.md`.
- Core algorithm (`base.py`, `root.py`, `child.py`): rare; read `docs/dev/architecture.md` first and check `git log` for related fixes before changing shared behavior.
- User-side workaround (can't wait for a release): customize the driver at runtime — `docs/user/custom-drivers.md#customizing-existing-drivers`.

Every fix ships with a regression test that reproduces the original symptom (`docs/dev/testing.md`, round-trip idiom) and a `CHANGELOG.md` entry. Fixes to one platform must not leak: run the full suite (`poetry run ./scripts/build.py lint-and-test`), not just the platform's test file.
