"""Comprehensive tests for RemediationReporter functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from hier_config import (
    HConfig,
    MatchRule,
    Platform,
    RemediationReporter,
    TagRule,
    WorkflowRemediation,
    get_hconfig,
)
from hier_config.models import ChangeDetail, ReportSummary


@pytest.fixture
def sample_remediation_1() -> tuple[HConfig, str]:
    """Create a sample remediation configuration for device 1."""
    running = get_hconfig(
        Platform.CISCO_IOS,
        """interface Vlan2
 ip address 10.0.0.1 255.255.255.0
line vty 0 4
 transport input ssh
ntp server 10.1.1.1""",
    )

    generated = get_hconfig(
        Platform.CISCO_IOS,
        """interface Vlan2
 ip address 10.0.0.2 255.255.255.0
line vty 0 4
 transport input ssh
 exec-timeout 5 0
ntp server 10.2.2.2
snmp-server community public RO""",
    )

    wfr = WorkflowRemediation(running, generated)
    return wfr.remediation_config, "device1"


@pytest.fixture
def sample_remediation_2() -> tuple[HConfig, str]:
    """Create a sample remediation configuration for device 2."""
    running = get_hconfig(
        Platform.CISCO_IOS,
        """interface Vlan3
 ip address 10.0.1.1 255.255.255.0
line vty 0 4
 transport input telnet
ntp server 10.1.1.1""",
    )

    generated = get_hconfig(
        Platform.CISCO_IOS,
        """interface Vlan3
 ip address 10.0.1.2 255.255.255.0
line vty 0 4
 transport input ssh
 exec-timeout 5 0
ntp server 10.2.2.2
snmp-server community public RO""",
    )

    wfr = WorkflowRemediation(running, generated)
    return wfr.remediation_config, "device2"


@pytest.fixture
def sample_remediation_3() -> tuple[HConfig, str]:
    """Create a sample remediation configuration for device 3."""
    running = get_hconfig(
        Platform.CISCO_IOS,
        """interface Vlan4
 ip address 10.0.2.1 255.255.255.0
ntp server 10.1.1.1""",
    )

    generated = get_hconfig(
        Platform.CISCO_IOS,
        """interface Vlan4
 ip address 10.0.2.2 255.255.255.0
ntp server 10.2.2.2""",
    )

    wfr = WorkflowRemediation(running, generated)
    return wfr.remediation_config, "device3"


def test_reporter_initialization() -> None:
    """Test RemediationReporter initialization."""
    reporter = RemediationReporter()
    assert reporter.device_count == 0

    with pytest.raises(ValueError, match="No remediations have been added"):
        _ = reporter.merged_config


def test_add_single_remediation(sample_remediation_1: tuple[HConfig, str]) -> None:
    """Test adding a single remediation."""
    remediation, _ = sample_remediation_1
    reporter = RemediationReporter()
    reporter.add_remediation(remediation)

    assert reporter.device_count == 1
    assert reporter.merged_config is not None


def test_add_multiple_remediations(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
    sample_remediation_3: tuple[HConfig, str],
) -> None:
    """Test adding multiple remediations."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2
    rem3, _ = sample_remediation_3

    reporter = RemediationReporter()
    reporter.add_remediations([rem1, rem2, rem3])

    assert reporter.device_count == 3


