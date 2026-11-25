//! Contracts that cannot be inferred from dynamic Python objects alone.

fn rendered_stub() -> String {
    pyo3::Python::initialize();
    _hier_config_rust::stub_info()
        .expect("binding metadata is valid")
        .modules
        .get("hier_config._hier_config_rust")
        .expect("canonical native module is registered")
        .to_string()
}

#[test]
fn generation_is_deterministic_and_declares_native_types_directly() {
    let rendered = rendered_stub();
    assert_eq!(rendered, rendered_stub());
    for declaration in [
        "class HConfig(",
        "class HConfigBase:",
        "class HConfigChild(",
        "class HConfigChildren:",
        "class WorkflowRemediation:",
        "class HierConfigError(",
        "class DuplicateChildError(HierConfigError):",
        "class InvalidConfigError(HierConfigError):",
        "import hier_config.models",
        "import hier_config.platforms.models",
        "def to_json(self, *, indent: typing.Optional[builtins.int] = 2)",
    ] {
        assert!(rendered.contains(declaration), "missing {declaration}");
    }
    assert!(!rendered.contains("typing.Any"));
    assert!(!rendered.contains("Some("));
    assert!(!rendered.contains("from hier_config.root import"));
}

#[test]
fn dynamic_contracts_preserve_overloads_and_setter_inputs() {
    let rendered = rendered_stub();
    for signature in [
        "def __getitem__(self, item: int | str, /) -> HConfigChild:",
        "def __getitem__(self, item: slice, /) -> list[HConfigChild]:",
        "def get(self, key: str, default: None = None) -> HConfigChild | None:",
        "def get(self, key: str, default: hier_config._typing.DefaultT) -> HConfigChild | hier_config._typing.DefaultT:",
        "def tags(self, value: collections.abc.Iterable[str]) -> None:",
        "def comments(self, value: collections.abc.Iterable[str]) -> None:",
        "def instances(self, value: collections.abc.Iterable[hier_config.models.Instance]) -> None:",
        "def __deepcopy__(self, memo: dict[int, object]) -> HConfig:",
        "def __deepcopy__(self, memo: dict[int, object]) -> HConfigChild:",
        "data: str | dict[str, hier_config._typing.ValueT]",
        "def remediation_json(self, *, list_keys: tuple[str, ...] | None = None) -> hier_config.formats.GnmiRemediation:",
    ] {
        assert!(rendered.contains(signature), "missing {signature}");
    }
    assert_eq!(rendered.matches("@typing.overload").count(), 4);
    assert_eq!(rendered.matches("Return key in self.").count(), 2);
}

#[test]
fn subclassable_constructors_preserve_the_requested_subclass() {
    let rendered = rendered_stub();
    let constructors: Vec<_> = rendered
        .lines()
        .filter(|line| line.contains("def __new__("))
        .collect();
    assert_eq!(constructors.len(), 5);
    for constructor in constructors {
        assert!(
            constructor.contains(" -> typing_extensions.Self:"),
            "{constructor}"
        );
    }
}

#[test]
fn python_argument_documentation_uses_unquoted_parameter_names() {
    let rendered = rendered_stub();
    for name in ["re_search", "tag_rules", "include_tags", "exclude_tags"] {
        assert!(!rendered.contains(&format!("`{name}`:")));
        assert!(!rendered.contains(&format!("`{name}` (")));
    }
    assert!(rendered.contains("re_search: str | None = None"));
}
