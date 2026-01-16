# Remediation Reporting

hier_config provides powerful reporting capabilities for aggregating and analyzing remediation configurations from multiple network devices. This enables network engineers to understand the scope of changes across their infrastructure, prioritize work, and generate reports for change management.

## Overview

The `RemediationReporter` class allows you to:

- **Merge multiple device remediations** into a single hierarchical tree
- **Track instances** of each configuration change across devices
- **Generate statistics** about remediation scope and impact
- **Filter by tags** to create category-specific reports
- **Export reports** in multiple formats (JSON, CSV, Markdown, Text)
- **Query specific changes** to understand their impact

## Quick Start

### Basic Usage

```python
from hier_config import (
    RemediationReporter,
    WorkflowRemediation,
    get_hconfig,
    Platform,
)

# Generate remediations for each device
devices_remediations = []
for device in devices:
    running = get_hconfig(Platform.CISCO_IOS, device.running_config)
    generated = get_hconfig(Platform.CISCO_IOS, device.generated_config)
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

### Output Example

```
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

## Creating a Reporter

### Method 1: From Remediations (Recommended)

```python
reporter = RemediationReporter.from_remediations([
    device1_remediation,
    device2_remediation,
    device3_remediation,
])
```

### Method 2: Add Incrementally

```python
reporter = RemediationReporter()

# Add one at a time
for device_remediation in device_remediations:
    reporter.add_remediation(device_remediation)

# Or add multiple at once
reporter.add_remediations(more_remediations)
```

### Method 3: From Pre-Merged Config

```python
# If you already have a merged configuration
merged = get_hconfig(Platform.CISCO_IOS)
merged.merge([device1, device2, device3])

reporter = RemediationReporter.from_merged_config(merged)
```

## Querying Changes

### Count Devices Affected by a Change

```python
# How many devices need this specific change?
count = reporter.get_device_count("line vty 0 4")
print(f"{count} devices need this change")
```

### Get Detailed Information

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

### Find High-Impact Changes

```python
# Changes affecting at least 50 devices
high_impact = reporter.get_changes_by_threshold(min_devices=50)

for change in high_impact:
    print(f"{change.text}: {len(change.instances)} devices")

# Changes affecting between 1-5 devices
isolated = reporter.get_changes_by_threshold(
    min_devices=1,
    max_devices=5,
)
```

### Get Top N Most Common Changes

```python
top_10 = reporter.get_top_changes(10)

for child, count in top_10:
    print(f"{child.text}: {count} devices")
```

### Pattern Matching

```python
# Find all VLAN interface changes
vlan_changes = reporter.get_changes_matching(r"interface Vlan\d+")

# Find all NTP-related changes
ntp_changes = reporter.get_changes_matching(r"ntp")

# More complex regex
acl_changes = reporter.get_changes_matching(r"access-list \d+ (permit|deny)")
```

## Tag-Based Reporting

Tags allow you to categorize changes and generate filtered reports.

### Apply Tag Rules

```python
from hier_config import TagRule, MatchRule

# Define tag rules
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

# Apply tags to the merged configuration
reporter.apply_tag_rules(tag_rules)
```

### Filter by Tags

```python
# Get only NTP changes
ntp_changes = reporter.get_all_changes(include_tags=["ntp"])

# Get only security-related changes
security_changes = reporter.get_all_changes(include_tags=["security"])

# Get all changes except those tagged as "critical"
safe_changes = reporter.get_all_changes(exclude_tags=["critical"])

# Combine filters: security changes that are not critical
moderate_security = reporter.get_all_changes(
    include_tags=["security"],
    exclude_tags=["critical"],
)
```

### Tag-Based Summary

```python
# Get summary breakdown by tags
tag_summary = reporter.summary_by_tags(["security", "ntp", "snmp"])

for tag, stats in tag_summary.items():
    print(f"\n{tag.upper()} Changes:")
    print(f"  Devices affected: {stats['device_count']}")
    print(f"  Total changes: {stats['change_count']}")
    print(f"  Changes:")
    for change in stats['changes'][:5]:  # Show first 5
        print(f"    - {change}")
```

Output:
```
SECURITY Changes:
  Devices affected: 145
  Total changes: 23
  Changes:
    - line vty 0 4
    - enable secret 5 ...
    - username admin privilege 15

NTP Changes:
  Devices affected: 132
  Total changes: 8
  Changes:
    - ntp server 10.2.2.2
    - ntp authenticate
```

## Analysis and Statistics

### Summary Statistics

```python
summary = reporter.summary()

print(f"Total devices: {summary.total_devices}")
print(f"Unique changes: {summary.total_unique_changes}")

# Top changes
for line, count in summary.most_common_changes[:5]:
    print(f"{line}: {count} devices")

# Changes by tag
for tag, count in summary.changes_by_tag.items():
    print(f"{tag}: {count} changes")
```