def test_from_remediations(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test creating reporter from remediations."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    assert reporter.device_count == 2
    assert reporter.merged_config is not None


def test_from_merged_config(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test creating reporter from already merged config."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    # Create a merged config manually
    merged = get_hconfig(Platform.CISCO_IOS)
    merged.merge([rem1, rem2])

    reporter = RemediationReporter.from_merged_config(merged)

    assert reporter.device_count == 2


def test_get_all_changes(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test getting all changes."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])
    changes = reporter.get_all_changes()

    assert len(changes) > 0
    assert all(hasattr(change, "text") for change in changes)


def test_get_device_count(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test getting device count for a specific line."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    # Both devices need "ntp server 10.2.2.2"
    ntp_count = reporter.get_device_count("ntp server 10.2.2.2")
    assert ntp_count == 2

    # Both devices need "snmp-server community public RO"
    snmp_count = reporter.get_device_count("snmp-server community public RO")
    assert snmp_count == 2


def test_get_change_detail(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test getting detailed information about a change."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    detail = reporter.get_change_detail("ntp server 10.2.2.2")

    assert detail is not None
    assert isinstance(detail, ChangeDetail)
    assert detail.line == "ntp server 10.2.2.2"
    assert detail.device_count == 2
    assert len(detail.device_ids) == 2


def test_get_change_detail_not_found(sample_remediation_1: tuple[HConfig, str]) -> None:
    """Test getting detail for a non-existent change."""
    rem1, _ = sample_remediation_1

    reporter = RemediationReporter.from_remediations([rem1])

    detail = reporter.get_change_detail("nonexistent line")
    assert detail is None


def test_get_changes_by_threshold(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
    sample_remediation_3: tuple[HConfig, str],
) -> None:
    """Test filtering changes by device threshold."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2
    rem3, _ = sample_remediation_3

    reporter = RemediationReporter.from_remediations([rem1, rem2, rem3])

    # Get changes affecting at least 2 devices
    high_impact = reporter.get_changes_by_threshold(min_devices=2)
    assert len(high_impact) > 0
    assert all(len(change.instances) >= 2 for change in high_impact)

    # Get changes affecting exactly 1 device
    low_impact = reporter.get_changes_by_threshold(min_devices=1, max_devices=1)
    assert all(len(change.instances) == 1 for change in low_impact)


def test_get_top_changes(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
    sample_remediation_3: tuple[HConfig, str],
) -> None:
    """Test getting top N most common changes."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2
    rem3, _ = sample_remediation_3

    reporter = RemediationReporter.from_remediations([rem1, rem2, rem3])

    top_5 = reporter.get_top_changes(5)

    assert len(top_5) > 0
    assert len(top_5) <= 5
    assert all(isinstance(item, tuple) for item in top_5)
    assert all(len(item) == 2 for item in top_5)

    # Verify sorted by count descending
    counts = [count for _, count in top_5]
    assert counts == sorted(counts, reverse=True)


def test_get_changes_matching(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test getting changes matching a regex pattern."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    # Find all interface-related changes
    interface_changes = reporter.get_changes_matching(r"interface Vlan\d+")
    assert len(interface_changes) > 0
    assert all("interface Vlan" in change.text for change in interface_changes)

    # Find NTP changes
    ntp_changes = reporter.get_changes_matching(r"ntp")
    assert len(ntp_changes) > 0
    assert all("ntp" in change.text.lower() for change in ntp_changes)


def test_summary(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test generating a summary."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    summary = reporter.summary()

    assert isinstance(summary, ReportSummary)
    assert summary.total_devices == 2
    assert summary.total_unique_changes > 0
    assert len(summary.most_common_changes) > 0
    assert isinstance(summary.changes_by_tag, dict)


def test_summary_text(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test generating a text summary."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    summary_text = reporter.summary_text(top_n=5)

    assert isinstance(summary_text, str)
    assert "Remediation Summary" in summary_text
    assert "Total devices: 2" in summary_text
    assert "Unique changes:" in summary_text


def test_apply_tag_rules(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test applying tag rules."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    # Create tag rules
    tag_rules = [
        TagRule(
            match_rules=(MatchRule(startswith="ntp"),),
            apply_tags=frozenset({"ntp", "time-sync"}),
        ),
        TagRule(
            match_rules=(MatchRule(startswith="snmp"),),
            apply_tags=frozenset({"snmp", "monitoring"}),
        ),
    ]

    reporter.apply_tag_rules(tag_rules)

    # Verify tags were applied
    ntp_changes = reporter.get_all_changes(include_tags=["ntp"])
    assert len(ntp_changes) > 0

    snmp_changes = reporter.get_all_changes(include_tags=["snmp"])
    assert len(snmp_changes) > 0


def test_get_all_changes_with_tag_filters(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test filtering changes by tags."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    # Apply tags
    tag_rules = [
        TagRule(
            match_rules=(MatchRule(startswith="ntp"),),
            apply_tags=frozenset({"ntp"}),
        ),
        TagRule(
            match_rules=(MatchRule(startswith="snmp"),),
            apply_tags=frozenset({"snmp"}),
        ),
    ]
    reporter.apply_tag_rules(tag_rules)

    # Get only NTP changes
    ntp_changes = reporter.get_all_changes(include_tags=["ntp"])
    assert all(change.text.startswith("ntp") for change in ntp_changes)

    # Get all except SNMP changes
    non_snmp_changes = reporter.get_all_changes(exclude_tags=["snmp"])
    assert all(not change.text.startswith("snmp") for change in non_snmp_changes)


def test_summary_by_tags(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test generating summary by tags."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    # Apply tags
    tag_rules = [
        TagRule(
            match_rules=(MatchRule(startswith="ntp"),),
            apply_tags=frozenset({"ntp"}),
        ),
    ]
    reporter.apply_tag_rules(tag_rules)

    tag_summary = reporter.summary_by_tags(["ntp"])

    assert "ntp" in tag_summary
    assert "device_count" in tag_summary["ntp"]
    assert "change_count" in tag_summary["ntp"]
    assert "changes" in tag_summary["ntp"]


def test_group_by_parent(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test grouping changes by parent."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    grouped = reporter.group_by_parent()

    assert isinstance(grouped, dict)
    assert len(grouped) > 0

    # Should have some root-level changes
    assert "root" in grouped or len(grouped) > 0


def test_get_impact_distribution(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
    sample_remediation_3: tuple[HConfig, str],
) -> None:
    """Test getting impact distribution."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2
    rem3, _ = sample_remediation_3

    reporter = RemediationReporter.from_remediations([rem1, rem2, rem3])

    distribution = reporter.get_impact_distribution()

    assert isinstance(distribution, dict)
    assert len(distribution) > 0
    assert all(isinstance(v, int) for v in distribution.values())


def test_get_tag_distribution(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test getting tag distribution."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    # Apply tags first
    tag_rules = [
        TagRule(
            match_rules=(MatchRule(startswith="ntp"),),
            apply_tags=frozenset({"ntp"}),
        ),
        TagRule(
            match_rules=(MatchRule(startswith="snmp"),),
            apply_tags=frozenset({"snmp"}),
        ),
    ]
    reporter.apply_tag_rules(tag_rules)

    tag_dist = reporter.get_tag_distribution()

    assert isinstance(tag_dist, dict)
    assert "ntp" in tag_dist or "snmp" in tag_dist


def test_to_text(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test exporting to text file."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".txt",
        delete=False,
    ) as f:
        temp_path = f.name

    try:
        reporter.to_text(temp_path, style="merged")

        # Verify file was created and has content
        output_path = Path(temp_path)
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert len(content) > 0
        assert "instance" in content.lower()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_to_json(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test exporting to JSON file."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".json",
        delete=False,
    ) as f:
        temp_path = f.name

    try:
        reporter.to_json(temp_path)

        # Verify file was created and has valid JSON
        output_path = Path(temp_path)
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        data = json.loads(content)
        assert "summary" in data
        assert "changes" in data
        assert data["summary"]["total_devices"] == 2
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_to_csv(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test exporting to CSV file."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".csv",
        delete=False,
    ) as f:
        temp_path = f.name

    try:
        reporter.to_csv(temp_path)

        # Verify file was created and has CSV headers
        output_path = Path(temp_path)
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "line,device_count,percentage,tags,comments,device_ids" in content
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_to_markdown(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test exporting to Markdown file."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".md",
        delete=False,
    ) as f:
        temp_path = f.name

    try:
        reporter.to_markdown(temp_path, top_n=5)

        # Verify file was created and has markdown formatting
        output_path = Path(temp_path)
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "# Remediation Report" in content
        assert "## Summary" in content
        assert "Total Devices" in content
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_export_all(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test exporting all formats at once."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    with tempfile.TemporaryDirectory() as temp_dir:
        reporter.export_all(
            temp_dir,
            formats=["json", "csv", "markdown", "text"],
        )

        # Verify all files were created
        output_path = Path(temp_dir)
        assert (output_path / "remediation_report.json").exists()
        assert (output_path / "remediation_report.csv").exists()
        assert (output_path / "remediation_report.md").exists()
        assert (output_path / "remediation_report.txt").exists()


def test_export_with_tag_filters(
    sample_remediation_1: tuple[HConfig, str],
    sample_remediation_2: tuple[HConfig, str],
) -> None:
    """Test exporting with tag filters."""
    rem1, _ = sample_remediation_1
    rem2, _ = sample_remediation_2

    reporter = RemediationReporter.from_remediations([rem1, rem2])

    # Apply tags
    tag_rules = [
        TagRule(
            match_rules=(MatchRule(startswith="ntp"),),
            apply_tags=frozenset({"ntp"}),
        ),
    ]
    reporter.apply_tag_rules(tag_rules)

    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".json",
        delete=False,
    ) as f:
        temp_path = f.name

    try:
        reporter.to_json(temp_path, include_tags=["ntp"])

        # Verify only NTP changes were exported
        output_path = Path(temp_path)
        content = output_path.read_text(encoding="utf-8")
        data = json.loads(content)
        changes = data["changes"]
        assert all("ntp" in change["line"].lower() for change in changes)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_empty_reporter() -> None:
    """Test reporter with no remediations."""
    reporter = RemediationReporter()

    with pytest.raises(ValueError, match="No remediations have been added"):
        reporter.summary()


def test_reporter_with_empty_remediation() -> None:
    """Test reporter with empty remediation config."""
    empty_config = get_hconfig(Platform.CISCO_IOS)

    reporter = RemediationReporter()
    reporter.add_remediation(empty_config)

    assert reporter.device_count == 1
    summary = reporter.summary()
    assert summary.total_unique_changes == 0
