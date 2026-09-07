from abc import ABC
from collections.abc import Callable, Iterable
from functools import cache
from json import loads
from pathlib import Path
from re import Match, search
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, cast

from pydantic import Field, PositiveInt

from hier_config.child import HConfigChild
from hier_config.models import (
    BaseModel,
    FullTextSubRule,
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    IndentAdjustRule,
    MatchRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    NegationRule,
    NegationStrategy,
    NegationSubRule,
    OrderingRule,
    ParentAllowsDuplicateChildRule,
    PerLineSubRule,
    Platform,
    SectionalExitingRule,
    SectionalOverwriteNoNegateRule,
    SectionalOverwriteRule,
    UnusedObjectRule,
)
from hier_config.root import HConfig

if TYPE_CHECKING:
    from hier_config.platforms.view_base import HConfigViewBase

#: Reads a platform's canonical rules JSON out of the compiled core. ``None``
#: when the extension is unavailable, in which case the on-disk copy is read.
get_platform_rules_json: Callable[[str], str] | None
try:
    from _hier_config_rust import get_platform_rules_json
except ImportError:  # pragma: no cover - the extension is a hard requirement
    get_platform_rules_json = None


def _full_text_sub_rules_default() -> list[FullTextSubRule]:
    return []


def _idempotent_commands_rules_default() -> list[IdempotentCommandsRule]:
    return []


def _idempotent_commands_avoid_rules_default() -> list[IdempotentCommandsAvoidRule]:
    return []


def _indent_adjust_rules_default() -> list[IndentAdjustRule]:
    return []


def _negation_rules_default() -> list[NegationRule]:
    return []


def _ordering_rules_default() -> list[OrderingRule]:
    return []


def _parent_allows_duplicate_child_rules_default() -> list[
    ParentAllowsDuplicateChildRule
]:
    return []


def _per_line_sub_rules_default() -> list[PerLineSubRule]:
    return []


def _post_load_callbacks_default() -> list[Callable[[HConfig], None]]:
    return []


def _sectional_exiting_rules_default() -> list[SectionalExitingRule]:
    return []


def _sectional_overwrite_rules_default() -> list[SectionalOverwriteRule]:
    return []


def _sectional_overwrite_no_negate_rules_default() -> list[
    SectionalOverwriteNoNegateRule
]:
    return []


def _unused_object_rules_default() -> list[UnusedObjectRule]:
    return []


def _negate_with_rules_default() -> list[NegationDefaultWithRule]:
    return []


def _negation_default_when_rules_default() -> list[NegationDefaultWhenRule]:
    return []


def _negation_sub_rules_default() -> list[NegationSubRule]:
    return []


