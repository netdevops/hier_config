"""Generate .pyi stubs for the Rust-backed hier_config tree types.

Ground truth for *what exists* is the live extension module. Prose and type
annotations are recovered from the last pure-Python release (v3.7.0) so the
API reference keeps its documentation. Members with no v3.7.0 counterpart are
emitted without annotations rather than guessing a type.

Why these stubs exist
---------------------
``hier_config.base``/``child``/``children``/``root`` are re-export shims for a
compiled extension. Neither mypy nor griffe (mkdocstrings) can read a ``.so``,
so without stubs every tree type is ``Any`` to downstream users and the API
reference fails to build outright. See docs/dev/architecture.md.

Usage
-----
Rebuild the extension first, since existence is probed at runtime::

    maturin develop --release
    python scripts/gen_stubs.py
    ruff check --fix hier_config/*.pyi && ruff format hier_config/*.pyi

``hier_config/exceptions.pyi`` is maintained by hand -- it is short, and the
exception hierarchy is a deliberate API decision rather than something to
mirror from a baseline.
"""

from __future__ import annotations

import argparse
import ast
import copy
import inspect
import pathlib
import subprocess
import sys

BASELINE = "98a9a49"
MODULES = ("base", "child", "children", "root")
STUB_DIR = pathlib.Path(__file__).resolve().parent.parent / "hier_config"

# runtime class -> (stub module, base class in stub)
CLASSES = {
    "HConfigBase": ("base", None),
    "HConfigChildren": ("children", None),
    "HConfigChild": ("child", "HConfigBase"),
    "HConfig": ("root", "HConfigBase"),
}

HEADERS = {
    "base": [
        "from collections.abc import Iterable, Iterator, Sequence",
        "from typing import Any",
        "",
        "from hier_config.child import HConfigChild",
        "from hier_config.children import HConfigChildren",
        "from hier_config.models import Dump, MatchRule, TagRule, TextStyle",
        "from hier_config.root import HConfig",
        "",
        "SetLikeOfStr = frozenset[str] | set[str]",
    ],
    "children": [
        "from collections.abc import Iterable, Iterator",
        "from typing import Any, TypeVar, overload",
        "",
        "from hier_config.child import HConfigChild",
        "",
        '_D = TypeVar("_D")',
    ],
    "child": [
        "from collections.abc import Iterable, Iterator",
        "from typing import Any",
        "",
        "from hier_config.base import HConfigBase",
        "from hier_config.models import Dump, Instance, MatchRule, TagRule",
        "from hier_config.platforms.driver_base import HConfigDriverBase",
        "from hier_config.root import HConfig",
        "",
        "SetLikeOfStr = frozenset[str] | set[str]",
    ],
    "root": [
        "from collections.abc import Iterable, Iterator, Sequence",
        "from os import PathLike",
        "from typing import Any",
        "",
        "from hier_config.base import HConfigBase",
        "from hier_config.child import HConfigChild",
        "from hier_config.models import Dump, DumpLine, MatchRule, Platform, TagRule",
        "from hier_config.tree_algorithms import FutureReport",
        "from hier_config.platforms.driver_base import HConfigDriverBase",
    ],
}

# v4 renamed a number of members (#300) and kept the v3 spellings as permanent
# aliases, so both names reach the same Rust implementation and necessarily share
# a signature.  Recovering the v4 name's signature from its v3 counterpart means
# the two can never drift, and the v3.7.0 docstring is inherited for free.
V4_ALIASES: dict[str, str] = {
    "add_tags": "tags_add",
    "indented_text": "cisco_style_text",
    "remediation": "config_to_get_to",
    "remove_tags": "tags_remove",
    "to_lines": "dump_simple",
}

