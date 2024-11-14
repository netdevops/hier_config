import pytest

from hier_config import (
    WorkflowRemediation,
    get_hconfig,
)
from hier_config.models import Platform, TagRule


@pytest.fixture(name="wfr")
def workflow_remediation(
    running_config: str, generated_config: str
) -> WorkflowRemediation:
    return WorkflowRemediation(
        running_config=get_hconfig(Platform.CISCO_IOS, running_config),
        generated_config=get_hconfig(Platform.CISCO_IOS, generated_config),
    )


def test_config_lengths(wfr: WorkflowRemediation) -> None:
    assert wfr.running_config.children
    assert wfr.generated_config.children
    assert wfr.remediation_config.children
    assert wfr.rollback_config.children


def test_apply_tags(
    wfr: WorkflowRemediation, tag_rules_ios: tuple[TagRule, ...]
) -> None:
    wfr.apply_remediation_tag_rules(tag_rules_ios)
    assert len(wfr.remediation_config.tags) > 0


def test_remediation_config_filtered_text(
    wfr: WorkflowRemediation,
    tag_rules_ios: tuple[TagRule, ...],
    remediation_config_with_safe_tags: str,
    remediation_config_without_tags: str,
) -> None:
    wfr.apply_remediation_tag_rules(tag_rules_ios)

    rem1 = wfr.remediation_config_filtered_text(set(), set())
    rem2 = wfr.remediation_config_filtered_text({"safe"}, set())

    assert rem1 != rem2
    assert rem1 == remediation_config_without_tags
    assert rem2 == remediation_config_with_safe_tags
