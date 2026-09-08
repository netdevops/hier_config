"""Probe script for verifying parity with the legacy object protocol."""

# pylint: disable=broad-exception-caught,too-many-try-statements,too-many-statements,too-few-public-methods

import copy
import pickle
from hier_config import HConfigChild, get_hconfig
from hier_config.base import HConfigBase
from hier_config.models import Platform


def probe() -> str:
    hc = get_hconfig(Platform.CISCO_IOS)
    c = hc.add_child("interface GigabitEthernet0/1")
    c.add_child("ip address 10.0.0.1 255.255.255.0")

    results = []

    # 1. Object identity
    first_get = hc.children[0]
    second_get = hc.children[0]
    results.append(f"identity: {first_get is second_get}")

    # 2. setattr (__slots__ behavior)
    try:
        c.custom_attr = "hello_probe"
        results.append(f"setattr: {c.custom_attr}")
    except AttributeError:
        results.append("setattr: AttributeError (has __slots__)")
    except Exception as e:
        results.append(f"setattr: {type(e).__name__}: {e}")

    # 3. facts dict
    c.facts["custom_key"] = "hello_facts"
    results.append(f"facts: {c.facts.get('custom_key')}")

    # 4. deepcopy
    try:
        d = copy.deepcopy(hc)
        results.append(f"deepcopy: OK len={len(list(d.all_children()))}")
    except Exception as e:
        results.append(f"deepcopy: {type(e).__name__}: {e}")

    # 5. pickle
    try:
        p = pickle.dumps(hc)
        loaded = pickle.loads(p)
        results.append(f"pickle: OK len={len(list(loaded.all_children()))}")
    except Exception as e:
        results.append(f"pickle: {type(e).__name__}: {e}")

    # 6. subclassing
    try:

        class CustomChild(HConfigChild):
            """Subclass probe."""

            def custom_method(self):
                return "custom"

        results.append(f"subclass: OK {CustomChild.__name__}")
    except Exception as e:
        results.append(f"subclass: {type(e).__name__}: {e}")

    # 7. tags (frozenset & tags_add)
    c.tags_add("tag_x")
    results.append(f"tags_type: {type(c.tags).__name__}")
    results.append(f"tags_contain: {'tag_x' in c.tags}")

    # 8. live comments mutation
    c.comments.add("comment_x")
    results.append(f"comments_mutation: {'comment_x' in c.comments}")

    # 9. children container
    results.append(f"children_type: {type(c.children).__name__}")

    # 10. vars / __dict__
    results.append(f"has_dict: {hasattr(c, '__dict__')}")

    # 11. class hierarchy
    results.append(f"hc_is_child: {isinstance(hc, HConfigChild)}")
    results.append(f"hc_is_base: {isinstance(hc, HConfigBase)}")
    results.append(f"child_is_base: {isinstance(c, HConfigBase)}")

    # 12. repr
    try:
        child_repr = repr(c)
        results.append(f"child_repr: {child_repr}")
    except Exception as e:
        results.append(f"child_repr: {type(e).__name__}")

    try:
        hc_repr = repr(hc)
        results.append(f"hc_repr: {hc_repr}")
    except Exception as e:
        results.append(f"hc_repr: {type(e).__name__}")

    output = "\n".join(results)
    return output


if __name__ == "__main__":
    print(probe())
