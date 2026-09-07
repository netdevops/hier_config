from hier_config.models import Platform
from hier_config.platforms.cisco_xr.view import HConfigViewCiscoIOSXR
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    core_owned,
    load_platform_rules,
)
from hier_config.root import HConfig


@core_owned
def fixup_xr_comments(config: HConfig) -> None:
    """Move ``!`` comment lines into the next sibling's comments set."""
    for parent in (config, *config.all_children()):
        siblings = list(parent.children)
        comment_buffer: list[str] = []
        for sibling in siblings:
            if sibling.text.startswith("!"):
                comment_text = sibling.text.removeprefix("!").lstrip(" ")
                if comment_text:
                    comment_buffer.append(comment_text)
                sibling.delete()
            elif comment_buffer:
                for comment in comment_buffer:
                    sibling.comments.add(comment)
                comment_buffer.clear()


class HConfigDriverCiscoIOSXR(HConfigDriverBase):
    """Driver for Cisco IOS XR.

    Configures XR-specific sectional exiting (end-policy, end-set,
    end-template, root), sectional overwrite for templates, indent-adjust for
    inline templates, and duplicate-child allowances inside route-policy
    blocks. ACL sequence-number idempotency (ipv4/ipv6 access-list) compares
    sibling nodes, so it is implemented natively in the Rust core rather than
    as a rule.
    Platform enum: Platform.CISCO_XR.
    """

    platform = Platform.CISCO_XR
    view_class = HConfigViewCiscoIOSXR

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules and attach this platform's post-load callbacks.

        The callbacks are declared here so custom drivers can discover and
        reuse them (#286); the Rust core applies them during parsing, so
        `hier_config.constructors` skips the redundant Python pass.
        """
        return load_platform_rules(
            Platform.CISCO_XR,
            post_load_callbacks=[
                fixup_xr_comments,
            ],
        )
