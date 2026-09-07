from hier_config.models import Platform
from hier_config.platforms.aruba_aoscx.view import HConfigViewArubaAOSCX
from hier_config.platforms.driver_base import (
    HConfigDriverBase,
    HConfigDriverRules,
    core_owned,
    load_platform_rules,
)
from hier_config.platforms.functions import expand_range
from hier_config.platforms.utils import split_vlan_id_lists
from hier_config.root import HConfig


@core_owned
def split_interface_vlan_trunk_allowed(config: HConfig) -> None:
    """Split AOS-CX additive trunk VLAN lists into one VLAN per line.

    ``vlan trunk allowed`` is additive on AOS-CX rather than declarative, so
    modelling one VLAN per line lets standard remediation add missing VLANs with
    ``vlan trunk allowed <id>`` and remove extra ones with
    ``no vlan trunk allowed <id>`` -- matching how the device actually behaves.
    A spec that does not parse to at least one VLAN id is left untouched so the
    line is never deleted without a replacement.
    """
    for interface in config.get_children(startswith="interface "):
        for allowed in tuple(interface.get_children(startswith="vlan trunk allowed ")):
            words = allowed.text.split(maxsplit=3)
            if len(words) != 4:
                continue
            spec = words[3]
            if spec in {"all", "none"} or not any(
                separator in spec for separator in (",", "-")
            ):
                continue
            try:
                vlan_ids = expand_range(spec)
            except ValueError:
                continue
            if not vlan_ids:
                continue
            for vlan_id in vlan_ids:
                interface.add_child(
                    f"vlan trunk allowed {vlan_id}",
                    return_if_present=True,
                )
            allowed.delete()


class HConfigDriverArubaAOSCX(HConfigDriverBase):
    """Driver for Aruba AOS-CX switches.

    AOS-CX uses a Cisco IOS/EOS-like hierarchical CLI with no negation, so it
    reuses the standard tree model and remediation. The one platform-specific
    behaviour is that vlan trunk allowed is additive rather than declarative:
    the driver splits comma/range VLAN lists into one VLAN per line (both on load
    and in the intended config, via post_load_callbacks) so remediation adds
    only the missing VLANs and negates only the removed ones. Unnamed collapsed
    VLAN headers like vlan 1,10 are split into separate VLAN sections the same
    way. Platform enum: Platform.ARUBA_AOSCX.
    """

    platform = Platform.ARUBA_AOSCX
    view_class = HConfigViewArubaAOSCX

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Load the canonical rules and attach this platform's post-load callbacks.

        The callbacks are declared here so custom drivers can discover and
        reuse them (#286); the Rust core applies them during parsing, so
        `hier_config.constructors` skips the redundant Python pass.
        """
        return load_platform_rules(
            Platform.ARUBA_AOSCX,
            post_load_callbacks=[
                split_vlan_id_lists,
                split_interface_vlan_trunk_allowed,
            ],
        )