# Members the extension exposes that have no v3.7.0 `def` to recover a signature
# from -- they were plain instance attributes, or are new to the Rust port.
# Types are taken from the Rust definitions in `crates/hier_config_py/src/`.
OVERRIDES: dict[str, tuple[str, str | None]] = {
    "HConfigChild.comments": ("set[str]", "Iterable[str]"),
    "HConfigChild.facts": ("dict[str, Any]", "dict[str, Any]"),
    "HConfigChild.instances": ("list[Instance]", "Iterable[Instance]"),
    "HConfigChild.order_weight": ("int", "int"),
    "HConfigChild.new_in_config": ("bool", "bool"),
    "HConfigChild.real_indent_level": ("int", "int"),
    # A nested child's parent is the enclosing `HConfigChild`, not the root;
    # only a top-level child's parent is the `HConfig`.  The signature is
    # recovered from `HConfig.add_child`, which sees just the root case, so it
    # has to be stated explicitly here.
    "HConfigChild.parent": ("HConfig | HConfigChild", "HConfig | HConfigChild"),
    "HConfigBase.children": ("HConfigChildren", None),
    "HConfigBase.del_child": ("(self, child: HConfigChild) -> None", None),
    "HConfigBase.del_child_by_text": ("(self, text: str) -> None", None),
    "HConfigBase.move_child": ("(self, child: HConfigChild) -> None", None),
    "HConfigBase.get_children_object": ("(self) -> HConfigChildren", None),
    "HConfigChildren.__delitem__": ("(self, key: str, /) -> None", None),
    "HConfig.__deepcopy__": ("(self, _memo: dict[int, Any]) -> HConfig", None),
}

# The v3.7.0 implementations were generators, but the Rust port returns eager
# collections (`tuple`/`list`).  Keeping the recovered `Iterator[...]` would be a
# lie -- callers can index these results and iterate them more than once.  Only
# the return annotation is replaced, so the recovered docstring survives intact.
RETURN_OVERRIDES: dict[str, str] = {
    "HConfigBase.all_children_sorted_by_tags": "Sequence[HConfigChild]",
    "HConfigBase.get_children": "Sequence[HConfigChild]",
    "HConfigBase.get_children_deep": "Sequence[HConfigChild]",
    "HConfigBase.lineage": "Sequence[HConfigChild]",
    "HConfigBase.path": "Sequence[str]",
    "HConfigBase.unified_diff": "Sequence[str]",
    "HConfig.unused_objects": "Sequence[HConfigChild]",
}

