from types import ModuleType

from scripts import check_native_surface


def test_surface_check_reports_missing_and_stale_exports() -> None:
    native = ModuleType("native")
    native.__dict__["current"] = str
    assert check_native_surface.surface_errors(
        native, "def removed() -> None: ...\n"
    ) == [
        "missing native export: current",
        "stale native export: removed",
    ]


def test_surface_check_rejects_undocumented_class_members() -> None:
    native = ModuleType("native")
    native.__dict__["Text"] = str
    errors = check_native_surface.surface_errors(native, "class Text: ...\n")
    assert "missing native member: Text.upper" in errors


def test_surface_check_accepts_inherited_stub_members() -> None:
    native = ModuleType("native")
    native.__dict__["Text"] = str
    methods = "\n".join(
        f"    def {name}(self) -> object: ..."
        for name in dir(str)
        if not name.startswith("_")
    )
    stub = f"class TextBase:\n{methods}\nclass Text(TextBase): ...\n"
    # TextBase is also exported so its declaration is not a stale API entry.
    native.__dict__["TextBase"] = str
    assert not check_native_surface.surface_errors(native, stub)
