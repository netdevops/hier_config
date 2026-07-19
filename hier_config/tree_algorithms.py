"""Tree comparison algorithms extracted from HConfigBase (#217).

These functions implement diffing (`compute_difference`), remediation
(`compute_remediation`), future-config prediction (`compute_future`), and
tag-filtered copying (`compute_with_tags`) over configuration trees. They
operate on `HConfig` / `HConfigChild` nodes through their public tree API,
so they can be tested and extended independently of the tree structure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from .base import HConfigBase
    from .child import HConfigChild
    from .root import HConfig

    _HConfigRootOrChildT = TypeVar("_HConfigRootOrChildT", bound=HConfig | HConfigChild)


def compute_remediation(
    source: HConfigBase,
    target: _HConfigRootOrChildT,
    delta: _HConfigRootOrChildT,
) -> _HConfigRootOrChildT:
    """Compute the commands needed to transition from source to target.

    source is the running_config, target is the generated_config; the result
    is written into delta (left pass negates missing, right pass adds new).
    """
    _remediation_left(source, target, delta)
    _remediation_right(source, target, delta)

    return delta


def _remediation_left(
    source: HConfigBase,
    target: HConfig | HConfigChild,
    delta: HConfig | HConfigChild,
) -> None:
    # find source.children that are not in target.children
    # i.e. what needs to be negated or defaulted
    # Also, find out if another command in source.children will overwrite
    # i.e. be idempotent
    for self_child in source.children:
        if self_child.text in target.children:
            continue
        if self_child.is_idempotent_command(target.children):
            continue

        # in other but not self
        # add this node but not any children
        negated = delta.add_child(self_child.text).negate()
        if self_child.children:
            negated.comments.add(f"removes {len(self_child.children) + 1} lines")


def _remediation_right(
    source: HConfigBase,
    target: HConfig | HConfigChild,
    delta: HConfig | HConfigChild,
) -> None:
    # Find what would need to be added to source_config to get to self
    for target_child in target.children:
        # If the child exist, recurse into its children
        if self_child := source.children.get(target_child.text):
            # Do we need to rewrite the child and its children as well?
            if self_child.use_sectional_overwrite():
                self_child.overwrite_with(target_child, delta)
                continue
            if self_child.use_sectional_overwrite_without_negation():
                self_child.overwrite_with(target_child, delta, negate=False)
                continue
            # Matched leaves can never produce delta lines - neither pass
            # has children to visit - so skip the subtree allocation (#191).
            if not (self_child.children or target_child.children):
                continue
            subtree = delta.instantiate_child(target_child.text)
            compute_remediation(self_child, target_child, subtree)
            if subtree.children:
                delta.children.append(subtree)
        # The child is absent, add it.
        else:
            # If the target_child is already in the delta, that means it was negated in the target config
            if target_child.text in delta.children:
                continue
            new_item = delta.add_deep_copy_of(target_child)
            # Mark the new item and all of its children as new_in_config.
            new_item.new_in_config = True
            for child in new_item.all_children():
                child.new_in_config = True
            if new_item.children:
                new_item.comments.add("new section")


def _strip_acl_sequence_number(hier_child: HConfigChild) -> str:
    words = hier_child.text.split()
    if words[0].isdecimal():
        words.pop(0)
    return " ".join(words)


def compute_difference(
    source: HConfigBase,
    target: _HConfigRootOrChildT,
    delta: _HConfigRootOrChildT,
    target_acl_children: dict[str, HConfigChild] | None = None,
    *,
    in_acl: bool = False,
) -> _HConfigRootOrChildT:
    """Compute the config from source that is not in target, writing into delta."""
    acl_sw_matches = tuple(f"ip{x} access-list " for x in ("", "v4", "v6"))

    for self_child in source.children:
        # Not dealing with negations and defaults for now
        if self_child.text.startswith((source.driver.negation_prefix, "default ")):
            continue

        if in_acl:
            # Ignore ACL sequence numbers
            if target_acl_children is None:
                message = "target_acl_children cannot be None"
                raise TypeError(message)
            target_child = target_acl_children.get(
                _strip_acl_sequence_number(self_child),
            )
        else:
            target_child = target.get_child(equals=self_child.text)

        if target_child is None:
            delta.add_deep_copy_of(self_child)
        else:
            delta_child = delta.add_child(self_child.text)
            if self_child.text.startswith(acl_sw_matches):
                compute_difference(
                    self_child,
                    target_child,
                    delta_child,
                    target_acl_children={
                        _strip_acl_sequence_number(c): c for c in target_child.children
                    },
                    in_acl=True,
                )
            else:
                compute_difference(self_child, target_child, delta_child)
            if not delta_child.children:
                delta_child.delete()

    return delta


def _future_pre(
    source: HConfigBase,
    config: HConfig | HConfigChild,
) -> tuple[set[str], set[str]]:
    negated_or_recursed: set[str] = set()
    config_children_ignore: set[str] = set()
    for self_child in source.children:
        # Is the command effectively negating a command in source.children?
        if (negation_text := source.root.driver.negate_with(self_child)) and (
            config_child := config.get_child(equals=negation_text)
        ):
            negated_or_recursed.add(self_child.text)
            config_children_ignore.add(config_child.text)
    return negated_or_recursed, config_children_ignore


def compute_future(  # ruff:ignore[complex-structure]
    source: HConfigBase,
    config: HConfig | HConfigChild,
    future_config: HConfig | HConfigChild,
) -> None:
    """Recursively compute the future configuration subtree.

    Called by :meth:`HConfig.future` to walk the config tree and merge
    ``config`` on top of ``source``, applying driver-specific rules for
    sectional overwrite, idempotency, and negation.  The result is written
    into ``future_config``.

    Known gaps (not yet accounted for):

    - Negating a numbered ACL when removing a single entry
    - Idempotent command avoid list
    - And likely other edge cases
    """
    negated_or_recursed, config_children_ignore = _future_pre(source, config)

    for config_child in config.children:
        if config_child.text in config_children_ignore:
            continue
        is_negation = config_child.text.startswith(source.driver.negation_prefix)
        # sectional_overwrite
        # sectional_overwrite_no_negate
        if (
            config_child.use_sectional_overwrite()
            or config_child.use_sectional_overwrite_without_negation()
        ):
            future_config.add_deep_copy_of(config_child)
        # A negation whose positive form exists removes it; neither line
        # survives. Evaluated before the idempotency rules, which can match
        # the negation line itself and keep it as a literal child (#269).
        elif is_negation and (
            exact := source.get_child(equals=config_child.text_without_negation)
        ):
            negated_or_recursed.add(exact.text)
        # Idempotent commands: interchangeable forms of one setting replace
        # each other. This deliberately covers negated forms tracked by a
        # rule (e.g. IOS `no logging console`), which persist in the render.
        elif self_child := source.root.driver.idempotent_for(
            config_child,
            source.children,
        ):
            future_config.add_deep_copy_of(config_child)
            negated_or_recursed.add(self_child.text)
        # Shorthand negation: `no description` removes `description foo`, as
        # devices do (#269).
        elif is_negation and (
            prefix_matches := [
                child
                for child in source.children
                if child.text.startswith(
                    f"{config_child.text_without_negation} ",
                )
            ]
        ):
            negated_or_recursed.update(child.text for child in prefix_matches)
        # config_child is already in source
        elif self_child := source.get_child(equals=config_child.text):
            future_child = future_config.add_shallow_copy_of(self_child)
            compute_future(self_child, config_child, future_child)
            negated_or_recursed.add(config_child.text)
        # A negation matching nothing is kept: it accounts for "no ..." lines
        # native to the running config and doubles as a did-not-apply-cleanly
        # signal for callers (#269).
        elif is_negation:
            future_config.add_shallow_copy_of(config_child)
        # The negated form of config_child is in source.children
        elif self_child := source.get_child(
            equals=f"{source.driver.negation_prefix}{config_child.text}",
        ):
            negated_or_recursed.add(self_child.text)
        # config_child is not in source and doesn't match a special case
        else:
            future_config.add_deep_copy_of(config_child)

    for self_child in source.children:
        # self_child matched an above special case and should be ignored
        if self_child.text in negated_or_recursed:
            continue
        # self_child was not modified above and should be present in the future config
        future_config.add_deep_copy_of(self_child)


def compute_with_tags(
    source: HConfigBase,
    tags: frozenset[str],
    new_instance: _HConfigRootOrChildT,
) -> _HConfigRootOrChildT:
    """Add children recursively that have a subset of tags."""
    for child in source.children:
        if tags.issubset(child.tags):
            new_child = new_instance.add_shallow_copy_of(child)
            compute_with_tags(child, tags, new_child)

    return new_instance


def prune_emptied_branches(
    source: HConfigBase,
    future_node: HConfigBase,
) -> None:
    """Remove branches that a change emptied out, as devices do (#269).

    Only prunes nodes whose counterpart in the running config had children;
    sections that were already empty (or are newly added empty) are kept.
    Cascades upward via post-order traversal.
    """
    for child in tuple(future_node.children):
        source_child = source.get_child(equals=child.text) if source else None
        if source_child is not None:
            prune_emptied_branches(source_child, child)
            if not child.children and source_child.children:
                child.delete()