# Members whose stub text cannot be expressed as a single signature -- emitted
# verbatim.  `OVERRIDES` renders exactly one `def`, so anything needing
# `@overload` has to live here.
RAW_OVERRIDES: dict[str, list[str]] = {
    "HConfig.__hash__": [
        "    def __hash__(self) -> int: ...",
    ],
    "HConfigBase.__hash__": [
        "    def __hash__(self) -> int: ...",
    ],
    "HConfigChild.__hash__": [
        "    def __hash__(self) -> int: ...",
    ],
    "HConfigChildren.__hash__": [
        "    def __hash__(self) -> int: ...",
    ],
    "HConfig.__eq__": [
        "    def __eq__(self, other: object) -> bool: ...",
    ],
    "HConfigBase.__eq__": [
        "    def __eq__(self, other: object) -> bool: ...",
    ],
    "HConfigChild.__eq__": [
        "    def __eq__(self, other: object) -> bool: ...",
    ],
    "HConfigChildren.__eq__": [
        "    def __eq__(self, other: object) -> bool: ...",
    ],
    # v4 turned `depth` from a method into a property (see the migration guide).
    "HConfigBase.depth": [
        "    @property",
        "    def depth(self) -> int:",
        '        """Distance from the root of the configuration tree."""',
    ],
    # `hier_config.constructors` drives these private native loaders directly.
    "HConfig._load_native": [
        "    def _load_native(self, config_text: str, run_post_load: bool) -> None: ...",
    ],
    "HConfig._load_fast_native": [
        "    def _load_fast_native(",
        "        self, lines: Iterable[str], run_post_load: bool",
        "    ) -> None: ...",
    ],
    "HConfig._load_file_native": [
        "    def _load_file_native(self, path: str, run_post_load: bool) -> None: ...",
    ],
    "HConfig._load_from_dump_native": [
        "    def _load_from_dump_native(self, lines: Iterable[DumpLine]) -> None: ...",
    ],
    "HConfigChild._default": [
        "    def _default(self) -> None:",
        '        """Prefix the line with `default `, in place."""',
    ],
    # Subscripting accepts an index/key or a slice, and the return type depends
    # on which: a slice yields a `list`.  Collapsing that to one signature would
    # force every caller to narrow a union the type checker could have resolved.
    "HConfigChildren.__getitem__": [
        "    @overload",
        "    def __getitem__(self, subscript: int | str) -> HConfigChild:",
        '        """Return self[key]."""',
        "",
        "    @overload",
        "    def __getitem__(self, subscript: slice) -> list[HConfigChild]:",
        '        """Return self[key]."""',
    ],
    # New in v4, so there is no v3.7.0 `def` to recover.  Types are taken from
    # the Rust definitions in `crates/hier_config_py/src/root.rs`.
    "HConfig.from_text": [
        "    @classmethod",
        "    def from_text(",
        "        cls,",
        "        platform_or_driver: Platform | str | HConfigDriverBase,",
        "        config_text: str | PathLike[str] | None = None,",
        "    ) -> HConfig: ...",
    ],
    "HConfig.from_lines": [
        "    @classmethod",
        "    def from_lines(",
        "        cls,",
        "        platform_or_driver: Platform | str | HConfigDriverBase,",
        "        lines: Iterable[str],",
        "    ) -> HConfig: ...",
    ],
    "HConfig.from_dump": [
        "    @classmethod",
        "    def from_dump(",
        "        cls,",
        "        platform_or_driver: Platform | str | HConfigDriverBase,",
        "        dump: Dump,",
        "    ) -> HConfig: ...",
    ],
    "HConfig.from_json": [
        "    @classmethod",
        "    def from_json(",
        "        cls,",
        "        platform_or_driver: Platform | str | HConfigDriverBase,",
        "        data: str | dict[str, Any],",
        "        *,",
        "        list_keys: tuple[str, ...] | None = None,",
        "    ) -> HConfig: ...",
    ],
    "HConfig.from_xml": [
        "    @classmethod",
        "    def from_xml(",
        "        cls,",
        "        platform_or_driver: Platform | str | HConfigDriverBase,",
        "        source: str,",
        "        *,",
        "        list_keys: tuple[str, ...] | None = None,",
        "    ) -> HConfig: ...",
    ],
    "HConfig.to_json": [
        "    def to_json(self, *, indent: int | None = 2) -> str:",
        '        """Render a tree built by `from_json` back to JSON text."""',
    ],
    "HConfig.to_xml": [
        "    def to_xml(self, *, indent: int | None = 2) -> str:",
        '        """Render a tree built by `from_xml` back to XML text."""',
    ],
    "HConfig.future_with_report": [
        "    def future_with_report(",
        "        self,",
        "        config: HConfig,",
        "        *,",
        "        prune_empty_branches: bool = False,",
        "    ) -> tuple[HConfig, FutureReport]:",
        '        """Like `future()`, but also reports how negations resolved."""',
    ],
}

SKIP = {
    "__class__",
    "__delattr__",
    "__dict__",
    "__dir__",
    "__doc__",
    "__format__",
    "__getattribute__",
    "__getstate__",
    "__init_subclass__",
    "__module__",
    "__new__",
    "__reduce_ex__",
    "__setattr__",
    "__sizeof__",
    "__subclasshook__",
    "__ne__",
    "__dictoffset__",
    "__basicsize__",
}

# Dunders `object` also defines, so the "not inherited" test discards them even
# though the extension overrides them.  `object.__lt__` exists only to return
# `NotImplemented`, so leaving `__lt__` out of the stub tells type checkers that
# children are unorderable -- and `sorted(config.children)`, which the library
# itself relies on, fails to type check for downstream users.
#
# Keyed by `Class.member`, because PyO3 installs a `__lt__` slot wrapper on
# every pyclass whether or not it implements ordering: `HConfig` and
# `HConfigChildren` both expose one that raises `TypeError`, so only
# `HConfigChild` may be advertised as orderable.
#
# `__eq__` is deliberately absent: `object.__eq__` already carries the right
# signature, so re-emitting it would add noise without adding information.
# `__eq__` is the same situation: the extension overrides it on every class,
# but `object` defines it too, so the "not inherited" test drops it. Without it
# in the stub a type checker assumes identity comparison and reports every
# `config == <other type>` assertion as a non-overlapping equality check.
FORCE_EMIT = {
    "HConfigChild.__lt__",
    "HConfig.__eq__",
    "HConfigBase.__eq__",
    "HConfigChild.__eq__",
    "HConfigChildren.__eq__",
    "HConfig.__hash__",
    "HConfigBase.__hash__",
    "HConfigChild.__hash__",
    "HConfigChildren.__hash__",
}


