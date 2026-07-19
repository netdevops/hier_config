# Remediation Reporting

This page covers `RemediationReporter`, which aggregates remediation configurations from many devices into a single report. Use it to understand the scope of changes across a fleet, prioritize work, and produce change-management artifacts. It assumes you can already generate a per-device remediation with [`WorkflowRemediation`](remediation-workflows.md).

The `RemediationReporter` class lets you:

- **Merge multiple device remediations** into a single hierarchical tree
- **Track instances** of each configuration change across devices
- **Generate statistics** about remediation scope and impact
- **Filter by tags** to create category-specific reports
- **Export reports** in multiple formats (JSON, CSV, Markdown, text)
- **Query specific changes** to understand their impact

## Quick start

```python
from hier_config import (
    RemediationReporter,
    WorkflowRemediation,
    HConfig,
    Platform,
)

# Generate remediations for each device
devices_remediations = []
for device in devices:
    running = HConfig.from_text(Platform.CISCO_IOS, device.running_config)
    generated = HConfig.from_text(Platform.CISCO_IOS, device.generated_config)
    wfr = WorkflowRemediation(running, generated)
    devices_remediations.append(wfr.remediation_config)

# Create reporter and merge all remediations
reporter = RemediationReporter.from_remediations(devices_remediations)

# Get summary statistics
summary = reporter.summary()
print(f"Total devices: {summary.total_devices}")
print(f"Unique changes: {summary.total_unique_changes}")

# Print human-readable summary
print(reporter.summary_text())
```

Example output:

```text
Remediation Summary
==================================================
Total devices: 150
Unique changes: 87

Top 10 Most Common Changes:
--------------------------------------------------
1. line vty 0 4
   145 devices (96.7%)
2. ntp server 10.2.2.2
   132 devices (88.0%)
3. snmp-server community public RO
   89 devices (59.3%)
...
```

## Creating a reporter

Three construction styles are available:

```python
# 1. From an iterable of remediations (recommended)
reporter = RemediationReporter.from_remediations([
    device1_remediation,
    device2_remediation,
    device3_remediation,
])

# 2. Incrementally
reporter = RemediationReporter()
for device_remediation in device_remediations:
    reporter.add_remediation(device_remediation)
reporter.add_remediations(more_remediations)  # or several at once

# 3. From a pre-merged HConfig
merged = HConfig.from_text(Platform.CISCO_IOS)
merged.merge([device1, device2, device3])
reporter = RemediationReporter.from_merged_config(merged)
```

## Querying changes

### Count devices affected by a change

```python
count = reporter.get_device_count("line vty 0 4")
print(f"{count} devices need this change")
```

### Get detailed information

```python
detail = reporter.get_change_detail("ntp server 10.2.2.2")

print(f"Line: {detail.line}")
print(f"Affects {detail.device_count} devices")
print(f"Device IDs: {detail.device_ids}")
print(f"Tags: {detail.tags}")
print(f"Comments: {detail.comments}")

# Access individual instances
for instance in detail.instances:
    print(f"Device {instance.id}: {instance.tags}")
```

### Filter by impact threshold

```python
# Changes affecting at least 50 devices
high_impact = reporter.get_changes_by_threshold(min_devices=50)

for change in high_impact:
    print(f"{change.text}: {len(change.instances)} devices")

# Changes affecting between 1-5 devices
isolated = reporter.get_changes_by_threshold(min_devices=1, max_devices=5)
```

### Get the top N most common changes

```python
top_10 = reporter.get_top_changes(10)

for child, count in top_10:
    print(f"{child.text}: {count} devices")
```

### Pattern matching

```python
# Find all VLAN interface changes
vlan_changes = reporter.get_changes_matching(r"interface Vlan\d+")

# Find all NTP-related changes
ntp_changes = reporter.get_changes_matching(r"ntp")

# More complex regex
acl_changes = reporter.get_changes_matching(r"access-list \d+ (permit|deny)")
```

## Tag-based reporting

Tags categorize changes so you can generate filtered reports — by risk level, functional area, or deployment phase. The same [`TagRule`/`MatchRule`](tags.md) model used for remediation filtering applies here.

### Apply tag rules

```python
from hier_config import TagRule, MatchRule

tag_rules = [
    TagRule(
        match_rules=(MatchRule(startswith="ntp"),),
        apply_tags=frozenset({"ntp", "time-sync", "safe"}),
    ),
    TagRule(
        match_rules=(MatchRule(startswith="snmp"),),
        apply_tags=frozenset({"snmp", "monitoring"}),
    ),
    TagRule(
        match_rules=(MatchRule(startswith="line vty"),),
        apply_tags=frozenset({"security", "access", "critical"}),
    ),
    TagRule(
        match_rules=(MatchRule(contains="password"),),
        apply_tags=frozenset({"security", "critical"}),
    ),
]

reporter.apply_tag_rules(tag_rules)
```

### Filter by tags