### Impact Distribution

```python
# Get distribution of changes by device impact
distribution = reporter.get_impact_distribution(
    bins=[1, 10, 25, 50, 100]
)

for range_label, count in distribution.items():
    print(f"{range_label} devices: {count} changes")
```

Output:
```
1-10 devices: 15 changes
10-25 devices: 8 changes
25-50 devices: 5 changes
50-100 devices: 3 changes
100+ devices: 2 changes
```

### Tag Distribution

```python
tag_dist = reporter.get_tag_distribution()

for tag, count in sorted(tag_dist.items(), key=lambda x: x[1], reverse=True):
    print(f"{tag}: {count} occurrences")
```

### Group by Parent

```python
# Group changes by their parent configuration context
grouped = reporter.group_by_parent()

for parent, children in grouped.items():
    print(f"\n{parent}:")
    for child in children[:3]:  # Show first 3
        print(f"  - {child.text} ({len(child.instances)} devices)")
```

Output:
```
interface Vlan2:
  - ip address 10.0.0.2 255.255.255.0 (15 devices)
  - description Updated (12 devices)

line vty 0 4:
  - transport input ssh (145 devices)
  - exec-timeout 5 0 (145 devices)
```

## Exporting Reports

### Export to Text

```python
# Export with merged style (shows instance counts)
reporter.to_text("remediation.txt", style="merged")

# Export with comments
reporter.to_text("remediation_comments.txt", style="with_comments")

# Export without comments (standard config format)
reporter.to_text("remediation_clean.txt", style="without_comments")

# Export only security changes
reporter.to_text(
    "security_remediation.txt",
    style="merged",
    include_tags=["security"],
)
```

**Text Output Example (`style="merged"`):**
```
interface Vlan2 !15 instances
  ip address 10.0.0.2 255.255.255.0 !15 instances
line vty 0 4 !145 instances
  transport input ssh !145 instances
  exec-timeout 5 0 !145 instances
ntp server 10.2.2.2 !132 instances
```

### Export to JSON

```python
reporter.to_json("remediation_report.json")

# With tag filters
reporter.to_json(
    "ntp_report.json",
    include_tags=["ntp"],
)

# Custom indentation
reporter.to_json("remediation_report.json", indent=4)
```

**JSON Output Structure:**
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
      "device_ids": [1, 2, 3, ...],
      "tags": ["security", "access", "critical"],
      "comments": ["Update VTY settings"],
      "instances": [
        {
          "id": 1,
          "tags": ["security"],
          "comments": ["Update VTY settings"]
        },
        ...
      ]
    }
  ]
}
```

### Export to CSV

```python
reporter.to_csv("remediation_report.csv")

# With tag filters
reporter.to_csv(
    "security_report.csv",
    include_tags=["security"],
)
```

**CSV Output:**
```csv
line,device_count,percentage,tags,comments,device_ids
"line vty 0 4",145,96.7,"security,access,critical","Update VTY settings","1,2,3,..."
"ntp server 10.2.2.2",132,88.0,"ntp,safe","Update NTP server","1,2,3,..."
```

### Export to Markdown

```python
reporter.to_markdown("remediation_report.md", top_n=20)

# With tag filters
reporter.to_markdown(
    "security_report.md",
    include_tags=["security"],
    top_n=10,
)
```

**Markdown Output:**
```markdown
# Remediation Report

## Summary

- **Total Devices**: 150
- **Unique Changes**: 87

## Top 20 Changes by Impact

| # | Configuration Line | Device Count | Percentage |
|---|-------------------|--------------|------------|
| 1 | `line vty 0 4` | 145 | 96.7% |
| 2 | `ntp server 10.2.2.2` | 132 | 88.0% |
...

## Changes by Tag

| Tag | Count |
|-----|-------|
| security | 45 |
| ntp | 32 |
```

### Export All Formats

```python
# Export all formats at once
reporter.export_all(
    output_dir="reports/",
    formats=["json", "csv", "markdown", "text"],
)

# With tag filters
reporter.export_all(
    output_dir="reports/security/",
    formats=["json", "csv", "markdown"],
    include_tags=["security"],
)
```

This creates:
- `reports/remediation_report.json`
- `reports/remediation_report.csv`
- `reports/remediation_report.md`
- `reports/remediation_report.txt`

## Real-World Use Cases

### Use Case 1: Impact Analysis

**Question**: *"How many devices will be affected if I push NTP server changes?"*

```python
from hier_config import RemediationReporter

