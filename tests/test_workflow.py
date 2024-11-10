from hier_config import (
    WorkflowRemediation,
    get_hconfig_from_simple,
)
from hier_config.model import Platform, TagRule


class TestWorkflowRemediation:
    def setup_method(self, running_config: str, generated_config: str) -> None:
        self.remediation_workflow = WorkflowRemediation(
            running_config=get_hconfig_from_simple(Platform.CISCO_IOS, running_config),
            generated_config=get_hconfig_from_simple(
                Platform.CISCO_IOS, generated_config
            ),
        )

    def test_config_lengths(self) -> None:
        assert self.remediation_workflow.running_config.children
        assert self.remediation_workflow.generated_config.children
        assert self.remediation_workflow.remediation_config.children
        assert self.remediation_workflow.rollback_config.children

    def test_apply_tags(self, tag_rules_ios: tuple[TagRule, ...]) -> None:
        self.remediation_workflow.apply_remediation_tag_rules(tag_rules_ios)
        assert len(self.remediation_workflow.remediation_config.tags) > 0

    def test_remediation_config_filtered_text(
        self,
        tag_rules_ios: tuple[TagRule, ...],
        remediation_config_with_safe_tags: str,
        remediation_config_without_tags: str,
    ) -> None:
        self.remediation_workflow.apply_remediation_tag_rules(tag_rules_ios)

        rem1 = self.remediation_workflow.remediation_config_filtered_text(set(), set())
        rem2 = self.remediation_workflow.remediation_config_filtered_text(
            {"safe"}, set()
        )

        assert rem1 != rem2
        assert rem1 == remediation_config_without_tags
        assert rem2 == remediation_config_with_safe_tags
