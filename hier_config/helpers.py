"""
Place any reusable functions for parsing HConfig object here
"""


def to_list(obj):
    """
    Consume an object and make it a single item list if it's
    not already a list.

    :param obj:
    :return: [obj]
    """
    if isinstance(obj, list):
        return obj
    else:
        return [obj]


def extend_builtin(hconfig_options, os):
    """
    Consumes options provided by a user and extends the builtin
    default options

    :param hconfig_options: type dict
    :param os: type str
    :return: default_options -> type dict
    """
    from hier_config.builtin import options

    default_options = options[os]

    for item in hconfig_options:
        if item in options[os]:
            default_options[item] = hconfig_options[item] + options[os][item]
        else:
            default_options[item] = hconfig_options[item]

    return default_options