def original_defs() -> dict[str, ast.AST]:
    """Map ``ClassName.member`` -> AST node from the v3.7.0 sources."""
    out: dict[str, ast.AST] = {}
    for module in MODULES:
        src = subprocess.run(
            ["git", "show", f"{BASELINE}:hier_config/{module}.py"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for node in ast.parse(src).body:
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.setdefault(f"{node.name}.{item.name}", item)
                elif isinstance(item, ast.AnnAssign) and isinstance(
                    item.target, ast.Name
                ):
                    out.setdefault(f"{node.name}.{item.target.id}", item)
    return out


def baseline_class_doc(cls_name: str, module: str) -> str:
    """Recover a class docstring from the pre-Rust baseline.

    PyO3 classes carry their own docstrings, but where one is missing the
    v3.7.0 Python source remains the reference text.
    """
    src = subprocess.run(
        ["git", "show", f"{BASELINE}:hier_config/{module}.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    node = next(
        (
            n
            for n in ast.parse(src).body
            if isinstance(n, ast.ClassDef) and n.name == cls_name
        ),
        None,
    )
    return (node and ast.get_docstring(node, clean=True)) or f"{cls_name}."


def docstring_lines(doc: str) -> list[str]:
    """Render a docstring as indented stub lines."""
    body = doc.strip().split("\n")
    if len(body) == 1:
        return [f'    """{body[0]}"""']
    return [
        f'    """{body[0]}',
        *(f"    {line}".rstrip() for line in body[1:]),
        '    """',
    ]


def class_member(cls: type, name: str) -> object:
    """Return a class attribute as a plainly-typed object.

    `vars()` on a type yields an untyped mapping, which strict type checkers
    flag when the result is passed on. Narrowing it here keeps `main()` clean.
    """
    return vars(cls)[name]


def runtime_owned(cls: type) -> list[str]:
    """Public + dunder members defined directly on ``cls`` (not inherited)."""
    inherited: set[str] = set()
    for base in cls.__mro__[1:]:
        inherited |= set(vars(base))
    names = [
        n
        for n in vars(cls)
        if n not in SKIP
        and (n not in inherited or f"{cls.__name__}.{n}" in FORCE_EMIT)
        and (not n.startswith("_") or (n.startswith("__") and n.endswith("__")))
    ]
    names += [
        n
        for n in vars(cls)
        if n.startswith("_")
        and not (n.startswith("__") and n.endswith("__"))
        and f"{cls.__name__}.{n}" in RAW_OVERRIDES
    ]
    return sorted(names)


def writable_members(cls_name: str) -> set[str]:
    """Names that accept assignment on a live instance (ground truth)."""
    import hier_config
    from hier_config.models import Platform

    cfg = hier_config.get_hconfig(
        Platform.CISCO_IOS, "interface Gi0/1\n  description x\n"
    )
    child = next(iter(cfg.all_children()))
    subject = {
        "HConfig": cfg,
        "HConfigChild": child,
        "HConfigBase": child,
        "HConfigChildren": cfg.children,
    }.get(cls_name)
    if subject is None:
        return set()
    out: set[str] = set()
    for name in dir(type(subject)):
        if name.startswith("_"):
            continue
        try:
            current = getattr(subject, name)
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        if callable(current) and not isinstance(
            current, (str, int, bool, frozenset, set)
        ):
            continue
        try:
            setattr(subject, name, current)
        except AttributeError:
            continue
        except Exception:  # pylint: disable=broad-exception-caught
            out.add(name)
            continue
        out.add(name)
    return out


# pylint: disable=too-many-branches,too-many-statements
def render(
    cls_name: str,
    name: str,
    obj: object,
    defs: dict[str, ast.AST],
    writable: bool = False,
) -> list[str]:
    node = defs.get(f"{cls_name}.{name}")
    # Fall back to a definition of the same name on any v3.7.0 class.
    if node is None:
        node = next((v for k, v in defs.items() if k.rsplit(".", 1)[1] == name), None)
    # ...then to the v3 spelling this member is the v4 alias of.
    if node is None and (alias := V4_ALIASES.get(name)):
        node = defs.get(f"{cls_name}.{alias}") or next(
            (v for k, v in defs.items() if k.rsplit(".", 1)[1] == alias), None
        )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node = copy.deepcopy(node)
            node.name = name

    raw = RAW_OVERRIDES.get(f"{cls_name}.{name}")
    if raw:
        return [*raw, ""]

    override = OVERRIDES.get(f"{cls_name}.{name}")
    if override and override[0].startswith("("):
        doc = inspect.getdoc(obj) or ""
        out = [f"    def {name}{override[0]}: ..."]
        if doc:
            out[-1] = out[-1].removesuffix(" ...")
            out.append(f'        """{doc.splitlines()[0]}"""')
        return out + [""]
    if override:
        doc = inspect.getdoc(obj) or ""
        out = ["    @property", f"    def {name}(self) -> {override[0]}: ..."]
        if doc:
            out[-1] = out[-1].removesuffix(" ...")
            out.append(f'        """{doc.splitlines()[0]}"""')
        if override[1] and writable:
            out.append(f"    @{name}.setter")
            out.append(f"    def {name}(self, value: {override[1]}) -> None: ...")
        return out + [""]

    doc = inspect.getdoc(obj) or ""
    if not doc and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        doc = ast.get_docstring(node, clean=True) or ""

    is_prop = isinstance(obj, (property, type(type.__dict__["__name__"])))
    lines: list[str] = []

    if isinstance(node, ast.AnnAssign):
        lines.append(f"    {ast.unparse(node)}")
        if doc:
            lines.append(f'    """{doc.splitlines()[0]}"""')
        return lines + [""]

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        clone = copy.deepcopy(node)
        decorators = [
            ast.unparse(d)
            for d in clone.decorator_list
            if ast.unparse(d) in {"property", "staticmethod", "classmethod"}
            or ast.unparse(d).endswith(".setter")
        ]
        clone.decorator_list = []
        clone.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
        forced = RETURN_OVERRIDES.get(f"{cls_name}.{name}")
        if forced:
            clone.returns = ast.parse(forced, mode="eval").body
        header = ast.unparse(clone).split("\n", maxsplit=1)[0]
        if not header.endswith("..."):
            header = f"{header.rstrip()} ..."
        lines.extend(f"    @{d}" for d in decorators)
        lines.append(f"    {header}")
    elif is_prop:
        lines.append("    @property")
        lines.append(f"    def {name}(self): ...")
    else:
        sig = getattr(obj, "__text_signature__", None)
        if sig:
            sig = (
                sig.replace("($self", "(self")
                .replace("($cls", "(cls")
                .replace("($module", "(cls")
            )
            lines.append(f"    def {name}{sig}: ...")
        else:
            lines.append(f"    {name}: Any")
            if doc:
                lines.insert(0, "")
            return lines + [""]

    if doc:
        body = doc.strip().split("\n")
        indent = "        "
        lines[-1] = lines[-1].removesuffix("...").rstrip()
        if not lines[-1].endswith(":"):
            lines[-1] += ":"
        if len(body) == 1:
            lines.append(f'{indent}"""{body[0]}"""')
        else:
            lines.append(f'{indent}"""{body[0]}')
            lines.extend(f"{indent}{line}".rstrip() for line in body[1:])
            lines.append(f'{indent}"""')
        lines.append(f"{indent}...")

    if writable:
        ann = "Any"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns:
            ann = ast.unparse(node.returns)
        lines.append("")
        lines.append(f"    @{name}.setter")
        lines.append(f"    def {name}(self, value: {ann}) -> None: ...")
    return lines + [""]


def ruff_fix(paths: list[pathlib.Path]) -> None:
    """Apply the ruff passes the committed stubs are normalised with.

    Invoked through ``sys.executable -m`` so it works regardless of whether the
    virtualenv's ``bin`` directory is on ``PATH``.
    """
    names = [str(path) for path in paths]
    for argv in (["check", "--fix", "-q"], ["format", "-q"]):
        subprocess.run([sys.executable, "-m", "ruff", *argv, *names], check=True)


def parse_check_flag() -> bool:
    """Return True when invoked with ``--check``."""
    parser = argparse.ArgumentParser(description="Generate hier_config .pyi stubs.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed stubs differ; never modify the tree.",
    )
    return bool(parser.parse_args().check)


def normalise_and_diff(
    targets: list[pathlib.Path], originals: dict[pathlib.Path, str]
) -> list[pathlib.Path]:
    """Ruff-normalise `targets` and return those differing from `originals`."""
    ruff_fix(targets)
    return [path for path in targets if path.read_text() != originals[path]]


def verify(targets: list[pathlib.Path], originals: dict[pathlib.Path, str]) -> int:
    """Normalise the freshly written stubs, diff them, then restore `originals`.

    The restore runs unconditionally so a failed check never leaves the working
    tree dirty -- CI reports drift, it does not repair it.
    """
    try:
        drifted = normalise_and_diff(targets, originals)
    finally:
        for path, original in originals.items():
            path.write_text(original)

    if not drifted:
        return 0
    print("Committed stubs are out of date:", file=sys.stderr)
    for path in drifted:
        print(f"  hier_config/{path.name}", file=sys.stderr)
    print("\nRegenerate with:  python scripts/gen_stubs.py", file=sys.stderr)
    return 1


def main() -> int:
    import _hier_config_rust as _native

    check = parse_check_flag()
    defs = original_defs()
    targets = [STUB_DIR / f"{module}.pyi" for module in MODULES]
    # Generation happens in place even under --check: ruff's per-file ignores are
    # keyed on `hier_config/*.pyi`, so generating anywhere else would lint
    # differently. Originals are restored below, so the tree is left untouched.
    originals = {path: path.read_text() for path in targets} if check else {}
    for cls_name, (module, base) in CLASSES.items():
        cls = getattr(_native, cls_name)
        lines = [
            "# Type stubs for the Rust-backed implementation in `_hier_config_rust`.",
            "#",
            "# griffe (mkdocstrings) and mypy cannot introspect a compiled extension,",
            "# so this stub is the documented, typed view of the native class. It is",
            "# generated from the live extension surface plus the v3.7.0 docstrings;",
            "# see docs/dev/architecture.md.",
            "",
        ]
        lines.extend(HEADERS[module])
        lines.append("")
        decl = f"class {cls_name}({base}):" if base else f"class {cls_name}:"
        lines.append(decl)
        doc = inspect.getdoc(cls) or baseline_class_doc(cls_name, module)
        lines.extend(docstring_lines(doc))
        lines.append("")

        ctor = getattr(cls, "__text_signature__", None)
        if ctor:
            init = defs.get(f"{cls_name}.__init__")
            if isinstance(init, (ast.FunctionDef, ast.AsyncFunctionDef)):
                clone = copy.deepcopy(init)
                clone.decorator_list = []
                clone.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
                header = ast.unparse(clone).split("\n", maxsplit=1)[0]
                if not header.endswith("..."):
                    header = f"{header.rstrip()} ..."
                lines.append(f"    {header}")
            else:
                lines.append(f"    def __init__{ctor.replace('($self', '(self')}: ...")
            lines.append("")

        writable = writable_members(cls_name)
        for name in runtime_owned(cls):
            lines.extend(
                render(cls_name, name, class_member(cls, name), defs, name in writable)
            )

        rendered = "\n".join(lines).rstrip()
        text = f"{rendered}\n"
        (STUB_DIR / f"{module}.pyi").write_text(text)
        if not check:
            print(f"wrote hier_config/{module}.pyi  ({text.count(chr(10))} lines)")

    if check:
        return verify(targets, originals)
    ruff_fix(targets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
