defaults = {
    "sectional_overwrite": [],
    "sectional_overwrite_no_negate": [],
    "ordering": [],
    "indent_adjust": [],
    "parent_allows_duplicate_child": [],
    "sectional_exiting": [],
    "full_text_sub": [],
    "per_line_sub": [],
    "idempotent_commands_blacklist": [],
    "idempotent_commands": [],
    "negation_default_when": [],
    "negation_negate_with": [],
}

options = {
    "ios": defaults.update({"style": "ios"}),
    "iosxr": defaults.update({"style": "iosxr"}),
    "nxos": defaults.update({"style": "nxos"}),
    "eos": defaults.update({"style": "eos"}),
}