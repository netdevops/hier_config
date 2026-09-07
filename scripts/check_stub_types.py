#!/usr/bin/env python3
"""Verify declared return types against what the extension actually returns.

``gen_stubs.py --check`` guards stub *names* and ``mypy.stubtest`` guards
*signatures*, but neither can see a return type: annotations are not
recoverable from a compiled ``.so``. For an extension module the stub *is*
the type checker's only source of truth, so a wrong return type is not an
error the checkers can find -- it is the premise they reason from.

Their coverage is therefore incidental: it depends on whether some caller
happens to use the value in a type-revealing way. Rewriting
``vlan_ids -> frozenset[int]`` as ``dict[str, bytes]`` changes the pyright
strict error count by zero, because nothing iterates it revealingly. The same
edit to ``vlans -> list[Vlan]`` does surface 38 errors, but every one of them
lands in the tests that touch ``.id``, and none point at the stub.

Generating the stub from the PyO3 layer does not fix this: 30% of the
exported methods return an opaque ``PyObject``/``Vec<PyObject>``, so
``vlans``, ``stack_members`` and ``ipv4_default_gw`` share one Rust signature
and three different Python types. Deriving annotations from Rust would
replace ``list[Vlan]`` with ``Any``. That holds for ``pyo3-stub-gen`` and for
``pyo3-introspection`` alike -- PyO3 maps an unconstrained object to
``_typeshed.Incomplete`` (see ``PyTypeInfo::TYPE_HINT``), which is ``Any`` --
because the information was never in the Rust types to begin with.
``pyo3-stub-gen`` can override an erased type, but ``type_repr`` is an
unvalidated string: its own test fixture carries the malformed
``"collections.abc.Callable[[str]]"``. For those 39 members an override is a
hand-written annotation relocated into a proc-macro attribute, so it inherits
the trust gap it would need to close. It also requires ``pyo3 >= 0.27``
against our pinned ``0.24``.

The type information does exist at runtime, so this script recovers it there:
it exercises the declared members against a corpus of real configs and checks
each observed value against its declared annotation, descending into
container element types. Parameter types stay unverifiable by construction --
nothing observes an argument that was never passed -- so those remain the
type checkers' responsibility alone. ``pyo3-stub-gen``'s ``override_type``
would cover them, and would derive the ~70% of returns that are not erased;
that is complementary to this script rather than a replacement, and worth
revisiting whenever PyO3 is upgraded for other reasons.
"""

from __future__ import annotations

import argparse
import ast
import collections.abc
import ipaddress
import itertools
import sys
import types
import typing
from dataclasses import dataclass, field
from pathlib import Path

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from hier_config.root import HConfig

REPO_ROOT = Path(__file__).resolve().parents[1]

# Stubs that describe objects implemented in the extension. The tree stubs are
# included because `_hier_config_rust.pyi` re-exports those classes rather than
# restating them, so their annotations describe native objects too.
STUB_FILES = (
    REPO_ROOT / "stubs" / "_hier_config_rust.pyi",
    REPO_ROOT / "hier_config" / "base.pyi",
    REPO_ROOT / "hier_config" / "child.pyi",
    REPO_ROOT / "hier_config" / "children.pyi",
    REPO_ROOT / "hier_config" / "root.pyi",
    REPO_ROOT / "hier_config" / "workflows.pyi",
)

# Members that no fixture exercises with a non-empty value. Listing one keeps
# the check quiet about it; omitting a genuinely unobserved member, or listing
# one that later becomes observed, is an error. See the file's header.
UNOBSERVED_ALLOWLIST = REPO_ROOT / "stubs" / "unobserved-allowlist.txt"

# Zero-argument methods that are safe to call on a probe. Properties are
# invoked automatically; methods are opt-in so that probing never mutates the
# configuration under observation.
SAFE_METHODS = frozenset(
    {
        "all_children",
        "all_children_sorted",
        "dump",
        "lineage",
        "to_lines",
        "to_text",
    },
)

FIXTURE_DIRS = (
    REPO_ROOT / "tests" / "integration" / "fixtures",
    REPO_ROOT / "tests" / "unit" / "fixtures",
)

# Errors a probe may legitimately raise for a config that lacks the feature.
PROBE_ERRORS = (
    AttributeError,
    LookupError,
    NotImplementedError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True)
class Declaration:
    """A return annotation recovered from a stub file."""

    owner: str
    member: str
    annotation: str
    is_property: bool
    source: Path


