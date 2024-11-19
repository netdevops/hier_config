from collections.abc import Iterable
from logging import getLogger
from typing import Optional

from .models import TagRule
from .root import HConfig

logger = getLogger(__name__)


class WorkflowRemediation:
    """Manages configuration workflows for a network device by comparing
    running and generated configurations and creating remediations to align
    the device with the intended configuration state.

    Attributes:
        running_config (HConfig): The current configuration of the network device.
        generated_config (HConfig): The target configuration for the network device.

    Raises:
        ValueError: If `running_config` and `generated_config` have different drivers.

    Example:
        Initialize `WorkflowRemediation` with the running and generated configurations
        and generate remediation and rollback configurations.

        ```python
        from hier_config import WorkflowRemediation, get_hconfig
        from hier_config.model import Platform

        # Create running and generated configurations as HConfig objects
        running_config = get_hconfig(Platform.CISCO_IOS, "running_config_text")
        generated_config = get_hconfig(Platform.CISCO_IOS, "generated_config_text")

        # Initialize WorkflowRemediation with running and generated configurations
        workflow = WorkflowRemediation(running_config, generated_config)

        # Generate the remediation configuration to apply the target configuration to the device
        remediation_config = workflow.remediation_config
        print("Remediation configuration:")
        for line in remediation_config.all_children_sorted():
            print(line.cisco_style_text())

        # Generate the rollback configuration to revert back to the running configuration
        rollback_config = workflow.rollback_config
        print("Rollback configuration:")
        for line in rollback_config.all_children_sorted():
            print(line.cisco_style_text())
        ```

    """

    def __init__(
        self,
        running_config: HConfig,
        generated_config: HConfig,
    ) -> None:
        self.running_config = running_config
        self.generated_config = generated_config

        if running_config.driver.__class__ is not generated_config.driver.__class__:
            message = "The running and generated configs must use the same driver."
            raise ValueError(message)

        self._remediation_config: Optional[HConfig] = None
        self._rollback_config: Optional[HConfig] = None

    @property
    def remediation_config(self) -> HConfig:
        """Builds and returns the remediation configuration to bring the device
        in line with the generated configuration.

        Returns:
            HConfig: The configuration needed to remediate the device.

        Notes:
            The remediation configuration is cached after the first call.

        """
        if self._remediation_config:
            return self._remediation_config

        remediation_config = self.running_config.config_to_get_to(
            self.generated_config
        ).set_order_weight()

        self._remediation_config = remediation_config

        return self._remediation_config

    @property
    def rollback_config(self) -> HConfig:
        """Builds and returns the rollback configuration to revert the device
        from the generated configuration back to the running configuration.

        Returns:
            HConfig: The configuration required to roll back to the original state.

        Notes:
            The rollback configuration is cached after the first call.

        """
        if self._rollback_config:
            return self._rollback_config

        rollback_config = self.generated_config.config_to_get_to(
            self.running_config, HConfig(self.running_config.driver)
        ).set_order_weight()

        self._rollback_config = rollback_config

        return rollback_config

    def apply_remediation_tag_rules(self, tag_rules: tuple[TagRule, ...]) -> None:
        """Applies tag rules to selectively label parts of the remediation configuration.

        Args:
            tag_rules (tuple[TagRule, ...]): A set of tag rules specifying sections to tag.

        Notes:
            This method is useful for managing configuration changes by marking specific
            parts of the config for conditional remediation.

        """
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
        """Returns the remediation configuration as text, filtered by included and excluded tags.

        Args:
            include_tags (Iterable[str], optional): Tags to include in the output.
            exclude_tags (Iterable[str], optional): Tags to exclude from the output.

        Returns:
            str: The filtered remediation configuration in a text format.

        Notes:
            - If no tags are provided, the complete sorted remediation configuration is returned.
            - Sorting respects configuration hierarchy and specified tags.

        """
        children = (
            self.remediation_config.all_children_sorted_by_tags(
                include_tags, exclude_tags
            )
            if include_tags or exclude_tags
            else self.remediation_config.all_children_sorted()
        )
        return "\n".join(c.cisco_style_text() for c in children)