reporter = RemediationReporter.from_remediations(all_device_remediations)

ntp_count = reporter.get_device_count("ntp server 10.2.2.2")
print(f"NTP change will affect {ntp_count} devices")

# Get the specific device IDs
detail = reporter.get_change_detail("ntp server 10.2.2.2")
print(f"Affected device IDs: {sorted(detail.device_ids)}")
```

### Use Case 2: Risk-Based Change Management

**Scenario**: Separate changes into risk categories

```python
from hier_config import TagRule, MatchRule

# Define risk-based tagging
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

# Generate separate change windows
reporter.to_text("low_risk_changes.txt", include_tags=["low-risk"])
reporter.to_text("high_risk_changes.txt", include_tags=["high-risk"])
reporter.to_text("medium_risk_changes.txt", include_tags=["medium-risk"])

# Get statistics
low_risk_changes = reporter.get_all_changes(include_tags=["low-risk"])
high_risk_changes = reporter.get_all_changes(include_tags=["high-risk"])

print(f"Low risk: {len(low_risk_changes)} change types")
print(f"High risk: {len(high_risk_changes)} change types")
```

### Use Case 3: Compliance Reporting

**Scenario**: Generate audit reports for security compliance

```python
# Tag security-related changes
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

# Generate compliance report
security_summary = reporter.summary_by_tags(["security"])

print("Security Compliance Remediation Report")
print("=" * 50)
for tag, stats in security_summary.items():
    print(f"\nCategory: {tag}")
    print(f"Devices requiring changes: {stats['device_count']}")
    print(f"Total change items: {stats['change_count']}")

# Export for audit trail
reporter.to_markdown(
    "security_compliance_report.md",
    include_tags=["security"],
)
```

### Use Case 4: Prioritization by Scope

**Scenario**: Focus on changes affecting the most devices

```python
# Get the top 10 most widespread changes
top_changes = reporter.get_top_changes(10)

print("Top 10 Changes by Device Count")
print("=" * 60)
for i, (change, count) in enumerate(top_changes, 1):
    percentage = (count / reporter.device_count) * 100
    print(f"{i}. {change.text}")
    print(f"   Affects {count} devices ({percentage:.1f}%)")
    print()

# Focus on changes affecting >80% of devices
high_impact = reporter.get_changes_by_threshold(
    min_devices=int(reporter.device_count * 0.8)
)

print(f"\nFound {len(high_impact)} changes affecting >80% of devices")
```

### Use Case 5: Category-Based Rollout

**Scenario**: Deploy changes in stages by category

```python
# Tag by functional category
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

# Generate phase-specific remediations
for phase in ["phase-1", "phase-2", "phase-3"]:
    reporter.export_all(
        output_dir=f"rollout/{phase}/",
        formats=["json", "csv", "text"],
        include_tags=[phase],
    )

    # Get statistics for each phase
    phase_changes = reporter.get_all_changes(include_tags=[phase])
    print(f"{phase}: {len(phase_changes)} change types")
```

### Use Case 6: Exception Reporting

**Scenario**: Find devices with unique or uncommon changes

```python
# Find changes affecting only 1-3 devices (potential exceptions)
exceptions = reporter.get_changes_by_threshold(
    min_devices=1,
    max_devices=3,
)

print(f"Found {len(exceptions)} exceptional changes")
print("\nUncommon Configuration Changes:")
print("=" * 60)

for change in exceptions:
    detail = reporter.get_change_detail(change.text)
    print(f"\n{change.text}")
    print(f"  Affects {detail.device_count} device(s): {sorted(detail.device_ids)}")
    if detail.comments:
        print(f"  Comments: {', '.join(detail.comments)}")
```

## Best Practices

### 1. Apply Tags for Better Organization

Always apply tags to enable flexible filtering and reporting:

```python
tag_rules = [
    # By function
    TagRule(
        match_rules=(MatchRule(startswith="ntp"),),
        apply_tags=frozenset({"ntp", "infrastructure"}),
    ),
    # By risk
    TagRule(
        match_rules=(MatchRule(contains="password"),),
        apply_tags=frozenset({"critical", "security"}),
    ),
    # By deployment phase
    TagRule(
        match_rules=(MatchRule(startswith="logging"),),
        apply_tags=frozenset({"phase-1"}),
    ),
]

reporter.apply_tag_rules(tag_rules)
```

### 2. Use Multiple Report Formats

Different stakeholders need different formats:

```python
# Technical team: detailed JSON
reporter.to_json("detailed_report.json")

# Management: summary markdown
reporter.to_markdown("executive_summary.md", top_n=10)

# Analysis: CSV for Excel
reporter.to_csv("analysis_data.csv")