@dataclass
class Report:
    """Outcome of checking every declaration against the probe corpus."""

    verified: list[str] = field(default_factory=list[str])
    unobserved: list[str] = field(default_factory=list[str])
    mismatches: list[str] = field(default_factory=list[str])


def _allowlist() -> set[str]:
    lines = UNOBSERVED_ALLOWLIST.read_text(encoding="utf-8").splitlines()
    return {
        stripped
        for line in lines
        if (stripped := line.strip()) and not stripped.startswith("#")
    }


def audit_coverage(report: Report) -> list[str]:
    """Return the ways the unobserved set has drifted from the allowlist."""
    allowed = _allowlist()
    unobserved = {entry.split(" ", 1)[0] for entry in report.unobserved}
    verified = set(report.verified)
    problems = [
        f"{member}: no fixture produces a non-empty value, and it is not in "
        f"{UNOBSERVED_ALLOWLIST.name}; add a fixture that exercises it, or "
        f"record the gap there"
        for member in sorted(unobserved - allowed)
    ]
    problems.extend(
        f"{member}: now verified against a live value, so its entry in "
        f"{UNOBSERVED_ALLOWLIST.name} is stale; delete the line"
        for member in sorted(allowed & verified)
    )
    problems.extend(
        f"{member}: listed in {UNOBSERVED_ALLOWLIST.name} but no longer "
        f"declared in any stub; delete the line"
        for member in sorted(allowed - unobserved - verified)
    )
    return problems


def _returns(node: ast.FunctionDef) -> str | None:
    return None if node.returns is None else ast.unparse(node.returns)


