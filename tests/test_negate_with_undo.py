from hier_config import WorkflowRemediation, get_hconfig_fast_load
from hier_config.model import Platform


def test_merge_with_undo() -> None:
    platform = Platform.HP_COMWARE5
    running_config = get_hconfig_fast_load(
        platform, "test_for_undo\nundo test_for_redo"
    )
    generated_config = get_hconfig_fast_load(
        platform, "undo test_for_undo\ntest_for_redo"
    )
    expected_remediation_config = get_hconfig_fast_load(
        platform, "undo test_for_undo\ntest_for_redo"
    )
    workflow_remediation = WorkflowRemediation(running_config, generated_config)
    remediation_config = workflow_remediation.remediation_config
    assert remediation_config == expected_remediation_config
