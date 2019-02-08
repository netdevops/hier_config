"""
Place any reusable functions for parsing HConfig object here
"""


def to_list(obj):
    from types import GeneratorType
    if isinstance(obj, (list, tuple, set, GeneratorType)):
        return list(obj)
    elif obj or obj is None:
        return [obj]
    return []