# Implementation: text config
reporter.to_text("deployment_config.txt", style="without_comments")
```

### 3. Validate Scope Before Deployment

Always check impact before pushing changes:

```python
# Check high-impact changes
high_impact = reporter.get_changes_by_threshold(min_devices=100)

if high_impact:
    print("WARNING: The following changes affect >100 devices:")
    for change in high_impact:
        print(f"  - {change.text}: {len(change.instances)} devices")

    # Require manual approval
    approval = input("Proceed? (yes/no): ")
    if approval.lower() != "yes":
        print("Deployment cancelled")
        exit(1)
```

### 4. Track Changes Over Time

Export reports with timestamps for historical tracking:

```python
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = f"reports/{timestamp}/"

reporter.export_all(output_dir, formats=["json", "markdown", "csv"])
print(f"Reports saved to {output_dir}")
```

### 5. Combine with Existing Workflows

Integrate reporting into your existing remediation workflow:

```python
from hier_config import WorkflowRemediation, RemediationReporter

# Generate remediations
remediations = []
for device in inventory:
    running = get_device_config(device)
    generated = generate_desired_config(device)

    wfr = WorkflowRemediation(running, generated)
    remediations.append(wfr.remediation_config)

# Create reports
reporter = RemediationReporter.from_remediations(remediations)

# Apply your organization's tag rules
reporter.apply_tag_rules(company_tag_rules)

# Generate required reports
reporter.export_all("reports/current/")

# Print summary for quick review
print(reporter.summary_text())
```

## API Reference

### RemediationReporter Class

#### Constructor

```python
reporter = RemediationReporter()
```

#### Class Methods

- `from_remediations(remediations)` - Create from iterable of HConfig objects
- `from_merged_config(merged_config)` - Create from pre-merged HConfig

#### Instance Methods

**Adding Data:**
- `add_remediation(remediation)` - Add single remediation
- `add_remediations(remediations)` - Add multiple remediations

**Tagging:**
- `apply_tag_rules(tag_rules)` - Apply TagRule sequence

**Querying:**
- `get_all_changes(include_tags=[], exclude_tags=[])` - Get all changes
- `get_change_detail(line, tag=None)` - Get detailed info about a line
- `get_device_count(line, tag=None)` - Count devices needing a change
- `get_changes_by_threshold(min_devices=0, max_devices=None, ...)` - Filter by impact
- `get_top_changes(n=10, ...)` - Get N most common changes
- `get_changes_matching(pattern, ...)` - Get changes matching regex

**Analysis:**
- `summary()` - Get ReportSummary object
- `summary_text(top_n=10)` - Get human-readable summary
- `summary_by_tags(tags=None)` - Get breakdown by tags
- `group_by_parent()` - Group changes by parent line
- `get_impact_distribution(bins=...)` - Get distribution of changes by impact
- `get_tag_distribution()` - Get tag occurrence counts

**Exporting:**
- `to_text(file_path, style="merged", ...)` - Export to text file
- `to_json(file_path, indent=2, ...)` - Export to JSON
- `to_csv(file_path, ...)` - Export to CSV
- `to_markdown(file_path, top_n=20, ...)` - Export to Markdown
- `export_all(output_dir, formats=[], ...)` - Export all formats

#### Properties

- `merged_config` - The merged HConfig object
- `device_count` - Number of unique devices

### Models

#### ReportSummary

```python
class ReportSummary:
    total_devices: int
    total_unique_changes: int
    most_common_changes: tuple[tuple[str, int], ...]
    changes_by_tag: dict[str, int]
```

#### ChangeDetail

```python
class ChangeDetail:
    line: str
    full_path: tuple[str, ...]
    device_count: int
    device_ids: frozenset[int]
    tags: frozenset[str]
    comments: frozenset[str]
    instances: tuple[Instance, ...]
    children: tuple[ChangeDetail, ...]
```

## Troubleshooting

### Issue: No changes showing up

```python
# Check if remediations were added
print(f"Device count: {reporter.device_count}")

# Check if remediation configs are empty
for i, remediation in enumerate(remediations):
    change_count = len(tuple(remediation.all_children()))
    print(f"Remediation {i}: {change_count} changes")
```

### Issue: Tags not working

```python
# Verify tags were applied
all_changes = reporter.get_all_changes()
for change in all_changes[:5]:
    print(f"{change.text}: tags={change.tags}")

# Check tag distribution
print(reporter.get_tag_distribution())
```

### Issue: Device count seems wrong

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

## See Also

- [Tags](tags.md) - Learn more about tagging configuration lines
- [Custom Workflows](custom-workflows.md) - Integrate reporting into your workflows
- [Getting Started](getting-started.md) - Basic hier_config usage