```python
# Only NTP changes
ntp_changes = reporter.get_all_changes(include_tags=["ntp"])

# All changes except those tagged as "critical"
safe_changes = reporter.get_all_changes(exclude_tags=["critical"])

# Combine filters: security changes that are not critical
moderate_security = reporter.get_all_changes(
    include_tags=["security"],
    exclude_tags=["critical"],
)
```

### Tag-based summary

```python
tag_summary = reporter.summary_by_tags(["security", "ntp", "snmp"])

for tag, stats in tag_summary.items():
    print(f"\n{tag.upper()} Changes:")
    print(f"  Devices affected: {stats['device_count']}")
    print(f"  Total changes: {stats['change_count']}")
    for change in stats['changes'][:5]:  # Show first 5
        print(f"    - {change}")
```

## Analysis and statistics

### Summary statistics

```python
summary = reporter.summary()

print(f"Total devices: {summary.total_devices}")
print(f"Unique changes: {summary.total_unique_changes}")

for line, count in summary.most_common_changes[:5]:
    print(f"{line}: {count} devices")

for tag, count in summary.changes_by_tag.items():
    print(f"{tag}: {count} changes")
```

### Impact distribution

```python
distribution = reporter.get_impact_distribution(bins=[1, 10, 25, 50, 100])

for range_label, count in distribution.items():
    print(f"{range_label} devices: {count} changes")
```

```text
1-10 devices: 15 changes
10-25 devices: 8 changes
25-50 devices: 5 changes
50-100 devices: 3 changes
100+ devices: 2 changes
```

### Tag distribution

```python
tag_dist = reporter.get_tag_distribution()

for tag, count in sorted(tag_dist.items(), key=lambda x: x[1], reverse=True):
    print(f"{tag}: {count} occurrences")
```

### Group by parent

```python
grouped = reporter.group_by_parent()

for parent, children in grouped.items():
    print(f"\n{parent}:")
    for child in children[:3]:  # Show first 3
        print(f"  - {child.text} ({len(child.instances)} devices)")
```

```text
interface Vlan2:
  - ip address 10.0.0.2 255.255.255.0 (15 devices)
  - description Updated (12 devices)

line vty 0 4:
  - transport input ssh (145 devices)
  - exec-timeout 5 0 (145 devices)
```

## Exporting reports

All exporters accept `include_tags` / `exclude_tags` filters, so any of the exports below can be scoped to a category (e.g. `include_tags=["security"]`).

### Text

```python
# Merged style shows instance counts per line
reporter.to_text("remediation.txt", style="merged")

# Or "with_comments" / "without_comments" (standard config format)
reporter.to_text("remediation_clean.txt", style="without_comments")
```

```text
interface Vlan2 !15 instances
  ip address 10.0.0.2 255.255.255.0 !15 instances
line vty 0 4 !145 instances
  transport input ssh !145 instances
ntp server 10.2.2.2 !132 instances
```

### JSON

```python
reporter.to_json("remediation_report.json", indent=4)
```

```json
{
  "summary": {
    "total_devices": 150,
    "total_unique_changes": 87
  },
  "changes": [
    {
      "line": "line vty 0 4",
      "device_count": 145,
      "device_ids": [1, 2, 3],
      "tags": ["security", "access", "critical"],
      "comments": ["Update VTY settings"],
      "instances": [
        {"id": 1, "tags": ["security"], "comments": ["Update VTY settings"]}
      ]
    }
  ]
}
```

### CSV

```python
reporter.to_csv("remediation_report.csv")
```

```csv
line,device_count,percentage,tags,comments,device_ids
"line vty 0 4",145,96.7,"security,access,critical","Update VTY settings","1,2,3,..."
"ntp server 10.2.2.2",132,88.0,"ntp,safe","Update NTP server","1,2,3,..."
```

### Markdown

```python
reporter.to_markdown("remediation_report.md", top_n=20)
```

Produces a summary section, a "Top N Changes by Impact" table, and a "Changes by Tag" table — suitable for management-facing summaries.

### All formats at once

```python
reporter.export_all(
    output_dir="reports/",
    formats=["json", "csv", "markdown", "text"],
)
```

This creates `remediation_report.json`, `.csv`, `.md`, and `.txt` in `reports/`.

## Common workflows

### Impact analysis

*"How many devices will be affected if I push NTP server changes?"*

```python
ntp_count = reporter.get_device_count("ntp server 10.2.2.2")
print(f"NTP change will affect {ntp_count} devices")

detail = reporter.get_change_detail("ntp server 10.2.2.2")
print(f"Affected device IDs: {sorted(detail.device_ids)}")
```

### Risk-based change management

Tag changes by risk, then generate a separate change window per risk level:

