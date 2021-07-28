class HConfigOptions:
    def __init__(self, os: str):
        if os == "ios":
            self.options = self.ios()

    def ios(self):
        return {
            "style": "ios",
            "sectional_overwrite": [],
            "sectional_overwrite_no_negate": [],
            "ordering": [
                {"lineage": [{"startswith": "no vlan filter"}], "order": 700},
                {
                    "lineage": [
                        {"startswith": "interface"},
                        {"startswith": "no shutdown"},
                    ],
                    "order": 700,
                },
            ],
            "indent_adjust": [],
            "parent_allows_duplicate_child": [],
            "sectional_exiting": [
                {
                    "lineage": [
                        {"startswith": "router bgp"},
                        {"startswith": "template peer-policy"},
                    ],
                    "exit_text": "exit-peer-policy",
                },
                {
                    "lineage": [
                        {"startswith": "router bgp"},
                        {"startswith": "template peer-session"},
                    ],
                    "exit_text": "exit-peer-session",
                },
                {
                    "lineage": [
                        {"startswith": "router bgp"},
                        {"startswith": "address-family"},
                    ],
                    "exit_text": "exit-address-family",
                },
            ],
            "full_text_sub": [],
            "per_line_sub": [
                {"search": "^Building configuration.*", "replace": ""},
                {"search": "^Current configuration.*", "replace": ""},
                {"search": "^! Last configuration change.*", "replace": ""},
                {"search": "^! NVRAM config last updated.*", "replace": ""},
                {"search": "^ntp clock-period .*", "replace": ""},
                {"search": "^version.*", "replace": ""},
                {"search": "^ logging event link-status$", "replace": ""},
                {"search": "^ logging event subif-link-status$", "replace": ""},
                {"search": "^\\s*ipv6 unreachables disable$", "replace": ""},
                {"search": "^end$", "replace": ""},
                {"search": "^\\s*[#!].*", "replace": ""},
                {"search": "^ no ip address", "replace": ""},
                {"search": "^ exit-peer-policy", "replace": ""},
                {"search": "^ exit-peer-session", "replace": ""},
                {"search": "^ exit-address-family", "replace": ""},
                {"search": "^crypto key generate rsa general-keys.*$", "replace": ""},
            ],
            "idempotent_commands_blacklist": [],
            "idempotent_commands": [
                {"lineage": [{"startswith": "vlan"}, {"startswith": "name"}]},
                {
                    "lineage": [
                        {"startswith": "interface"},
                        {"startswith": ["description", "ip address"]},
                    ]
                },
            ],
            "negation_default_when": [],
            "negation_negate_with": [],
        }