class HConfigDriverRules(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Pydantic model holding all rule collections for a platform driver.

    Each field corresponds to one category of driver behaviour (e.g. negation,
    ordering, idempotency).  Instantiated by each driver's ``_instantiate_rules``
    static method and stored on :class:`HConfigDriverBase`.
    """

    full_text_sub: list[FullTextSubRule] = Field(
        default_factory=_full_text_sub_rules_default
    )
    idempotent_commands: list[IdempotentCommandsRule] = Field(
        default_factory=_idempotent_commands_rules_default
    )
    idempotent_commands_avoid: list[IdempotentCommandsAvoidRule] = Field(
        default_factory=_idempotent_commands_avoid_rules_default
    )
    indent_adjust: list[IndentAdjustRule] = Field(
        default_factory=_indent_adjust_rules_default
    )
    indentation: PositiveInt = 2
    negation: list[NegationRule] = Field(default_factory=_negation_rules_default)
    ordering: list[OrderingRule] = Field(default_factory=_ordering_rules_default)
    parent_allows_duplicate_child: list[ParentAllowsDuplicateChildRule] = Field(
        default_factory=_parent_allows_duplicate_child_rules_default
    )
    per_line_sub: list[PerLineSubRule] = Field(
        default_factory=_per_line_sub_rules_default
    )
    post_load_callbacks: list[Callable[[HConfig], None]] = Field(
        default_factory=_post_load_callbacks_default
    )
    remediation_transform_callbacks: list[Callable[[HConfig], None]] = Field(
        default_factory=_post_load_callbacks_default
    )
    sectional_exiting: list[SectionalExitingRule] = Field(
        default_factory=_sectional_exiting_rules_default
    )
    sectional_overwrite: list[SectionalOverwriteRule] = Field(
        default_factory=_sectional_overwrite_rules_default
    )
    sectional_overwrite_no_negate: list[SectionalOverwriteNoNegateRule] = Field(
        default_factory=_sectional_overwrite_no_negate_rules_default
    )
    unused_objects: list[UnusedObjectRule] = Field(
        default_factory=_unused_object_rules_default
    )

    # --- v3 compatibility ---
    #
    # v3 split negation across three rule lists; v4 uses the single ordered
    # `negation` list above. Both spellings are supported permanently, so a v3
    # driver keeps working unchanged whether it passes these to the constructor
    # or appends to them afterwards -- the idiom v3's own custom-driver docs
    # teach. `all_negation_rules()` resolves both on every lookup.
    negate_with: list[NegationDefaultWithRule] = Field(
        default_factory=_negate_with_rules_default
    )
    negation_default_when: list[NegationDefaultWhenRule] = Field(
        default_factory=_negation_default_when_rules_default
    )
    negation_sub: list[NegationSubRule] = Field(
        default_factory=_negation_sub_rules_default
    )

    def all_negation_rules(self) -> list[NegationRule]:
        """Return `negation` plus the v3 negation fields, in resolution order.

        Computed on every call, so appending to `negation` **or** to one of the
        v3 fields takes effect either way, and nothing is ever folded in twice.

        The v3 fields are appended in the order DEFAULT, REPLACE, REGEX_SUB.
        That is the order `load_driver_rules()` already uses and it reproduces
        the v3 priority: `driver.negate_with()` scans every REPLACE rule first,
        so REPLACE placement does not matter, and DEFAULT is then evaluated
        ahead of REGEX_SUB.
        """
        if not (self.negation_default_when or self.negate_with or self.negation_sub):
            return self.negation

        return [
            *self.negation,
            *(rule.to_negation_rule() for rule in self.negation_default_when),
            *(rule.to_negation_rule() for rule in self.negate_with),
            *(rule.to_negation_rule() for rule in self.negation_sub),
        ]


@cache
def _load_platform_data(platform_name: str) -> dict[str, Any]:
    """Read a platform's canonical rule definitions.

    The JSON embedded in the Rust core is the single source of truth for the
    built-in platforms, so Python and Rust cannot drift apart. Falls back to
    the checked-in copy when running against an uninstalled extension.
    """
    raw_json = None
    if get_platform_rules_json is not None:
        try:
            raw_json = get_platform_rules_json(platform_name)
        except ValueError:
            raw_json = None
    if raw_json is None:
        platform_dir = (
            Path(__file__).resolve().parents[2]
            / "crates"
            / "hier_config_core"
            / "src"
            / "platforms"
            / platform_name
        )
        raw_json = (platform_dir / "rules.json").read_text(encoding="utf-8")
    return cast("dict[str, Any]", loads(raw_json))


@cache
def _cached_platform_rules(platform_name: str) -> HConfigDriverRules:
    return HConfigDriverRules.model_validate(
        _load_platform_data(platform_name)["rules"]
    )


def clear_rules_cache() -> None:
    """Clear cached platform rules and raw platform data."""
    _load_platform_data.cache_clear()
    _cached_platform_rules.cache_clear()


def load_platform_rules(
    platform: Platform | str,
    *,
    post_load_callbacks: list[Callable[[HConfig], None]] | None = None,
) -> HConfigDriverRules:
    """Load the default driver rules for `platform`."""
    name = (
        platform.name.lower()
        if isinstance(platform, Platform)
        else str(platform).lower()
    )
    cached = _cached_platform_rules(name)
    # Every rule model is frozen, so copying the lists is enough to isolate
    # callers from one another; a deep copy would clone immutable rule objects
    # for no benefit and dominates driver construction time.
    update: dict[str, Any] = {
        field: list(cast("list[object]", value))
        for field, value in cached.__dict__.items()
        if isinstance(value, list)
    }
    if post_load_callbacks is not None:
        update["post_load_callbacks"] = list(post_load_callbacks)
    return cached.model_copy(update=update)


#: Driver hooks the v4 engine never calls. See `__init_subclass__`.
_REMOVED_HOOKS = ("idempotent_for", "negate_with", "sectional_exit")


#: Platforms whose stock post-load fixups are applied by the Rust core during
#: parsing. Their Python equivalents stay public so custom drivers can reuse
#: them, but re-running one over an already-fixed tree would be wasted work, so
#: `hier_config.constructors` skips core-owned callbacks for these platforms.
CORE_POST_LOAD_PLATFORMS: frozenset[Platform] = frozenset(
    {
        Platform.ARUBA_AOSCX,
        Platform.CISCO_IOS,
        Platform.CISCO_XR,
        Platform.HP_PROCURVE,
    }
)

_CORE_OWNED_ATTR = "__hier_config_core_owned__"
_CoreOwnedT = TypeVar("_CoreOwnedT", bound=Callable[..., object])


def core_owned(callback: _CoreOwnedT) -> _CoreOwnedT:
    """Mark a callable as one the Rust core already implements.

    Two kinds of callable carry this marker:

    - Post-load callbacks. The marker suppresses the redundant Python pass for
      the platforms in `CORE_POST_LOAD_PLATFORMS`. A custom driver on any other
      platform that reuses one of these callbacks still gets it executed
      normally.
    - Overrides of the hooks in `_REMOVED_HOOKS`. Those are normally rejected
      because the core owns the behavior; the marker records that this
      particular override *is* the core implementation, mirrored in Python for
      reuse by custom drivers.
    """
    setattr(callback, _CORE_OWNED_ATTR, True)
    return callback


def runs_in_core(
    callback: Callable[[HConfig], None], platform: Platform | None
) -> bool:
    """Report whether the core already applied `callback` for `platform`."""
    return platform in CORE_POST_LOAD_PLATFORMS and getattr(
        callback, _CORE_OWNED_ATTR, False
    )


def _is_core_owned(obj: object) -> bool:
    """Report whether `obj` is marked as mirrored by the Rust core."""
    return getattr(obj, _CORE_OWNED_ATTR, False) is True


class HConfigDriverBase(ABC):
    """Defines all hier_config options, rules, and rule checking methods.
    Override methods as needed.
    """

    #: View class instantiated by ``get_hconfig_view()``. ``None`` means the
    #: platform has no config view. Set this on a driver subclass to register
    #: a view for a custom platform or to override a built-in view.
    view_class: ClassVar[type["HConfigViewBase"] | None] = None

    #: Platform whose canonical rules `_instantiate_rules()` loads by default.
    #: `None` means the driver must override `_instantiate_rules()`.
    platform: ClassVar[Platform | None] = None

    def __init__(self) -> None:
        self.rules = self._instantiate_rules()

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Reject subclasses that define a hook the v4 engine cannot call.

        Only rule *data* crosses into the Rust core, so a Python override of
        `idempotent_for`, `negate_with` or `sectional_exit` is never invoked.
        Silently ignoring one produces wrong remediation with no signal, so
        defining one is an error. Express the behavior as an
        `IdempotentCommandsRule`, a `NegationRule`, or a
        `SectionalExitingRule` instead -- all support `re_search` capture
        groups, and `NegationRule.use` supports backreferences.

        A built-in driver whose behavior the core already reproduces natively
        may keep its Python copy by marking it `@core_owned`, so that calling
        the method directly still returns the right answer.
        """
        super().__init_subclass__(**kwargs)
        for hook in _REMOVED_HOOKS:
            if hook in cls.__dict__ and not _is_core_owned(cls.__dict__[hook]):
                msg = (
                    f"{cls.__name__} defines {hook}(), which the v4 engine never "
                    f"calls: only rule data crosses into the Rust core. Express "
                    f"this as a rule on HConfigDriverRules instead. See "
                    f"https://hier-config.readthedocs.io/en/latest/user/migration-v3-to-v4/"
                )
                raise TypeError(msg)

    def idempotent_for(
        self,
        config: HConfigChild,
        other_children: Iterable[HConfigChild],
    ) -> HConfigChild | None:
        """Return the child in `other_children` that `config` idempotently overwrites.

        The default implementation derives a structural idempotency key from
        the lineage and the `idempotent_commands` match rules. Override for
        imperative idempotency logic.
        """
        for rule in self.rules.idempotent_commands:
            if not config.is_lineage_match(rule.match_rules):
                continue

            config_key = self._idempotency_key(config, rule.match_rules)

            for other_child in other_children:
                if not other_child.is_lineage_match(rule.match_rules):
                    continue

                if self._idempotency_key(other_child, rule.match_rules) == config_key:
                    return other_child

        return None

    def negate_with(self, config: HConfigChild) -> str | None:
        """Return a fixed replacement negation string for `config`, if any.

        Reads REPLACE-strategy rules from the unified `negation` rule list,
        plus any v3 `negate_with` rules. Drivers may override this method for
        imperative negation logic.
        """
        for rule in self.rules.all_negation_rules():
            if rule.strategy is NegationStrategy.REPLACE and config.is_lineage_match(
                rule.match_rules
            ):
                return rule.use
        return None

    def sectional_exit(self, config: HConfigChild) -> str | None:
        """Return the exit token to render at the end of `config`'s section.

        Sectional-exiting rules are consulted first; a matching rule without
        `exit_text` suppresses the token. Otherwise, sections with children
        default to `exit` and leaves to None.
        """
        for exit_rule in self.rules.sectional_exiting:
            if config.is_lineage_match(exit_rule.match_rules):
                if exit_text := exit_rule.exit_text:
                    return exit_text
                return None
        if config.children:
            return "exit"
        return None

    def swap_negation(self, child: HConfigChild) -> HConfigChild:
        """Swap negation of a `child.text`."""
        if child.text.startswith(self.negation_prefix):
            child.text = child.text_without_negation
        else:
            child.text = f"{self.negation_prefix}{child.text}"

        return child

    def _idempotency_key(
        self,
        config: HConfigChild,
        match_rules: tuple[MatchRule, ...],
    ) -> tuple[str, ...]:
        """Build a structural identity for `config` that respects driver rules.

        Args:
            config: The child being evaluated for idempotency.
            match_rules: The match rules describing the lineage signature.

        Returns:
            A tuple of string fragments representing the idempotency key.

        """
        lineage = tuple(config.lineage())
        if len(lineage) != len(match_rules):
            return ()

        components: list[str] = []
        for child, rule in zip(lineage, match_rules, strict=False):
            components.append(self._idempotency_component_key(child, rule))
        return tuple(components)

    def _idempotency_component_key(
        self,
        child: HConfigChild,
        rule: MatchRule,
    ) -> str:
        """Derive the structural key for a single lineage component.

        Args:
            child: The lineage child contributing to the key.
            rule: The rule governing how to match the child.

        Returns:
            A string fragment representing the component key.

        """
        text = child.text
        normalized_text = text.removeprefix(self.negation_prefix)

        parts: list[str] = []
        parts.extend(self._key_from_equals(rule.equals, text))
        parts.extend(self._key_from_prefix(rule.startswith, normalized_text))
        parts.extend(self._key_from_suffix(rule.endswith, normalized_text))
        parts.extend(self._key_from_contains(rule.contains, normalized_text))
        parts.extend(self._key_from_regex(rule.re_search, normalized_text, text))

        if not parts:
            parts.append(f"text|{normalized_text}")

        return ";".join(parts)

    @staticmethod
    def _key_from_equals(equals: str | frozenset[str] | None, text: str) -> list[str]:
        """Return key fragments constrained by `equals` match rules.

        Args:
            equals: The equals constraint specified by the rule.
            text: The original command text to fall back on for sets.

        Returns:
            A list containing zero or one key fragments.

        """
        if equals is None:
            return []
        if isinstance(equals, str):
            return [f"equals|{equals}"]
        return [f"equals|{text}"]

    def _key_from_prefix(
        self,
        prefix: str | tuple[str, ...] | None,
        normalized_text: str,
    ) -> list[str]:
        """Return key fragments for `startswith` match rules.

        Args:
            prefix: The `startswith` constraint(s) to evaluate.
            normalized_text: The command text without the negation prefix.

        Returns:
            A list containing zero or one key fragments.

        """
        if prefix is None:
            return []
        matched = self._match_prefix(normalized_text, prefix)
        if matched is None:
            return []
        return [f"startswith|{matched}"]

    def _key_from_suffix(
        self,
        suffix: str | tuple[str, ...] | None,
        normalized_text: str,
    ) -> list[str]:
        """Return key fragments for `endswith` match rules.

        Args:
            suffix: The `endswith` constraint(s) to evaluate.
            normalized_text: The command text without the negation prefix.

        Returns:
            A list containing zero or one key fragments.

        """
        if suffix is None:
            return []
        matched = self._match_suffix(normalized_text, suffix)
        if matched is None:
            return []
        return [f"endswith|{matched}"]

    def _key_from_contains(
        self,
        contains: str | tuple[str, ...] | None,
        normalized_text: str,
    ) -> list[str]:
        """Return key fragments for `contains` match rules.

        Args:
            contains: The `contains` constraint(s) to evaluate.
            normalized_text: The command text without the negation prefix.

        Returns:
            A list containing zero or one key fragments.

        """
        if contains is None:
            return []
        matched = self._match_contains(normalized_text, contains)
        if matched is None:
            return []
        return [f"contains|{matched}"]

    def _key_from_regex(
        self,
        pattern: str | None,
        normalized_text: str,
        original_text: str,
    ) -> list[str]:
        """Return key fragments derived from regex match rules.

        Args:
            pattern: The regex pattern to match.
            normalized_text: The command text without the negation prefix.
            original_text: The command text including any negation.

        Returns:
            A list containing zero or one key fragments.

        """
        if pattern is None:
            return []

        match = search(pattern, normalized_text)
        match_source = normalized_text
        if match is None:
            match = search(pattern, original_text)
            match_source = original_text

        if match is None:
            return []

        regex_key = self._normalize_regex_key(pattern, match_source, match)
        return [f"re|{regex_key}"]

    @staticmethod
    def _match_prefix(value: str, prefix: str | tuple[str, ...]) -> str | None:
        if isinstance(prefix, tuple):
            matches = [candidate for candidate in prefix if value.startswith(candidate)]
            if matches:
                return max(matches, key=len)
            return None

        if value.startswith(prefix):
            return prefix

        return None

    @staticmethod
    def _match_suffix(value: str, suffix: str | tuple[str, ...]) -> str | None:
        if isinstance(suffix, tuple):
            matches = [candidate for candidate in suffix if value.endswith(candidate)]
            if matches:
                return max(matches, key=len)
            return None

        if value.endswith(suffix):
            return suffix

        return None

    @staticmethod
    def _match_contains(value: str, contains: str | tuple[str, ...]) -> str | None:
        if isinstance(contains, tuple):
            matches = [candidate for candidate in contains if candidate in value]
            if matches:
                return max(matches, key=len)
            return None

        if contains in value:
            return contains

        return None

    @staticmethod
    def _normalize_regex_key(pattern: str, value: str, match: Match[str]) -> str:
        """Normalize regex matches so equivalent commands hash the same."""
        result = match.group(0)

        if match.re.groups:
            groups = tuple(g or "" for g in match.groups())
            if any(groups):
                normalized_groups = tuple(group.strip() for group in groups)
                if any(normalized_groups):
                    return "|".join(normalized_groups)

        trimmed_pattern = pattern.rstrip("$")
        for suffix in (".*", ".+"):
            if trimmed_pattern.endswith(suffix):
                candidate_pattern = trimmed_pattern[: -len(suffix)]
                if not candidate_pattern:
                    break
                trimmed_match = search(candidate_pattern, value)
                if trimmed_match is not None:
                    candidate = trimmed_match.group(0).strip()
                    if candidate:
                        return candidate
                break

        return result.strip()

    @property
    def declaration_prefix(self) -> str:
        """The string prepended to positive commands on set-style platforms.

        Defaults to an empty string; set-style drivers override this with
        e.g. `set `.
        """
        return ""

    @property
    def negation_prefix(self) -> str:
        """The string prepended to a command to negate it.

        Defaults to `no `; drivers override this with e.g. `undo ` or
        `delete `.
        """
        return "no "

    @staticmethod
    def config_preprocessor(config_text: str) -> str:
        """Transform raw config text before parsing.

        The default is a no-op. Override to convert a platform's native
        rendering into parseable lines (e.g. flattening JunOS curly-brace
        config into `set` commands). Runs inside `HConfig.from_text()` after
        full-text substitutions and before tree construction.
        """
        return config_text

    @staticmethod
    def _instantiate_rules() -> HConfigDriverRules:
        """Build this driver's rule set.

        Built-in drivers return `load_platform_rules(<platform>)`, the same
        canonical rules the Rust core compiles against, so the two can never
        disagree. Custom drivers return an `HConfigDriverRules` they build
        themselves.

        Not abstract, so `HConfigDriverBase` stays instantiable for the
        introspection tests and tooling that rely on it.
        """
        message = "Driver subclasses must implement _instantiate_rules()"
        raise NotImplementedError(message)
