# Driver Rule Reference

This page catalogs every rule model that can appear in a driver's `HConfigDriverRules`, with its fields and purpose. It is the reference companion to [Customizing Driver Rules](../admin/customizing-rules.md) and [Creating a Platform Driver](creating-drivers.md).

All rule models are frozen Pydantic models defined in `hier_config/models.py`. Most take a `match_rules: tuple[MatchRule, ...]` describing the full lineage path a configuration line must match — one `MatchRule` per level of hierarchy.

---

## Match rules

**Purpose**: provide a flexible way to define conditions for matching configuration lines.

**`MatchRule`** fields (all optional; when multiple are set, every criterion must match):

- `equals`: matches lines exactly equal to a string (or contained in a frozenset of strings).
- `startswith`: matches lines that start with the specified text or any of a tuple of texts.
- `endswith`: matches lines that end with the specified text or any of a tuple of texts.
- `contains`: matches lines that contain the specified text or any of a tuple of texts.
- `re_search`: matches lines using a regular expression.

A tuple of MatchRules describes a lineage: `(MatchRule(startswith="interface "), MatchRule(startswith="description "))` matches `description` lines under `interface` sections. `HConfigChild.is_lineage_match()` performs the evaluation.

---

## Negation rules

**Purpose**: define how commands are negated or reset to a default state.

**`NegationRule`** — a single unified model with a `NegationStrategy` enum. REPLACE rules are consulted first (via `driver.negate_with()`); the remaining rules are then evaluated in list order and the first matching rule wins.

- `match_rules`: the conditions under which the rule applies.
- `strategy`:
    - `NegationStrategy.REPLACE` — replace the negation with the fixed string in `use`.
    - `NegationStrategy.DEFAULT` — rewrite the command to its `default <command>` form.
    - `NegationStrategy.REGEX_SUB` — apply `re.sub(search, replace, ...)` to the *already-negated* text (negation prefix included); `replace` supports back-references such as `\1`.
- `use`: the replacement negation command (required for REPLACE).
- `search` / `replace`: the regex substitution (`search` required for REGEX_SUB).

A model validator enforces the per-strategy required fields at construction time.

```python
NegationRule(
    strategy=NegationStrategy.REPLACE,
    match_rules=(MatchRule(startswith="logging console "),),
    use="logging console debugging",
)
```

---

## Sectional exiting

**Purpose**: manage hierarchical configuration sections by defining the command that closes each section when rendering.

**`SectionalExitingRule`**:

- `match_rules`: defines the section's boundaries.
- `exit_text`: the command used to exit the section.
- `exit_text_parent_level`: boolean (default `False`). When `True`, the exit text is rendered at the parent's indentation level rather than the section's own level (e.g., IOS XR `end-policy` appears unindented).

---

## Ordering

**Purpose**: assign weights to commands to control the order of operations during configuration application.

**`OrderingRule`**:

- `match_rules`: defines the commands to be ordered.
- `weight`: an integer determining the order (lower weights are applied earlier).

---

## Substitutions

**Purpose**: modify or clean up configuration text at load time, before parsing.

**`PerLineSubRule`** — applied to each line individually:

- `search`: a string or regex to search for.
- `replace`: the replacement text.

**`FullTextSubRule`** — same fields, but applied to the entire text block (useful for multi-line patterns).

---

## Idempotent commands

**Purpose**: identify last-value-wins commands so remediation overwrites instead of negating and re-adding, and so `future()` does not duplicate them.

**`IdempotentCommandsRule`**:

- `match_rules`: defines the idempotent command family. Use regex capture groups in `re_search` to parameterize idempotency keys — e.g. `r"^client (\S+) server-key"` makes each client IP independently idempotent. Prefer separate rules for unrelated command families rather than combining them via a tuple `startswith` in a single `MatchRule`.

**`IdempotentCommandsAvoidRule`**:

- `match_rules`: commands that must *not* be treated as idempotent even if they would otherwise match (e.g. secondary IP addresses).

---

## Sectional overwriting

**Purpose**: replace whole sections instead of diffing line-by-line.

