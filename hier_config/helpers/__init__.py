"""
Place any reusable functions for parsing HConfig object here
"""


def to_list(obj):
    if isinstance(obj, list):
        return obj
    else:
        return [obj]
