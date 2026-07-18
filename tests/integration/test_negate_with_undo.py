from hier_config import HConfig, WorkflowRemediation
from hier_config.models import Platform


def test_merge_with_undo() -> None:
    platform = Platform.HP_COMWARE5
    running_config = HConfig.from_lines(
        platform, "test_for_undo\nundo test_for_redo"
    )
    generated_config = HConfig.from_lines(
        platform, "undo test_for_undo\ntest_for_redo"
    )
    expected_remediation_config = HConfig.from_lines(
        platform, "undo test_for_undo\ntest_for_redo"
    )
    workflow_remediation = WorkflowRemediation(running_config, generated_config)
    remediation_config = workflow_remediation.remediation_config
    assert remediation_config == expected_remediation_config