```python
tag_rules = [
    TagRule(
        match_rules=(
            MatchRule(startswith="ntp"),
            MatchRule(startswith="logging"),
        ),
        apply_tags=frozenset({"low-risk", "safe"}),
    ),
    TagRule(
        match_rules=(MatchRule(contains="password"),),
        apply_tags=frozenset({"high-risk", "critical"}),
    ),
    TagRule(
        match_rules=(
            MatchRule(startswith="interface"),
            MatchRule(startswith="routing"),
        ),
        apply_tags=frozenset({"medium-risk", "requires-review"}),
    ),
]

reporter.apply_tag_rules(tag_rules)

for risk in ["low-risk", "medium-risk", "high-risk"]:
    reporter.to_text(f"{risk}_changes.txt", include_tags=[risk])
    changes = reporter.get_all_changes(include_tags=[risk])
    print(f"{risk}: {len(changes)} change types")
```

### Compliance reporting

Tag security-related changes and export an audit trail:

```python
security_tags = [
    TagRule(
        match_rules=(MatchRule(contains="password"),),
        apply_tags=frozenset({"security", "authentication"}),
    ),
    TagRule(
        match_rules=(MatchRule(startswith="line vty"),),
        apply_tags=frozenset({"security", "access-control"}),
    ),
    TagRule(
        match_rules=(MatchRule(startswith="snmp"),),
        apply_tags=frozenset({"security", "monitoring"}),
    ),
]

reporter.apply_tag_rules(security_tags)

security_summary = reporter.summary_by_tags(["security"])
for tag, stats in security_summary.items():
    print(f"Category: {tag}")
    print(f"Devices requiring changes: {stats['device_count']}")
    print(f"Total change items: {stats['change_count']}")

reporter.to_markdown("security_compliance_report.md", include_tags=["security"])
```

### Prioritization by scope

Focus on the changes affecting the most devices first:

```python
top_changes = reporter.get_top_changes(10)
for i, (change, count) in enumerate(top_changes, 1):
    percentage = (count / reporter.device_count) * 100
    print(f"{i}. {change.text}: {count} devices ({percentage:.1f}%)")

# Changes affecting >80% of devices
high_impact = reporter.get_changes_by_threshold(
    min_devices=int(reporter.device_count * 0.8)
)
```

### Phased rollout by category

Tag by deployment phase and export a per-phase package:

```python
category_tags = [
    TagRule(
        match_rules=(MatchRule(startswith="ntp"),),
        apply_tags=frozenset({"phase-1", "time-services"}),
    ),
    TagRule(
        match_rules=(MatchRule(startswith="logging"),),
        apply_tags=frozenset({"phase-1", "logging"}),
    ),
    TagRule(
        match_rules=(MatchRule(startswith="snmp"),),
        apply_tags=frozenset({"phase-2", "monitoring"}),
    ),
    TagRule(
        match_rules=(MatchRule(startswith="interface"),),
        apply_tags=frozenset({"phase-3", "interfaces"}),
    ),
]

reporter.apply_tag_rules(category_tags)

for phase in ["phase-1", "phase-2", "phase-3"]:
    reporter.export_all(
        output_dir=f"rollout/{phase}/",
        formats=["json", "csv", "text"],
        include_tags=[phase],
    )
```

### Exception reporting

Find devices with unique or uncommon changes:

```python
exceptions = reporter.get_changes_by_threshold(min_devices=1, max_devices=3)

for change in exceptions:
    detail = reporter.get_change_detail(change.text)
    print(f"{change.text}")
    print(f"  Affects {detail.device_count} device(s): {sorted(detail.device_ids)}")
    if detail.comments:
        print(f"  Comments: {', '.join(detail.comments)}")
```

## Best practices

- **Apply tags early** — tagging enables every filtered query and export that follows.
- **Match the format to the audience** — JSON for tooling, Markdown for management summaries, CSV for spreadsheet analysis, plain text for deployment.
- **Validate scope before deployment** — check `get_changes_by_threshold()` for unexpectedly widespread changes and require approval for them.
- **Timestamp exported reports** (e.g. `reports/20260718_120000/`) to keep a history of remediation scope over time.

## Troubleshooting

### No changes showing up

```python
# Check if remediations were added
print(f"Device count: {reporter.device_count}")

# Check if remediation configs are empty
for i, remediation in enumerate(remediations):
    change_count = len(tuple(remediation.all_children()))
    print(f"Remediation {i}: {change_count} changes")
```

### Tags not working

```python
# Verify tags were applied
all_changes = reporter.get_all_changes()
for change in all_changes[:5]:
    print(f"{change.text}: tags={change.tags}")

# Check tag distribution
print(reporter.get_tag_distribution())
```

### Device count seems wrong

```python
# Check unique device IDs
all_changes = reporter.get_all_changes()
all_device_ids = set()
for change in all_changes:
    for instance in change.instances:
        all_device_ids.add(instance.id)

print(f"Unique device IDs found: {len(all_device_ids)}")
print(f"Reporter device count: {reporter.device_count}")
```

## Next steps

- [Working with Tags](tags.md) — the tagging model in detail.
- [Remediation Workflows](remediation-workflows.md) — generating the per-device remediations that feed the reporter.
- [API Reference](../dev/api-reference.md) — full `RemediationReporter`, `ReportSummary`, and `ChangeDetail` signatures.
