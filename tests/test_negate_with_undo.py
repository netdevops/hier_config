from hier_config import Host
from hier_config.platforms.model import Platform


def test_merge_with_undo() -> None:
    running_config = "test_for_undo\nundo test_for_redo"
    generated_config = "undo test_for_undo\ntest_for_redo"
    remediation = "undo test_for_undo\ntest_for_redo"
    host = Host(Platform.HP_COMWARE5)
    host.load_running_config(running_config)
    host.load_generated_config(generated_config)
    host.remediation_config()
    assert remediation == str(host.remediation_config())
