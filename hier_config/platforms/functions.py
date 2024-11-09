from __future__ import annotations

import re


def expand_range(number_range_str: str) -> tuple[int, ...]:
    """Expand ranges like 2-5,8,22-45."""
    numbers: list[int] = []
    for number_range in number_range_str.split(","):
        start_stop = number_range.split("-")
        if len(start_stop) == 2:
            start = int(start_stop[0])
            stop = int(start_stop[1])
            numbers.extend(n for n in range(start, stop + 1))
        else:
            numbers.append(int(start_stop[0]))
    assert len(set(numbers)) == len(numbers)
    return tuple(numbers)


def expand_vlan_range(vlan_config: str) -> tuple[int, ...]:
    """
    Given an IOS-like vlan list of configurations, return the list of VLANs.

    Args:
        vlan_config: IOS-like vlan list of configurations.

    Returns:
        Sorted string list of integers according to IOS-like vlan list rules

    Examples:
        >>> vlan_config = '''switchport trunk allowed vlan 1025,1069-1072,1114,1173-1181,1501,1502'''
        >>> expand_vlan_range(vlan_config)
        [1025, 1069, 1070, 1071, 1072, 1114, 1173, 1174, 1175, 1176, 1177, 1178, 1179, 1180, 1181, 1501, 1502]
        >>>

    """
    # Check for invalid data within the vlan_config
    # example: switchport trunk allowed vlan 1025,1069-1072,BADDATA
    invalid_data = re.findall(r",?[^0-9\-],?$", vlan_config)
    # Regular VLANs that are not condensed and can be converted to integers
    vlans = list(map(int, re.findall(r"\d+", vlan_config)))

    # Fail if invalid data is found
    if invalid_data and vlans:
        message = f"There were non-digits and dashes found in `{vlan_config}`."
        raise ValueError(message)
    if invalid_data:
        message = f"No digits found in `{vlan_config}`"
        raise ValueError(message)

    vlan_ranges = re.findall(r"\d+-\d+", vlan_config)
    for v_range in vlan_ranges:
        first, second = v_range.split("-")
        # Add one to first to prevent duplicates that already exist within vlans
        vlans.extend(list(range(*[int(first) + 1, int(second)])))

    vlans = sorted(vlans)
    if vlans[-1] > 4094:
        message = f"Valid VLAN range is 1-4094, found {vlans[-1]}"
        raise ValueError(message)
    return tuple(vlans)