**`SectionalOverwriteRule`**:

- `match_rules`: sections that are negated and re-created wholesale during remediation.

**`SectionalOverwriteNoNegateRule`**:

- `match_rules`: sections re-created *without* prior negation (e.g. IOS XR `route-policy`, where re-entering the block replaces it).

---

## Indentation adjustments

**Purpose**: correct configuration blocks whose native rendering uses inconsistent indentation (e.g. IOS XR inline templates).

**`IndentAdjustRule`**:

- `start_expression`: regex marking the start of an adjustment.
- `end_expression`: regex marking the end of an adjustment.

---

## Duplicate children

**Purpose**: permit multiple children with identical text under one parent.

**`ParentAllowsDuplicateChildRule`**:

- `match_rules`: parents that may hold duplicate children (e.g. `endif` tokens in IOS XR route-policies). A rule with *empty* `match_rules` applies to the root, allowing duplicate top-level lines.

---

## Unused object detection

**Purpose**: find objects (ACLs, prefix lists, ...) that are defined but never referenced. Consumed by `HConfig.unused_objects()`; not enabled in any driver by default.

**`UnusedObjectRule`**:

- `match_rules`: locates the object definitions.
- `name_re`: regex with a `(?P<name>...)` capture group extracting the object name.
- `reference_locations`: tuple of `ReferenceLocation` entries to search.

**`ReferenceLocation`**:

- `match_rules`: a lineage prefix that narrows the search scope.
- `reference_re`: regex containing `{name}`, interpolated with the (escaped) object name before matching.

---

## Tagging

**Purpose**: apply tags to configuration lines for filtering and reporting. Tag rules are applied via `WorkflowRemediation.apply_remediation_tag_rules()` or `RemediationReporter.apply_tag_rules()` rather than being stored on drivers.

**`TagRule`**:

- `match_rules`: defines the lines to tag.
- `apply_tags`: a frozenset of tags to apply.

---

## Callbacks

**Purpose**: apply imperative transformations that declarative rules cannot express. These are plain Python callables (`Callable[[HConfig], None]`), not Pydantic models, and therefore cannot be loaded from YAML.

- `post_load_callbacks` — run against the tree immediately after parsing (e.g. IOS VLAN-list splitting, ProCurve VLAN membership normalization).
- `remediation_transform_callbacks` — run against each computed remediation, before user plugins (see [Remediation Workflows](../user/remediation-workflows.md#the-remediation-transform-pipeline)).

---

## Rendering

- `indentation` (`PositiveInt`, default `2`) — spaces per depth level used by `indented_text()` and text rendering.

---

## Metadata and serialization models

These models support tree metadata and round-tripping rather than driver behavior:

**`Instance`** — metadata snapshot for one device's occurrence of a line in a merged/reporting tree:

- `id`: a unique positive integer identifier.
- `comments`: a frozenset of comments.
- `tags`: a frozenset of tags.

**`DumpLine`** — one serialized line:

- `depth`: hierarchy level of the line.
- `text`: the configuration text.
- `tags` / `comments`: frozensets associated with the line.
- `new_in_config`: boolean indicating whether the line is new.

**`Dump`**:

- `lines`: a tuple of `DumpLine` objects representing the whole tree (see [Loading Configurations](../user/loading-configs.md#serialization-round-trip-dump-and-from_dump)).

---

## General rule-building patterns

1. **Define matching conditions** with `MatchRule` for flexible, precise control over which configuration lines a rule applies to.
2. **Apply context-specific logic** with the specialized models (`SectionalExitingRule`, `IdempotentCommandsRule`, ...) for hierarchical or idempotency-related scenarios.
3. **Rely on immutability** — the models are frozen and validated by Pydantic, so a rule cannot be mutated after construction; extend drivers by appending new rules to the (mutable) rule lists.

## Next steps

- [Customizing Driver Rules](../admin/customizing-rules.md) — apply these models to a built-in driver.
- [Creating a Platform Driver](creating-drivers.md) — assemble a full rule set for a new platform.
- [API Reference](api-reference.md) — generated documentation for every model.
