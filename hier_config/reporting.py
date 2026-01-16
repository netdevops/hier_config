"""Remediation reporting functionality for hier_config.

This module provides tools for aggregating and analyzing remediation
configurations from multiple network devices.
"""

import csv
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from hier_config.child import HConfigChild
from hier_config.models import ChangeDetail, ReportSummary, TagRule
from hier_config.root import HConfig


class RemediationReporter:  # noqa: PLR0904
    """A reporting tool for aggregating and analyzing remediation configurations.

    This class provides methods to merge multiple device remediations,
    generate statistics, filter by tags, and export reports in various formats.

    Example:
        ```python
        from hier_config import RemediationReporter

        reporter = RemediationReporter()
        reporter.add_remediations([device1_remediation, device2_remediation])

        # Get summary statistics
        summary = reporter.summary()

        # Export reports
        reporter.to_json("report.json")
        reporter.to_csv("report.csv")
        ```

    """

    def __init__(self) -> None:
        """Initialize a new RemediationReporter."""
        self._merged_config: HConfig | None = None
        self._device_count: int = 0
        self._device_ids: set[int] = set()

    @property
    def merged_config(self) -> HConfig:
        """Get the merged configuration.

        Raises:
            ValueError: If no remediations have been added yet.

        """
        if self._merged_config is None:
            msg = "No remediations have been added yet"
            raise ValueError(msg)
        return self._merged_config

    @property
    def device_count(self) -> int:
        """Get the number of unique devices that have been added."""
        return self._device_count

    def add_remediation(self, remediation: HConfig) -> None:
        """Add a single remediation configuration to the reporter.

        Args:
            remediation: An HConfig object representing a device remediation.

        """
        device_id = id(remediation)
        if device_id not in self._device_ids:
            self._device_ids.add(device_id)
            self._device_count += 1

        if self._merged_config is None:
            # Create a new empty HConfig with the same driver
            self._merged_config = HConfig(remediation.driver)

        self._merged_config.merge(remediation)

    def add_remediations(self, remediations: Iterable[HConfig]) -> None:
        """Add multiple remediation configurations to the reporter.

        Args:
            remediations: An iterable of HConfig objects.

        """
        for remediation in remediations:
            self.add_remediation(remediation)

    @classmethod
    def from_remediations(
        cls,
        remediations: Iterable[HConfig],
    ) -> "RemediationReporter":
        """Create a RemediationReporter from an iterable of remediations.

        Args:
            remediations: An iterable of HConfig objects.

        Returns:
            A new RemediationReporter instance with all remediations merged.

        Example:
            ```python
            reporter = RemediationReporter.from_remediations([
                device1_remediation,
                device2_remediation,
            ])
            ```

        """
        reporter = cls()
        reporter.add_remediations(remediations)
        return reporter

    @classmethod
    def from_merged_config(cls, merged_config: HConfig) -> "RemediationReporter":
        """Create a RemediationReporter from an already merged configuration.

        Args:
            merged_config: An HConfig object with merged remediations.

        Returns:
            A new RemediationReporter instance.

        Example:
            ```python
            merged = get_hconfig(Platform.CISCO_IOS)
            merged.merge([device1, device2])
            reporter = RemediationReporter.from_merged_config(merged)
            ```

        """
        reporter = cls()
        reporter._merged_config = merged_config

        # Count unique device IDs from instances
        device_ids = set()
        for child in merged_config.all_children_sorted():
            device_ids.update(instance.id for instance in child.instances)

        reporter._device_ids = device_ids
        reporter._device_count = len(device_ids)
        return reporter

    def apply_tag_rules(self, tag_rules: Sequence[TagRule]) -> None:
        """Apply tag rules to the merged configuration.

        Args:
            tag_rules: A sequence of TagRule objects to apply.

        Example:
            ```python
            from hier_config import MatchRule, TagRule

            tag_rules = [
                TagRule(
                    match_rules=(MatchRule(startswith="ntp"),),
                    apply_tags=frozenset({"ntp", "safe"}),
                )
            ]
            reporter.apply_tag_rules(tag_rules)
            ```

        """
        for tag_rule in tag_rules:
            for child in self.merged_config.get_children_deep(tag_rule.match_rules):
                child.tags_add(tag_rule.apply_tags)

    def get_all_changes(
        self,
        *,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> tuple[HConfigChild, ...]:
        """Get all configuration changes, optionally filtered by tags.

        Args:
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.

        Returns:
            A tuple of HConfigChild objects representing changes.

        """
        if include_tags or exclude_tags:
            return tuple(
                self.merged_config.all_children_sorted_by_tags(
                    include_tags,
                    exclude_tags,
                )
            )
        return tuple(self.merged_config.all_children_sorted())

    def get_change_detail(
        self,
        line: str,
        *,
        tag: str | None = None,
    ) -> ChangeDetail | None:
        """Get detailed information about a specific configuration line.

        Args:
            line: The configuration line to search for.
            tag: Optional tag to filter instances.

        Returns:
            A ChangeDetail object or None if the line is not found.

        Example:
            ```python
            detail = reporter.get_change_detail("line vty 0 4")
            print(f"Affects {detail.device_count} devices")
            ```

        """
        child = self.merged_config.get_child(equals=line)
        if child is None:
            return None

        return self._build_change_detail(child, tag=tag)

    def _build_change_detail(
        self,
        child: HConfigChild,
        *,
        tag: str | None = None,
    ) -> ChangeDetail:
        """Build a ChangeDetail object from an HConfigChild.

        Args:
            child: The HConfigChild to build details from.
            tag: Optional tag to filter instances.

        Returns:
            A ChangeDetail object with aggregated information.

        """
        # Filter instances by tag if specified
        relevant_instances = tuple(
            instance
            for instance in child.instances
            if tag is None or tag in instance.tags
        )

        # Aggregate data
        device_ids = frozenset(instance.id for instance in relevant_instances)
        all_tags = frozenset(
            tag_item
            for instance in relevant_instances
            for tag_item in instance.tags
        )
        all_comments = frozenset(
            comment
            for instance in relevant_instances
            for comment in instance.comments
        )

        # Build path
        path_parts = []
        current: HConfigChild | HConfig | None = child
        while current is not None and hasattr(current, "text"):
            if isinstance(current, HConfigChild):
                path_parts.insert(0, current.text)
            current = getattr(current, "parent", None)

        # Get children details
        children_details = tuple(
            self._build_change_detail(grandchild, tag=tag)
            for grandchild in child.children
        )

        return ChangeDetail(
            line=child.text,
            full_path=tuple(path_parts),
            device_count=len(device_ids),
            device_ids=device_ids,
            tags=all_tags,
            comments=all_comments,
            instances=relevant_instances,
            children=children_details,
        )

    def get_device_count(self, line: str, *, tag: str | None = None) -> int:
        """Get the number of devices that need a specific configuration line.

        Args:
            line: The configuration line to search for.
            tag: Optional tag to filter instances.

        Returns:
            The number of devices requiring this change.

        Example:
            ```python
            count = reporter.get_device_count("line vty 0 4")
            print(f"{count} devices need this change")
            ```

        """
        detail = self.get_change_detail(line, tag=tag)
        return detail.device_count if detail else 0

    def get_changes_by_threshold(
        self,
        *,
        min_devices: int = 0,
        max_devices: int | None = None,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> tuple[HConfigChild, ...]:
        """Get changes affecting a certain number of devices.

        Args:
            min_devices: Minimum number of devices (inclusive).
            max_devices: Maximum number of devices (inclusive), or None for unlimited.
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.

        Returns:
            A tuple of HConfigChild objects matching the criteria.

        Example:
            ```python
            # Get high-impact changes affecting 50+ devices
            high_impact = reporter.get_changes_by_threshold(min_devices=50)

            # Get isolated changes affecting 1-5 devices
            isolated = reporter.get_changes_by_threshold(
                min_devices=1,
                max_devices=5,
            )
            ```

        """
        all_changes = self.get_all_changes(
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        filtered_changes = []
        for child in all_changes:
            instance_count = len(child.instances)
            if instance_count >= min_devices:
                if max_devices is None or instance_count <= max_devices:
                    filtered_changes.append(child)

        return tuple(filtered_changes)

    def get_top_changes(
        self,
        n: int = 10,
        *,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> tuple[tuple[HConfigChild, int], ...]:
        """Get the top N most common changes across devices.

        Args:
            n: Number of top changes to return.
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.

        Returns:
            A tuple of (HConfigChild, count) pairs, sorted by count descending.

        Example:
            ```python
            top_10 = reporter.get_top_changes(10)
            for child, count in top_10:
                print(f"{child.text}: {count} devices")
            ```

        """
        all_changes = self.get_all_changes(
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        # Create list of (child, instance_count) pairs
        changes_with_counts = [
            (child, len(child.instances)) for child in all_changes
        ]

        # Sort by count descending and take top N
        changes_with_counts.sort(key=lambda x: x[1], reverse=True)
        return tuple(changes_with_counts[:n])

    def get_changes_matching(
        self,
        pattern: str,
        *,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> tuple[HConfigChild, ...]:
        """Get changes matching a regex pattern.

        Args:
            pattern: A regex pattern to match against configuration lines.
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.

        Returns:
            A tuple of HConfigChild objects matching the pattern.

        Example:
            ```python
            # Get all VLAN interface changes
            vlan_changes = reporter.get_changes_matching(r"interface Vlan\\d+")
            ```

        """
        all_changes = self.get_all_changes(
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        regex = re.compile(pattern)
        return tuple(child for child in all_changes if regex.search(child.text))

    def summary(self) -> ReportSummary:
        """Generate a summary of all remediations.

        Returns:
            A ReportSummary object with aggregate statistics.

        Example:
            ```python
            summary = reporter.summary()
            print(f"Total devices: {summary.total_devices}")
            print(f"Unique changes: {summary.total_unique_changes}")
            ```

        """
        all_changes = self.get_all_changes()

        # Get most common changes
        changes_with_counts = [
            (child.text, len(child.instances)) for child in all_changes
        ]
        changes_with_counts.sort(key=lambda x: x[1], reverse=True)
        most_common = tuple(changes_with_counts[:10])

        # Count changes by tag
        tag_counter: Counter[str] = Counter()
        for child in all_changes:
            for tag in child.tags:
                tag_counter[tag] += 1

        return ReportSummary(
            total_devices=self.device_count,
            total_unique_changes=len(all_changes),
            most_common_changes=most_common,
            changes_by_tag=dict(tag_counter),
        )

    def summary_by_tags(
        self,
        tags: Iterable[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Generate a summary breakdown by tags.

        Args:
            tags: Specific tags to include, or None for all tags.

        Returns:
            A dictionary mapping tag names to their statistics.

        Example:
            ```python
            tag_summary = reporter.summary_by_tags(["security", "ntp"])
            for tag, stats in tag_summary.items():
                print(f"{tag}: {stats['device_count']} devices")
            ```

        """
        all_changes = self.get_all_changes()

        # Collect all tags if not specified
        if tags is None:
            all_tags = {tag for child in all_changes for tag in child.tags}
        else:
            all_tags = set(tags)

        result = {}
        for tag in all_tags:
            tagged_changes = self.get_all_changes(include_tags=[tag])

            # Count unique devices for this tag
            device_ids = {
                instance.id
                for child in tagged_changes
                for instance in child.instances
                if tag in instance.tags
            }

            result[tag] = {
                "device_count": len(device_ids),
                "change_count": len(tagged_changes),
                "changes": [child.text for child in tagged_changes],
            }

        return result

    def summary_text(self, *, top_n: int = 10) -> str:
        """Generate a human-readable text summary.

        Args:
            top_n: Number of top changes to include in the summary.

        Returns:
            A formatted string with summary statistics.

        Example:
            ```python
            print(reporter.summary_text())
            ```

        """
        summary = self.summary()
        lines = [
            "Remediation Summary",
            "=" * 50,
            f"Total devices: {summary.total_devices}",
            f"Unique changes: {summary.total_unique_changes}",
            "",
            f"Top {min(top_n, len(summary.most_common_changes))} Most Common Changes:",
            "-" * 50,
        ]

        for i, (line, count) in enumerate(summary.most_common_changes[:top_n], 1):
            percentage = (
                (count / summary.total_devices * 100) if summary.total_devices else 0
            )
            lines.append(f"{i}. {line}")
            lines.append(f"   {count} devices ({percentage:.1f}%)")

        if summary.changes_by_tag:
            lines.extend(["", "Changes by Tag:", "-" * 50])
            for tag, count in sorted(
                summary.changes_by_tag.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"  {tag}: {count} changes")

        return "\n".join(lines)

    def group_by_parent(self) -> dict[str, list[HConfigChild]]:
        """Group all changes by their parent configuration line.

        Returns:
            A dictionary mapping parent lines to their children.

        Example:
            ```python
            grouped = reporter.group_by_parent()
            for parent, children in grouped.items():
                print(f"{parent}: {len(children)} changes")
            ```

        """
        groups: dict[str, list[HConfigChild]] = defaultdict(list)

        for child in self.get_all_changes():
            if child.parent and hasattr(child.parent, "text"):
                parent_text = child.parent.text
            else:
                parent_text = "root"
            groups[parent_text].append(child)

        return dict(groups)

    def get_impact_distribution(
        self,
        bins: Sequence[int] = (1, 10, 25, 50, 100),
    ) -> dict[str, int]:
        """Get the distribution of changes by device impact.

        Args:
            bins: Boundaries for impact ranges.

        Returns:
            A dictionary with range labels as keys and counts as values.

        Example:
            ```python
            dist = reporter.get_impact_distribution()
            # {'1-10': 15, '10-25': 8, '25-50': 5, '50-100': 3, '100+': 2}
            ```

        """
        all_changes = self.get_all_changes()
        distribution: dict[str, int] = defaultdict(int)

        for child in all_changes:
            instance_count = len(child.instances)

            # Find the appropriate bin
            for i, threshold in enumerate(bins):
                if instance_count < threshold:
                    if i == 0:
                        label = f"1-{threshold}"
                    else:
                        label = f"{bins[i - 1]}-{threshold}"
                    distribution[label] += 1
                    break
            else:
                # Higher than all bins
                distribution[f"{bins[-1]}+"] += 1

        return dict(distribution)

    def get_tag_distribution(self) -> dict[str, int]:
        """Get the distribution of tags across all changes.

        Returns:
            A dictionary mapping tag names to their occurrence count.

        Example:
            ```python
            tags = reporter.get_tag_distribution()
            # {'security': 45, 'ntp': 32, 'snmp': 28}
            ```

        """
        tag_counter: Counter[str] = Counter()

        for child in self.get_all_changes():
            for tag in child.tags:
                tag_counter[tag] += 1

        return dict(tag_counter)

    def to_text(
        self,
        file_path: str | Path,
        *,
        style: str = "merged",
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> None:
        """Export remediation configuration to a text file.

        Args:
            file_path: Path to the output file.
            style: Text style ('merged', 'with_comments', or 'without_comments').
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.

        Example:
            ```python
            reporter.to_text("remediation.txt", style="merged")
            ```

        """
        changes = self.get_all_changes(
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        lines = [child.cisco_style_text(style=style) for child in changes]

        output_path = Path(file_path)
        output_path.write_text("\n".join(lines), encoding="utf-8")

    def to_json(
        self,
        file_path: str | Path,
        *,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
        indent: int = 2,
    ) -> None:
        """Export remediation data to a JSON file.

        Args:
            file_path: Path to the output file.
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.
            indent: JSON indentation level.

        Example:
            ```python
            reporter.to_json("remediation.json")
            ```

        """
        changes = self.get_all_changes(
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        data = {
            "summary": {
                "total_devices": self.device_count,
                "total_unique_changes": len(changes),
            },
            "changes": [
                {
                    "line": child.text,
                    "device_count": len(child.instances),
                    "device_ids": sorted(
                        instance.id for instance in child.instances
                    ),
                    "tags": sorted(child.tags),
                    "comments": sorted(child.comments),
                    "instances": [
                        {
                            "id": instance.id,
                            "tags": sorted(instance.tags),
                            "comments": sorted(instance.comments),
                        }
                        for instance in child.instances
                    ],
                }
                for child in changes
            ],
        }

        output_path = Path(file_path)
        output_path.write_text(
            json.dumps(data, indent=indent),
            encoding="utf-8",
        )

    def to_csv(
        self,
        file_path: str | Path,
        *,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> None:
        """Export remediation data to a CSV file.

        Args:
            file_path: Path to the output file.
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.

        Example:
            ```python
            reporter.to_csv("remediation.csv")
            ```

        """
        changes = self.get_all_changes(
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        output_path = Path(file_path)
        with output_path.open("w", encoding="utf-8", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "line",
                    "device_count",
                    "percentage",
                    "tags",
                    "comments",
                    "device_ids",
                ]
            )

            for child in changes:
                device_count = len(child.instances)
                percentage = (
                    (device_count / self.device_count * 100) if self.device_count else 0
                )
                tags = ",".join(sorted(child.tags))
                comments = " | ".join(sorted(child.comments))
                device_ids = ",".join(
                    str(instance.id) for instance in child.instances
                )

                writer.writerow(
                    [
                        child.text,
                        device_count,
                        f"{percentage:.1f}",
                        tags,
                        comments,
                        device_ids,
                    ]
                )

    def to_markdown(
        self,
        file_path: str | Path,
        *,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
        top_n: int = 20,
    ) -> None:
        """Export remediation report to a Markdown file.

        Args:
            file_path: Path to the output file.
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.
            top_n: Number of top changes to include in detail.

        Example:
            ```python
            reporter.to_markdown("remediation.md", top_n=15)
            ```

        """
        changes = self.get_all_changes(
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        lines = [
            "# Remediation Report",
            "",
            "## Summary",
            "",
            f"- **Total Devices**: {self.device_count}",
            f"- **Unique Changes**: {len(changes)}",
            "",
            f"## Top {min(top_n, len(changes))} Changes by Impact",
            "",
            "| # | Configuration Line | Device Count | Percentage |",
            "|---|-------------------|--------------|------------|",
        ]

        # Sort by instance count
        sorted_changes = sorted(
            changes,
            key=lambda c: len(c.instances),
            reverse=True,
        )

        for i, child in enumerate(sorted_changes[:top_n], 1):
            device_count = len(child.instances)
            percentage = (
                (device_count / self.device_count * 100) if self.device_count else 0
            )
            lines.append(
                f"| {i} | `{child.text}` | {device_count} | {percentage:.1f}% |"
            )

        # Add tag summary if tags exist
        tag_dist = self.get_tag_distribution()
        if tag_dist:
            lines.extend(
                [
                    "",
                    "## Changes by Tag",
                    "",
                    "| Tag | Count |",
                    "|-----|-------|",
                ]
            )
            for tag, count in sorted(
                tag_dist.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"| {tag} | {count} |")

        output_path = Path(file_path)
        output_path.write_text("\n".join(lines), encoding="utf-8")

    def export_all(
        self,
        output_dir: str | Path,
        *,
        formats: Iterable[str] = ("json", "csv", "markdown", "text"),
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> None:
        """Export reports in multiple formats to a directory.

        Args:
            output_dir: Directory to write reports to.
            formats: Formats to export ('json', 'csv', 'markdown', 'text').
            include_tags: Only include changes with these tags.
            exclude_tags: Exclude changes with these tags.

        Example:
            ```python
            reporter.export_all(
                "reports/",
                formats=["json", "csv", "markdown"],
            )
            ```

        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        format_methods = {
            "json": (self.to_json, "remediation_report.json"),
            "csv": (self.to_csv, "remediation_report.csv"),
            "markdown": (self.to_markdown, "remediation_report.md"),
            "text": (self.to_text, "remediation_report.txt"),
        }

        for fmt in formats:
            if fmt in format_methods:
                method, filename = format_methods[fmt]
                file_path = output_path / filename
                method(
                    file_path,
                    include_tags=include_tags,
                    exclude_tags=exclude_tags,
                )