def _decorators(node: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            names.add(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            names.add(decorator.attr)
    return names


def _takes_only_self(node: ast.FunctionDef) -> bool:
    args = node.args
    if args.vararg is not None or args.kwonlyargs or args.kwarg:
        return False
    return [arg.arg for arg in args.posonlyargs + args.args] == ["self"]


def _collect_from_class(node: ast.ClassDef, source: Path) -> Iterator[Declaration]:
    for item in node.body:
        if not isinstance(item, ast.FunctionDef):
            continue
        annotation = _returns(item)
        if annotation is None:
            continue
        decorators = _decorators(item)
        is_property = "property" in decorators
        if "setter" in decorators or "staticmethod" in decorators:
            continue
        if not is_property and (
            item.name not in SAFE_METHODS or not _takes_only_self(item)
        ):
            continue
        yield Declaration(node.name, item.name, annotation, is_property, source)


def collect_declarations() -> list[Declaration]:
    """Recover every checkable return annotation from the extension stubs."""
    found: list[Declaration] = []
    for path in STUB_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                found.extend(_collect_from_class(node, path))
    return found


def _namespace() -> dict[str, object]:
    import hier_config
    from hier_config import children, formats, models, platforms, root, workflows
    from hier_config.platforms import models as platform_models
    from hier_config.platforms import view_base

    space: dict[str, object] = {
        "ipaddress": ipaddress,
        "IPv4Address": ipaddress.IPv4Address,
        "IPv4Interface": ipaddress.IPv4Interface,
        "typing": typing,
    }
    space.update(vars(typing))
    for module in (
        children,
        platforms,
        platform_models,
        view_base,
        models,
        formats,
        root,
        workflows,
        hier_config,
    ):
        space.update(
            {
                name: value
                for name, value in vars(module).items()
                if not name.startswith("_")
            },
        )
    _add_stub_aliases(space)
    return space


def _add_stub_aliases(space: dict[str, object]) -> None:
    """Resolve `X: TypeAlias = ...` declarations that exist only in the stubs."""
    for path in STUB_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if (
                not isinstance(node, ast.AnnAssign)
                or not isinstance(node.target, ast.Name)
                or node.value is None
                or ast.unparse(node.annotation) != "TypeAlias"
            ):
                continue
            try:
                # ruff: ignore[suspicious-eval-usage]
                # pylint: disable-next=eval-used
                space[node.target.id] = eval(
                    ast.unparse(node.value),
                    dict(space),
                )
            except PROBE_ERRORS:  # pragma: no cover - alias specific
                continue


def _resolve(annotation: str, space: dict[str, object]) -> object:
    # The input is an annotation lifted verbatim out of a first-party stub in
    # this repository, evaluated in a namespace we build ourselves. There is no
    # untrusted input, and `typing` offers no parser for the union and
    # subscript syntax stubs use.
    return eval(annotation, dict(space))  # ruff: ignore[suspicious-eval-usage]  # pylint: disable=eval-used


def _origin_ok(value: object, origin: object) -> bool:
    if origin is typing.Union or origin is types.UnionType:
        return True
    return isinstance(origin, type) and isinstance(value, origin)


def _check_union(value: object, args: Sequence[object]) -> str | None:
    if any(check_value(value, arg) is None for arg in args):
        return None
    rendered = " | ".join(_render(arg) for arg in args)
    return f"{type(value).__name__} is not one of {rendered}"


# `tuple[T, ...]` -- a homogeneous tuple -- resolves to exactly two args.
VARIADIC_TUPLE_ARGS = 2

#: `typing.get_origin` of a `Callable[...]` annotation.
CallableOrigin = typing.cast("object", collections.abc.Callable)


def _check_tuple(value: tuple[object, ...], args: Sequence[object]) -> str | None:
    if len(args) == VARIADIC_TUPLE_ARGS and args[1] is Ellipsis:
        return _check_elements(value, args[0])
    if len(args) != len(value):
        return f"tuple of {len(value)} does not match {len(args)} declared items"
    for item, arg in zip(value, args, strict=True):
        failure = check_value(item, arg)
        if failure is not None:
            return failure
    return None


def _check_elements(values: object, arg: object) -> str | None:
    if not isinstance(values, (list, tuple, set, frozenset)):
        return None
    items: tuple[object, ...] = tuple(typing.cast("tuple[object, ...]", values))
    for item in items:
        failure = check_value(item, arg)
        if failure is not None:
            return f"element: {failure}"
    return None


def check_value(value: object, annotation: object) -> str | None:
    """Return a description of how ``value`` contradicts ``annotation``."""
    if (
        annotation is typing.Any
        or annotation is object
        or isinstance(annotation, typing.TypeVar)
    ):
        return None
    if annotation is None or annotation is types.NoneType:
        return None if value is None else f"{type(value).__name__} is not None"

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is None:
        if isinstance(annotation, type):
            return (
                None
                if isinstance(value, annotation)
                else f"{type(value).__name__} is not {annotation.__name__}"
            )
        return None

    if origin is CallableOrigin:
        return None if callable(value) else f"{type(value).__name__} is not callable"

    if origin is typing.Union or origin is types.UnionType:
        return _check_union(value, args)
    if not _origin_ok(value, origin):
        return f"{type(value).__name__} is not {_render(annotation)}"
    if origin is tuple and isinstance(value, tuple):
        items: tuple[object, ...] = typing.cast("tuple[object, ...]", value)
        return _check_tuple(items, args)
    if origin is dict:
        return None
    return _check_elements(value, args[0]) if args else None


def _render(annotation: object) -> str:
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return not value
    return False


def _configs() -> Iterator[tuple[str, object]]:
    from hier_config import HConfig, Platform

    prefixes = {
        "aruba_aoscx": Platform.ARUBA_AOSCX,
        "comware5": Platform.HP_COMWARE5,
        "eos": Platform.ARISTA_EOS,
        "fortios": Platform.FORTINET_FORTIOS,
        "ios": Platform.CISCO_IOS,
        "iosxr": Platform.CISCO_XR,
        "junos": Platform.JUNIPER_JUNOS,
        "nxos": Platform.CISCO_NXOS,
        "procurve": Platform.HP_PROCURVE,
        "vyos": Platform.VYOS,
    }
    ordered = sorted(prefixes, key=len, reverse=True)
    for directory in FIXTURE_DIRS:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.conf")):
            prefix = next((p for p in ordered if path.name.startswith(p)), None)
            if prefix is None:
                continue
            try:
                yield prefix, HConfig.from_text(prefixes[prefix], path.read_text())
            except PROBE_ERRORS:  # pragma: no cover - fixture specific
                continue


def build_probes() -> dict[str, list[object]]:
    """Build a corpus of live objects to observe, keyed by class name."""
    from hier_config.platforms.view_base import ConfigViewInterface, HConfigView

    probes: dict[str, list[object]] = {
        name: []
        for name in (
            "ConfigViewInterface",
            "HConfig",
            "HConfigBase",
            "HConfigChild",
            "HConfigChildren",
            "HConfigView",
            "WorkflowRemediation",
        )
    }
    by_platform: dict[str, list[object]] = {}
    for platform, config in _configs():
        by_platform.setdefault(platform, []).append(config)
        probes["HConfig"].append(config)
        probes["HConfigBase"].append(config)
        children: list[object] = list(config.all_children())  # type: ignore[attr-defined]
        probes["HConfigChild"].extend(children[:40])
        probes["HConfigBase"].extend(children[:40])
        probes["HConfigChildren"].append(config.children)  # type: ignore[attr-defined]
        try:
            view = HConfigView(config)  # type: ignore[arg-type]
        except PROBE_ERRORS:  # pragma: no cover - platform specific
            continue
        try:
            interfaces = view.interface_views
        except PROBE_ERRORS:  # pragma: no cover - platform specific
            continue
        probes["HConfigView"].append(view)
        probes["ConfigViewInterface"].extend(interfaces)
    probes["ConfigViewInterface"] = [
        probe
        for probe in probes["ConfigViewInterface"]
        if isinstance(probe, ConfigViewInterface)
    ]
    probes["WorkflowRemediation"] = _workflow_probes(by_platform)
    return probes


def _workflow_probes(by_platform: dict[str, list[object]]) -> list[object]:
    """Pair same-platform configs so remediation and rollback are exercised."""
    from hier_config.workflows import WorkflowRemediation

    built: list[object] = []
    for configs in by_platform.values():
        for running, generated in itertools.pairwise(configs):
            try:
                workflow = WorkflowRemediation(running, generated)  # type: ignore[arg-type]
            except PROBE_ERRORS:  # pragma: no cover - platform specific
                continue
            built.append(workflow)
    built.extend(_plugin_workflow_probes(by_platform))
    return built


def _plugin_workflow_probes(by_platform: dict[str, list[object]]) -> list[object]:
    """Build one workflow carrying a plugin so `plugins` is non-empty.

    Without this every corpus workflow reports an empty tuple, which would
    leave the `Callable` arm of `check_value` permanently unexercised.
    """
    from hier_config.workflows import WorkflowRemediation

    def _noop(config: HConfig) -> None:  # pylint: disable=unused-argument
        """A minimal remediation transform."""

    for configs in by_platform.values():
        if len(configs) < VARIADIC_TUPLE_ARGS:
            continue
        try:
            workflow = WorkflowRemediation(
                configs[0],  # type: ignore[arg-type]
                configs[1],  # type: ignore[arg-type]
                plugins=[_noop],
            )
        except PROBE_ERRORS:  # pragma: no cover - platform specific
            continue
        return [workflow]
    return []


def _observe(probe: object, declaration: Declaration) -> object | None:
    try:
        attribute: object = getattr(probe, declaration.member)
    except PROBE_ERRORS:
        return None
    if declaration.is_property:
        return attribute
    try:
        return typing.cast("typing.Callable[[], object]", attribute)()
    except PROBE_ERRORS:
        return None


def check(declarations: Sequence[Declaration]) -> Report:
    """Check every declaration against every probe of its owning class."""
    space = _namespace()
    probes = build_probes()
    report = Report()
    for declaration in declarations:
        label = f"{declaration.owner}.{declaration.member}"
        targets = probes.get(declaration.owner, [])
        if not targets:
            report.unobserved.append(f"{label} (no probe)")
            continue
        try:
            annotation = _resolve(declaration.annotation, space)
        except (NameError, SyntaxError, TypeError):
            report.unobserved.append(f"{label} (unresolvable annotation)")
            continue
        _check_one(declaration, label, targets, annotation, report)
    return report


def _check_one(
    declaration: Declaration,
    label: str,
    targets: Sequence[object],
    annotation: object,
    report: Report,
) -> None:
    informative = False
    for probe in targets:
        value = _observe(probe, declaration)
        failure = check_value(value, annotation)
        if failure is not None:
            report.mismatches.append(
                f"{label}: declared {declaration.annotation!r}, but {failure}"
                f"  [{declaration.source.name}]",
            )
            return
        informative = informative or not _is_empty(value)
    if informative:
        report.verified.append(label)
    else:
        report.unobserved.append(f"{label} (only empty values observed)")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check and report; return a process exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when a declared return type is contradicted",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="list every member that could not be observed",
    )
    args = parser.parse_args(argv)

    report = check(collect_declarations())
    for mismatch in report.mismatches:
        print(f"error: {mismatch}")
    drift = audit_coverage(report)
    for problem in drift:
        print(f"error: {problem}")
    if args.verbose:
        for entry in report.unobserved:
            print(f"note: unobserved {entry}")
    print(
        f"checked {len(report.verified)} return types against live objects; "
        f"{len(report.unobserved)} unobserved (allowlisted), "
        f"{len(report.mismatches)} mismatched",
    )
    return 1 if args.check and (report.mismatches or drift) else 0


if __name__ == "__main__":
    sys.exit(main())
