from collections.abc import Iterable
from logging import getLogger

from .model import TagRule
from .root import HConfig

logger = getLogger(__name__)


class WorkflowRemediation:
    """A host object is a convenient way to loading host inventory
    items into a single object.

    The default is to load "hostname", "os", and "options" to the host object,
    however, it can easily be extended for developer needs.

    .. code:: python

        import yaml
        from hier_config.host import Host

        options = yaml.load(open("./tests/fixtures/options_ios.yml"), loader=yaml.SafeLoader())
        host = Host("example.rtr", "ios", options)

        # Example of loading running config and generated configs into a host object
        host.load_running_config_from_file("./tests/files/running_config.conf)
        host.load_generated_config_from_file("./tests/files/generated_config.conf)

        # Example of creating a remediation config without a tag targeting specific config
        host.remediation_config()

        # Example of creating a remediation config with a tag ("safe") targeting a specific config.
        host.remediation_config_filtered_text({"safe"}, set()})
    """

    def __init__(
        self,
        running_config: HConfig,
        generated_config: HConfig,
    ) -> None:
        self.running_config = running_config
        self.generated_config = generated_config

        if running_config.driver != generated_config.driver:
            message = "The running and generated configs must use the same driver."
            raise ValueError(message)

        self._remediation_config: HConfig | None = None
        self._rollback_config: HConfig | None = None

    @property
    def remediation_config(self) -> HConfig:
        """Build the remediation config by comparing the running and generated configs."""
        if self._remediation_config:
            return self._remediation_config

        remediation_config = self.running_config.config_to_get_to(
            self.generated_config, HConfig(self.running_config.driver)
        ).set_order_weight()

        self._remediation_config = remediation_config

        return self._remediation_config

    @property
    def rollback_config(self) -> HConfig:
        """Build the rollback config by comparing the generated and running configs."""
        if self._rollback_config:
            return self._rollback_config

        rollback_config = self.generated_config.config_to_get_to(
            self.running_config, HConfig(self.running_config.driver)
        ).set_order_weight()

        self._rollback_config = rollback_config

        return rollback_config

    def apply_remediation_tag_rules(self, tag_rules: tuple[TagRule, ...]) -> None:
        for tag_rule in tag_rules:
            for child in self.remediation_config.get_children_deep(
                tag_rule.match_rules
            ):
                child.tags_add(tag_rule.apply_tags)

    def remediation_config_filtered_text(
        self,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> str:
        children = (
            self.remediation_config.all_children_sorted_by_tags(
                include_tags, exclude_tags
            )
            if include_tags or exclude_tags
            else self.remediation_config.all_children_sorted()
        )
        return "\n".join(c.cisco_style_text() for c in children)
