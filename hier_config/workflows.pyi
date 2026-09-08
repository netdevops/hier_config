# Type stubs for the Rust-backed implementation in `_hier_config_rust`.
#
# griffe (mkdocstrings) and mypy cannot introspect a compiled extension,
# so this stub is the documented, typed view of the native class.

from collections.abc import Callable, Iterable
from typing import Any, TypeAlias

from hier_config.models import Platform, TagRule
from hier_config.root import HConfig

#: A remediation transform. `RemediationPlugin` instances are callable, so a
#: plain function with the same shape works anywhere a plugin does.
RemediationTransform: TypeAlias = Callable[[HConfig], None]

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
        from hier_config.models import Platform

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
        plugins: Iterable[RemediationTransform] | None = None,
    ) -> None: ...
    @property
    def plugins(self) -> tuple[RemediationTransform, ...]:
        """The remediation plugins applied to every generated remediation."""

    @property
    def running_config(self) -> HConfig: ...
    @property
    def generated_config(self) -> HConfig: ...
    @property
    def remediation_config(self) -> HConfig: ...
    @property
    def rollback_config(self) -> HConfig: ...
    def apply_remediation_tag_rules(self, tag_rules: tuple[TagRule, ...]) -> None:
        """Applies tag rules to selectively label parts of the remediation configuration.

        Args:
            tag_rules (tuple[TagRule, ...]): A set of tag rules specifying sections to tag.

        Notes:
            This method is useful for managing configuration changes by marking specific
            parts of the config for conditional remediation.

        """

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

    def remediation_text(
        self,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> str:
        """Remediation configuration as text, filtered by included and excluded tags."""

    def rollback_text(
        self,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> str:
        """Rollback configuration as text, filtered by included and excluded tags."""

    def rollback_config_filtered_text(
        self,
        include_tags: Iterable[str] = (),
        exclude_tags: Iterable[str] = (),
    ) -> str:
        """Rollback configuration as text, filtered by included and excluded tags."""

    def remediation_netconf_xml(
        self,
        *,
        list_keys: tuple[str, ...] | None = None,
    ) -> str:
        """Render the remediation as a NETCONF edit-config payload.

        Requires running and generated configs built by `HConfig.from_xml()`.
        """

    def remediation_json(
        self,
        *,
        list_keys: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Render the remediation as a gNMI-SetRequest-style dict.

        Requires running and generated configs built by `HConfig.from_json()`.
        """

    @classmethod
    def from_strings(
        cls,
        platform: Platform | str,
        running_text: str,
        generated_text: str,
    ) -> WorkflowRemediation:
        """Constructs a `WorkflowRemediation` by parsing running and generated configuration
        strings natively in Rust with the GIL released.

        Args:
            platform: Platform enum member or string name (e.g. 'cisco_ios').
            running_text: Raw configuration text of running state.
            generated_text: Raw configuration text of intended/generated state.

        Returns:
            WorkflowRemediation: Initialized workflow instance with running and generated configs.

        """

__all__ = ("WorkflowRemediation",)
