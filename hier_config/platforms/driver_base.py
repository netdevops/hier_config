from abc import ABC
from collections.abc import Callable
from functools import cache
from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, cast

from pydantic import Field, PositiveInt

from hier_config.models import (
    BaseModel,
    FullTextSubRule,
    IdempotentCommandsAvoidRule,
    IdempotentCommandsRule,
    IndentAdjustRule,
    NegationDefaultWhenRule,
    NegationDefaultWithRule,
    NegationRule,
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
_REMOVED_HOOKS = (
    "idempotent_for",
    "negate_with",
    "sectional_exit",
    "swap_negation",
)


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
    """Mark a post-load callback as one the Rust core already implements.

    The marker suppresses the redundant Python pass for the platforms in
    `CORE_POST_LOAD_PLATFORMS`. A custom driver on any other platform that
    reuses one of these callbacks still gets it executed normally.
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
        `idempotent_for`, `negate_with`, `sectional_exit` or `swap_negation`
        is never invoked. Silently ignoring one produces wrong remediation
        with no signal, so defining one is an error. Express the behavior as
        an `IdempotentCommandsRule`, a `NegationRule`, or a
        `SectionalExitingRule` instead -- all support `re_search` capture
        groups, and `NegationRule.use` supports backreferences. Negation
        prefixes come from `declaration_prefix` and `negation_prefix`, which
        the core reads from the driver's rule data.
        """
        super().__init_subclass__(**kwargs)
        for hook in _REMOVED_HOOKS:
            if hook in cls.__dict__:
                msg = (
                    f"{cls.__name__} defines {hook}(), which the v4 engine never "
                    f"calls: only rule data crosses into the Rust core. Express "
                    f"this as a rule on HConfigDriverRules instead. See "
                    f"https://hier-config.readthedocs.io/en/latest/user/migration-v3-to-v4/"
                )
                raise TypeError(msg)

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
